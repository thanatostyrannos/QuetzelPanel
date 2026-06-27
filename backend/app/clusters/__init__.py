"""Multi-cluster seams: a registry of clusters + a cluster-aware provider factory.

Phase 0 ships a local-only registry (the in-cluster control plane). WP-D adds
remote clusters (kubeconfig/SA-token Secrets) and makes the provider + metrics
provider cluster-aware (one client per cluster).
"""
from .registry import (  # noqa: F401
    ClusterRef,
    ClusterRegistry,
    LocalClusterRegistry,
    MockMultiClusterRegistry,
    RemoteClusterRegistry,
    make_cluster_registry,
    provider_for_cluster,
)
