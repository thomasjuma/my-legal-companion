"""
SQLAlchemy database layer for the Legal Companion backend.

- Configure ``DATABASE_URL`` in the environment (optionally from ``.env``;
  :func:`configure` calls :func:`dotenv.load_dotenv`).

- Use :class:`Base` to declare models in :mod:`database.models` or a sibling
  module that registers tables on the same :attr:`Base.metadata` object.

- Use :func:`get_db` with FastAPI ``Depends`` or :func:`session_scope` in
  scripts and services.

Example (FastAPI)::

    from database import configure, get_db, init_db

    configure()
    @app.on_event("startup")
    def _on_startup() -> None:
        init_db()

    @app.get("/items")
    def list_items(session: Session = Depends(get_db)):
        ...
"""

from .base import Base
from .config import configure, get_database_url
from .crud import CRUD, get_crud
from .engine import dispose_engine, get_engine
from .session import get_db, get_session_maker, session_scope, reset_session_factory
from .init_db import init_db, drop_all_tables

__all__ = [
    "Base",
    "CRUD",
    "configure",
    "get_database_url",
    "get_engine",
    "dispose_engine",
    "get_db",
    "get_crud",
    "get_session_maker",
    "reset_session_factory",
    "session_scope",
    "init_db",
    "drop_all_tables",
]
