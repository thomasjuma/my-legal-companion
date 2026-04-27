import os

import pytest

# Ensure tests never rely on a prior process env before `database` is imported.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def _sqlite_memory_per_test() -> None:
    """
    New in-memory SQLite for each test and cleanup after.

    The engine and session factory are cached globally; dispose between tests
    so each test sees a fresh :memory: database.
    """
    from database import dispose_engine

    dispose_engine()
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    yield
    dispose_engine()


@pytest.fixture
def db_session():
    """Init schema and yield a :class:`sqlalchemy.orm.Session` (closed in teardown)."""
    from database import get_session_maker, init_db

    init_db()
    session = get_session_maker()()
    try:
        yield session
    finally:
        session.close()
