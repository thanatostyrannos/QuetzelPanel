"""Request principal + the auth dependency seam.

`current_user` resolves the caller from the Authorization header via a pluggable
verifier. With no verifier configured (mock/dev) it returns a platform-admin so
the app is fully usable offline. WP-A calls set_token_verifier() with a real
JWT/session decoder; once set, missing/invalid tokens yield 401.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException

from .roles import Role, at_least


@dataclass
class AuthContext:
    """The authenticated caller for a request."""

    user_id: str
    username: str
    role: Role
    customer_id: Optional[str]  # None for platform-admin (cross-customer scope)


# Permissive dev principal used when no identity provider is wired (mock mode).
ANONYMOUS_ADMIN = AuthContext(
    user_id="dev",
    username="dev",
    role=Role.platform_admin,
    customer_id=None,
)

# Verifier seam: (token: str | None) -> AuthContext | None. Set by WP-A.
_verifier: Optional[Callable[[Optional[str]], Optional[AuthContext]]] = None


def set_token_verifier(fn: Optional[Callable[[Optional[str]], Optional[AuthContext]]]) -> None:
    global _verifier
    _verifier = fn


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def current_user(authorization: Optional[str] = Header(default=None)) -> AuthContext:
    if _verifier is None:
        # No IdP configured (mock/dev): allow as platform-admin.
        return ANONYMOUS_ADMIN
    ctx = _verifier(_bearer(authorization))
    if ctx is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return ctx


def require_role(required: Role):
    """Dependency factory enforcing a minimum role."""

    async def dep(user: AuthContext = Depends(current_user)) -> AuthContext:
        if not at_least(user.role, required):
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return dep
