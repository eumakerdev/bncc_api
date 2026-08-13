"""
Testes unitários do validador de código (EI/EF/EM) e dos helpers puros de
extração (T022, US1).
"""

from __future__ import annotations

import pytest
from app.models.bncc import (
    Habilidade,
    etapa_from_codigo,
    is_valid_codigo,
)
from scripts.extract_bncc_data import (
    anos_from_ef,
    clean_description,
    parse_ef,
    parse_em,
)


# --------------------------------------------------------------------------- #
# Validador de código — três formatos oficiais
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "codigo",
    ["EI03EO01", "EF05MA07", "EF15LP01", "EF67EF01", "EM13MAT101", "EM13LP01"],
)
def test_codigos_validos(codigo):
    assert is_valid_codigo(codigo)


@pytest.mark.parametrize(
    "codigo", ["", "ABC", "EF5MA07", "EF05MA7", "EM12MAT101", "XYZ123", "EF05MA070"]
)
def test_codigos_invalidos(codigo):
    assert not is_valid_codigo(codigo)


def test_is_valid_normaliza_lowercase():
    assert is_valid_codigo("ef05ma07")


@pytest.mark.parametrize(
    "codigo,etapa",
    [
        ("EI03EO01", "educacao_infantil"),
        ("EF05MA07", "ensino_fundamental"),
        ("EM13MAT101", "ensino_medio"),
    ],
)
def test_etapa_from_codigo(codigo, etapa):
    assert etapa_from_codigo(codigo) == etapa


def test_etapa_from_codigo_invalido():
    assert etapa_from_codigo("XYZ") is None


# --------------------------------------------------------------------------- #
# Modelo Habilidade valida o código nos três formatos
# --------------------------------------------------------------------------- #
def test_habilidade_aceita_em():
    h = Habilidade(
        codigo="em13mat101",
        descricao="x",
        etapa="ensino_medio",
        area_conhecimento="matematica",
    )
    assert h.codigo == "EM13MAT101"


def test_habilidade_rejeita_codigo_malformado():
    with pytest.raises(ValueError):
        Habilidade(
            codigo="INVALIDO",
            descricao="x",
            etapa="ensino_medio",
            area_conhecimento="matematica",
        )


def test_habilidade_rejeita_competencia_geral_fora_range():
    with pytest.raises(ValueError):
        Habilidade(
            codigo="EF05MA07",
            descricao="x",
            etapa="ensino_fundamental",
            area_conhecimento="matematica",
            competencias_gerais=[11],
        )


# --------------------------------------------------------------------------- #
# Helpers puros de extração
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "digits,esperado",
    [
        ("05", ["5"]),
        ("15", ["1", "2", "3", "4", "5"]),
        ("67", ["6", "7"]),
        ("69", ["6", "7", "8", "9"]),
        ("01", ["1"]),
    ],
)
def test_anos_from_ef(digits, esperado):
    assert anos_from_ef(digits) == esperado


def test_clean_description_normaliza_espacos():
    raw = "Resolver problemas    com\nnúmeros\n\nnaturais"
    assert clean_description(raw) == "Resolver problemas com números naturais"


def test_clean_description_corta_ruido_de_cabecalho():
    raw = (
        "Esta é a descrição válida e completa da habilidade avaliada aqui "
        "BASE NACIONAL COMUM CURRICULAR"
    )
    assert clean_description(raw) == (
        "Esta é a descrição válida e completa da habilidade avaliada aqui"
    )


def test_parse_ef_extrai_codigo_e_componente():
    texto = "(EF05MA07) Resolver e elaborar problemas de adição e subtração."
    result = parse_ef(texto)
    assert len(result) == 1
    hab = result[0]
    assert hab["codigo"] == "EF05MA07"
    assert hab["componente"] == "matematica"
    assert hab["area_conhecimento"] == "matematica"
    assert hab["anos"] == ["5"]
    assert "adição" in hab["descricao"]


def test_parse_em_area_e_lp():
    texto = "(EM13MAT101) Interpretar situações. (EM13LP01) Relacionar o texto."
    result = {h["codigo"]: h for h in parse_em(texto)}
    assert result["EM13MAT101"]["area_conhecimento"] == "matematica"
    assert result["EM13MAT101"]["componente"] is None
    assert result["EM13LP01"]["componente"] == "lingua_portuguesa"


def test_parse_ef_deduplica_codigo():
    texto = "(EF05MA07) Primeira descrição da habilidade. (EF05MA07) segunda ocorrência."
    result = parse_ef(texto)
    assert len(result) == 1
    assert "Primeira" in result[0]["descricao"]


# --------------------------------------------------------------------------- #
# Regressão (Princípio IV): as classes canônicas à-û/á-û aceitam exatamente os
# mesmos caracteres que as ranges sobrepostas originais — o texto extraído não
# pode mudar quando o extrator é editado.
# --------------------------------------------------------------------------- #
def test_fix_ligatures_rejunta_ligaduras_quebradas():
    from scripts.extract_bncc_data import _fix_ligatures

    # Caso do docstring do extrator (corrupção real de ligadura na prosa).
    assert _fix_ligatures("classifi cá-la") == "classificá-la"
    assert _fix_ligatures("afi rmou") == "afirmou"
    # Hífen partido.
    assert _fix_ligatures("a-fl uxo") == "afluxo"
    assert _fix_ligatures("in-fl uência") == "influência"
    # Extremidades do bloco de acentos: à (U+00E0), á (U+00E1), ú (U+00FA), û (U+00FB).
    assert _fix_ligatures("àfi la") == "àfila"
    assert _fix_ligatures("afi laû") == "afilaû"
    assert _fix_ligatures("fl á") == "flá"
    assert _fix_ligatures("fl û") == "flû"
    # Texto íntegro não é tocado (sem ligadura quebrada).
    assert _fix_ligatures("fila afiada") == "fila afiada"
