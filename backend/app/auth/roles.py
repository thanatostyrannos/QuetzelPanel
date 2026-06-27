"""Role enum + precedence. Pure, dependency-free."""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    platform_admin = "platform-admin"
    customer_admin = "customer-admin"
    customer_user = "customer-user"


# Higher rank == more privilege.
_ORDER = {
    Role.customer_user: 0,
    Role.customer_admin: 1,
    Role.platform_admin: 2,
}


def role_rank(role: Role) -> int:
    return _ORDER[role]


def at_least(user_role: Role, required: Role) -> bool:
    """True if user_role meets or exceeds the required role."""
    return _ORDER[user_role] >= _ORDER[required]
