"""
Regressão de configuração insegura (FR-023 / SC-010).

A aplicação NÃO pode subir em produção com SECRET_KEY placeholder/ausente ou
ALLOWED_HOSTS contendo "*". Fora de produção, defaults permissivos são tolerados.
"""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def _make(**overrides):
    base = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "x" * 48,
        "ALLOWED_HOSTS": ["https://bncc.example.com"],
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_production_rejects_placeholder_secret():
    with pytest.raises(ValidationError):
        _make(SECRET_KEY="change-me-dev-only-not-for-production")


def test_production_rejects_empty_secret():
    with pytest.raises(ValidationError):
        _make(SECRET_KEY="")


def test_production_rejects_weak_short_secret():
    with pytest.raises(ValidationError):
        _make(SECRET_KEY="short")


def test_production_rejects_wildcard_allowed_hosts():
    with pytest.raises(ValidationError):
        _make(ALLOWED_HOSTS=["*"])


def test_production_accepts_strong_config():
    settings = _make()
    assert settings.is_production
    assert "*" not in settings.ALLOWED_HOSTS


def test_development_tolerates_permissive_defaults():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        SECRET_KEY="change-me-dev-only-not-for-production",
        ALLOWED_HOSTS=["*"],
    )
    assert not settings.is_production


def test_db_password_injected_into_url_placeholder():
    """A senha (secret) substitui o placeholder — nunca em texto plano no env."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:__DB_PASSWORD__@/db?host=/cloudsql/x",
        DB_PASSWORD="s3nh@/forte",
    )
    assert "__DB_PASSWORD__" not in settings.DATABASE_URL
    # caracteres especiais são url-encoded (/ e @ não quebram a URL)
    assert "s3nh%40%2Fforte" in settings.DATABASE_URL


def test_db_password_absent_leaves_url_untouched():
    url = "sqlite+aiosqlite:///./data/platform.db"
    settings = Settings(_env_file=None, DATABASE_URL=url)
    assert settings.DATABASE_URL == url
