"""kopf reconciler for the GameServer CRD.

NOTE: written but NOT yet exercised on a live cluster (k3s/WSL is down — see
BLOCKERS.md B1). The pure pieces it relies on (manifests.py, status.py) ARE
unit-tested. Once the cluster is healthy:  kopf run -m quetzel_operator.handlers

Reconciliation per GameServer:
  1. ensure the RCON Secret (generated once, never regenerated or logged)
  2. apply the LoadBalancer Service (idempotent)
  3. apply the StatefulSet (replicas:1 + volumeClaimTemplate) (idempotent)
  4. all children carry ownerReferences -> deleting the CR garbage-collects them
  5. derive + patch status (phase/address/ready) from observed Service + StatefulSet

Idempotency rules:
  - Secret: create-if-missing only (stable password).
  - Service: create-if-missing, else strategic-merge patch ports/type.
  - StatefulSet: create-if-missing, else patch only the mutable container bits
    (image/env/resources) to avoid immutable-field errors.
"""
from __future__ import annotations

import kopf
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from . import catalog, manifests, status

GROUP = "quetzel.gg"
VERSION = "v1alpha1"


def _apis():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    # Modest, predictable behavior for a single-node local operator.
    settings.posting.level = 20  # INFO events
    settings.watching.server_timeout = 60


def _ensure_secret(core: client.CoreV1Api, name, ns, owner, log) -> None:
    sname = manifests.secret_name(name)
    try:
        core.read_namespaced_secret(sname, ns)
        return  # exists -> keep the stable password, never regenerate/log it
    except ApiException as e:
        if e.status != 404:
            raise
    password = manifests.generate_rcon_password()
    body = manifests.build_secret(name, ns, password, owner=owner)
    core.create_namespaced_secret(ns, body)
    log.info(f"created RCON secret {sname}")  # value never logged


def _ensure_service(core: client.CoreV1Api, name, ns, game, rcon_enabled, owner, log) -> None:
    body = manifests.build_service(name, ns, game, rcon_enabled, owner=owner)
    try:
        core.read_namespaced_service(name, ns)
        core.patch_namespaced_service(
            name, ns, {"spec": {"type": body["spec"]["type"], "ports": body["spec"]["ports"]}}
        )
    except ApiException as e:
        if e.status != 404:
            raise
        core.create_namespaced_service(ns, body)
        log.info(f"created service {name}")


def _ensure_statefulset(apps: client.AppsV1Api, name, ns, spec, game, owner, log) -> None:
    body = manifests.build_statefulset(name, ns, spec, game, owner=owner)
    try:
        apps.read_namespaced_stateful_set(name, ns)
        container = body["spec"]["template"]["spec"]["containers"][0]
        apps.patch_namespaced_stateful_set(
            name,
            ns,
            {"spec": {"template": {"spec": {"containers": [
                {"name": container["name"], "image": container["image"],
                 "env": container["env"], "resources": container["resources"]}
            ]}}}},
        )
    except ApiException as e:
        if e.status != 404:
            raise
        apps.create_namespaced_stateful_set(ns, body)
        log.info(f"created statefulset {name}")


def _observe_status(core, apps, name, ns, game) -> dict:
    game_port = game["ports"][0]["port"]
    ss_exists, ready = False, 0
    try:
        ss = apps.read_namespaced_stateful_set(name, ns)
        ss_exists = True
        ready = ss.status.ready_replicas or 0
    except ApiException as e:
        if e.status != 404:
            raise
    address = None
    try:
        svc = core.read_namespaced_service(name, ns).to_dict()
        address = status.service_address(svc, game_port)
    except ApiException as e:
        if e.status != 404:
            raise
    s = status.compute_phase(
        deleting=False, statefulset_exists=ss_exists, ready_replicas=ready, address=address
    )
    s["podName"] = f"{name}-0" if ss_exists else None
    return s


@kopf.on.create(GROUP, VERSION, "gameservers")
@kopf.on.update(GROUP, VERSION, "gameservers")
@kopf.on.resume(GROUP, VERSION, "gameservers")
def reconcile(spec, meta, name, namespace, patch, logger, **_):
    game = catalog.get_game(spec.get("game", ""))
    if not game:
        patch.status["phase"] = "Error"
        patch.status["message"] = f"unknown game '{spec.get('game')}'"
        return

    owner = manifests.owner_reference(name, meta["uid"])
    core, apps = _apis()

    rcon_enabled = bool(spec.get("rconEnabled")) and bool(game.get("rcon", {}).get("enabled"))
    if rcon_enabled:
        _ensure_secret(core, name, namespace, owner, logger)
    _ensure_service(core, name, namespace, game, rcon_enabled, owner, logger)
    _ensure_statefulset(apps, name, namespace, spec, game, owner, logger)

    s = _observe_status(core, apps, name, namespace, game)
    for k, v in s.items():
        patch.status[k] = v


@kopf.timer(GROUP, VERSION, "gameservers", interval=10.0)
def refresh_status(spec, name, namespace, patch, **_):
    game = catalog.get_game(spec.get("game", ""))
    if not game:
        return
    core, apps = _apis()
    s = _observe_status(core, apps, name, namespace, game)
    for k, v in s.items():
        patch.status[k] = v


@kopf.on.delete(GROUP, VERSION, "gameservers")
def on_delete(name, patch, logger, **_):
    # Children carry ownerReferences, so k8s GC removes the StatefulSet/Service/
    # Secret automatically. The StatefulSet's preStop hook performs the graceful
    # save+stop before the pod terminates.
    patch.status["phase"] = "Stopping"
    logger.info(f"deleting {name}; children GC via owner references")
