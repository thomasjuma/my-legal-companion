from __future__ import annotations

import pytest
from sqlalchemy import text


def test_get_engine_creates_and_dispose_rebuilds() -> None:
    from database import dispose_engine, get_engine, get_database_url

    e1 = get_engine()
    assert e1 is get_engine()
    dispose_engine()
    e2 = get_engine()
    assert e1 is not e2
    u = get_database_url()
    assert u.startswith("sqlite:///")


def test_session_scope_commits() -> None:
    from database import init_db, session_scope
    from database.models import User
    from database.crud import get_crud

    init_db()
    user_crud = get_crud(User)
    with session_scope() as session:
        user_crud.create(
            session,
            clerk_user_id="u1",
            display_name="A",
        )
    with session_scope() as read:
        u = read.execute(text("select count(*) from users")).scalar_one()
        assert int(u) == 1


def test_session_scope_rolls_back_on_error() -> None:
    from database import init_db, session_scope
    from database.models import User
    from database.crud import get_crud

    init_db()
    user_crud = get_crud(User)
    with pytest.raises(RuntimeError, match="boom"):
        with session_scope() as session:
            user_crud.create(
                session,
                clerk_user_id="u-rollback",
                display_name="B",
            )
            raise RuntimeError("boom")
    with session_scope() as read:
        c = read.execute(
            text("select count(*) from users where clerk_user_id = 'u-rollback'")
        ).scalar_one()
        assert int(c) == 0


def test_get_db_rolls_back_and_closes() -> None:
    from database import get_db, init_db, session_scope
    from database.models import User
    from database.crud import get_crud

    init_db()
    user_crud = get_crud(User)
    g = get_db()
    s = next(g)
    user_crud.create(s, clerk_user_id="dep", display_name="D")
    with pytest.raises(ValueError, match="fail"):
        g.throw(ValueError("fail"))
    with session_scope() as read:
        c = read.execute(
            text("select count(*) from users where clerk_user_id = 'dep'")
        ).scalar_one()
        assert int(c) == 0
