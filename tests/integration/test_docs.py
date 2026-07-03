"""
Teste de integração de sincronia da documentação (US3 — T052).

Verifica que o OpenAPI segue sendo a fonte da verdade (Princípio I/FR-013),
que o Swagger UI embutido do FastAPI (/docs) responde e que o guia estilizado
(/guia) renderiza mencionando autenticação por API key. Não assumimos a
contagem exata de endpoints (outras histórias podem estar em desenvolvimento
em paralelo) — apenas que o contrato OpenAPI existe e não está vazio.
"""

from __future__ import annotations


def test_openapi_json_exposes_paths(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    assert "paths" in payload
    assert isinstance(payload["paths"], dict)
    assert len(payload["paths"]) > 0


def test_swagger_ui_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_docs_guide_page_renders_and_mentions_api_key_auth(client):
    response = client.get("/guia")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    body = response.text
    assert "API key" in body
    assert "Authorization" in body
    assert "/api/v1/openapi.json" in body
    # Deve linkar a documentação real gerada pelo FastAPI, sem sobrescrever /docs.
    assert 'href="/docs"' in body
    assert 'href="/redoc"' in body
