"""
Testes de contrato dos endpoints de Competências (T020, US1).
"""

from __future__ import annotations

import pytest
from app.main import app
from app.services.bncc_service import BNCCDataService

COMP_GERAIS = [
    {"numero": i, "titulo": f"Competência {i}", "descricao": f"Descrição {i}."}
    for i in range(1, 11)
]

TEST_DATA = {
    "metadata": {"versao": "v-test"},
    "competencias_gerais": COMP_GERAIS,
    "competencias_especificas": [
        {
            "codigo": "EFMAT01",
            "numero": 1,
            "area_conhecimento": "matematica",
            "componente": "matematica",
            "descricao": "Reconhecer a Matemática como ciência humana.",
            "etapa": "ensino_fundamental",
        },
        {
            "codigo": "EMLGG01",
            "numero": 1,
            "area_conhecimento": "linguagens",
            "componente": None,
            "descricao": "Compreender o funcionamento das linguagens.",
            "etapa": "ensino_medio",
        },
    ],
    "habilidades": [],
}


@pytest.fixture
def seeded(override_api_key_auth):
    from app.core.deps import get_bncc_service

    service = BNCCDataService(data=TEST_DATA)
    app.dependency_overrides[get_bncc_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_bncc_service, None)


# --------------------------------------------------------------------------- #
# /competencias/gerais
# --------------------------------------------------------------------------- #
def test_lista_competencias_gerais(client, seeded):
    resp = client.get("/api/v1/competencias/gerais")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 10
    assert [c["numero"] for c in body] == list(range(1, 11))


def test_competencia_geral_por_numero(client, seeded):
    resp = client.get("/api/v1/competencias/gerais/3")
    assert resp.status_code == 200
    assert resp.json()["numero"] == 3


def test_competencia_geral_fora_do_range_404(client, seeded):
    assert client.get("/api/v1/competencias/gerais/11").status_code == 404


# --------------------------------------------------------------------------- #
# /competencias/especificas
# --------------------------------------------------------------------------- #
def test_lista_competencias_especificas(client, seeded):
    resp = client.get("/api/v1/competencias/especificas")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_competencias_especificas_filtra_por_etapa(client, seeded):
    resp = client.get("/api/v1/competencias/especificas?etapa=ensino_medio")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["codigo"] == "EMLGG01"


def test_competencias_especificas_filtra_por_area(client, seeded):
    resp = client.get("/api/v1/competencias/especificas?area=matematica")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["codigo"] == "EFMAT01"


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def test_sem_api_key_retorna_401(client):
    assert client.get("/api/v1/competencias/gerais").status_code == 401
