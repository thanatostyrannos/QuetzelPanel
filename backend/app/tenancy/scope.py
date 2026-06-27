"""Pure tenancy scoping — no I/O, fully unit-tested.

A platform-admin sees everything; everyone else sees only their own customer's
servers. Ownership is carried on the GameServer (spec.customer) and mirrored to
the `quetzel.gg/customer` label on cluster objects (WP-D wires the label).
"""
from __future__ import annotations

from typing import Callable, Iterable

from ..auth.context import AuthContext
from ..auth.roles import Role

CUSTOMER_LABEL = "quetzel.gg/customer"


def server_customer(server) -> str | None:
    """Extract a server's owning customer id from a GameServer or a dict."""
    spec = getattr(server, "spec", None)
    if spec is not None:
        return getattr(spec, "customer", None)
    if isinstance(server, dict):
        return (server.get("spec") or {}).get("customer")
    return None


def can_see(user: AuthContext, server) -> bool:
    if user.role == Role.platform_admin:
        return True
    return server_customer(server) is not None and server_customer(server) == user.customer_id


def scope_for(user: AuthContext) -> Callable[[object], bool]:
    """Return a predicate selecting the servers `user` is allowed to see."""
    return lambda server: can_see(user, server)


def visible_servers(user: AuthContext, servers: Iterable):
    pred = scope_for(user)
    return [s for s in servers if pred(s)]
