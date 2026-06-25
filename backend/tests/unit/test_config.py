"""Config tests (CLAUDE.md §10 — Config DoD).

Asserts: production rejects placeholder/missing secrets; DATABASE_URL is built
from parts; CORS parsing; get_settings() is cached. Settings are exercised
through the real ingress — process environment — via monkeypatch, with
``_env_file=None`` so a developer's local ``.env`` never leaks in.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings, get_settings

_REAL_SECRET = "a" * 64

# Env keys we manage so each test starts from a known, isolated baseline.
_MANAGED = [
    "APP_ENV",
    "JWT_SECRET_KEY",
    "AUDIT_HMAC_KEY",
    "POSTGRES_PASSWORD",
    "POSTGRES_USER",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "DATABASE_URL",
    "CORS_ORIGINS",
    "ALLOWED_FILE_TYPES",
    "AUDIT_CHAIN_GENESIS_HASH",
]


@pytest.fixture
def prod_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid production baseline with real secrets; tests override one key."""
    for key in _MANAGED:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", _REAL_SECRET)
    monkeypatch.setenv("AUDIT_HMAC_KEY", _REAL_SECRET)
    monkeypatch.setenv("POSTGRES_PASSWORD", "real-strong-password")


def _settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_placeholder_jwt_secret(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_64_CHAR_RANDOM_HEX")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        _settings()


def test_production_rejects_placeholder_audit_key(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIT_HMAC_KEY", "CHANGE_ME_64_CHAR_RANDOM_HEX")
    with pytest.raises(ValueError, match="AUDIT_HMAC_KEY"):
        _settings()


def test_production_rejects_placeholder_postgres_password(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "CHANGE_ME_STRONG_PASSWORD")
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        _settings()


def test_production_rejects_blank_secret(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "   ")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        _settings()


def test_development_allows_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-production must boot with defaults so local dev is frictionless.
    for key in _MANAGED:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    settings = _settings()
    assert settings.app_env == "development"
    # DATABASE_URL is still built from the default parts.
    assert settings.database_url is not None


def test_database_url_built_from_parts(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_USER", "aegis_app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "aegis")
    settings = _settings()
    assert settings.database_url == "postgresql+asyncpg://aegis_app:pw@db:6543/aegis"


def test_explicit_database_url_preserved(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://u:p@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", url)
    assert _settings().database_url == url


def test_production_rejects_placeholder_in_database_url(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:CHANGE_ME_STRONG_PASSWORD@host:5432/db",
    )
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _settings()


def test_cors_origins_parsed_to_list(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test ,")
    assert _settings().cors_origins_list == ["http://a.test", "http://b.test"]


def test_allowed_file_types_parsed_to_list(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_FILE_TYPES", "PDF, DOCX ,txt")
    assert _settings().allowed_file_types_list == ["pdf", "docx", "txt"]


def test_genesis_hash_must_be_64_hex(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_CHAIN_GENESIS_HASH", "nothex")
    with pytest.raises(ValueError, match="AUDIT_CHAIN_GENESIS_HASH"):
        _settings()


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _MANAGED:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
