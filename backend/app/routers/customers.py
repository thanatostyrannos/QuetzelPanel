"""Customer (tenant) routes (SEED — WP-D owns/expands this file).

Phase 0 lists customers (scoped by role) and a customer's servers (filtered by
ownership via the pure tenancy scope). WP-D wires cross-cluster rollups.
WP-A adds POST /customers (admin-only tenant creation for e2e seeding).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.context import AuthContext, current_user, require_role
from ..auth.roles import Role
from ..deps import get_customer_store, get_provider
from ..models import GameServer
from ..providers.base import Provider
from ..tenancy import Customer, CustomerStore
from ..tenancy.scope import server_customer

router = APIRouter(prefix="/customers", tags=["customers"])


class CreateCustomerRequest(BaseModel):
    id: Optional[str] = None
    name: str


def _visible_customers(user: AuthContext, customers: list[Customer]) -> list[Customer]:
    if user.role == Role.platform_admin:
        return customers
    return [c for c in customers if c.id == user.customer_id]


@router.post("", response_model=Customer, status_code=201)
async def create_customer(
    body: CreateCustomerRequest,
    store: CustomerStore = Depends(get_customer_store),
    _admin: AuthContext = Depends(require_role(Role.platform_admin)),
):
    return store.create(name=body.name, customer_id=body.id)


@router.get("", response_model=list[Customer])
async def list_customers(
    store: CustomerStore = Depends(get_customer_store),
    user: AuthContext = Depends(current_user),
):
    return _visible_customers(user, store.list_customers())


@router.get("/{customer_id}/servers", response_model=list[GameServer])
async def customer_servers(
    customer_id: str,
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),
):
    if user.role != Role.platform_admin and user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="not your customer")
    servers = await provider.list_servers()
    return [s for s in servers if server_customer(s) == customer_id]
