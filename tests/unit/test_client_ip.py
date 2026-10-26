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


def test_client_ip_via_firebase_skips_the_google_proxy(monkeypatch):
    # Via Firebase Hosting o último item é o proxy do Google (muda a cada request);
    # o cliente é o anterior. Com o IP do proxy, clientes diferentes dividiam a cota.
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert deps.client_ip(_req("203.0.113.7, 192.178.11.137")) == "203.0.113.7"
    assert deps.client_ip(_req("6.6.6.6, 203.0.113.7, 74.125.210.165")) == "203.0.113.7"


def test_client_ip_via_firebase_skips_fastly_too(monkeypatch):
    # Se o Firebase Hosting repassar o IP da Fastly entre o cliente e o proxy do
    # Google, parar nele voltaria a dividir a cota por ponto de presença.
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert deps.client_ip(_req("203.0.113.7, 151.101.1.1, 74.125.210.165")) == "203.0.113.7"


def test_client_ip_spoofed_google_ip_on_the_left_is_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert deps.client_ip(_req("66.102.8.10, 203.0.113.7, 74.125.210.165")) == "203.0.113.7"


def test_client_ip_google_cloud_customer_is_a_client_not_a_proxy(monkeypatch):
    # Uma VM no GCP chamando o .run.app direto não pode escolher o próprio "IP".
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert deps.client_ip(_req("6.6.6.6, 34.95.0.1")) == "34.95.0.1"


def test_client_ip_only_google_hops_keeps_the_leftmost(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert deps.client_ip(_req("66.102.8.10")) == "66.102.8.10"
    assert deps.client_ip(_req("garbage, 74.125.210.165")) == "garbage"


def test_client_ip_outside_production_uses_socket_peer(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert deps.client_ip(_req("6.6.6.6")) == "10.0.0.1"
