"""
Testes de contrato do Complemento de Computação à BNCC.

Cobre a superfície nova adicionada pela feature de Computação: a habilidade `CO`
serializa os campos `eixo`, `area_conhecimento`/`componente` = "computacao"; o
filtro `eixo` em `GET /habilidades`; e a filtragem por `componente=computacao`.

A auth por API key é sobreposta (`override_api_key_auth`) e o serviço de dados é
injetado com um snapshot determinístico em memória (isola o contrato da extração
do PDF).
"""

from __future__ import annotations

import pytest
from app.main import app
from app.services.bncc_service import BNCCDataService

COMP_GERAIS = [
    {"numero": i, "titulo": f"Competência {i}", "descricao": f"Descrição {i}."}
    for i in range(1, 11)
]


def _hab(codigo, etapa, eixo, anos, desc="Descrição de habilidade de Computação."):
    return {
        "codigo": codigo,
        "descricao": desc,
        "etapa": etapa,
        "anos": anos,
        "area_conhecimento": "computacao",
        "componente": "computacao",
        "competencias_gerais": [],
        "competencias_especificas": [],
        "objetos_conhecimento": [],
        "eixo": eixo,
    }


TEST_DATA = {
    "metadata": {"versao": "v-test", "data_publicacao": "2026-01-01"},
    "competencias_gerais": COMP_GERAIS,
    "competencias_especificas": [],
    "objetos_conhecimento": [],
    "unidades_tematicas": [],
    "campos_experiencia": [],
    "habilidades": [
        _hab("EI03CO01", "educacao_infantil", "pensamento_computacional", ["03"]),
        _hab("EF01CO04", "ensino_fundamental", "mundo_digital", ["1"]),
        _hab("EF06CO09", "ensino_fundamental", "cultura_digital", ["6"]),
        _hab("EM13CO01", "ensino_medio", None, ["1", "2", "3"]),
        # Uma habilidade regular (não-Computação), para garantir isolamento do filtro.
        {
            "codigo": "EF05MA07",
            "descricao": "Resolver e elaborar problemas de adição e subtração.",
            "etapa": "ensino_fundamental",
            "anos": ["5"],
            "area_conhecimento": "matematica",
            "componente": "matematica",
            "competencias_gerais": [],
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
# GET /habilidades/{codigo} — serialização dos campos de Computação
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "codigo,eixo",
    [
        ("EI03CO01", "pensamento_computacional"),
        ("EF01CO04", "mundo_digital"),
        ("EF06CO09", "cultura_digital"),
    ],
)
def test_habilidade_computacao_expoe_eixo(client, seeded, codigo, eixo):
    resp = client.get(f"/api/v1/habilidades/{codigo}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["codigo"] == codigo
    assert body["eixo"] == eixo
    assert body["area_conhecimento"] == "computacao"
    assert body["componente"] == "computacao"


def test_habilidade_computacao_em_sem_eixo(client, seeded):
    body = client.get("/api/v1/habilidades/EM13CO01").json()
    assert body["eixo"] is None
    assert body["area_conhecimento"] == "computacao"


# --------------------------------------------------------------------------- #
# GET /habilidades?eixo=...  (filtro novo)
# --------------------------------------------------------------------------- #
def test_filtra_por_eixo(client, seeded):
    resp = client.get("/api/v1/habilidades?eixo=mundo_digital")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["codigo"] == "EF01CO04"


def test_filtra_por_eixo_combinado_com_etapa(client, seeded):
    resp = client.get("/api/v1/habilidades?etapa=ensino_fundamental&eixo=cultura_digital")
    assert resp.status_code == 200
    body = resp.json()
    assert [i["codigo"] for i in body["items"]] == ["EF06CO09"]


def test_eixo_invalido_retorna_400(client, seeded):
    # A app converte erros de validação de query em 400 (ver test_habilidades).
    resp = client.get("/api/v1/habilidades?eixo=inexistente")
    assert resp.status_code == 400


def test_filtra_por_componente_computacao(client, seeded):
    resp = client.get("/api/v1/habilidades?componente=computacao")
    assert resp.status_code == 200
    codigos = {i["codigo"] for i in resp.json()["items"]}
    assert codigos == {"EI03CO01", "EF01CO04", "EF06CO09", "EM13CO01"}
    assert "EF05MA07" not in codigos  # habilidade regular não vaza no filtro
