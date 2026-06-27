"""Observability routes (SEED — WP-C owns/expands this file).

Per-server usage + cluster health. Works against the synthetic MetricsProvider
in mock mode; WP-C swaps in the real metrics-server / kubelet-stats provider.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.context import AuthContext, current_user
from ..deps import get_metrics_provider
from ..metrics import ClusterHealth, MetricsProvider, ServerMetrics

router = APIRouter(tags=["metrics"])


@router.get("/servers/{name}/metrics", response_model=ServerMetrics)
async def server_metrics(
    name: str,
    metrics: MetricsProvider = Depends(get_metrics_provider),
    user: AuthContext = Depends(current_user),
):
    m = await metrics.server_metrics(name)
    if m is None:
        raise HTTPException(status_code=404, detail=f"no metrics for server '{name}'")
    return m


@router.get("/cluster/health", response_model=ClusterHealth)
async def cluster_health(
    metrics: MetricsProvider = Depends(get_metrics_provider),
    user: AuthContext = Depends(current_user),
):
    return await metrics.cluster_health()
