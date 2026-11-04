"""Token verification for the internal listener."""

from __future__ import annotations

import hmac

TOKEN_HEADER = "X-Menu-Planner-Token"


def token_matches(provided: str | None, expected: str) -> bool:
    """Constant-time comparison. An absent header never matches."""
    if not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
