"""Bootstrap admin helper — WP-D.

Creates a platform-admin user from environment variables on application startup.
Idempotent: if the user already exists it is left unchanged.

Environment variables:
  QUETZEL_BOOTSTRAP_ADMIN_USER      – username (default: "admin")
  QUETZEL_BOOTSTRAP_ADMIN_PASSWORD  – password (required to activate; if absent,
                                       no user is created and the function is a no-op)

Usage in main.py lifespan (lead wires this):

    from app.auth.bootstrap import bootstrap_admin
    from app.deps import get_user_store

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bootstrap_admin(get_user_store())
        # ... rest of startup (JWT verifier, etc.)
        yield
        # ... teardown

The admin user is not exported by any API; it only exists in the UserStore and is
used by the e2e harness (QZ_ADMIN_USER / QZ_ADMIN_PASS env vars) to seed tenants.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

from ..auth.roles import Role

if TYPE_CHECKING:  # avoid a runtime cycle: users/__init__ re-exports this module
    from ..users.store import UserStore

log = logging.getLogger(__name__)


def bootstrap_admin(user_store: "UserStore") -> Optional[str]:
    """Create the bootstrap platform-admin user if env vars are set.

    Returns the user_id of the created or pre-existing admin, or None if the
    env vars are absent (no-op path).
    """
    username = os.getenv("QUETZEL_BOOTSTRAP_ADMIN_USER", "admin")
    password = os.getenv("QUETZEL_BOOTSTRAP_ADMIN_PASSWORD")

    if not password:
        # Environment not configured for a bootstrap admin — skip silently.
        return None

    # Idempotent: if already present, do nothing.
    existing = user_store.get_by_username(username)
    if existing is not None:
        log.info("bootstrap_admin: user '%s' already exists (id=%s) — skipped", username, existing.id)
        return existing.id

    try:
        user = user_store.create_user(
            username=username,
            password=password,
            role=Role.platform_admin,
            customer_id=None,
        )
        log.info(
            "bootstrap_admin: created platform-admin user '%s' (id=%s)",
            username,
            user.id,
        )
        return user.id
    except ValueError:
        # Race condition (e.g. two workers starting simultaneously); already exists.
        found = user_store.get_by_username(username)
        if found:
            log.info("bootstrap_admin: user '%s' created by a concurrent worker — skipped", username)
            return found.id
        raise
