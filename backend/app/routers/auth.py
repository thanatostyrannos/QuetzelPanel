"""Auth routes (SEED — WP-A owns/expands this file).

Phase 0 exposes the current-user endpoint (works in mock mode). Real login,
JWT issuance, Google OIDC, and user management are implemented by WP-A.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.context import AuthContext, current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: AuthContext = Depends(current_user)):
    return {
        "userId": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "customerId": user.customer_id,
    }


@router.post("/login")
async def login():
    # WP-A: authenticate against the UserStore (local user/pass) + issue a JWT,
    # and add the "Sign in with Google" OIDC path.
    raise HTTPException(status_code=501, detail="login is implemented in WP-A (auth)")
