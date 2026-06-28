"""Pure classification / aggregation helpers for observability (WP-C).

All functions are I/O-free so they can be unit-tested without a cluster.

Terminology
-----------
* pod_status  – one of "ok" | "error" | "crashloop"
* node_ready  – True if all conditions with type="Ready" are True (or absent → False)
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Pod classification
# ---------------------------------------------------------------------------

_CRASHLOOP_REASONS = frozenset(
    [
        "CrashLoopBackOff",
        "OOMKilled",
        "Error",
    ]
)

_ERROR_PHASES = frozenset(["Failed", "Unknown"])

_TERMINAL_WAITING_REASONS = frozenset(
    [
        "CrashLoopBackOff",
        "ImagePullBackOff",
        "ErrImagePull",
        "InvalidImageName",
        "CreateContainerConfigError",
        "CreateContainerError",
        "RunContainerError",
        "OOMKilled",
    ]
)


def classify_pod(
    phase: str,
    ready: bool,
    restart_count: int,
    waiting_reason: str | None = None,
) -> str:
    """Classify a pod into "ok" | "error" | "crashloop".

    Parameters
    ----------
    phase:          Pod.status.phase (Running / Pending / Succeeded / Failed / Unknown)
    ready:          True when the pod's Ready condition is True
    restart_count:  Total restart count across all containers
    waiting_reason: The waiting.reason for the first non-running container, if any
    """
    # Explicit crashloop-family reasons take highest priority.
    if waiting_reason == "CrashLoopBackOff":
        return "crashloop"

    if phase in _ERROR_PHASES:
        return "error"

    if phase == "Running":
        if restart_count >= 5:
            return "crashloop"
        if waiting_reason in _TERMINAL_WAITING_REASONS:
            return "error"
        if ready:
            return "ok"
        # running but not ready — still starting or failing; surface as error
        if waiting_reason:
            return "error"
        return "ok"  # transient not-ready (e.g. readiness probe warmup) → ok

    if phase == "Succeeded":
        return "ok"

    if phase == "Pending":
        if waiting_reason in _TERMINAL_WAITING_REASONS:
            return "error"
        return "ok"  # still starting

    return "error"


# ---------------------------------------------------------------------------
# Node readiness
# ---------------------------------------------------------------------------


def node_is_ready(node: dict[str, Any]) -> bool:
    """Return True when the node has a 'Ready' condition with status 'True'.

    Handles both the raw API dict (camelCase 'conditions') and a .to_dict()
    response (also camelCase at the top level but condition entries may vary).
    """
    status = node.get("status") or {}
    conditions = status.get("conditions") or []
    for cond in conditions:
        if cond.get("type") == "Ready":
            return str(cond.get("status", "")).lower() in ("true", "1")
    return False


# ---------------------------------------------------------------------------
# Percent-of-limit math
# ---------------------------------------------------------------------------


def cpu_percent(usage_nano: int | None, limit_nano: int | None) -> float | None:
    """Return CPU usage as a % of the limit.

    Returns None if either value is missing or limit is zero.
    """
    if usage_nano is None or limit_nano is None or limit_nano == 0:
        return None
    return round(min(usage_nano / limit_nano * 100.0, 100.0), 1)


def memory_percent(usage_bytes: int | None, limit_bytes: int | None) -> float | None:
    """Return memory usage as a % of the limit.

    Returns None if either value is missing or limit is zero.
    """
    if usage_bytes is None or limit_bytes is None or limit_bytes == 0:
        return None
    return round(min(usage_bytes / limit_bytes * 100.0, 100.0), 1)


def disk_percent(used_bytes: int | None, capacity_bytes: int | None) -> float | None:
    """Return disk usage as a % of capacity.

    Returns None if either value is missing or capacity is zero.
    """
    if used_bytes is None or capacity_bytes is None or capacity_bytes == 0:
        return None
    return round(min(used_bytes / capacity_bytes * 100.0, 100.0), 1)


# ---------------------------------------------------------------------------
# CPU / memory quantity parsing
# ---------------------------------------------------------------------------


def parse_cpu_to_nano(value: str) -> int:
    """Convert a Kubernetes CPU quantity string to nanocores.

    metrics-server reports pod CPU usage in NANOCORES (the ``n`` suffix, e.g.
    ``114690582n``); limits/requests use millicores (``m``) or whole cores.
    Examples: "114690582n" -> 114690582, "500m" -> 500_000_000,
              "1" -> 1_000_000_000, "1500u" -> 1_500_000.
    """
    value = value.strip()
    if value.endswith("n"):  # nanocores
        return int(float(value[:-1]))
    if value.endswith("u"):  # microcores
        return int(float(value[:-1]) * 1_000)
    if value.endswith("m"):  # millicores
        return int(float(value[:-1]) * 1_000_000)
    return int(float(value) * 1_000_000_000)


def parse_memory_to_bytes(value: str) -> int:
    """Convert a Kubernetes memory quantity string to bytes.

    Handles Ki, Mi, Gi, Ti, Pi, Ei (binary) and k, M, G, T, P, E (SI).
    """
    value = value.strip()
    _BINARY = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4, "Pi": 1024**5, "Ei": 1024**6}
    _SI = {"k": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4, "P": 1000**5, "E": 1000**6}
    for suffix, mult in _BINARY.items():
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * mult)
    for suffix, mult in _SI.items():
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * mult)
    return int(float(value))


# ---------------------------------------------------------------------------
# metrics-server CPU nano from pod metrics
# ---------------------------------------------------------------------------


def usage_cpu_nano_from_metrics(pod_metrics: dict[str, Any]) -> int | None:
    """Sum all container CPU usages from a metrics.k8s.io PodMetrics object.

    Handles both camelCase ('containers') and the flat dict returned by .to_dict().
    """
    containers = pod_metrics.get("containers") or []
    total = 0
    found = False
    for c in containers:
        usage = c.get("usage") or {}
        cpu_str = usage.get("cpu")
        if cpu_str:
            total += parse_cpu_to_nano(cpu_str)
            found = True
    return total if found else None


def usage_memory_bytes_from_metrics(pod_metrics: dict[str, Any]) -> int | None:
    """Sum all container memory usages from a metrics.k8s.io PodMetrics object."""
    containers = pod_metrics.get("containers") or []
    total = 0
    found = False
    for c in containers:
        usage = c.get("usage") or {}
        mem_str = usage.get("memory")
        if mem_str:
            total += parse_memory_to_bytes(mem_str)
            found = True
    return total if found else None


# ---------------------------------------------------------------------------
# Pod limit extraction
# ---------------------------------------------------------------------------


def limit_cpu_nano_from_pod(pod: dict[str, Any]) -> int | None:
    """Sum all container CPU limits from a Pod object (camelCase or snake_case)."""
    spec = pod.get("spec") or {}
    containers = spec.get("containers") or []
    total = 0
    found = False
    for c in containers:
        resources = c.get("resources") or {}
        limits = resources.get("limits") or {}
        cpu_str = limits.get("cpu")
        if cpu_str:
            total += parse_cpu_to_nano(cpu_str)
            found = True
    return total if found else None


def limit_memory_bytes_from_pod(pod: dict[str, Any]) -> int | None:
    """Sum all container memory limits from a Pod object."""
    spec = pod.get("spec") or {}
    containers = spec.get("containers") or []
    total = 0
    found = False
    for c in containers:
        resources = c.get("resources") or {}
        limits = resources.get("limits") or {}
        mem_str = limits.get("memory")
        if mem_str:
            total += parse_memory_to_bytes(mem_str)
            found = True
    return total if found else None


# ---------------------------------------------------------------------------
# Kubelet summary stats disk parsing
# ---------------------------------------------------------------------------


def disk_percent_from_summary(summary: dict[str, Any], pvc_name: str) -> float | None:
    """Extract disk % for a PVC from a kubelet /stats/summary response.

    The summary looks like:
      {
        "pods": [
          {
            "podRef": { "name": "<pod-name>", ... },
            "volume": [
              { "name": "data", "pvcRef": { "name": "data-<server>-0" }, "usedBytes": ..., "capacityBytes": ... }
            ]
          }
        ]
      }
    """
    pods = summary.get("pods") or []
    for pod in pods:
        volumes = pod.get("volume") or []
        for vol in volumes:
            pvc_ref = vol.get("pvcRef") or {}
            if pvc_ref.get("name") == pvc_name:
                used = vol.get("usedBytes")
                cap = vol.get("capacityBytes")
                if used is not None and cap:
                    return disk_percent(used, cap)
    return None


# ---------------------------------------------------------------------------
# Waiting reason extraction
# ---------------------------------------------------------------------------


def waiting_reason_from_pod(pod: dict[str, Any]) -> str | None:
    """Return the waiting.reason for the first container that is waiting, or None."""
    status = pod.get("status") or {}
    container_statuses = status.get("containerStatuses") or status.get("container_statuses") or []
    for cs in container_statuses:
        state = cs.get("state") or {}
        waiting = state.get("waiting")
        if waiting:
            return waiting.get("reason")
    return None


def restart_count_from_pod(pod: dict[str, Any]) -> int:
    """Sum restart counts across all containers."""
    status = pod.get("status") or {}
    container_statuses = status.get("containerStatuses") or status.get("container_statuses") or []
    return sum(cs.get("restartCount", cs.get("restart_count", 0)) for cs in container_statuses)


def ready_from_pod(pod: dict[str, Any]) -> bool:
    """Return True if the pod's Ready condition is True."""
    status = pod.get("status") or {}
    conditions = status.get("conditions") or []
    for cond in conditions:
        if cond.get("type") == "Ready":
            return str(cond.get("status", "")).lower() in ("true", "1")
    return False


