"""
Teste de contrato: POST /api/v1/busca-semantica (US4 / T057).

Cobre (contracts/semantic-search.md):
- 200 com fontes rastreaveis; conteudo gerado marcado como NAO-oficial.
- 200 "sem resultados confiaveis" quando abaixo do limiar (nao inventa).
- 400 para query vazia/curta/longa (sanitizada).
- 503 quando a camada de IA esta indisponivel (AIUnavailableError).

As libs pesadas de IA NAO sao necessarias: `ai_service.responder` e sempre
mockado (monkeypatch), nunca chamado de verdade.
"""

from __future__ import annotations

import pytest
from app.models.search import AVISO_NAO_OFICIAL, BuscaSemanticaResponse, DocumentoFonte

URL = "/api/v1/busca-semantica"


def _canned_response() -> BuscaSemanticaResponse:
    return BuscaSemanticaResponse(
        resposta="Resposta gerada por IA (nao-oficial) sobre fracoes no 5o ano.",
        fontes=[
            DocumentoFonte(
                codigo="EF05MA03",
                tipo="habilidade",
                relevancia=0.91,
                titulo="Habilidade EF05MA03 - Matematica",
            )
        ],
        documentos_consultados=1,
        tempo_processamento=0.42,
        oficial=False,
        aviso=AVISO_NAO_OFICIAL,
    )


def _sem_resultados() -> BuscaSemanticaResponse:
    return BuscaSemanticaResponse(
        resposta=(
            "Nao encontrei correspondencia confiavel na BNCC. Nenhuma informacao " "foi inventada."
        ),
        fontes=[],
        documentos_consultados=0,
        tempo_processamento=0.05,
        oficial=False,
        aviso=AVISO_NAO_OFICIAL,
    )


@pytest.fixture
def _valid_payload():
    return {
        "query": "Quais habilidades tratam de fracoes no 5o ano?",
        "max_resultados": 5,
        "incluir_contexto": True,
    }


def test_busca_200_com_fontes(client, override_api_key_auth, monkeypatch, _valid_payload):
    async def fake_responder(query, max_resultados=5, incluir_contexto=True, vector_service=None):
        return _canned_response()

    monkeypatch.setattr("app.services.ai_service.responder", fake_responder)

    resp = client.post(URL, json=_valid_payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Fontes rastreaveis (SC-006): codigo + tipo + relevancia.
    assert body["fontes"], "esperava ao menos uma fonte"
    fonte = body["fontes"][0]
    assert fonte["codigo"] == "EF05MA03"
    assert fonte["tipo"] == "habilidade"
    assert 0.0 <= fonte["relevancia"] <= 1.0

    # Conteudo gerado CLARAMENTE marcado como nao-oficial (FR-016).
    assert body["oficial"] is False
    assert body["aviso"]
    assert body["documentos_consultados"] == 1
    assert "tempo_processamento" in body


def test_busca_sem_match_retorna_sem_resultados(
    client, override_api_key_auth, monkeypatch, _valid_payload
):
    async def fake_responder(query, max_resultados=5, incluir_contexto=True, vector_service=None):
        return _sem_resultados()

    monkeypatch.setattr("app.services.ai_service.responder", fake_responder)

    resp = client.post(URL, json=_valid_payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fontes"] == []
    assert body["oficial"] is False
    assert body["documentos_consultados"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "",  # vazia
        "ab",  # curta demais (<3)
        "a" * 501,  # longa demais (>500)
        "   ",  # apenas espacos -> sanitiza para vazia
    ],
)
def test_busca_query_invalida_400(client, override_api_key_auth, query):
    resp = client.post(URL, json={"query": query, "max_resultados": 5, "incluir_contexto": True})
    assert resp.status_code == 400, resp.text


def test_busca_ia_indisponivel_503(client, override_api_key_auth, monkeypatch, _valid_payload):
    async def raising(query, max_resultados=5, incluir_contexto=True, vector_service=None):
        from app.services.ai_service import AIUnavailableError

        raise AIUnavailableError("Camada de IA indisponivel para teste.")

    monkeypatch.setattr("app.services.ai_service.responder", raising)

    resp = client.post(URL, json=_valid_payload)
    assert resp.status_code == 503, resp.text
    body = resp.json()
    # Erro acionavel, sem stack trace (Principio VI).
    assert "detail" in body
    assert body["detail"]


def test_busca_sem_auth_401(client, monkeypatch, _valid_payload):
    # Sem override de auth: API key ausente -> 401 (independe da camada de IA).
    async def fake_responder(query, max_resultados=5, incluir_contexto=True, vector_service=None):
        return _canned_response()

    monkeypatch.setattr("app.services.ai_service.responder", fake_responder)

    resp = client.post(URL, json=_valid_payload)
    assert resp.status_code == 401, resp.text
