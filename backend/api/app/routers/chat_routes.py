from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.clerk_auth import clerk_bearer, get_clerk_user_id
from core.schemas import ChatRequest, ChatResponse
from services.chat_service import get_effective_model_name, run_chat
from counsel_agents.writer import store_consultation_report



_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
    dependencies=[Depends(clerk_bearer)],
)


def _latest_user_message_text(body: ChatRequest) -> str:
    for message in reversed(body.messages):
        if message.role == "user":
            return message.content
    return body.messages[-1].content


@router.post(
    "/messages",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with the Legal Companion assistant (OpenAI)",
)
async def post_chat_message(
    body: ChatRequest,
    request: Request,
) -> ChatResponse:
    """
    Send a conversation and receive one assistant message.

    The frontend can send the full `messages` array (e.g. OpenAI-style
    `system` / `user` / `assistant` turns); the last turn should be from the
    user so the model can continue naturally.
    """
    sub = get_clerk_user_id(request)

    try:
        result = await run_chat(body.messages, max_turns=body.max_turns)
    except ValueError as e:
        # Misconfiguration (missing key, etc.)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    except Exception as e:
        _log.exception("Chat agent failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service failed to respond. Please try again later.",
        ) from e

    generated_report = result["generated_report"]
    if generated_report is not None:
        try:
            await store_consultation_report(
                clerk_user_id=sub,
                consultation_query=_latest_user_message_text(body),
                consultation_report=generated_report.report,
                consultation_summary=generated_report.summary,
                evaluation_score=(
                    result["evaluation"].score if result["evaluation"] is not None else None
                ),
                evaluation_feedback=(
                    result["evaluation"].feedback if result["evaluation"] is not None else None
                ),
            )
        except Exception:
            # Report persistence is best-effort; don't fail chat completion on DB issues.
            _log.exception("Failed to store generated consultation report")

    return ChatResponse(
        message=result["message"],
        model=get_effective_model_name(),
        evaluation_feedback=(
            result["evaluation"].feedback if result["evaluation"] is not None else None
        ),
        evaluation_score=(
            result["evaluation"].score if result["evaluation"] is not None else None
        ),
        final_report_summary=(
            result["generated_report"].summary
            if result["generated_report"] is not None
            else None
        ),
        final_report=(
            result["generated_report"].report
            if result["generated_report"] is not None
            else None
        ),
    )