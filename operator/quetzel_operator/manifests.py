"""Pure builders that turn a GameServer (spec + catalog entry) into the child
Kubernetes objects it reconciles to: a Secret, a Service, and a StatefulSet.

Kept free of any cluster/kopf dependency so the full reconciliation *shape* is
unit-testable offline (which is exactly what we need while k3s is down). The
handlers module wires these into the live API and sets owner references for GC.

Data-driven: anything game-specific (ports, env, version env, data path, RCON
wiring, graceful stop command) comes from the catalog entry, so adding a game is
a catalog change, not a code change.
"""
from __future__ import annotations

import secrets

GROUP = "quetzel.gg"
VERSION = "v1alpha1"
KIND = "GameServer"
API_VERSION = f"{GROUP}/{VERSION}"

SECRET_KEY = "rcon-password"


def generate_rcon_password(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


def compute_resources(sizing: dict, max_players: int) -> dict:
    """Player-based sizing -> {"requests": {...}, "limits": {...}} (PURE).

    SEED: implemented by WP-B (player-sizing). Must be monotonic in max_players,
    clamped to the sizing ceilings, with sane rounding (Mi/m units). build_statefulset
    uses it when explicit spec.resources are absent (explicit always overrides).
    """
    raise NotImplementedError("compute_resources is implemented in WP-B (player-sizing)")


def labels(name: str) -> dict:
    return {
        "app.kubernetes.io/name": "quetzel-gameserver",
        "app.kubernetes.io/instance": name,
        "app.kubernetes.io/managed-by": "quetzel-operator",
        "quetzel.gg/server": name,
    }


def secret_name(name: str) -> str:
    return f"{name}-rcon"


def owner_reference(name: str, uid: str) -> dict:
    """Owner ref so deleting the GameServer garbage-collects its children."""
    return {
        "apiVersion": API_VERSION,
        "kind": KIND,
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


def _meta(name: str, namespace: str, owner: dict | None) -> dict:
    meta = {"name": name, "namespace": namespace, "labels": labels(name)}
    if owner:
        meta["ownerReferences"] = [owner]
    return meta


def build_secret(name: str, namespace: str, password: str, owner: dict | None = None) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": _meta(secret_name(name), namespace, owner),
        "type": "Opaque",
        "stringData": {SECRET_KEY: password},
    }


def build_service(
    name: str, namespace: str, game: dict, rcon_enabled: bool, owner: dict | None = None
) -> dict:
    ports = [
        {
            "name": p["name"],
            "port": p["port"],
            "targetPort": p["port"],
            "protocol": p.get("protocol", "TCP"),
        }
        for p in game["ports"]
    ]
    rcon = game.get("rcon", {})
    if rcon_enabled and rcon.get("enabled") and rcon.get("port"):
        ports.append(
            {
                "name": "rcon",
                "port": rcon["port"],
                "targetPort": rcon["port"],
                "protocol": "TCP",
            }
        )
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": _meta(name, namespace, owner),
        "spec": {
            "type": "LoadBalancer",  # k3s ServiceLB assigns the node IP locally
            "selector": labels(name),
            "ports": ports,
        },
    }


def _container_env(spec: dict, game: dict, name: str) -> list[dict]:
    merged = dict(game.get("defaultEnv", {}))
    merged.update(spec.get("env") or {})

    env: list[dict] = [{"name": k, "value": str(v)} for k, v in merged.items()]

    version_env = game.get("versionEnv")
    if version_env and spec.get("version"):
        env.append({"name": version_env, "value": str(spec["version"])})

    rcon = game.get("rcon", {})
    if spec.get("rconEnabled") and rcon.get("enabled"):
        if rcon.get("enableEnv"):
            env.append({"name": rcon["enableEnv"], "value": "true"})
        if rcon.get("passwordEnv"):
            # injected from the Secret — never inlined as a literal value
            env.append(
                {
                    "name": rcon["passwordEnv"],
                    "valueFrom": {
                        "secretKeyRef": {"name": secret_name(name), "key": SECRET_KEY}
                    },
                }
            )
    return env


def build_pdb(name: str, namespace: str, owner: dict | None = None) -> dict:
    """PodDisruptionBudget (P5): keep the single game pod available across
    voluntary disruptions (node drains), so the world isn't yanked mid-session."""
    return {
        "apiVersion": "policy/v1",
        "kind": "PodDisruptionBudget",
        "metadata": _meta(name, namespace, owner),
        "spec": {
            "minAvailable": 1,
            "selector": {"matchLabels": labels(name)},
        },
    }


def build_statefulset(
    name: str, namespace: str, spec: dict, game: dict, owner: dict | None = None
) -> dict:
    image = spec.get("image") or game["image"]
    data_path = game.get("dataPath", "/data")
    volume_name = "world"
    game_port = game["ports"][0]["port"]
    resources = spec.get("resources") or {}
    cpu = resources.get("cpu", "1")
    mem = resources.get("mem", "2Gi")

    stop_cmd = game.get("stopCommand")
    # Graceful shutdown: run the game's save+stop if it has one, else give the
    # process time to flush on SIGTERM.
    prestop_cmd = (
        ["/bin/sh", "-c", stop_cmd] if stop_cmd else ["/bin/sh", "-c", "sleep 5"]
    )

    container = {
        "name": game["id"],
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "env": _container_env(spec, game, name),
        "ports": [
            {"containerPort": p["port"], "protocol": p.get("protocol", "TCP")}
            for p in game["ports"]
        ],
        "resources": {
            "requests": {"cpu": cpu, "memory": mem},
            "limits": {"cpu": cpu, "memory": mem},
        },
        "volumeMounts": [{"name": volume_name, "mountPath": data_path}],
        "readinessProbe": {
            "tcpSocket": {"port": game_port},
            "initialDelaySeconds": 20,
            "periodSeconds": 10,
            "failureThreshold": 30,
        },
        "lifecycle": {"preStop": {"exec": {"command": prestop_cmd}}},
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": _meta(name, namespace, owner),
        "spec": {
            "replicas": 1,
            "serviceName": name,
            "selector": {"matchLabels": labels(name)},
            # Reclaim the world volume when the GameServer is deleted, but keep it
            # across scaling / pod restarts (self-heal must preserve world state).
            "persistentVolumeClaimRetentionPolicy": {
                "whenDeleted": "Delete",
                "whenScaled": "Retain",
            },
            "template": {
                "metadata": {"labels": labels(name)},
                "spec": {
                    "terminationGracePeriodSeconds": 60,
                    "containers": [container],
                },
            },
            "volumeClaimTemplates": [
                {
                    "metadata": {"name": volume_name, "labels": labels(name)},
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        # storageClassName omitted -> k3s default (local-path)
                        "resources": {"requests": {"storage": spec.get("storageSize", "2Gi")}},
                    },
                }
            ],
        },
    }
