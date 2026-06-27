"""ClusterRegistry interface + a local-only implementation + a provider factory."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from ..providers.base import Provider


class ClusterRef(BaseModel):
    id: str
    name: str
    local: bool = False


class ClusterRegistry(ABC):
    @abstractmethod
    def list_clusters(self) -> list[ClusterRef]: ...

    @abstractmethod
    def get(self, cluster_id: str) -> Optional[ClusterRef]: ...


class LocalClusterRegistry(ClusterRegistry):
    """Single cluster: the control plane the platform runs in."""

    def __init__(self, cluster_id: str = "local", name: str = "local") -> None:
        self._ref = ClusterRef(id=cluster_id, name=name, local=True)

    def list_clusters(self) -> list[ClusterRef]:
        return [self._ref]

    def get(self, cluster_id: str) -> Optional[ClusterRef]:
        return self._ref if cluster_id == self._ref.id else None


class RemoteClusterRegistry(ClusterRegistry):
    """Registry backed by stored kubeconfig/SA-token Secrets — WP-D."""

    def list_clusters(self):  # pragma: no cover - WP-D
        raise NotImplementedError("RemoteClusterRegistry is implemented in WP-D (multi-cluster)")

    def get(self, cluster_id):  # pragma: no cover - WP-D
        raise NotImplementedError("RemoteClusterRegistry is implemented in WP-D (multi-cluster)")


def make_cluster_registry() -> ClusterRegistry:
    kind = os.getenv("QUETZEL_CLUSTERS", "local").lower()
    if kind == "remote":
        return RemoteClusterRegistry()
    return LocalClusterRegistry()


def provider_for_cluster(cluster: ClusterRef) -> Provider:
    """Return a Provider bound to a cluster. Phase 0: only the local cluster is
    wired (delegates to the process default provider). WP-D builds per-cluster
    clients from stored credentials for remote clusters."""
    from ..deps import get_provider

    if cluster.local:
        return get_provider()
    raise NotImplementedError("remote per-cluster providers are implemented in WP-D (multi-cluster)")
