"""Multi-cluster routes (SEED — WP-D owns/expands this file).

Phase 0 lists the local cluster and reports its health. WP-D adds remote
clusters and cross-cluster aggregation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.context import AuthContext, current_user
from ..clusters import ClusterRef, ClusterRegistry
from ..deps import get_cluster_registry, get_metrics_provider
from ..metrics import ClusterHealth, MetricsProvider

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterRef])
async def list_clusters(
    registry: ClusterRegistry = Depends(get_cluster_registry),
    user: AuthContext = Depends(current_user),
):
    return registry.list_clusters()


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
