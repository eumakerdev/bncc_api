"""
Testes unitários dos helpers puros do extrator do Complemento de Computação.

Cobrem a derivação determinística (etapa/anos a partir do código) e o casamento
robusto do rótulo de eixo por multiconjunto de letras — incluindo o caso de
caracteres rotacionados intercalados (o motivo de não ordenarmos por posição).
"""

from __future__ import annotations

import pytest
from app.models.bncc import EixoComputacao, Habilidade, is_valid_codigo
from scripts.extract_bncc_computacao import (
    anos_from_code,
    etapa_from_code,
    match_eixo,
)


# --------------------------------------------------------------------------- #
# Os códigos `CO` são reconhecidos pelo validador oficial das três etapas
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("codigo", ["EI03CO01", "EF01CO07", "EF15CO09", "EF69CO12", "EM13CO26"])
def test_codigos_computacao_sao_validos(codigo):
    assert is_valid_codigo(codigo)


@pytest.mark.parametrize(
    "codigo,etapa",
    [
        ("EI03CO01", "educacao_infantil"),
        ("EF01CO01", "ensino_fundamental"),
        ("EF69CO12", "ensino_fundamental"),
        ("EM13CO01", "ensino_medio"),
    ],
)
def test_etapa_from_code(codigo, etapa):
    assert etapa_from_code(codigo) == etapa


@pytest.mark.parametrize(
    "codigo,anos",
    [
        ("EI03CO01", ["03"]),
        ("EF01CO01", ["1"]),
        ("EF09CO01", ["9"]),
        ("EF15CO01", ["1", "2", "3", "4", "5"]),
        ("EF69CO01", ["6", "7", "8", "9"]),
        ("EM13CO01", ["1", "2", "3"]),
    ],
)
def test_anos_from_code(codigo, anos):
    assert anos_from_code(codigo) == anos


# --------------------------------------------------------------------------- #
# Casamento de eixo por multiconjunto de letras (robusto a ordem/intercalamento)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "texto,eixo",
    [
        ("PENSAMENTOCOMPUTACIONAL", "pensamento_computacional"),
        ("MUNDODIGITAL", "mundo_digital"),
        ("CULTURADIGITAL", "cultura_digital"),
        # Rótulo rotacionado com caracteres intercalados (caso real das pág. EF).
        ("COPEMNPSUATAMCEINOTN", "pensamento_computacional"),
        # Ordem invertida (leitura bottom-to-top) também casa.
        ("LATIGIDODNUM", "mundo_digital"),
    ],
)
def test_match_eixo(texto, eixo):
    assert match_eixo(texto) == eixo


def test_match_eixo_vazio_retorna_none():
    assert match_eixo("") is None
    assert match_eixo("123 !!!") is None


def test_eixo_values_batem_com_enum():
    valores = {e.value for e in EixoComputacao}
    assert valores == {"pensamento_computacional", "mundo_digital", "cultura_digital"}


# --------------------------------------------------------------------------- #
# O modelo aceita uma habilidade de Computação completa
# --------------------------------------------------------------------------- #
def test_habilidade_computacao_valida_no_modelo():
    hab = Habilidade(
        codigo="EF01CO04",
        descricao="Reconhecer o que é a informação.",
        etapa="ensino_fundamental",
        anos=["1"],
        area_conhecimento="computacao",
        componente="computacao",
        eixo="mundo_digital",
    )
    assert hab.eixo == EixoComputacao.MUNDO_DIGITAL
    assert hab.area_conhecimento.value == "computacao"
