"""Shared FastAPI dependencies / process-wide singletons.

The provider (mock or real k8s) is created once and handed to routers via
`Depends(get_provider)`. Tests swap it with `app.dependency_overrides[get_provider]`.
Auth/tenancy dependencies are published here too (see app.auth) so every router
imports its seams from one place.
"""
from __future__ import annotations

from .clusters import ClusterRegistry, make_cluster_registry
from .metrics import MetricsProvider, make_metrics_provider
from .providers import make_provider
from .providers.base import Provider
from .tenancy import CustomerStore, make_customer_store
from .users import UserStore, make_user_store

_provider: Provider = make_provider()
_user_store: UserStore = make_user_store()
_customer_store: CustomerStore = make_customer_store()
_metrics: MetricsProvider = make_metrics_provider()
_clusters: ClusterRegistry = make_cluster_registry()


def get_provider() -> Provider:
    return _provider


def set_provider(p: Provider) -> None:
    """Seam for tests / wiring to replace the process provider."""
    global _provider
    _provider = p


def get_user_store() -> UserStore:
    return _user_store


def get_customer_store() -> CustomerStore:
    return _customer_store


def get_metrics_provider() -> MetricsProvider:
    return _metrics


def get_cluster_registry() -> ClusterRegistry:
    return _clusters
