"""SQLite-backed CustomerStore (stdlib sqlite3 — no external deps).

Mirrors SQLiteUserStore design: schema auto-created, file path injected.
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import Optional

from .models import Customer
from .store import CustomerStore


class SQLiteCustomerStore(CustomerStore):
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _row_to_customer(self, row: sqlite3.Row) -> Customer:
        return Customer(id=row["id"], name=row["name"])

    def list_customers(self) -> list[Customer]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM customers").fetchall()
        return [self._row_to_customer(r) for r in rows]

    def get(self, customer_id: str) -> Optional[Customer]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return self._row_to_customer(row) if row else None

    def create(self, name: str, customer_id: Optional[str] = None) -> Customer:
        cid = customer_id or str(uuid.uuid4())
        # idempotent: return existing if id already present
        existing = self.get(cid)
        if existing:
            return existing
        with self._connect() as conn:
            conn.execute("INSERT INTO customers (id, name) VALUES (?, ?)", (cid, name))
            conn.commit()
        return Customer(id=cid, name=name)
