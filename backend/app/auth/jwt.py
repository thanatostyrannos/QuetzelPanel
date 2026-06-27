"""JWT issuance + verification for QuetzelPanel.

Dependencies: PyJWT (stdlib-safe; no cryptography needed for HS256).

The JWT payload:
  sub   – user_id
  usr   – username
  rol   – role value (string)
  cid   – customer_id (string or null)
  iat   – issued-at (Unix epoch, set by PyJWT)
  exp   – expiry  (set by PyJWT)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import jwt as _jwt

from .context import AuthContext
from .roles import Role


@dataclass(frozen=True)
class JWTConfig:
    secret: str
    algorithm: str = "HS256"
    ttl: int = 3600  # seconds


def issue_token(
    cfg: JWTConfig,
    *,
    user_id: str,
    username: str,
    role: str,
    customer_id: Optional[str],
) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "usr": username,
        "rol": role,
        "cid": customer_id,
        "iat": now,
        "exp": now + cfg.ttl,
    }
    return _jwt.encode(payload, cfg.secret, algorithm=cfg.algorithm)


def verify_token(cfg: JWTConfig, token: Optional[str]) -> Optional[AuthContext]:
    """Decode and validate a JWT; return AuthContext or None."""
    if not token:
        return None
    try:
        payload = _jwt.decode(
            token,
            cfg.secret,
            algorithms=[cfg.algorithm],
            options={"require": ["sub", "usr", "rol", "exp"]},
        )
        return AuthContext(
            user_id=payload["sub"],
            username=payload["usr"],
            role=Role(payload["rol"]),
            customer_id=payload.get("cid"),
        )
    except Exception:
        return None


def build_token_verifier(cfg: JWTConfig) -> Callable[[Optional[str]], Optional[AuthContext]]:
    """Return a callable compatible with set_token_verifier.

    The callable accepts the raw Authorization header value (e.g. "Bearer <tok>")
    or a bare token string, and returns AuthContext | None.
    """

    def _verify(raw: Optional[str]) -> Optional[AuthContext]:
        if not raw:
            return None
        token = raw[7:].strip() if raw.lower().startswith("bearer ") else raw
        return verify_token(cfg, token)

    return _verify


def jwt_config_from_env() -> Optional[JWTConfig]:
    """Read JWT config from environment; return None if JWT_SECRET is not set."""
    import os

    secret = os.getenv("JWT_SECRET")
    if not secret:
        return None
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    ttl = int(os.getenv("JWT_TTL", "3600"))
    return JWTConfig(secret=secret, algorithm=algorithm, ttl=ttl)
