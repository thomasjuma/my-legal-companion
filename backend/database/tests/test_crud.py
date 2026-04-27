import pytest
from sqlalchemy.orm import Session

from database.crud import CRUD, get_crud
from database.models import Consultation, ConsultationType, User


def test_get_crud_alias() -> None:
    assert get_crud(User) is not None
    assert get_crud(User).model is User


def test_crud_create_get_update_delete(db_session: Session) -> None:
    crud = CRUD(User)
    created = crud.create(
        db_session,
        clerk_user_id="c1",
        display_name="Alice",
    )
    assert created.id is not None
    got = crud.get(db_session, created.id)
    assert got is not None
    assert got.clerk_user_id == "c1"

    updated = crud.update(
        db_session, created.id, data={"display_name": "Alicia"}
    )
    assert updated is not None
    assert updated.display_name == "Alicia"
    assert crud.delete(db_session, created.id) is True
    assert crud.get(db_session, created.id) is None
    assert crud.delete(db_session, 999) is False


def test_get_by_get_many_count(db_session: Session) -> None:
    c = get_crud(User)
    c.create(
        db_session, clerk_user_id="x1", display_name="One"
    )
    c.create(
        db_session, clerk_user_id="x2", display_name="Two"
    )
    one = c.get_by(db_session, clerk_user_id="x1")
    assert one is not None and one.display_name == "One"
    with pytest.raises(ValueError):
        c.get_by(db_session)
    many = c.get_many(
        db_session, order_by="clerk_user_id", limit=1, offset=0
    )
    assert len(many) == 1
    assert c.count(db_session) == 2
    with pytest.raises(ValueError):
        c.get_many(db_session, not_a_column=1)


def test_create_with_enum(db_session: Session) -> None:
    cr = get_crud(Consultation)
    row = cr.create(
        db_session,
        consultation_type=ConsultationType.LEGAL,
        consultation_query="q",
        consultation_report="r",
        consultation_notes="n",
    )
    again = cr.get(db_session, row.id)
    assert again is not None
    t = again.consultation_type
    assert t == "legal" or t == ConsultationType.LEGAL


def test_get_wrong_tuple_key_length_raises(db_session: Session) -> None:
    c = get_crud(User)
    with pytest.raises(TypeError, match="primary key"):
        c.get(db_session, (1, 2))
