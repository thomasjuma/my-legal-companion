from __future__ import annotations

import json
import os
from urllib.parse import quote

from dotenv import load_dotenv

_configured: bool = False
_built_url_cache: str | None = None


def _database_url_from_aurora_env() -> str | None:
    """
    Build ``DATABASE_URL`` from ``AURORA_*`` and Secrets Manager when the
    process env has no ``DATABASE_URL`` (e.g. if a local ``.env`` overwrote
    it with an empty value before the override fix, or a platform quirk).
    """
    global _built_url_cache
    if _built_url_cache is not None:
        return _built_url_cache

    host = (os.environ.get("AURORA_CLUSTER_HOST") or "").strip()
    secret_arn = (os.environ.get("AURORA_SECRET_ARN") or "").strip()
    db_name = (os.environ.get("AURORA_DATABASE") or "").strip()
    if not (host and secret_arn and db_name):
        return None
    try:
        import boto3
    except ImportError:
        return None

    region = (os.environ.get("DEFAULT_AWS_REGION") or os.environ.get("AWS_REGION") or "").strip()
    client = (
        boto3.client("secretsmanager", region_name=region) if region else boto3.client("secretsmanager")
    )
    raw = client.get_secret_value(SecretId=secret_arn)
    creds = json.loads(raw["SecretString"])
    user = creds.get("username")
    password = creds.get("password")
    if not user or password is None:
        return None
    u = f"postgresql+psycopg://{quote(str(user), safe='')}:{quote(str(password), safe='')}"
    u = f"{u}@{host}:5432/{quote(str(db_name), safe='')}"
    _built_url_cache = u
    return u


def configure(override: bool = False) -> None:
    """
    Load environment variables from ``.env`` (if present). Call once from
    application startup before using the engine or :func:`get_database_url`.

    ``override`` defaults to ``False`` so variables already in the process
    environment (e.g. ``DATABASE_URL`` from App Runner or Docker) are never
    overwritten by a local ``.env`` (including an empty entry).
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
        load_dotenv(override=False)
        _configured = True

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        url = (_database_url_from_aurora_env() or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it to a SQLAlchemy URL, e.g. "
            "postgresql+psycopg://user:pass@host:5432/dbname or sqlite:///./app.db"
        )
    return url
