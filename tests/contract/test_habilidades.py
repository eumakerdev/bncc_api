"""
Testes de contrato dos endpoints de Habilidades (T019, US1).

Auth por API key é sobreposta (`override_api_key_auth`) e o serviço de dados é
injetado com um snapshot determinístico em memória, para isolar o contrato da
qualidade da extração do PDF.
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
    "metadata": {"versao": "v-test", "data_publicacao": "2026-01-01"},
    "competencias_gerais": COMP_GERAIS,
    "competencias_especificas": [
        {
            "codigo": "EFMAT01",
            "numero": 1,
            "area_conhecimento": "matematica",
            "componente": "matematica",
            "descricao": "Competência específica de Matemática.",
            "etapa": "ensino_fundamental",
        }
    ],
    "objetos_conhecimento": [
        {
            "nome": "Frações",
            "unidade_tematica": "Números",
            "componente": "matematica",
            "etapa": "ensino_fundamental",
        }
    ],
    "unidades_tematicas": [
        {"nome": "Números", "componente": "matematica", "etapa": "ensino_fundamental"}
    ],
    "campos_experiencia": [],
    "habilidades": [
        {
            "codigo": "EF05MA07",
            "descricao": "Resolver e elaborar problemas de adição e subtração.",
            "etapa": "ensino_fundamental",
            "anos": ["5"],
            "area_conhecimento": "matematica",
            "componente": "matematica",
            "competencias_gerais": [1, 2],
            "competencias_especificas": ["EFMAT01"],
            "objetos_conhecimento": ["Frações"],
            "unidade_tematica": "Números",
        },
        {
            "codigo": "EF05MA08",
            "descricao": "Resolver problemas de multiplicação e divisão.",
            "etapa": "ensino_fundamental",
            "anos": ["5"],
            "area_conhecimento": "matematica",
            "componente": "matematica",
            "competencias_gerais": [1],
            "competencias_especificas": [],
            "objetos_conhecimento": [],
        },
        {
            "codigo": "EM13MAT101",
            "descricao": "Interpretar criticamente situações econômicas e sociais.",
            "etapa": "ensino_medio",
            "anos": ["1", "2", "3"],
            "area_conhecimento": "matematica",
            "componente": None,
            "competencias_gerais": [1, 3],
            "competencias_especificas": [],
            "objetos_conhecimento": [],
        },
        {
            "codigo": "EI03EO01",
            "descricao": "Demonstrar empatia pelos outros.",
            "etapa": "educacao_infantil",
            "anos": [],
            "area_conhecimento": "linguagens",
            "componente": None,
            "competencias_gerais": [],
            "competencias_especificas": [],
            "objetos_conhecimento": [],
            "campo_experiencia": "EO",
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
# GET /habilidades/{codigo}
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("codigo", ["EF05MA07", "EM13MAT101", "EI03EO01"])
def test_get_habilidade_por_codigo_cada_etapa(client, seeded, codigo):
    resp = client.get(f"/api/v1/habilidades/{codigo}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["codigo"] == codigo
    assert body["descricao"]
    assert "etapa" in body


def test_get_habilidade_codigo_lowercase_normalizado(client, seeded):
    resp = client.get("/api/v1/habilidades/ef05ma07")
    assert resp.status_code == 200
    assert resp.json()["codigo"] == "EF05MA07"


def test_get_habilidade_malformada_400(client, seeded):
    resp = client.get("/api/v1/habilidades/NAO-EXISTE")
    assert resp.status_code == 400
    assert "error_code" in resp.json()


def test_get_habilidade_valida_inexistente_404(client, seeded):
    resp = client.get("/api/v1/habilidades/EF99ZZ99")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# GET /habilidades (lista + filtros + paginação)
# --------------------------------------------------------------------------- #
def test_list_habilidades_paginada(client, seeded):
    resp = client.get("/api/v1/habilidades?page=1&size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert {"items", "total", "page", "size", "pages"}.issubset(body)
    assert body["total"] == 4
    assert body["pages"] == 2
    assert len(body["items"]) == 2


def test_list_habilidades_filtra_por_etapa(client, seeded):
    resp = client.get("/api/v1/habilidades?etapa=ensino_medio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["codigo"] == "EM13MAT101"


def test_list_habilidades_filtra_por_componente(client, seeded):
    resp = client.get("/api/v1/habilidades?etapa=ensino_fundamental&componente=matematica")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_list_habilidades_page_invalida_400(client, seeded):
    assert client.get("/api/v1/habilidades?page=0").status_code == 400


def test_list_habilidades_size_acima_do_maximo_400(client, seeded):
    assert client.get("/api/v1/habilidades?size=101").status_code == 400


# --------------------------------------------------------------------------- #
# GET /habilidades/{codigo}/relacoes
# --------------------------------------------------------------------------- #
def test_relacoes_resolve_competencias(client, seeded):
    resp = client.get("/api/v1/habilidades/EF05MA07/relacoes")
    assert resp.status_code == 200
    body = resp.json()
    nums = [c["numero"] for c in body["competencias_gerais"]]
    assert nums == [1, 2]
    cods = [c["codigo"] for c in body["competencias_especificas"]]
    assert cods == ["EFMAT01"]
    assert "Números" in body["unidades_tematicas"]


def test_relacoes_habilidade_inexistente_404(client, seeded):
    resp = client.get("/api/v1/habilidades/EF99ZZ99/relacoes")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Auth: sem override, sem key → 401
# --------------------------------------------------------------------------- #
def test_sem_api_key_retorna_401(client):
    resp = client.get("/api/v1/habilidades/EF05MA07")
    assert resp.status_code == 401
