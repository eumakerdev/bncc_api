"""
Testes de contrato de Taxonomia e Sistema/versão-dados (T021, US1).
"""

from __future__ import annotations

import pytest
from app.main import app
from app.services.bncc_service import BNCCDataService

TEST_DATA = {
    "metadata": {
        "versao": "v1",
        "data_publicacao": "2026-01-01",
        "checksum_fontes": {"ensino_fundamental": "abc123"},
        "missing_sources": ["educacao_infantil"],
    },
    "competencias_gerais": [
        {"numero": i, "titulo": f"C{i}", "descricao": f"D{i}."} for i in range(1, 11)
    ],
    "competencias_especificas": [],
    "objetos_conhecimento": [
        {
            "nome": "Frações",
            "unidade_tematica": "Números",
            "componente": "matematica",
            "etapa": "ensino_fundamental",
        }
    ],
    "campos_experiencia": [
        {"codigo": "EO", "nome": "O eu, o outro e o nós", "objetivos_aprendizagem": []}
    ],
    "habilidades": [
        {
            "codigo": "EF05MA07",
            "descricao": "Resolver problemas.",
            "etapa": "ensino_fundamental",
            "anos": ["5"],
            "area_conhecimento": "matematica",
            "componente": "matematica",
            "competencias_gerais": [1],
            "competencias_especificas": [],
            "objetos_conhecimento": ["Frações"],
            "unidade_tematica": "Números",
        },
        {
            "codigo": "EM13MAT101",
            "descricao": "Interpretar situações.",
            "etapa": "ensino_medio",
            "anos": ["1", "2", "3"],
            "area_conhecimento": "matematica",
            "componente": None,
            "competencias_gerais": [1],
            "competencias_especificas": [],
            "objetos_conhecimento": [],
        },
    ],
}


@pytest.fixture
def seeded(override_api_key_auth):
    from app.core.deps import get_bncc_service

    service = BNCCDataService(data=TEST_DATA)
    app.dependency_overrides[get_bncc_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_bncc_service, None)


# --------------------------------------------------------------------------- #
# /taxonomia
# --------------------------------------------------------------------------- #
def test_taxonomia_arvore(client, seeded):
    resp = client.get("/api/v1/taxonomia")
    assert resp.status_code == 200
    body = resp.json()
    assert "etapas" in body
    assert "ensino_fundamental" in body["etapas"]
    assert "ensino_medio" in body["etapas"]
    assert "campos_experiencia" in body


def test_taxonomia_navegavel_ate_objetos(client, seeded):
    body = client.get("/api/v1/taxonomia").json()
    ef = body["etapas"]["ensino_fundamental"]["areas"]["matematica"]["componentes"]
    ut = ef["matematica"]["unidades_tematicas"]
    assert "Números" in ut
    assert "Frações" in ut["Números"]["objetos"]


def test_taxonomia_sem_api_key_401(client):
    assert client.get("/api/v1/taxonomia").status_code == 401


# --------------------------------------------------------------------------- #
# /sistema/versao-dados
# --------------------------------------------------------------------------- #
def test_versao_dados(client, seeded):
    resp = client.get("/api/v1/sistema/versao-dados")
    assert resp.status_code == 200
    body = resp.json()
    assert body["versao"] == "v1"
    assert body["contagens"]["por_etapa"]["ensino_fundamental"] == 1
    assert body["contagens"]["por_etapa"]["ensino_medio"] == 1
    assert body["missing_sources"] == ["educacao_infantil"]


def test_versao_dados_sem_api_key_401(client):
    assert client.get("/api/v1/sistema/versao-dados").status_code == 401


# --------------------------------------------------------------------------- #
# /sistema/health e /sistema/readiness (públicos)
# --------------------------------------------------------------------------- #
def test_health_publico(client):
    resp = client.get("/api/v1/sistema/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readiness_publico(client):
    resp = client.get("/api/v1/sistema/readiness")
    assert resp.status_code == 200
    assert "components" in resp.json()
