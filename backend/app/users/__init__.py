"""User persistence seam.

QUETZEL_USERSTORE=memory   (default) — InMemoryUserStore (dev/CI/mock)
QUETZEL_USERSTORE=sqlite   — SQLiteUserStore (local profile, file from QUETZEL_DB_PATH)
QUETZEL_USERSTORE=postgres — PostgresUserStore (enterprise; WP-A stub)
"""
from __future__ import annotations

import os

from .store import InMemoryUserStore, User, UserStore  # noqa: F401


def make_user_store() -> UserStore:
    kind = os.getenv("QUETZEL_USERSTORE", "memory").lower()
    if kind == "sqlite":
        from .sqlite_store import SQLiteUserStore

        db_path = os.getenv("QUETZEL_DB_PATH", "quetzel.db")
        return SQLiteUserStore(db_path)
    if kind == "postgres":
        from .store import PostgresUserStore

        return PostgresUserStore(os.environ.get("QUETZEL_DB_DSN", ""))
    return InMemoryUserStore()
