"""Shared fixtures.

`asyncio.run` is used to drive the async Provider directly (no pytest-asyncio needed).
The `client` fixture swaps in a fresh MockProvider per test so API tests don't share state.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main
from app.providers.mock import MockProvider


def run(coro):
    return asyncio.run(coro)


class FakeClock:
    """Manually-advanced clock for deterministic lifecycle tests."""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def client(monkeypatch):
    # Each test gets a clean in-memory provider behind the real FastAPI app.
    monkeypatch.setattr(main, "provider", MockProvider())
    with TestClient(main.app) as c:
        yield c
