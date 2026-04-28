from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from database.models import ConsultationType


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=32_000)


class ChatRequest(BaseModel):
    """Chat turns in order (e.g. system, then user/assistant alternation)."""

    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        max_length=200,
    )
    max_turns: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Override agent run max turns (default from CHAT_MAX_TURNS or 5).",
    )


class ChatResponse(BaseModel):
    message: str
    model: str
    evaluation_feedback: str | None = None
    evaluation_score: float | None = None
    final_report_summary: str | None = None
    final_report: str | None = None


class ConsultationCreate(BaseModel):
    consultation_type: ConsultationType
    consultation_query: str
    consultation_report: str
    consultation_notes: str


class ConsultationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consultation_type: ConsultationType
    consultation_query: str
    consultation_report: str
    consultation_notes: str
    created_at: datetime


class CaseReferenceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=255)
    consultation_id: int | None = None


class CaseReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    consultation_id: int | None
    created_at: datetime
