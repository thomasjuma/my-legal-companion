from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from clerk_auth import clerk_bearer
from database import get_crud, get_db
from database.models import Consultation

from schemas import ConsultationCreate, ConsultationRead

router = APIRouter(
    prefix="/api/consultations",
    tags=["consultations"],
    dependencies=[Depends(clerk_bearer)],
)
_consultation_crud = get_crud(Consultation)


@router.post(
    "",
    response_model=ConsultationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_consultation(
    body: ConsultationCreate,
    session: Session = Depends(get_db),
) -> Consultation:
    row = _consultation_crud.create(
        session,
        data=body.model_dump(),
    )
    session.commit()
    session.refresh(row)
    return row


@router.get("", response_model=list[ConsultationRead])
def list_consultations(
    session: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
) -> list[Consultation]:
    return _consultation_crud.get_many(
        session,
        offset=offset,
        limit=limit,
        order_by="created_at",
        descending=True,
    )
