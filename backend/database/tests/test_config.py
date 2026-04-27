import pytest


def test_get_database_url_uses_env(monkeypatch) -> None:
    from database import config

    # ``load_dotenv(override=True)`` would clobber a test value with a project .env.
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:custom")
    from database import get_database_url

    assert get_database_url() == "sqlite:///:memory:custom"


def test_get_database_url_empty_raises(monkeypatch) -> None:
    from database import config

    # Avoid the project .env re-populating DATABASE_URL during the first call.
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None, raising=True)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from database import get_database_url

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_database_url()


def test_configure_loads_no_crash() -> None:
    from database import configure

    configure(override=True)
