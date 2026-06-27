"""Provider selection. QUETZEL_PROVIDER=mock|k8s (default: mock)."""
from __future__ import annotations

import os

from .base import Provider


def make_provider() -> Provider:
    kind = os.getenv("QUETZEL_PROVIDER", "mock").lower()
    if kind == "k8s":
        from .k8s import K8sProvider

        return K8sProvider()
    from .mock import MockProvider

    return MockProvider()
