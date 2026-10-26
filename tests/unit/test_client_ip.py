"""
Regressão: o IP da cota por IP não pode vir da parte forjável do X-Forwarded-For.

Antes, ``client_ip`` lia o primeiro item do header — o que o próprio cliente manda —
e bastava trocar o valor a cada tentativa para furar a cota de login/signup.
"""

from __future__ import annotations

from app.core import deps
from app.core.config import settings
from starlette.requests import Request


def _req(xff: str | None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": ("10.0.0.1", 1234)})


def test_client_ip_ignores_spoofed_leftmost_entry(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert deps.client_ip(_req("6.6.6.6, 203.0.113.7")) == "203.0.113.7"


def test_client_ip_counts_trusted_hops_from_the_right(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
    assert deps.client_ip(_req("6.6.6.6, 203.0.113.7, 35.191.0.1")) == "203.0.113.7"
    # Menos itens que o configurado: fica com o mais à esquerda disponível.
    assert deps.client_ip(_req("203.0.113.7")) == "203.0.113.7"


def test_client_ip_outside_production_uses_socket_peer(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert deps.client_ip(_req("6.6.6.6")) == "10.0.0.1"
