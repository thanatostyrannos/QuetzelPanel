"""Game catalog routes."""
from __future__ import annotations

from fastapi import APIRouter

from .. import catalog

router = APIRouter(tags=["games"])


@router.get("/games")
async def get_games():
    return {"games": catalog.list_games()}
