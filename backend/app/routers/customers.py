"""Customer (tenant) routes (WP-D).

Endpoints:
  POST /customers                    – create customer (platform-admin only)
  GET  /customers                    – list customers (admin: all; customer: own)
  GET  /customers/{id}/servers       – servers for one customer, merged across
                                       all registered clusters.

WP-D wires cross-cluster rollups: GET /customers/{id}/servers fetches from every
registered cluster and merges the results so an admin gets a unified view even
when a customer's servers span multiple clusters.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.context import AuthContext, current_user, require_role
from ..auth.roles import Role
from ..clusters import ClusterRegistry
from ..clusters.registry import RemoteClusterRegistry
from ..deps import get_cluster_registry, get_customer_store, get_provider
from ..models import GameServer
from ..providers.base import Provider
from ..tenancy import Customer, CustomerStore
from ..tenancy.scope import server_customer

log = logging.getLogger(__name__)

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
    registry: ClusterRegistry = Depends(get_cluster_registry),
    user: AuthContext = Depends(current_user),
):
    """Return servers belonging to ``customer_id``, merged across all clusters.

    Access rules:
    - Platform-admins may query any customer.
    - Customer-users may only query their own customer_id.

    With a multi-cluster registry, this fans out to every registered cluster
    and merges the results before filtering by customer ownership.
    """
    if user.role != Role.platform_admin and user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="not your customer")

    clusters = registry.list_clusters()

    if len(clusters) <= 1:
        # Fast-path: single cluster — use the injected provider directly.
        servers = await provider.list_servers()
        return [s for s in servers if server_customer(s) == customer_id]

    # Multi-cluster: fan out, merge, filter.
    async def _fetch(ref) -> list[GameServer]:
        try:
            # Use the injected ``provider`` for the local cluster to honour
            # FastAPI dependency_overrides (important for tests).
            if ref.local:
                prov = provider
            elif isinstance(registry, RemoteClusterRegistry):
                stored = registry.get_provider(ref.id)
                if stored is None:
                    raise NotImplementedError(f"no provider for '{ref.id}'")
                prov = stored
            else:
                raise NotImplementedError(f"no provider for '{ref.id}'")
            return await prov.list_servers()
        except NotImplementedError:
            log.warning("customer_servers: no provider for cluster '%s' — skipping", ref.id)
            return []
        except Exception as exc:  # noqa: BLE001
            log.warning("customer_servers: error fetching cluster '%s': %s", ref.id, exc)
            return []

    results = await asyncio.gather(*[_fetch(c) for c in clusters])
    all_servers: list[GameServer] = []
    for srvs in results:
        all_servers.extend(srvs)

    return [s for s in all_servers if server_customer(s) == customer_id]
