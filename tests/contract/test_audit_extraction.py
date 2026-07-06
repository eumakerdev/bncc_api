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

# Após a recuperação por célula + trim de código embutido, a extração ficou sem
# achados ERROR. Mantemos uma folga pequena para não quebrar por 1 caso-limite
# eventual, mas o alvo é zero — nunca deve crescer.
_MAX_ERROS = 2


def test_auditoria_sem_regressao_de_qualidade():
    erros = [f for f in _FINDINGS if f.severity == "ERROR"]
    assert len(erros) <= _MAX_ERROS, "\n".join(f"{f.check} {f.codigo}: {f.detail}" for f in erros)


def test_sem_contaminacao_de_cabecalho_nas_descricoes():
    """A contaminação de cabeçalho/banner (149 casos) foi zerada e deve continuar 0."""
    contaminadas = [f for f in _FINDINGS if f.check == "contaminada"]
    assert not contaminadas, [f.codigo for f in contaminadas]


def test_sem_blob_catastrofico():
    """Nenhuma descrição deve absorver páginas inteiras (>1500 chars = ERROR)."""
    catastroficos = [f for f in _FINDINGS if f.check == "blob" and f.severity == "ERROR"]
    # EF06HI14 é um mis-split conhecido e isolado; teto de 5 evita crescimento.
    assert len(catastroficos) <= 5, [f.codigo for f in catastroficos]
