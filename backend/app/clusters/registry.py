"""ClusterRegistry interface + implementations.

Three concrete registries are provided:

LocalClusterRegistry   – single cluster (the one the platform runs in).
RemoteClusterRegistry  – reads cluster records from an in-process store that
                         is populated at startup from kubeconfig/SA-token Secrets
                         labelled ``quetzel.gg/cluster`` (enterprise).  In the
                         absence of a real cluster, the same store can be seeded
                         with mock-remote entries for unit-testing aggregation.
MockMultiClusterRegistry – always returns two in-memory clusters so aggregation
                           paths are exercisable in CI / demo with no second k8s.

``make_cluster_registry()`` selects the implementation via QUETZEL_CLUSTERS:
  local  (default)  → LocalClusterRegistry
  remote            → RemoteClusterRegistry (reads live Secrets)
  mock-multi        → MockMultiClusterRegistry (two mock clusters, no k8s)

``provider_for_cluster(ref)`` builds a Provider for each cluster:
  - local cluster  → delegates to the process-wide get_provider()
  - remote cluster → builds a K8sProvider for the cluster's kubeconfig namespace
  - mock-remote    → returns a per-cluster MockProvider (seeded in the registry)
"""
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
    """Registry backed by stored kubeconfig/SA-token Secrets.

    On startup, call ``load_from_secrets(core_api, namespace)`` to populate
    the registry from Secrets labelled ``quetzel.gg/cluster=true`` in the
    given namespace.  Each Secret must contain:

      data:
        id:         <cluster-id>       # unique short id
        name:       <human name>
        kubeconfig: <base64 kubeconfig> | token: <SA token>

    You can also call ``register(ref, provider)`` directly to add entries
    programmatically (used by tests / MockMultiClusterRegistry).
    """

    def __init__(self) -> None:
        self._refs: dict[str, ClusterRef] = {}
        self._providers: dict[str, Provider] = {}

    def register(self, ref: ClusterRef, provider: Optional[Provider] = None) -> None:
        """Register a cluster (and optionally its provider) directly."""
        self._refs[ref.id] = ref
        if provider is not None:
            self._providers[ref.id] = provider

    def get_provider(self, cluster_id: str) -> Optional[Provider]:
        return self._providers.get(cluster_id)

    def load_from_secrets(self, core_api, namespace: str) -> None:  # pragma: no cover
        """Populate from Kubernetes Secrets labelled ``quetzel.gg/cluster=true``."""
        import base64

        label_selector = "quetzel.gg/cluster=true"
        try:
            resp = core_api.list_namespaced_secret(namespace, label_selector=label_selector)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning("RemoteClusterRegistry: failed to list cluster Secrets: %s", exc)
            return

        for secret in resp.items:
            data = secret.data or {}

            def _decode(key: str) -> Optional[str]:
                raw = data.get(key)
                if not raw:
                    return None
                return base64.b64decode(raw).decode()

            cid = _decode("id") or (secret.metadata.name if secret.metadata else None)
            cname = _decode("name") or cid
            if not cid:
                continue

            ref = ClusterRef(id=cid, name=cname, local=False)
            # Build a per-cluster K8sProvider if a kubeconfig is embedded.
            kubeconfig_str = _decode("kubeconfig")
            if kubeconfig_str:
                try:
                    from ..providers.k8s import K8sProvider
                    from kubernetes import client as k8s_client, config as k8s_config
                    import tempfile, os as _os

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w") as f:
                        f.write(kubeconfig_str)
                        kc_path = f.name
                    cfg_obj = k8s_config.new_client_from_config(config_file=kc_path)
                    _os.unlink(kc_path)
                    provider = K8sProvider()
                    provider._api = k8s_client.CustomObjectsApi(cfg_obj)
                    self.register(ref, provider)
                    continue
                except Exception as exc2:  # noqa: BLE001
                    import logging
                    logging.getLogger(__name__).warning(
                        "RemoteClusterRegistry: could not build K8sProvider for '%s': %s", cid, exc2
                    )
            self.register(ref)

    def list_clusters(self) -> list[ClusterRef]:
        return list(self._refs.values())

    def get(self, cluster_id: str) -> Optional[ClusterRef]:
        return self._refs.get(cluster_id)


class MockMultiClusterRegistry(RemoteClusterRegistry):
    """Two in-memory mock clusters — exercisable with no second real k8s.

    Used by QUETZEL_CLUSTERS=mock-multi for demo / CI aggregation tests.
    Each cluster gets its own MockProvider so servers can be created independently.
    """

    def __init__(self) -> None:
        super().__init__()
        from ..providers.mock import MockProvider

        local_ref = ClusterRef(id="local", name="local", local=True)
        remote_ref = ClusterRef(id="remote-1", name="mock-remote-1", local=False)
        self.register(local_ref)  # no provider: delegates to process get_provider()
        self.register(remote_ref, MockProvider())


def make_cluster_registry() -> ClusterRegistry:
    kind = os.getenv("QUETZEL_CLUSTERS", "local").lower()
    if kind == "remote":
        return RemoteClusterRegistry()
    if kind == "mock-multi":
        return MockMultiClusterRegistry()
    return LocalClusterRegistry()


def provider_for_cluster(cluster: ClusterRef, registry: Optional[ClusterRegistry] = None) -> Provider:
    """Return a Provider bound to a cluster.

    Resolution order:
    1. If the registry provides a stored provider for this cluster id, use it.
    2. If the cluster is local, delegate to the process-wide get_provider().
    3. Otherwise raise NotImplementedError (remote cluster with no stored provider).
    """
    # Ask the registry if it has a stored provider for this cluster.
    if registry is not None and isinstance(registry, RemoteClusterRegistry):
        stored = registry.get_provider(cluster.id)
        if stored is not None:
            return stored

    if cluster.local:
        from ..deps import get_provider
        return get_provider()

    raise NotImplementedError(
        f"No provider registered for remote cluster '{cluster.id}'. "
        "Register it via RemoteClusterRegistry.register() or load_from_secrets()."
    )
