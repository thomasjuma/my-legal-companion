from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)

# clerk_auth.py lives at app/core/clerk_auth.py → 4 parents up reaches repo root
# _ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(override=False)

_clerk_bearer: ClerkHTTPBearer | None = None


def _get_clerk_bearer() -> ClerkHTTPBearer:
    """Lazily build ClerkHTTPBearer so .env is guaranteed loaded before use."""
    global _clerk_bearer
    if _clerk_bearer is None:
        jwks_url = os.environ.get("CLERK_JWKS_URL", "").strip()
        issuer = os.environ.get("CLERK_ISSUER", "").strip()
        if not jwks_url:
            raise RuntimeError(
                "CLERK_JWKS_URL is not set. Add it to your .env or environment."
            )
        clerk_config = ClerkConfig(jwks_url=jwks_url, issuer=issuer or None)
        # add_state=True makes ClerkHTTPBearer write decoded credentials to
        # request.state.clerk_auth, which get_clerk_user_id() reads below.
        _clerk_bearer = ClerkHTTPBearer(config=clerk_config, add_state=True)
    return _clerk_bearer


async def clerk_bearer(request: Request) -> None:
    """FastAPI dependency: validates the Clerk JWT on every protected request."""
    await _get_clerk_bearer()(request)


def get_clerk_creds(request: Request) -> HTTPAuthorizationCredentials:
    creds: HTTPAuthorizationCredentials = request.state.clerk_auth
    if not creds or not creds.decoded or not creds.decoded.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or missing subject in token.",
        )
    return creds


def get_clerk_user_id(request: Request) -> str:
    """Clerk `sub` claim (application user id). Use for linking to your `users` table."""
    return str(get_clerk_creds(request).decoded["sub"])
