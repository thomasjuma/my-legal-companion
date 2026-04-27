from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from clerk_auth import clerk_bearer

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    dependencies=[Depends(clerk_bearer)],
)


@router.get(
    "/me",
    summary="Current Clerk user (from session JWT)",
    description="Requires `Authorization: Bearer <clerk session token>`.",
)
def read_clerk_user(request: Request) -> dict:
    creds = request.state.clerk_auth
    decoded = creds.decoded or {}
    return {
        "clerk_user_id": decoded.get("sub"),
        "session_id": decoded.get("sid"),
    }
