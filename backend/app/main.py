"""QuetzelPanel backend API — app wiring only.

Domain logic lives in app/routers/* (servers, games, auth, metrics, clusters,
customers) and the contracts under app/{auth,users,metrics,tenancy,clusters}.
This module only constructs the app, installs middleware, manages provider
lifespan, and mounts the routers.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.bootstrap import bootstrap_admin
from .auth.context import set_token_verifier
from .auth.jwt import build_token_verifier, jwt_config_from_env
from .deps import get_provider, get_user_store
from .providers.base import Provider
from .routers import auth, clusters, customers, games, metrics, servers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Wire JWT auth when configured (JWT_SECRET present). With no config the
    # verifier stays None and current_user is permissive (mock/dev demoable).
    cfg = jwt_config_from_env()
    set_token_verifier(build_token_verifier(cfg) if cfg else None)
    # Idempotently seed a platform-admin from env (enables API-driven tenant
    # seeding under enforced auth; no-op if the env vars are unset).
    bootstrap_admin(get_user_store())
    provider = get_provider()
    await provider.startup()
    yield
    await provider.shutdown()
    set_token_verifier(None)


app = FastAPI(title="QuetzelPanel API", version="0.2.0", lifespan=lifespan)

# CORS: the Vite dev server / any origin in dev. Locked down per-deploy via env.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["meta"])
async def healthz(provider: Provider = Depends(get_provider)):
    return {"status": "ok", "provider": provider.kind()}


# --- AUTH PLACEHOLDER ---------------------------------------------------------
# WP-A mounts the auth router and adds Depends(current_user) to the protected
# routers (servers/metrics/clusters/customers). The dependency seam is published
# in app.auth; the UserStore in app.users.
# -----------------------------------------------------------------------------

app.include_router(games.router)
app.include_router(servers.router)
app.include_router(auth.router)
app.include_router(metrics.router)
app.include_router(clusters.router)
app.include_router(customers.router)
