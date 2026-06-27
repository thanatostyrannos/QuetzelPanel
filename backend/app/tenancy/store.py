"""CustomerStore interface + in-memory mock + factory.

QUETZEL_USERSTORE=memory   (default) — InMemoryCustomerStore
QUETZEL_USERSTORE=sqlite   — SQLiteCustomerStore (local profile)
QUETZEL_USERSTORE=postgres — PostgresCustomerStore (enterprise stub; WP-A/WP-D)
"""
from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from .models import Customer


class CustomerStore(ABC):
    @abstractmethod
    def list_customers(self) -> list[Customer]: ...

    @abstractmethod
    def get(self, customer_id: str) -> Optional[Customer]: ...

    @abstractmethod
    def create(self, name: str, customer_id: Optional[str] = None) -> Customer: ...


class InMemoryCustomerStore(CustomerStore):
    def __init__(self) -> None:
        self._by_id: dict[str, Customer] = {}

    def list_customers(self) -> list[Customer]:
        return list(self._by_id.values())

    def get(self, customer_id: str) -> Optional[Customer]:
        return self._by_id.get(customer_id)

    def create(self, name: str, customer_id: Optional[str] = None) -> Customer:
        cid = customer_id or str(uuid.uuid4())
        if cid in self._by_id:
            return self._by_id[cid]
        c = Customer(id=cid, name=name)
        self._by_id[cid] = c
        return c


class PostgresCustomerStore(CustomerStore):
    """Enterprise persistence — implemented by WP-A/WP-D."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def list_customers(self):  # pragma: no cover
        raise NotImplementedError("PostgresCustomerStore is implemented in WP-A/WP-D")

    def get(self, customer_id):  # pragma: no cover
        raise NotImplementedError("PostgresCustomerStore is implemented in WP-A/WP-D")

    def create(self, name, customer_id=None):  # pragma: no cover
        raise NotImplementedError("PostgresCustomerStore is implemented in WP-A/WP-D")


def make_customer_store() -> CustomerStore:
    kind = os.getenv("QUETZEL_USERSTORE", "memory").lower()
    if kind == "sqlite":
        from .sqlite_store import SQLiteCustomerStore

        db_path = os.getenv("QUETZEL_DB_PATH", "quetzel.db")
        return SQLiteCustomerStore(db_path)
    if kind == "postgres":
        return PostgresCustomerStore(os.environ.get("QUETZEL_DB_DSN", ""))
    return InMemoryCustomerStore()
