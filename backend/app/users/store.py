"""UserStore interface + an in-memory mock (real password hashing, stdlib only).

WP-A provides PostgresUserStore (enterprise) and may upgrade hashing to argon2.
The in-memory store keeps QUETZEL_PROVIDER=mock fully demoable/testable offline.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..auth.roles import Role


@dataclass
class User:
    id: str
    username: str
    role: Role
    customer_id: Optional[str]
    password_hash: str = field(default="", repr=False)  # never serialized out


def hash_password(password: str, salt: Optional[bytes] = None, iterations: int = 100_000) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


class UserStore(ABC):
    @abstractmethod
    def get(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]: ...

    @abstractmethod
    def create_user(
        self, username: str, password: str, role: Role, customer_id: Optional[str] = None
    ) -> User: ...

    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[User]: ...

    @abstractmethod
    def list_users(self) -> list[User]: ...


class InMemoryUserStore(UserStore):
    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_name: dict[str, User] = {}

    def get(self, user_id: str) -> Optional[User]:
        return self._by_id.get(user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        return self._by_name.get(username)

    def create_user(self, username, password, role, customer_id=None) -> User:
        if username in self._by_name:
            raise ValueError(f"user '{username}' already exists")
        role = role if isinstance(role, Role) else Role(role)
        u = User(
            id=str(uuid.uuid4()),
            username=username,
            role=role,
            customer_id=customer_id,
            password_hash=hash_password(password),
        )
        self._by_id[u.id] = u
        self._by_name[username] = u
        return u

    def authenticate(self, username, password) -> Optional[User]:
        u = self._by_name.get(username)
        if u and verify_password(password, u.password_hash):
            return u
        return None

    def list_users(self) -> list[User]:
        return list(self._by_id.values())


class PostgresUserStore(UserStore):
    """Enterprise persistence — implemented by WP-A (auth)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def get(self, user_id):  # pragma: no cover - WP-A
        raise NotImplementedError("PostgresUserStore is implemented in WP-A (auth)")

    def get_by_username(self, username):  # pragma: no cover - WP-A
        raise NotImplementedError("PostgresUserStore is implemented in WP-A (auth)")

    def create_user(self, username, password, role, customer_id=None):  # pragma: no cover
        raise NotImplementedError("PostgresUserStore is implemented in WP-A (auth)")

    def authenticate(self, username, password):  # pragma: no cover - WP-A
        raise NotImplementedError("PostgresUserStore is implemented in WP-A (auth)")

    def list_users(self):  # pragma: no cover - WP-A
        raise NotImplementedError("PostgresUserStore is implemented in WP-A (auth)")
