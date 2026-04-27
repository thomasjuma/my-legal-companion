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

# Match main.py: repo-root `.env` for local / container runs
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)


def _jwks_url() -> str:
    return (os.environ.get("CLERK_JWKS_URL") or "").strip()


def _build_config() -> ClerkConfig:
    url = _jwks_url()
    if not url:
        raise RuntimeError(
            "Set CLERK_JWKS_URL in the environment (e.g. in the repo .env). "
            "In Clerk: Dashboard → your app → API Keys, use the "
            "Frontend / JWKS URL, usually ending in /.well-known/jwks.json"
        )
    leeway = float((os.environ.get("CLERK_JWT_LEEWAY") or "0").strip() or "0")
    aud = (os.environ.get("CLERK_JWT_AUDIENCE") or "").strip() or None
    iss = (os.environ.get("CLERK_JWT_ISSUER") or "").strip() or None
    return ClerkConfig(
        jwks_url=url,
        leeway=leeway,
        audience=aud,
        issuer=iss,
        verify_aud=(os.environ.get("CLERK_JWT_VERIFY_AUDIENCE", "").strip().lower() in ("1", "true", "yes")),
        verify_iss=(os.environ.get("CLERK_JWT_VERIFY_ISSUER", "").strip().lower() in ("1", "true", "yes")),
    )


# Validates JWTs from the Authorization: Bearer <session> header
clerk_bearer = ClerkHTTPBearer(
    config=_build_config(),
    scheme_name="ClerkSessionToken",
    description="Clerk session token (use the token from the signed-in user in the client)",
    add_state=True,
    debug_mode=os.environ.get("CLERK_JWT_DEBUG", "").strip() == "1",
)


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
