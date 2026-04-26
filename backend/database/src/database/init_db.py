"""
Create or drop all tables for models registered on :class:`Base`.
"""


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


def drop_all_tables() -> None:
    """
    Drop all tables. Intended for test fixtures or controlled resets, not
    for production.
    """
    from . import models  # noqa: F401
    from .base import Base
    from .engine import get_engine

    Base.metadata.drop_all(bind=get_engine())
