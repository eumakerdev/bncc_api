"""
Headers de segurança e Content-Security-Policy (Princípio V).

Regressão da auditoria de produção de 2026-07-29 (achado 5): a CSP era publicada
em `Content-Security-Policy-Report-Only` e, sem `report-uri` configurado, os
relatórios não iam a lugar nenhum — na prática a política não oferecia proteção
alguma. Antes desta suíte **nenhum** teste cobria os headers de segurança, então a
regressão era invisível.
"""

from __future__ import annotations

import pytest
from app.core.config import settings

REQUIRED_DIRECTIVES = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
]


def test_csp_is_enforcing_by_default(client) -> None:
    """A política vai no header bloqueante, não no Report-Only."""
    headers = client.get("/api/v1/sistema/health").headers
    assert "content-security-policy" in headers
    assert "content-security-policy-report-only" not in headers


def test_csp_report_only_is_still_available_for_debugging(client, monkeypatch) -> None:
    """`CSP_ENFORCE=false` volta ao modo relatório — a escape hatch continua valendo."""
    monkeypatch.setattr(settings, "CSP_ENFORCE", False)
    headers = client.get("/api/v1/sistema/health").headers
    assert "content-security-policy-report-only" in headers
    assert "content-security-policy" not in headers


@pytest.mark.parametrize("directive", REQUIRED_DIRECTIVES)
def test_csp_covers_the_essential_directives(client, directive: str) -> None:
    policy = client.get("/api/v1/sistema/health").headers["content-security-policy"]
    assert directive in policy


@pytest.mark.parametrize("path", ["/", "/guia", "/docs", "/api/v1/sistema/health"])
def test_security_headers_on_every_surface(client, path: str) -> None:
    """Landing, docs e API carregam o mesmo conjunto mínimo de headers."""
    headers = client.get(path).headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "content-security-policy" in headers


def test_security_headers_reach_error_responses(client) -> None:
    """Os headers são registrados por fora: chegam mesmo quando a resposta é erro."""
    headers = client.get("/api/v1/rota-inexistente").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in headers


def test_hsts_only_in_production(client, monkeypatch) -> None:
    """HSTS só faz sentido onde a conexão real é HTTPS (produção atrás do Cloud Run)."""
    assert "strict-transport-security" not in client.get("/api/v1/sistema/health").headers

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    headers = client.get("/api/v1/sistema/health").headers
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
