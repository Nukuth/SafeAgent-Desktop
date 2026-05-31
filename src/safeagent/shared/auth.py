from __future__ import annotations

import hmac

from safeagent.shared.errors import AuthError


def require_bearer_token(authorization_header: str | None, expected_token: str) -> None:
    """Validate a bearer token without leaking token values through comparisons or errors."""

    if not expected_token:
        raise AuthError("Server token is not configured")
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise AuthError()
    supplied = authorization_header.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, expected_token):
        raise AuthError()

