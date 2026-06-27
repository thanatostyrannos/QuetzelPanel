"""Google OIDC helpers (Authlib-based).

The module is lazy: GoogleOIDCConfig.from_env() returns None when the env vars
are absent, which makes the /auth/google/* routes return 503 instead of crashing.

Flow:
  GET /auth/google/login   → redirect to Google's consent screen
  GET /auth/google/callback?code=...&state=... → exchange code → issue JWT
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GoogleOIDCConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorization_endpoint: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint: str = "https://oauth2.googleapis.com/token"
    userinfo_endpoint: str = "https://www.googleapis.com/oauth2/v3/userinfo"

    @classmethod
    def from_env(cls) -> Optional["GoogleOIDCConfig"]:
        cid = os.getenv("GOOGLE_CLIENT_ID")
        csecret = os.getenv("GOOGLE_CLIENT_SECRET")
        ruri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
        if not (cid and csecret):
            return None
        return cls(client_id=cid, client_secret=csecret, redirect_uri=ruri)


def build_authorization_url(cfg: GoogleOIDCConfig, state: Optional[str] = None) -> str:
    """Build the Google OAuth2 authorization URL."""
    from urllib.parse import urlencode

    state = state or secrets.token_urlsafe(16)
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{cfg.authorization_endpoint}?{urlencode(params)}"


async def exchange_code_for_userinfo(cfg: GoogleOIDCConfig, code: str) -> dict:
    """Exchange authorization code for user info dict.

    Returns dict with keys: sub, email, name (at minimum).
    Raises httpx.HTTPError on network failure.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            cfg.token_endpoint,
            data={
                "code": code,
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "redirect_uri": cfg.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        # Fetch user info
        userinfo_resp = await client.get(
            cfg.userinfo_endpoint,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()
