from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from database.models import ConsultationType


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
