"""
API key authentication.

Two tiers of keys:
  - "Master" keys: static, configured via the API_KEYS env var. These
    exist for bootstrapping (so there's always a way in before any
    DB-issued key exists) and for CI/ops use. They're also the only keys
    allowed to administer other keys (create/revoke) -- a DB-issued key
    can inspect tool calls but can't mint more keys for itself.
  - Issued keys: created via POST /v1/admin/keys, stored hashed in the
    api_keys table, individually revocable without touching the .env
    file or restarting the service.

Every protected non-admin endpoint accepts either kind. Admin endpoints
require a master key specifically.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.api_keys import verify_key as verify_issued_key

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected: Bearer <api_key>",
        )
    token = credentials.credentials

    if token in settings.api_key_set:
        return token

    if verify_issued_key(token):
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked API key",
    )


async def verify_master_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Used for admin endpoints (issuing/revoking keys) -- master keys only."""
    if credentials is None or credentials.credentials not in settings.api_key_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a master API key",
        )
    return credentials.credentials
