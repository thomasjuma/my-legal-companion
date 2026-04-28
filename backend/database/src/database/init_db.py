"""
Create or drop all tables for models registered on :class:`Base`.
"""

from sqlalchemy import inspect, text


def _ensure_consultation_clerk_column() -> None:
    """
    Backfill schema for environments created before ``clerk_user_id`` was added.
    ``create_all`` does not alter existing tables, so this keeps older DBs usable.
    """
    from .engine import get_engine

    engine = get_engine()
    inspector = inspect(engine)
    if "consultations" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("consultations")}
    with engine.begin() as conn:
        if "clerk_user_id" not in columns:
            conn.execute(
                text("ALTER TABLE consultations ADD COLUMN clerk_user_id VARCHAR(255)")
            )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_consultations_clerk_user_id "
                "ON consultations (clerk_user_id)"
            )
        )


def init_db() -> None:
    """
    Create all tables for models that inherit from :class:`database.base.Base`
    and are imported in :mod:`database.models` (or define models in
    :mod:`database.models` and import that module from here as needed).
    """
    from . import models  # noqa: F401
    from .base import Base
    from .engine import get_engine

    Base.metadata.create_all(bind=get_engine())
    _ensure_consultation_clerk_column()


def drop_all_tables() -> None:
    """
    Drop all tables. Intended for test fixtures or controlled resets, not
    for production.
    """
    from . import models  # noqa: F401
    from .base import Base
    from .engine import get_engine

    Base.metadata.drop_all(bind=get_engine())
