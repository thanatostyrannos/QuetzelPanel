"""User persistence seam. QUETZEL_USERSTORE=memory|postgres (default: memory)."""
from __future__ import annotations

import os

from .store import InMemoryUserStore, User, UserStore  # noqa: F401


def make_user_store() -> UserStore:
    kind = os.getenv("QUETZEL_USERSTORE", "memory").lower()
    if kind == "postgres":
        from .store import PostgresUserStore

        return PostgresUserStore(os.environ.get("QUETZEL_DB_DSN", ""))
    return InMemoryUserStore()
