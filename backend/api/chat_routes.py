from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from chat_service import get_effective_model_name, run_chat
from schemas import ChatRequest, ChatResponse

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "/messages",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with the Legal Companion assistant (OpenAI)",
)
async def post_chat_message(body: ChatRequest) -> ChatResponse:
    """
    Send a conversation and receive one assistant message.

    The frontend can send the full `messages` array (e.g. OpenAI-style
    `system` / `user` / `assistant` turns); the last turn should be from the
    user so the model can continue naturally.
    """
    try:
        text = await run_chat(body.messages, max_turns=body.max_turns)
    except ValueError as e:
        # Misconfiguration (missing key, etc.)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    except Exception:
        _log.exception("Chat agent failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service failed to respond. Please try again later.",
        ) from e
    return ChatResponse(
        message=text,
        model=get_effective_model_name(),
    )
