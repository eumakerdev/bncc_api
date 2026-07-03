"""
Teste de integração de cobertura das etapas (T023, SC-001).

Valida o snapshot real `data/bncc_v1.json`: cobertura de EF e EM > 0, unicidade e
formato dos códigos, exatamente 10 competências gerais. A Educação Infantil é
tratada como bloqueio conhecido (T024): contagem 0 + `missing_sources`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.core.config import settings
from app.models.bncc import (
    CODE_PATTERN_EF,
    is_valid_codigo,
)

SNAPSHOT_PATH = Path(settings.BNCC_DATA_PATH)


@pytest.fixture(scope="module")
def snapshot():
    if not SNAPSHOT_PATH.exists():
        pytest.skip(f"Snapshot {SNAPSHOT_PATH} ausente — rode scripts/extract_bncc_data.py.")
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_cobertura_ensino_fundamental(snapshot):
    counts = snapshot["metadata"]["contagens"]["por_etapa"]
    assert counts.get("ensino_fundamental", 0) > 0


def test_cobertura_ensino_medio(snapshot):
    counts = snapshot["metadata"]["contagens"]["por_etapa"]
    assert counts.get("ensino_medio", 0) > 0


def test_educacao_infantil_bloqueada_t024(snapshot):
    """EI ausente por falta de fonte oficial (T024) — documentado, não fabricado."""
    counts = snapshot["metadata"]["contagens"]["por_etapa"]
    assert counts.get("educacao_infantil", 0) == 0
    assert "educacao_infantil" in snapshot["metadata"].get("missing_sources", [])


def test_dez_competencias_gerais(snapshot):
    assert len(snapshot["competencias_gerais"]) == 10


def test_codigos_unicos_e_bem_formados(snapshot):
    codigos = [h["codigo"] for h in snapshot["habilidades"]]
    assert len(codigos) == len(set(codigos)), "Há códigos duplicados no snapshot."
    for codigo in codigos:
        assert is_valid_codigo(codigo), f"Código malformado: {codigo}"


def test_codigo_casa_com_etapa(snapshot):
    for hab in snapshot["habilidades"]:
        codigo, etapa = hab["codigo"], hab["etapa"]
        if etapa == "ensino_fundamental":
            assert CODE_PATTERN_EF.match(codigo), codigo
        elif etapa == "ensino_medio":
            assert is_valid_codigo(codigo) and codigo.startswith("EM13"), codigo


def test_checksum_das_fontes_presente(snapshot):
    checksums = snapshot["metadata"]["checksum_fontes"]
    assert "ensino_fundamental" in checksums
    assert "ensino_medio" in checksums
    assert all(len(v) == 64 for v in checksums.values())  # SHA-256 hex
