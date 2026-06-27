"""QuetzelPanel backend API.

REST/JSON over a Provider (mock or real k8s). Endpoints per spec:
  GET    /games            catalog
  GET    /servers          list + status
  POST   /servers          create from {game, name, options}
  GET    /servers/{name}   status incl. address
  DELETE /servers/{name}   delete
  GET    /healthz          liveness

NOTE: single trusted user for v1 — no auth. Auth/multi-tenancy would slot in as
FastAPI dependencies on these routes (see AUTH PLACEHOLDER below).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import catalog
from .models import CreateServerRequest, GameServer
from .providers import make_provider

provider = make_provider()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await provider.startup()
    yield
    await provider.shutdown()


app = FastAPI(title="QuetzelPanel API", version="0.1.0", lifespan=lifespan)

# Single-user local dev: allow the Vite dev server / any origin. Lock down for prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTH PLACEHOLDER ---------------------------------------------------------
# For multi-tenant v2, add a dependency here, e.g.:
#   async def current_user(authorization: str = Header(...)) -> User: ...
# and attach `Depends(current_user)` to the /servers routes, then scope provider
# operations by user. v1 is intentionally single trusted user.
# -----------------------------------------------------------------------------


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "provider": provider.kind()}


@app.get("/games")
async def get_games():
    return {"games": catalog.list_games()}


@app.get("/servers", response_model=list[GameServer])
async def list_servers():
    return await provider.list_servers()


@app.post("/servers", response_model=GameServer, status_code=201)
async def create_server(req: CreateServerRequest):
    if not catalog.get_game(req.game):
        raise HTTPException(status_code=400, detail=f"unknown game '{req.game}'")
    try:
        return await provider.create_server(req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/servers/{name}", response_model=GameServer)
async def get_server(name: str):
    srv = await provider.get_server(name)
    if not srv:
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    return srv


@app.delete("/servers/{name}", status_code=204)
async def delete_server(name: str):
    ok = await provider.delete_server(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"server '{name}' not found")
    return None
