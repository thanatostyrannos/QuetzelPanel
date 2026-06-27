"""Observability seam. QUETZEL_METRICS=mock|k8s (default: mock)."""
from __future__ import annotations

import os

from .provider import (  # noqa: F401
    ClusterHealth,
    MetricsProvider,
    ServerMetrics,
    SyntheticMetricsProvider,
)


def make_metrics_provider() -> MetricsProvider:
    kind = os.getenv("QUETZEL_METRICS", os.getenv("QUETZEL_PROVIDER", "mock")).lower()
    if kind == "k8s":
        from .provider import K8sMetricsProvider

        return K8sMetricsProvider()
    return SyntheticMetricsProvider()
