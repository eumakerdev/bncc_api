"""
Regressão das relações navegáveis no snapshot versionado (FR-005, Princípio IV).

Guarda contra a regressão em que `competencias_especificas`, `unidades_tematicas`,
`objetos_conhecimento` e `campos_experiencia` voltavam sempre `[]`/`{}` (extração
guardava só a coluna HABILIDADES). Roda contra o `data/bncc_v1.json` COMMITADO —
não precisa dos PDFs.
"""

from __future__ import annotations

import asyncio

import pytest
from app.services.bncc_service import BNCCDataService

# Serviço carregando o snapshot real versionado (singleton de módulo evitado de
# propósito: instanciar direto lê `settings.BNCC_DATA_PATH`).
svc = BNCCDataService()


def test_colecoes_de_relacao_nao_vazias():
    data = svc.data
    assert data["competencias_especificas"], "catálogo de competências específicas vazio"
    assert data["unidades_tematicas"], "unidades temáticas vazias"
    assert data["objetos_conhecimento"], "objetos de conhecimento vazios"
    assert data["campos_experiencia"], "campos de experiência vazios"


def test_integridade_referencial_objetos_e_competencias():
    data = svc.data
    objeto_nomes = {o["nome"] for o in data["objetos_conhecimento"]}
    comp_codes = {str(c["codigo"]).upper() for c in data["competencias_especificas"]}
    for h in data["habilidades"]:
        for nome in h.get("objetos_conhecimento") or []:
            assert nome in objeto_nomes, f"{h['codigo']}: objeto órfão {nome!r}"
        for cod in h.get("competencias_especificas") or []:
            assert str(cod).upper() in comp_codes, f"{h['codigo']}: competência órfã {cod!r}"


def test_taxonomia_desce_ate_unidade_tematica_e_objetos():
    body = asyncio.run(svc.get_taxonomia())
    ef = body["etapas"]["ensino_fundamental"]["areas"]
    mat = ef["matematica"]["componentes"]["matematica"]["unidades_tematicas"]
    assert "Números" in mat
    assert mat["Números"]["objetos"], "unidade temática sem objetos"
    assert len(body["campos_experiencia"]) == 5


def test_habilidade_ef_tem_unidade_tematica_e_objeto():
    hab = asyncio.run(svc.get_habilidade_by_codigo("EF01MA01"))
    assert hab is not None
    assert hab.unidade_tematica == "Números"
    assert hab.objetos_conhecimento


def test_competencia_especifica_em_derivada_por_codigo():
    rel = asyncio.run(svc.get_relacoes("EM13CHS101"))
    assert rel is not None
    codigos = [c["codigo"] for c in rel["competencias_especificas"]]
    assert "EMCHS01" in codigos


@pytest.mark.parametrize(
    "area_tag,esperado",
    [("EMLGG", 7), ("EMMAT", 5), ("EMCNT", 3), ("EMCHS", 6)],
)
def test_contagem_competencias_especificas_em_por_area(area_tag: str, esperado: int):
    data = svc.data
    n = sum(1 for c in data["competencias_especificas"] if c["codigo"].startswith(area_tag))
    assert n == esperado


@pytest.mark.parametrize("componente", ["lingua_portuguesa", "lingua_inglesa"])
def test_lp_li_tem_organizador_na_unidade_tematica(componente: str):
    """Língua Portuguesa (práticas) e Língua Inglesa (eixos) preenchem unidade_tematica."""
    ef = [
        h
        for h in svc.data["habilidades"]
        if h["etapa"] == "ensino_fundamental" and h.get("componente") == componente
    ]
    assert ef, f"sem habilidades de {componente}"
    com_ut = [h for h in ef if h.get("unidade_tematica")]
    assert len(com_ut) == len(ef), f"{componente}: {len(ef) - len(com_ut)} sem unidade temática"


def test_lingua_inglesa_usa_os_cinco_eixos():
    ef = [
        h
        for h in svc.data["habilidades"]
        if h["etapa"] == "ensino_fundamental" and h.get("componente") == "lingua_inglesa"
    ]
    eixos = {h["unidade_tematica"] for h in ef}
    esperados = {
        "Oralidade",
        "Leitura",
        "Escrita",
        "Conhecimentos Linguísticos",
        "Dimensão Intercultural",
    }
    assert eixos == esperados, f"eixos inesperados: {eixos ^ esperados}"


def test_unidade_tematica_sem_ruido_de_cabecalho():
    """Nenhuma unidade temática pode ser banner/cabeçalho (CAMPO/EIXO/CAIXA ALTA)."""
    for u in svc.data["unidades_tematicas"]:
        nome = u["nome"]
        assert not nome.upper().startswith(("CAMPO", "EIXO", "UNIDADE TEM")), nome
        letras = [c for c in nome if c.isalpha()]
        # nome real é caixa Título, nunca majoritariamente CAIXA ALTA
        if len(letras) >= 6:
            assert sum(c.isupper() for c in letras) / len(letras) <= 0.7, nome
