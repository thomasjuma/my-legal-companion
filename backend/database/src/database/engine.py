import logging
import os
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from .config import get_database_url

_log = logging.getLogger(__name__)

_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """
    Return a process-wide (lazy) SQLAlchemy :class:`Engine`.

    The engine is configured with a small connection pool for network databases.
    For SQLite in-memory, ``StaticPool`` keeps a single shared connection so
    all sessions use the same database. File-based SQLite uses ``NullPool``.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = get_database_url()
    _log.info("Creating database engine for URL prefix: %s", url.split("://", 1)[0])
    if url.startswith("sqlite"):
        connect_args: dict = {"check_same_thread": False} if ":memory:" in url else {}
        if ":memory:" in url:
            # One shared connection so init_db and sessions see the same in-memory db
            pool = StaticPool
        else:
            pool = NullPool
        _engine = create_engine(
            url,
            connect_args=connect_args,
            poolclass=pool,
            future=True,
        )
    else:
        db_connect_timeout = int((os.environ.get("DB_CONNECT_TIMEOUT") or "8"))
        _engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_pre_ping=True,
            pool_size=int((os.environ.get("DB_POOL_SIZE") or "5")),
            max_overflow=int((os.environ.get("DB_POOL_MAX_OVERFLOW") or "10")),
            connect_args={"connect_timeout": db_connect_timeout},
            future=True,
        )

    @event.listens_for(_engine, "connect")
    def _enable_sqlite_fk_and_wal(  # type: ignore[no-untyped-def]
        dbapi_connection, _connection_record
    ) -> None:
        if not url.startswith("sqlite"):
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    _log.debug("Database engine created for URL prefix: %s…", url.split("://", 1)[0])
    return _engine


def dispose_engine() -> None:
    """
    Dispose of the process-wide engine (e.g. tests, graceful shutdown in workers).
    A new call to :func:`get_engine` will create a fresh engine.
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
    from .session import reset_session_factory

    reset_session_factory()
