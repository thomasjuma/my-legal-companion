from __future__ import annotations

import os
import logging
from datetime import datetime

from agents import Agent, Runner
from agents.extensions.models.litellm_model import LitellmModel

from schemas import ChatMessage

logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

_log = logging.getLogger(__name__)

_DEFAULT_MAX_TURNS = 5


def _transcript_for_agent(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for m in messages:
        if m.role == "user":
            parts.append(f"User:\n{m.content}")
        elif m.role == "assistant":
            parts.append(f"Assistant:\n{m.content}")
        else:
            parts.append(f"System:\n{m.content}")
    return (
        "Below is a conversation. Reply as the assistant to the most recent user "
        "message, using the prior lines only as context.\n\n" + "\n\n".join(parts)
    )


def _chat_instructions() -> str:
    today = datetime.now().strftime("%B %d, %Y")
    return f"""You are a helpful assistant for the Legal Companion application. \
Today is {today}.

You are not a lawyer. Do not provide definitive legal advice. Offer clear, \
general information that may help users understand their situation, suggest \
appropriate questions to ask a qualified professional, and encourage them to \
seek a licensed attorney when the matter is serious, time-sensitive, or unclear.

Be concise, respectful, and plain-spoken."""


def _get_chat_model() -> str:
    return (os.environ.get("CHAT_OPENAI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o").strip()


async def run_chat(
    messages: list[ChatMessage], *, max_turns: int | None = None
) -> str:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        msg = "OPENAI_API_KEY is not set. Add it to your environment to use chat."
        _log.warning(msg)
        raise ValueError(msg)

    model_id = _get_chat_model()
    if not model_id:
        raise ValueError("CHAT_OPENAI_MODEL / OPENAI_MODEL is empty.")

    model = LitellmModel(model=f"openai/{model_id}")
    agent = Agent(
        name="Legal Companion",
        instructions=_chat_instructions(),
        model=model,
    )
    user_input = _transcript_for_agent(messages)
    turns = max_turns if max_turns is not None else int(
        os.environ.get("CHAT_MAX_TURNS", str(_DEFAULT_MAX_TURNS))
    )
    result = await Runner.run(
        agent,
        input=user_input,
        max_turns=max(1, min(turns, 50)),
    )
    return result.final_output or ""


def get_effective_model_name() -> str:
    return _get_chat_model()
