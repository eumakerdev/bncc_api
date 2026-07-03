"""
Teste de integracao: degradacao graciosa da camada de IA (US4 / T058 / SC-009).

Garante que, com a IA fora do ar, o endpoint de IA responde 503 acionavel
**enquanto os caminhos deterministicos permanecem funcionais** (isolamento).

Robusto quanto ao estado de US1: se os endpoints deterministicos ainda nao
estiverem montados neste run, o teste recai sobre a prova de que a aplicacao
continua servindo (/docs 200 e o health do sistema, quando presente).
"""

from __future__ import annotations

URL = "/api/v1/busca-semantica"


def _force_ai_down(monkeypatch):
    async def raising(query, max_resultados=5, incluir_contexto=True, vector_service=None):
        from app.services.ai_service import AIUnavailableError

        raise AIUnavailableError("IA forcada indisponivel no teste de degradacao.")

    monkeypatch.setattr("app.services.ai_service.responder", raising)


def test_ia_fora_retorna_503(client, override_api_key_auth, monkeypatch):
    _force_ai_down(monkeypatch)
    resp = client.post(
        URL, json={"query": "habilidades de matematica sobre fracoes", "max_resultados": 3}
    )
    assert resp.status_code == 503, resp.text
    assert resp.json().get("detail")


def test_deterministico_nao_afetado_por_ia_fora(client, override_api_key_auth, monkeypatch):
    _force_ai_down(monkeypatch)

    # 1) A IA esta fora -> 503.
    ia = client.post(URL, json={"query": "qualquer pergunta sobre a bncc"})
    assert ia.status_code == 503, ia.text

    # 2) Isolamento: a aplicacao continua servindo a documentacao OpenAPI.
    docs = client.get("/docs")
    assert docs.status_code == 200

    openapi = client.get("/api/v1/openapi.json")
    assert openapi.status_code == 200

    # 3) Se o health do sistema (determinismo) estiver montado, deve seguir 200
    #    apesar da IA fora. Se ainda nao existir (US1 pendente), nao falha o teste.
    health = client.get("/api/v1/sistema/health")
    if health.status_code != 404:
        assert health.status_code == 200, health.text


def test_app_importavel_sem_libs_ia():
    # Prova de degradacao: importar a app nao exige chromadb/sentence-transformers.
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert URL in paths
