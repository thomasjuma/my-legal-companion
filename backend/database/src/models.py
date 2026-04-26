"""
Define SQLAlchemy ORM models by subclassing :class:`database.base.Base`.
Import this module (or a package that re-exports your models) before
:func:`database.init_db` so that :attr:`Base.metadata` is fully populated.
"""


from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum
from .base import Base

from typing import List

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clerk_user_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class DocumentReference(Base):
    __tablename__ = "document_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class CaseReference(Base):
    __tablename__ = "case_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class ConsultationType(str, Enum):
    LEGAL = "legal"
    FINANCIAL = "financial"
    CORPORATE = "Corporate & Business Services"
    EMPLOYMENT = "Employment & Human Resources"
    REGULATORY = "Regulatory & Compliance"
    REAL_ESTATE = "Real Estate & Property"
    INDIVIDUALS = "Individuals & Personal Matters"

class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    consultation_type: Mapped[ConsultationType] = mapped_column(String(255))
    consultation_query: Mapped[str] = mapped_column(Text)
    consultation_report: Mapped[str] = mapped_column(Text)
    consultation_notes: Mapped[str] = mapped_column(Text)
    document_references: Mapped[List[DocumentReference]] = relationship("DocumentReference", back_populates="consultation")
    case_references: Mapped[List[CaseReference]] = relationship("CaseReference", back_populates="consultation")
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )