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
