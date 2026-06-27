"""Shared FastAPI dependencies / process-wide singletons.

The provider (mock or real k8s) is created once and handed to routers via
`Depends(get_provider)`. Tests swap it with `app.dependency_overrides[get_provider]`.
Auth/tenancy dependencies are published here too (see app.auth) so every router
imports its seams from one place.
"""
from __future__ import annotations

from .providers import make_provider
from .providers.base import Provider

_provider: Provider = make_provider()


def get_provider() -> Provider:
    return _provider


def set_provider(p: Provider) -> None:
    """Seam for tests / wiring to replace the process provider."""
    global _provider
    _provider = p
