"""Multi-cluster routes (WP-D).

Endpoints:
  GET /clusters                  – list all registered clusters (any authenticated user)
  GET /clusters/rollup/servers   – cross-cluster server aggregation (static path first!)
  GET /clusters/{id}/health      – health of one cluster (any authenticated user)
  GET /clusters/{id}/servers     – all servers on a cluster (admin: all; customer: own)

IMPORTANT: the static ``/rollup/servers`` route MUST be declared before
``/{cluster_id}/servers`` in this file.  FastAPI resolves paths in declaration
order and would otherwise capture "rollup" as a cluster_id.

Cross-cluster aggregation is available for platform-admins via the
GET /clusters endpoints.  Customer-users see the same filtered view they would
get from /servers, projected onto the cluster they happen to be served from.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from ..auth.context import AuthContext, current_user
from ..clusters import ClusterRef, ClusterRegistry, provider_for_cluster
from ..clusters.registry import RemoteClusterRegistry
from ..deps import get_cluster_registry, get_metrics_provider, get_provider
from ..metrics import ClusterHealth, MetricsProvider
from ..models import GameServer
from ..providers.base import Provider
from ..tenancy.scope import visible_servers

log = logging.getLogger(__name__)

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterRef])
async def list_clusters(
    registry: ClusterRegistry = Depends(get_cluster_registry),
    user: AuthContext = Depends(current_user),
):
    """List all registered clusters.

    Platform-admins see all clusters; customer-users see all clusters too
    (they need to know which cluster to connect to), but their server list
    will be scoped by tenancy.
    """
    return registry.list_clusters()


# NOTE: /rollup/servers MUST be declared before /{cluster_id}/servers
# so FastAPI matches the literal path first.
def _provider_for(ref: ClusterRef, registry: ClusterRegistry, default_provider: Provider) -> Provider:
    """Resolve a Provider for ``ref``.

    For the local cluster we use the FastAPI-injected ``default_provider``
    (honours dependency_overrides in tests).  For remote clusters we look up
    the stored provider in the registry.
    """
    if ref.local:
        return default_provider
    if isinstance(registry, RemoteClusterRegistry):
        stored = registry.get_provider(ref.id)
        if stored is not None:
            return stored
    raise NotImplementedError(
        f"No provider registered for remote cluster '{ref.id}'."
    )


@router.get("/rollup/servers", response_model=list[GameServer])
async def rollup_servers(
    registry: ClusterRegistry = Depends(get_cluster_registry),
    default_provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    """Cross-cluster server aggregation (admin: all clusters; customer: own scope).

    Merges servers from every registered cluster, then applies tenancy scoping.
    """
    clusters = registry.list_clusters()

    async def _fetch(ref: ClusterRef) -> list[GameServer]:
        try:
            prov = _provider_for(ref, registry, default_provider)
            return await prov.list_servers()
        except NotImplementedError:
            log.warning("rollup: no provider for cluster '%s' — skipping", ref.id)
            return []
        except Exception as exc:  # noqa: BLE001
            log.warning("rollup: error fetching cluster '%s': %s", ref.id, exc)
            return []

    results = await asyncio.gather(*[_fetch(c) for c in clusters])
    all_servers: list[GameServer] = []
    for servers in results:
        all_servers.extend(servers)

    # Tenancy filter applied after merge.
    return visible_servers(user, all_servers)


@router.get("/{cluster_id}/health", response_model=ClusterHealth)
async def cluster_health(
    cluster_id: str,
    registry: ClusterRegistry = Depends(get_cluster_registry),
    metrics: MetricsProvider = Depends(get_metrics_provider),
    user: AuthContext = Depends(current_user),
):
    ref = registry.get(cluster_id)
    if ref is None:
        raise HTTPException(status_code=404, detail=f"unknown cluster '{cluster_id}'")
    health = await metrics.cluster_health()
    health.cluster = ref.id
    return health


@router.get("/{cluster_id}/servers", response_model=list[GameServer])
async def cluster_servers(
    cluster_id: str,
    registry: ClusterRegistry = Depends(get_cluster_registry),
    default_provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    """List servers on a specific cluster, tenancy-filtered."""
    ref = registry.get(cluster_id)
    if ref is None:
        raise HTTPException(status_code=404, detail=f"unknown cluster '{cluster_id}'")
    try:
        prov = _provider_for(ref, registry, default_provider)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    servers = await prov.list_servers()
    return visible_servers(user, servers)
