"""Contract tests for the auth seam (Role precedence, current_user, require_role)."""
import asyncio

import pytest
from fastapi import HTTPException

from app.auth.context import (
    AuthContext,
    current_user,
    require_role,
    set_token_verifier,
)
from app.auth.roles import Role, at_least


def test_role_precedence():
    assert at_least(Role.platform_admin, Role.customer_user)
    assert at_least(Role.customer_admin, Role.customer_user)
    assert at_least(Role.customer_user, Role.customer_user)
    assert not at_least(Role.customer_user, Role.customer_admin)
    assert not at_least(Role.customer_admin, Role.platform_admin)


def test_current_user_permissive_without_verifier():
    set_token_verifier(None)
    ctx = asyncio.run(current_user(authorization=None))
    assert ctx.role == Role.platform_admin


def test_current_user_enforces_with_verifier():
    def verify(token):
        if token == "good":
            return AuthContext("u1", "alice", Role.customer_user, "cust-a")
        return None

    set_token_verifier(verify)
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(current_user(authorization=None))
        assert ei.value.status_code == 401
        ctx = asyncio.run(current_user(authorization="Bearer good"))
        assert ctx.username == "alice" and ctx.customer_id == "cust-a"
    finally:
        set_token_verifier(None)


def test_require_role():
    admin = AuthContext("a", "admin", Role.platform_admin, None)
    user = AuthContext("u", "user", Role.customer_user, "c")
    dep = require_role(Role.customer_admin)
    assert asyncio.run(dep(user=admin)) is admin
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dep(user=user))
    assert ei.value.status_code == 403


def test_me_endpoint(client):
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["role"] == "platform-admin"


def test_login_seed_not_implemented(client):
    assert client.post("/auth/login").status_code == 501
