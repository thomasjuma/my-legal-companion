from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_crud, get_db
from database.models import CaseReference, Consultation

from http_messages import HTTP_404
from schemas import CaseReferenceCreate, CaseReferenceRead

router = APIRouter(prefix="/case-references", tags=["case_references"])
_case_ref_crud = get_crud(CaseReference)
_consultation_crud = get_crud(Consultation)


@router.post(
    "",
    response_model=CaseReferenceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_case_reference(
    body: CaseReferenceCreate,
    session: Session = Depends(get_db),
) -> CaseReference:
    if body.consultation_id is not None:
        parent = _consultation_crud.get(session, body.consultation_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=HTTP_404
            )
    row = _case_ref_crud.create(session, data=body.model_dump())
    session.commit()
    session.refresh(row)
    return row


@router.get("", response_model=list[CaseReferenceRead])
def list_case_references(
    session: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
) -> list[CaseReference]:
    return _case_ref_crud.get_many(
        session,
        offset=offset,
        limit=limit,
        order_by="created_at",
        descending=True,
    )
