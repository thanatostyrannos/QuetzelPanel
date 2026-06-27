"""GameServer CRUD routes.

NOTE (seam): auth/tenancy guards are layered on by WP-A (current_user) and WP-D
(scope_for) via Depends. Phase 0 keeps these routes open so QUETZEL_PROVIDER=mock
stays demoable; the dependency seam lives in app.auth / app.tenancy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import catalog
from ..auth.context import AuthContext, current_user
from ..auth.roles import Role
from ..deps import get_provider
from ..models import CreateServerRequest, GameServer
from ..providers.base import Provider
from ..tenancy.scope import can_see, visible_servers

router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=list[GameServer])
async def list_servers(
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    # Tenancy scoping: platform-admin sees all; others see only their customer's.
    return visible_servers(user, await provider.list_servers())


@router.post("/servers", response_model=GameServer, status_code=201)
async def create_server(
    req: CreateServerRequest,
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    if not catalog.get_game(req.game):
        raise HTTPException(status_code=400, detail=f"unknown game '{req.game}'")
    # Non-admins can only create within their own customer; force it.
    if user.role != Role.platform_admin and user.customer_id:
        req.options = {**(req.options or {}), "customer": user.customer_id}
    try:
        return await provider.create_server(req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/servers/{name}", response_model=GameServer)
async def get_server(
    name: str,
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    srv = await provider.get_server(name)
    if not srv or not can_see(user, srv):
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    return srv


@router.delete("/servers/{name}", status_code=204)
async def delete_server(
    name: str,
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    existing = await provider.get_server(name)
    if not existing or not can_see(user, existing):
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    ok = await provider.delete_server(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    return None
