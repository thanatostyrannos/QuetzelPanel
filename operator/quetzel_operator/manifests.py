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
    """Player-based sizing -> {"requests": {...}, "limits": {...}} (PURE, WP-B).

    Formula (all integer arithmetic, no floats):
      memory_MiB = baseMemoryMiB + memoryPerPlayerMiB * N
      cpu_milli  = baseCpuMilli  + cpuPerPlayerMilli  * N
    where N = clamp(max_players, 0, sizing["maxPlayers"]).

    Optional ceiling keys clamp the computed values from above:
      ceilingMemoryMiB, ceilingCpuMilli

    Validation:
      - baseMemoryMiB and baseCpuMilli must be >= 0
      - per-player factors must be >= 0

    Output: {"requests": {"cpu": "<int>m", "memory": "<int>Mi"},
             "limits":   {"cpu": "<int>m", "memory": "<int>Mi"}}
    requests == limits (Guaranteed QoS).
    Monotonic non-decreasing in max_players.
    """
    base_mem = sizing["baseMemoryMiB"]
    per_mem = sizing["memoryPerPlayerMiB"]
    base_cpu = sizing["baseCpuMilli"]
    per_cpu = sizing["cpuPerPlayerMilli"]
    max_n = sizing["maxPlayers"]

    if base_mem < 0:
        raise ValueError(f"baseMemoryMiB must be >= 0, got {base_mem}")
    if base_cpu < 0:
        raise ValueError(f"baseCpuMilli must be >= 0, got {base_cpu}")
    if per_mem < 0:
        raise ValueError(f"memoryPerPlayerMiB must be >= 0, got {per_mem}")
    if per_cpu < 0:
        raise ValueError(f"cpuPerPlayerMilli must be >= 0, got {per_cpu}")

    # Clamp player count: [0, sizing.maxPlayers]
    n = max(0, min(int(max_players), max_n))

    mem_mib = base_mem + per_mem * n
    cpu_m = base_cpu + per_cpu * n

    # Apply optional ceilings
    ceiling_mem = sizing.get("ceilingMemoryMiB")
    if ceiling_mem is not None:
        mem_mib = min(mem_mib, ceiling_mem)

    ceiling_cpu = sizing.get("ceilingCpuMilli")
    if ceiling_cpu is not None:
        cpu_m = min(cpu_m, ceiling_cpu)

    tier = {"cpu": f"{cpu_m}m", "memory": f"{mem_mib}Mi"}
    return {"requests": tier, "limits": tier}


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

    # WP-B: propagate player count to the game container if the catalog entry
    # declares a playersEnv key (e.g. Minecraft's MAX_PLAYERS).
    players_env = game.get("playersEnv")
    max_players = spec.get("maxPlayers")
    if players_env and max_players is not None:
        env.append({"name": players_env, "value": str(int(max_players))})

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

    # WP-B: resource resolution priority:
    #   1. Explicit spec.resources (non-empty cpu or mem) — always wins.
    #   2. Player-based sizing: game has a "sizing" block + spec.maxPlayers is set.
    #   3. Default: cpu=1, mem=2Gi.
    explicit_resources = spec.get("resources") or {}
    has_explicit = bool(explicit_resources.get("cpu") or explicit_resources.get("mem"))

    sizing = game.get("sizing")
    max_players = spec.get("maxPlayers")

    if has_explicit:
        cpu = explicit_resources.get("cpu", "1")
        mem = explicit_resources.get("mem", "2Gi")
    elif sizing and max_players is not None:
        computed = compute_resources(sizing, int(max_players))
        cpu = computed["requests"]["cpu"]
        mem = computed["requests"]["memory"]
    else:
        cpu = "1"
        mem = "2Gi"

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