# ---------------------------------------------------------------------------
# Cluster health aggregation
# ---------------------------------------------------------------------------


def build_cluster_health(
    nodes: list[dict[str, Any]],
    pods: list[dict[str, Any]],
    servers: list[dict[str, Any]],
    cluster_name: str = "local",
) -> dict[str, Any]:
    """Aggregate raw k8s objects into a ClusterHealth dict.

    Parameters
    ----------
    nodes:    List of Node dicts (from k8s API or .to_dict())
    pods:     List of Pod dicts in the quetzel namespace
    servers:  List of GameServer CRs (status.phase / status.ready)
    cluster_name: Name to embed in the result

    Returns a plain dict matching the ClusterHealth pydantic model.
    """
    nodes_total = len(nodes)
    nodes_ready = sum(1 for n in nodes if node_is_ready(n))

    pods_running = 0
    pods_error = 0
    problems: list[str] = []

    for pod in pods:
        metadata = pod.get("metadata") or {}
        pod_name = metadata.get("name", "<unknown>")
        status = pod.get("status") or {}
        phase = status.get("phase", "Unknown")
        ready = ready_from_pod(pod)
        restarts = restart_count_from_pod(pod)
        waiting_reason = waiting_reason_from_pod(pod)
        classification = classify_pod(phase, ready, restarts, waiting_reason)

        if classification == "ok":
            if phase == "Running":
                pods_running += 1
        elif classification == "crashloop":
            pods_error += 1
            problems.append(f"pod/{pod_name}: CrashLoopBackOff (restarts={restarts})")
        else:  # error
            pods_error += 1
            desc = waiting_reason or phase
            problems.append(f"pod/{pod_name}: {desc}")

    # Node problems
    for node in nodes:
        nm = (node.get("metadata") or {}).get("name", "<node>")
        if not node_is_ready(node):
            problems.append(f"node/{nm}: NotReady")

    # GameServer desired vs ready
    servers_desired = len(servers)
    servers_ready = 0
    for srv in servers:
        status = srv.get("status") or {}
        phase = status.get("phase", "")
        ready = status.get("ready", False)
        if phase == "Running" and ready:
            servers_ready += 1
        elif phase not in ("Running", "Pending", "Provisioning", "Terminating", ""):
            problems.append(f"server/{(srv.get('metadata') or {}).get('name', '?')}: {phase}")

    return {
        "cluster": cluster_name,
        "nodesReady": nodes_ready,
        "nodesTotal": nodes_total,
        "podsRunning": pods_running,
        "podsError": pods_error,
        "serversDesired": servers_desired,
        "serversReady": servers_ready,
        "problems": problems,
    }
