from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy.orm import Session, sessionmaker

from .engine import get_engine

_SessionLocal: Optional[sessionmaker[Session]] = None


def reset_session_factory() -> None:
    """
    Clear the cached :class:`sessionmaker` so the next access binds to a new
    :func:`database.engine.get_engine` (e.g. after :func:`database.engine.dispose_engine`).
    """
    global _SessionLocal
    _SessionLocal = None


def get_session_maker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            class_=Session,
            autoflush=False,
            autocommit=False,
            future=True,
        )
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Transactional scope: commit on success, rollback on error, then close the session.
    Use in scripts, CLI, or one-off service calls.
    """
    session = get_session_maker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yield a :class:`sqlalchemy.orm.Session` and close it when
    the request ends. Call ``commit()`` in the route (or a service) when
    persisting data.
    """
    session = get_session_maker()()
    try:
        yield session
    finally:
        session.close()
