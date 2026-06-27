"""GameServer CRUD routes.

NOTE (seam): auth/tenancy guards are layered on by WP-A (current_user) and WP-D
(scope_for) via Depends. Phase 0 keeps these routes open so QUETZEL_PROVIDER=mock
stays demoable; the dependency seam lives in app.auth / app.tenancy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import catalog
from ..deps import get_provider
from ..models import CreateServerRequest, GameServer
from ..providers.base import Provider

router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=list[GameServer])
async def list_servers(provider: Provider = Depends(get_provider)):
    return await provider.list_servers()


@router.post("/servers", response_model=GameServer, status_code=201)
async def create_server(req: CreateServerRequest, provider: Provider = Depends(get_provider)):
    if not catalog.get_game(req.game):
        raise HTTPException(status_code=400, detail=f"unknown game '{req.game}'")
    try:
        return await provider.create_server(req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/servers/{name}", response_model=GameServer)
async def get_server(name: str, provider: Provider = Depends(get_provider)):
    srv = await provider.get_server(name)
    if not srv:
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    return srv


@router.delete("/servers/{name}", status_code=204)
async def delete_server(name: str, provider: Provider = Depends(get_provider)):
    ok = await provider.delete_server(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    return None
