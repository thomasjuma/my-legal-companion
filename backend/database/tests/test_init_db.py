from sqlalchemy import inspect as sa_inspect, text

from database import drop_all_tables, get_engine, get_session_maker, init_db


def test_init_db_creates_tables() -> None:
    init_db()
    engine = get_engine()
    insp = sa_inspect(engine)
    assert insp.has_table("users")
    assert insp.has_table("consultations")
    session = get_session_maker()()
    try:
        session.execute(text("select 1 from users limit 1"))
    finally:
        session.close()


def test_drop_all_removes_tables() -> None:
    init_db()
    drop_all_tables()
    engine = get_engine()
    insp = sa_inspect(engine)
    assert not insp.has_table("users")
    assert not insp.has_table("consultations")
