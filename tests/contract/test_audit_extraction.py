"""
Portão de regressão da QUALIDADE da extração (descrições/relações).

Roda a auditoria (`scripts/audit_extraction.py`) contra o `data/bncc_v1.json`
commitado e falha se a contagem de achados graves crescer — impede que blobs,
truncamentos e contaminação de cabeçalho voltem a passar despercebidos (a classe
de erro que a validação de códigos/contagens não pegava).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.audit_extraction import audit  # noqa: E402

_SNAP = json.loads((ROOT / "data" / "bncc_v1.json").read_text(encoding="utf-8"))
_FINDINGS = audit(_SNAP)
_HABS = {h["codigo"]: h for h in _SNAP["habilidades"]}


def _count(check: str) -> int:
    return sum(1 for f in _FINDINGS if f.check == check)


def test_auditoria_sem_achados_error():
    """Alvo: ZERO achados ERROR. A recuperação por célula (mesclada) + trim de código
    embutido + sanitização de relações zeraram a classe ERROR — nunca deve voltar."""
    erros = [f for f in _FINDINGS if f.severity == "ERROR"]
    assert not erros, "\n".join(f"{f.check} {f.codigo}: {f.detail}" for f in erros)


def test_sem_contaminacao_de_cabecalho_nas_descricoes():
    """A contaminação de cabeçalho/banner (149 casos) foi zerada e deve continuar 0."""
    contaminadas = [f for f in _FINDINGS if f.check == "contaminada"]
    assert not contaminadas, [f.codigo for f in contaminadas]


def test_sem_blob_catastrofico():
    """Nenhuma descrição deve absorver páginas inteiras (>1500 chars = ERROR)."""
    catastroficos = [f for f in _FINDINGS if f.check == "blob" and f.severity == "ERROR"]
    # EF06HI14 é um mis-split conhecido e isolado; teto de 5 evita crescimento.
    assert len(catastroficos) <= 5, [f.codigo for f in catastroficos]


def test_truncacao_de_descricao_sob_controle():
    """As ~31 descrições truncadas (célula mesclada de anos combinados) foram
    recuperadas da fonte; sobra 1 caso com texto completo sem ponto final. Teto baixo
    (3) trava a regressão do "residual difícil"."""
    assert _count("sem_pontuacao") <= 3, [f.codigo for f in _FINDINGS if f.check == "sem_pontuacao"]


def test_bleed_de_relacoes_sob_controle():
    """O bleed de prosa de campo/exemplo nos objetos foi descartado (40 → ~15). A
    unidade temática de LP mantém 15 casos longos conhecidos (não removíveis sem
    reescrever ef_relations). Tetos evitam crescimento."""
    assert _count("objeto_longo") <= 16, [f.codigo for f in _FINDINGS if f.check == "objeto_longo"]
    assert _count("ut_longa") <= 16, [f.codigo for f in _FINDINGS if f.check == "ut_longa"]


def test_descricoes_de_celula_mesclada_recuperadas():
    """Regressão do fix de célula mesclada: habilidades de anos combinados cujo texto
    atravessa as colunas de ano devem vir COMPLETAS e terminadas em ponto."""
    esperado = {
        "EF35LP13": "que não representa fonema.",
        "EF12LP15": "slogans publicitários.",
        "EF67LP34": "noção de negação.",
        "EF67LP35": "e palavras compostas.",
    }
    for cod, fim in esperado.items():
        desc = _HABS[cod]["descricao"]
        assert desc.endswith(fim), f"{cod} não recuperada: {desc!r}"
