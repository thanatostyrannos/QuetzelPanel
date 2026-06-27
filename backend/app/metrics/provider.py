"""MetricsProvider interface + a synthetic mock.

Real per-server usage (CPU/mem as % of limits via metrics-server, disk % via
kubelet PVC volume stats) and cluster health classification land in WP-C
(K8sMetricsProvider + pure parsers in app/metrics/classify.py).
"""
from __future__ import annotations

import zlib
from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel, Field


class ServerMetrics(BaseModel):
    name: str
    cpuPercent: float  # of the pod CPU limit
    memoryPercent: float  # of the pod memory limit
    diskPercent: float  # PVC usedBytes / capacityBytes
    cpuMilli: int | None = None
    memoryMiB: int | None = None


class ClusterHealth(BaseModel):
    cluster: str = "local"
    nodesReady: int = 0
    nodesTotal: int = 0
    podsRunning: int = 0
    podsError: int = 0
    serversDesired: int = 0
    serversReady: int = 0
    problems: List[str] = Field(default_factory=list)


class MetricsProvider(ABC):
    @abstractmethod
    async def server_metrics(self, name: str) -> ServerMetrics | None: ...

    @abstractmethod
    async def cluster_health(self) -> ClusterHealth: ...

    def kind(self) -> str:
        return self.__class__.__name__


def _seed(name: str) -> int:
    return zlib.crc32(name.encode())


class SyntheticMetricsProvider(MetricsProvider):
    """Plausible, deterministic-per-name data so the UI renders with no cluster."""

    async def server_metrics(self, name: str) -> ServerMetrics:
        import random

        rnd = random.Random(_seed(name))
        return ServerMetrics(
            name=name,
            cpuPercent=round(rnd.uniform(10, 80), 1),
            memoryPercent=round(rnd.uniform(20, 85), 1),
            diskPercent=round(rnd.uniform(5, 60), 1),
            cpuMilli=int(rnd.uniform(100, 900)),
            memoryMiB=int(rnd.uniform(256, 1800)),
        )

    async def cluster_health(self) -> ClusterHealth:
        return ClusterHealth(
            cluster="local",
            nodesReady=1,
            nodesTotal=1,
            podsRunning=3,
            podsError=0,
            serversDesired=0,
            serversReady=0,
            problems=[],
        )


class K8sMetricsProvider(MetricsProvider):
    """Real metrics from metrics-server + kubelet stats.

    CPU/memory: metrics.k8s.io/v1beta1 PodMetrics, expressed as % of pod limits.
    Disk:       kubelet /stats/summary for the PVC volume named "world-<server>-0".
    Health:     nodes + quetzel-namespace pods + GameServer CRs.
    """

    def __init__(self, namespace: str | None = None) -> None:
        import os

        self.namespace = namespace or os.getenv("QUETZEL_NAMESPACE", "quetzel")
        self._core: "client.CoreV1Api | None" = None  # type: ignore[name-defined]
        self._custom: "client.CustomObjectsApi | None" = None  # type: ignore[name-defined]
        self._metrics_custom: "client.CustomObjectsApi | None" = None  # type: ignore[name-defined]

    def _init_clients(self) -> None:
        from kubernetes import client, config  # noqa: F401

        if self._core is not None:
            return
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self._core = client.CoreV1Api()
        self._custom = client.CustomObjectsApi()

    # ------------------------------------------------------------------
    # server_metrics
    # ------------------------------------------------------------------

    async def server_metrics(self, name: str) -> "ServerMetrics | None":
        from .classify import (
            cpu_percent,
            limit_cpu_nano_from_pod,
            limit_memory_bytes_from_pod,
            memory_percent,
            disk_percent_from_summary,
            usage_cpu_nano_from_metrics,
            usage_memory_bytes_from_metrics,
        )

        self._init_clients()
        assert self._core is not None and self._custom is not None

        # --- pod ---
        pod_name = f"{name}-0"  # StatefulSet pod
        try:
            pod_obj = self._core.read_namespaced_pod(pod_name, self.namespace)
            pod = pod_obj.to_dict()
        except Exception:  # pragma: no cover
            return None

        cpu_limit = limit_cpu_nano_from_pod(pod)
        mem_limit = limit_memory_bytes_from_pod(pod)

        # --- metrics-server ---
        try:
            pm = self._custom.get_namespaced_custom_object(
                "metrics.k8s.io", "v1beta1", self.namespace, "pods", pod_name
            )
        except Exception:  # pragma: no cover
            pm = {}

        cpu_usage = usage_cpu_nano_from_metrics(pm)
        mem_usage = usage_memory_bytes_from_metrics(pm)

        cpu_pct = cpu_percent(cpu_usage, cpu_limit) if cpu_usage is not None and cpu_limit else None
        mem_pct = memory_percent(mem_usage, mem_limit) if mem_usage is not None and mem_limit else None

        # --- disk via kubelet summary ---
        # The operator's volumeClaimTemplate is named "world" (manifests.py),
        # so the StatefulSet pod's PVC is "world-<name>-0".
        pvc_name = f"world-{name}-0"
        disk_pct: float | None = None
        try:
            # Identify which node runs the pod
            node_name = pod.get("spec", {}).get("nodeName")
            if node_name:
                # Use the proxy subresource to call kubelet /stats/summary
                import json

                raw = self._core.connect_get_node_proxy_with_path(
                    node_name, "stats/summary"
                )
                summary = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                disk_pct = disk_percent_from_summary(summary, pvc_name)
        except Exception:  # pragma: no cover
            disk_pct = None

        return ServerMetrics(
            name=name,
            cpuPercent=cpu_pct if cpu_pct is not None else 0.0,
            memoryPercent=mem_pct if mem_pct is not None else 0.0,
            diskPercent=disk_pct if disk_pct is not None else 0.0,
            cpuMilli=round(cpu_usage / 1_000_000) if cpu_usage is not None else None,
            memoryMiB=round(mem_usage / 1024 / 1024) if mem_usage is not None else None,
        )

    # ------------------------------------------------------------------
    # cluster_health
    # ------------------------------------------------------------------

    async def cluster_health(self) -> "ClusterHealth":
        from .classify import build_cluster_health

        self._init_clients()
        assert self._core is not None and self._custom is not None

        # nodes
        try:
            nodes_raw = self._core.list_node()
            nodes = [n.to_dict() for n in nodes_raw.items]
        except Exception:  # pragma: no cover
            nodes = []

        # pods in namespace
        try:
            pods_raw = self._core.list_namespaced_pod(self.namespace)
            pods = [p.to_dict() for p in pods_raw.items]
        except Exception:  # pragma: no cover
            pods = []

        # GameServer CRs
        try:
            gs_raw = self._custom.list_namespaced_custom_object(
                "quetzel.gg", "v1alpha1", self.namespace, "gameservers"
            )
            servers = gs_raw.get("items", [])
        except Exception:  # pragma: no cover
            servers = []

        data = build_cluster_health(nodes, pods, servers, cluster_name="local")
        return ClusterHealth(**data)
