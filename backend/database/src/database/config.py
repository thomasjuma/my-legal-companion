import os

from dotenv import load_dotenv

_configured: bool = False


def configure(override: bool = True) -> None:
    """
    Load environment variables from ``.env`` (if present). Call once from
    application startup before using the engine or :func:`get_database_url`.
    """
    load_dotenv(override=override)
    global _configured
    _configured = True


def get_database_url() -> str:
    """
    Return the SQLAlchemy database URL from the environment (``DATABASE_URL``).

    Loads from ``.env`` on the first use unless you already called
    :func:`configure`, which also loads the file.

    Set ``DATABASE_URL`` to a connection string, for example::

        postgresql+psycopg://user:pass@host:5432/dbname
        sqlite:///./local.db
    """
    global _configured
    if not _configured:
        load_dotenv(override=True)
        _configured = True

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it to a SQLAlchemy URL, e.g. "
            "postgresql+psycopg://user:pass@host:5432/dbname or sqlite:///./app.db"
        )
    return url
