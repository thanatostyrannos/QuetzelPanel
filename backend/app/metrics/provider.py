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
    """Real metrics from metrics-server + kubelet stats — implemented by WP-C."""

    async def server_metrics(self, name):  # pragma: no cover - WP-C
        raise NotImplementedError("K8sMetricsProvider is implemented in WP-C (observability)")

    async def cluster_health(self):  # pragma: no cover - WP-C
        raise NotImplementedError("K8sMetricsProvider is implemented in WP-C (observability)")
