"""Authentication & authorization seams.

Phase 0 publishes the contract (Role, AuthContext, current_user dependency,
require_role) with a permissive dev default so QUETZEL_PROVIDER=mock works with
no identity provider. WP-A installs a real token verifier (JWT/session) backed by
the UserStore, turning enforcement on.
"""
from .roles import Role, at_least, role_rank  # noqa: F401
from .context import (  # noqa: F401
    AuthContext,
    current_user,
    require_role,
    set_token_verifier,
)
