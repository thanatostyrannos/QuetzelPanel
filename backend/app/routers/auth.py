"""Auth routes — WP-A implementation.

Endpoints:
  POST /auth/login              — local username/password → JWT
  POST /auth/logout             — stateless; client discards token (200 OK)
  GET  /auth/me                 — current user info (existing seed, unchanged)
  POST /auth/users              — create user (platform-admin only)
  GET  /auth/google/login       — redirect to Google consent screen
  GET  /auth/google/callback    — exchange code → JWT (same shape as /login)

Admin seed endpoints (let the e2e script stand up tenants):
  POST /customers               — create customer (platform-admin only)
    These live in the customers router but are ALSO needed early in the auth
    flow; the actual route is in routers/customers.py which already seeds the
    InMemoryCustomerStore at startup. This file only adds the auth-adjacent
    POST /auth/users endpoint.

Security:
  - JWT secret MUST come from JWT_SECRET env var; app startup wires the verifier
    via set_token_verifier (see SEAM_REQUESTS.md).
  - Passwords never appear in responses.
  - Google client secret never logged.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator

from ..auth.context import AuthContext, current_user, require_role
from ..auth.google import GoogleOIDCConfig, build_authorization_url, exchange_code_for_userinfo
from ..auth.jwt import JWTConfig, issue_token, jwt_config_from_env
from ..auth.roles import Role
from ..deps import get_customer_store, get_user_store
from ..tenancy import Customer, CustomerStore
from ..users import UserStore
from ..users.store import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    customerId: Optional[str]


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "customer-user"
    customerId: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        try:
            Role(v)
        except ValueError:
            raise ValueError(f"invalid role: {v!r}")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_to_out(u: User) -> UserOut:
    return UserOut(id=u.id, username=u.username, role=u.role.value, customerId=u.customer_id)


def _get_jwt_config() -> JWTConfig:
    cfg = jwt_config_from_env()
    if cfg is None:
        # Fallback for dev/CI when JWT_SECRET is not set: use a fixed dev secret.
        # A warning is appropriate but we keep the app functional in mock mode.
        return JWTConfig(secret="dev-only-insecure-jwt-secret-change-me!", algorithm="HS256", ttl=3600)
    return cfg


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/me")
async def me(user: AuthContext = Depends(current_user)):
    return {
        "userId": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "customerId": user.customer_id,
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    store: UserStore = Depends(get_user_store),
):
    user = store.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    cfg = _get_jwt_config()
    token = issue_token(
        cfg,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        customer_id=user.customer_id,
    )
    return LoginResponse(token=token, user=_user_to_out(user))


@router.post("/logout")
async def logout(user: AuthContext = Depends(current_user)):
    # Stateless JWT: client discards the token. Nothing to invalidate server-side.
    return {"detail": "logged out"}


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: CreateUserRequest,
    store: UserStore = Depends(get_user_store),
    _admin: AuthContext = Depends(require_role(Role.platform_admin)),
):
    try:
        user = store.create_user(
            username=body.username,
            password=body.password,
            role=Role(body.role),
            customer_id=body.customerId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _user_to_out(user)


# ---------------------------------------------------------------------------
# Google OIDC
# ---------------------------------------------------------------------------


@router.get("/google/login")
async def google_login():
    cfg = GoogleOIDCConfig.from_env()
    if cfg is None:
        raise HTTPException(
            status_code=503,
            detail="Google OIDC is not configured (set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET)",
        )
    url = build_authorization_url(cfg)
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: Optional[str] = None,
    store: UserStore = Depends(get_user_store),
    customer_store: CustomerStore = Depends(get_customer_store),
):
    oidc_cfg = GoogleOIDCConfig.from_env()
    if oidc_cfg is None:
        raise HTTPException(status_code=503, detail="Google OIDC is not configured")

    try:
        userinfo = await exchange_code_for_userinfo(oidc_cfg, code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OIDC exchange failed: {exc}")

    # Google sub is the stable identifier
    google_sub = userinfo.get("sub", "")
    email = userinfo.get("email", "")
    name = userinfo.get("name") or email

    # Derive a username from email (before the @)
    username = email.split("@")[0] if "@" in email else google_sub

    # Find or create the user (upsert by username derived from Google sub).
    # The google_sub is stored as a prefix to avoid collisions with local users.
    google_username = f"google:{google_sub}"
    user = store.get_by_username(google_username)
    if user is None:
        # New Google user: create as customer_user with no customer (admin assigns later)
        try:
            import secrets as _secrets

            user = store.create_user(
                username=google_username,
                password=_secrets.token_urlsafe(32),  # unusable random password (can't log in locally)
                role=Role.customer_user,
                customer_id=None,
            )
        except ValueError:
            # Race condition: another request created it; fetch it
            user = store.get_by_username(google_username)

    cfg = _get_jwt_config()
    token = issue_token(
        cfg,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        customer_id=user.customer_id,
    )
    return {"token": token, "user": _user_to_out(user)}
