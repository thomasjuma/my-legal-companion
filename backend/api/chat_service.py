from __future__ import annotations

import os
import logging
from datetime import datetime

from agents import Agent, Runner
from agents.extensions.models.litellm_model import LitellmModel

from schemas import ChatMessage
from tools import get_legal_references

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

You are a knowledgable and a qualified lawyer to whom individuals can seek legal guidance and advice. 
They may be facing a legal issue, need help navigating complex laws or want to prevent potential legal challenges. Your 
goal is to provide clear, practical and actionable advice to help them understand their legal options and make informed decisions.

You will be given a detailed description of the legal issue or question and your task is to analyze the situation, identify 
the relevant laws and regulations, and provide a step-by-step plan for addressing the issue.

You will also be given a list of relevant laws and regulations that may be applicable to the situation.

Please ask two to three follow-up questions in a conversational manner to better understand the situation and the legal issue if 
needed. Do not ask more than three follow-up questions. Only ask follow-up questions if the user has not provided enough information.

Also, you are provided with a tool to retrieve legal references from a S3 Vectors knowledge base. Based on the legal issue, 
formulate a query to use this tool to retrieve relevant information from the knowledge base. Use the retrieved information to 
provide a detailed and comprehensive advice to the user.

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
        tools=[get_legal_references],
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
