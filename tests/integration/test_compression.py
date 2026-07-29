"""
Compressão das respostas (Padrões Técnicos — desempenho e custo).

Regressão da auditoria de produção de 2026-07-29 (achado 3): nenhuma resposta
trazia `Content-Encoding`, mesmo com `Accept-Encoding: gzip, br` explícito.
`/api/v1/taxonomia` trafegava 67 KB (~440ms só de transferência) e a landing
51 KB. A Fastly já anunciava `vary: accept-encoding`, mas a origem nunca
comprimia — então o CDN não tinha variante comprimida para servir, e o egress do
Cloud Run é faturado por byte.
"""

from __future__ import annotations

GZIP = {"Accept-Encoding": "gzip"}


def test_taxonomia_is_compressed(client, override_api_key_auth) -> None:
    """O maior payload determinístico da API viaja comprimido."""
    response = client.get("/api/v1/taxonomia", headers=GZIP)
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    # O httpx descomprime de forma transparente: o corpo decodificado é o JSON real.
    assert len(response.content) > 1000
    assert response.json()["etapas"]


def test_landing_is_compressed(client) -> None:
    """A landing SSR (servida pela CDN do Firebase) também comprime."""
    response = client.get("/", headers=GZIP)
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"


def test_vary_advertises_accept_encoding(client, override_api_key_auth) -> None:
    """Sem `Vary: Accept-Encoding` a CDN serviria a variante errada a quem não aceita gzip."""
    response = client.get("/api/v1/taxonomia", headers=GZIP)
    assert "accept-encoding" in response.headers["vary"].lower()


def test_small_responses_are_not_compressed(client) -> None:
    """Abaixo de `minimum_size` o overhead do gzip não compensa."""
    response = client.get("/api/v1/sistema/health", headers=GZIP)
    assert response.status_code == 200
    assert len(response.content) < 1000
    assert "content-encoding" not in response.headers


def test_client_without_gzip_gets_plain_response(client, override_api_key_auth) -> None:
    """Quem não anuncia gzip continua recebendo o corpo sem codificação."""
    response = client.get("/api/v1/taxonomia", headers={"Accept-Encoding": "identity"})
    assert response.status_code == 200
    assert "content-encoding" not in response.headers
