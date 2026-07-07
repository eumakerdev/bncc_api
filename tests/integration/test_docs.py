"""
Teste de integração de sincronia da documentação (US3 — T052).

Verifica que o OpenAPI segue sendo a fonte da verdade (Princípio I/FR-013),
que a referência interativa (/docs, renderizada pelo Scalar) responde a partir
do bundle self-hosted (Princípio V — sem CDN) e que o guia estilizado (/guia)
renderiza mencionando autenticação por API key. Não assumimos a contagem exata
de endpoints (outras histórias podem estar em desenvolvimento em paralelo) —
apenas que o contrato OpenAPI existe e não está vazio.
"""

from __future__ import annotations


def test_openapi_json_exposes_paths(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    assert "paths" in payload
    assert isinstance(payload["paths"], dict)
    assert len(payload["paths"]) > 0


def test_api_reference_rendered_by_scalar(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    body = response.text
    # Referência viva apontando para o contrato OpenAPI...
    assert "/api/v1/openapi.json" in body
    # ...renderizada pelo Scalar a partir do bundle self-hosted (sem CDN — Princípio V).
    assert "/static/vendor/scalar.standalone.js" in body
    # Sem CDN externo: nada de unpkg/jsdelivr/cdn.* (o canonical pode usar http:// em
    # dev, então checamos a ausência de hosts de CDN, não a de "http://" em geral).
    lowered = body.lower()
    assert "cdn." not in lowered
    assert "unpkg" not in lowered
    assert "jsdelivr" not in lowered
    assert "https://cdn" not in lowered


def test_api_reference_version_switcher_lists_v1(client):
    """A referência mais recente traz o seletor de versão listando v1."""
    response = client.get("/docs")
    assert response.status_code == 200

    body = response.text
    assert 'id="version-switcher"' in body
    assert "<select" in body
    # A opção da versão atual (v1) aparece marcada como atual.
    assert "v1" in body
    assert "(atual)" in body


def test_docs_versioned_slug_renders(client):
    """/docs/v1 renderiza a referência da versão v1."""
    response = client.get("/docs/v1")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    body = response.text
    assert "/api/v1/openapi.json" in body
    assert "/static/vendor/scalar.standalone.js" in body


def test_docs_unknown_version_returns_404(client):
    """Uma versão de docs desconhecida responde 404."""
    response = client.get("/docs/v999")
    assert response.status_code == 404


def test_docs_invalid_release_falls_back_to_live(client):
    """?release= não arquivada cai para o OpenAPI vivo, sem quebrar."""
    response = client.get("/docs/v1?release=0.0.0-inexistente")
    assert response.status_code == 200

    body = response.text
    # data-url do Scalar aponta para o contrato vivo, não para um snapshot congelado.
    assert 'data-url="/api/v1/openapi.json"' in body
    assert "/releases/0.0.0-inexistente/" not in body


def test_api_versions_manifest(client):
    """O manifesto /api/versions expõe a versão mais recente."""
    response = client.get("/api/versions")
    assert response.status_code == 200

    payload = response.json()
    assert payload["latest"] == "v1"
    slugs = [v["slug"] for v in payload["versions"]]
    assert "v1" in slugs


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
