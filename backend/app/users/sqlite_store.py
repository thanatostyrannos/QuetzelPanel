"""SQLite-backed UserStore (stdlib sqlite3 — no external deps).

Used for the 'local' profile and for CI tests that cannot hit a real Postgres.
File path comes from the QUETZEL_DB_PATH env var; defaults to quetzel.db.
Schema is auto-created on first connect.
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import Optional

from ..auth.roles import Role
from .store import User, UserStore, hash_password, verify_password


class SQLiteUserStore(UserStore):
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL,
                    customer_id TEXT,
                    password_hash TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            role=Role(row["role"]),
            customer_id=row["customer_id"],
            password_hash=row["password_hash"],
        )

    # ------------------------------------------------------------------
    # UserStore interface
    # ------------------------------------------------------------------

    def get(self, user_id: str) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return self._row_to_user(row) if row else None

    def create_user(
        self, username: str, password: str, role: Role, customer_id: Optional[str] = None
    ) -> User:
        if self.get_by_username(username) is not None:
            raise ValueError(f"user '{username}' already exists")
        role = role if isinstance(role, Role) else Role(role)
        uid = str(uuid.uuid4())
        ph = hash_password(password)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users (id, username, role, customer_id, password_hash) VALUES (?, ?, ?, ?, ?)",
                (uid, username, role.value, customer_id, ph),
            )
            conn.commit()
        return User(id=uid, username=username, role=role, customer_id=customer_id, password_hash=ph)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        u = self.get_by_username(username)
        if u and verify_password(password, u.password_hash):
            return u
        return None

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
        return [self._row_to_user(r) for r in rows]
