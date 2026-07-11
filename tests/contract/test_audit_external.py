"""
Testes da FERRAMENTA de auditoria externa de fidelidade (Princípio III).

Verifica o comportamento do motor determinístico e do ledger — NÃO transforma a
auditoria em portão de dados: divergências são achados esperados para o relatório,
não falhas. Cobre:

  - classificação por cobertura (concordante / divergente / sem_fontes);
  - tolerância a "bleed" da testemunha (cobertura ignora texto extra na fonte);
  - o caminho `--offline` não faz rede;
  - o ledger é idempotente (aplicar 2× os mesmos vereditos → estado idêntico).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.audit.engine import (  # noqa: E402
    STATUS_CONCORDANTE,
    STATUS_DIVERGENTE,
    STATUS_SEM_FONTES,
    cobertura,
    comparar,
)
from scripts.audit.sources import SourceRecord, carregar_fontes  # noqa: E402
from scripts.audit_external import atualizar_ledger, proximo_lote, selecionar  # noqa: E402

_OFICIAL = (
    "Comparar características de diferentes materiais presentes em objetos de uso "
    "cotidiano, discutindo sua origem, os modos como são descartados e como podem "
    "ser usados de forma mais consciente."
)


def _rec(fonte: str, desc: str, codigo: str = "EF01CI01") -> SourceRecord:
    return SourceRecord(fonte=fonte, codigo=codigo, descricao=desc, url="x", obtido_em="2026-07-11")


# -- motor: cobertura -------------------------------------------------------
def test_cobertura_ignora_bleed_da_testemunha():
    """Texto oficial + bleed de coluna na fonte ⇒ cobertura permanece total."""
    testemunha = _OFICIAL + " Vida e evolução Corpo humano"  # bleed de coluna
    assert cobertura(_OFICIAL, testemunha) == 1.0


def test_cobertura_penaliza_texto_do_snapshot_ausente_na_fonte():
    """Se o snapshot tem conteúdo que a fonte não sustenta, a cobertura cai."""
    fonte_incompleta = "Comparar características de diferentes materiais."
    assert cobertura(_OFICIAL, fonte_incompleta) < 0.6


def test_cobertura_texto_vazio_nao_quebra():
    assert cobertura("", "qualquer") == 0.0


# -- motor: classificação ---------------------------------------------------
def _hab(desc: str = _OFICIAL) -> dict:
    return {
        "codigo": "EF01CI01",
        "descricao": desc,
        "etapa": "ensino_fundamental",
        "componente": "ciencias",
    }


def test_classifica_concordante_com_bleed():
    r = comparar(_hab(), {"arbiter_pdf": _rec("arbiter_pdf", _OFICIAL + " lixo de coluna")})
    assert r.status == STATUS_CONCORDANTE
    assert r.melhor_cobertura == 1.0


def test_classifica_divergente_quando_nenhuma_fonte_sustenta():
    r = comparar(_hab(), {"arbiter_pdf": _rec("arbiter_pdf", "Texto totalmente diferente aqui.")})
    assert r.status == STATUS_DIVERGENTE
    assert r.fontes_divergentes


def test_classifica_concordante_se_a_melhor_fonte_sustenta():
    """Uma fonte diverge e outra concorda ⇒ concordante (melhor cobertura ≥ limiar)."""
    r = comparar(
        _hab(),
        {
            "mec_portal": _rec("mec_portal", "Coisa diferente."),
            "arbiter_pdf": _rec("arbiter_pdf", _OFICIAL),
        },
    )
    assert r.status == STATUS_CONCORDANTE


def test_classifica_sem_fontes_quando_todas_ausentes():
    r = comparar(_hab(), {"arbiter_pdf": None, "bncc_mcp_csv": None})
    assert r.status == STATUS_SEM_FONTES
    assert r.melhor_cobertura is None


def test_comparar_e_deterministico():
    reg = {"arbiter_pdf": _rec("arbiter_pdf", _OFICIAL)}
    a = comparar(_hab(), reg)
    b = comparar(_hab(), reg)
    assert (a.status, a.melhor_cobertura) == (b.status, b.melhor_cobertura)


# -- fontes: offline não faz rede ------------------------------------------
def test_offline_nao_instancia_rede(tmp_path):
    """Com --offline e sem cache, o portal MEC fica indisponível (nada de rede)."""
    fontes = carregar_fontes(("mec_portal",), offline=True, cache_dir=tmp_path)
    assert fontes == []


# -- ledger: idempotência ---------------------------------------------------
def test_ledger_idempotente():
    r = comparar(_hab(), {"arbiter_pdf": _rec("arbiter_pdf", _OFICIAL)})
    l1 = atualizar_ledger({"codigos": {}}, [r], lote=1, hoje="2026-07-11", snapshot_versao="v1")
    l2 = atualizar_ledger(
        dict(l1, codigos=dict(l1["codigos"])), [r], lote=1, hoje="2026-07-11", snapshot_versao="v1"
    )
    assert l1 == l2


def test_selecionar_pula_ja_auditados():
    habs = [{"codigo": "EF01CI01"}, {"codigo": "EF01CI02"}, {"codigo": "EF01CI03"}]
    ledger = {"codigos": {"EF01CI01": {"lote": 1}}}
    sel = selecionar(habs, ledger, n=10, codigos=None, reauditar=False)
    assert [h["codigo"] for h in sel] == ["EF01CI02", "EF01CI03"]


def test_proximo_lote_incrementa():
    assert proximo_lote({"codigos": {}}) == 1
    assert proximo_lote({"codigos": {"X": {"lote": 3}, "Y": {"lote": 5}}}) == 6
