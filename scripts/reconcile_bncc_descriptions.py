"""
Reconciliação de fidelidade das descrições do snapshot da BNCC (Princípio IV).

Aplica ao `data/bncc_v1.json` a tabela de correções revisada em
`scripts/bncc_description_fixes.json`, produzida por auditoria (2026-07-06) que
cruzou o snapshot com DUAS testemunhas independentes do texto oficial:

  1. Documento oficial `data/BNCC_EI_EF_110518_versaofinal_site.pdf` (600 págs.,
     normalizado com pikepdf; EI+EF+EM). É o ÁRBITRO.
  2. Dataset `github.com/dfdb76/bncc-mcp` (CSVs da "versão final homologada"), que
     casa 100% com o PDF nos códigos EI+EF e com o snapshot no EM final.

As correções consertam descrições corrompidas por interleaving de coluna,
truncamento e "bleed" de células vizinhas na extração original, e inserem o código
`EF05CO11` (Computação) que estava ausente. Texto oficial da BNCC é de livre
utilização (Lei nº 9.610/98, art. 8º, IV).

O script é IDEMPOTENTE (só altera descrições que ainda divergem do alvo) e
DETERMINÍSTICO. As contagens em `metadata.contagens` são recomputadas dos dados.

Uso:
    python scripts/reconcile_bncc_descriptions.py [--dry-run] [caminho_snapshot]
"""

from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("reconcile_bncc")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT / "data" / "bncc_v1.json"
FIXES_FILE = ROOT / "scripts" / "bncc_description_fixes.json"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    s = s.replace("­", "")
    return re.sub(r"\s+", " ", s).strip()


def _recompute_counts(snap: dict[str, Any]) -> None:
    habs = snap["habilidades"]
    cont = snap["metadata"]["contagens"]
    cont["por_etapa"] = dict(Counter(h.get("etapa", "?") for h in habs))
    cont["por_componente"] = dict(Counter(h.get("componente") or "sem_componente" for h in habs))
    comp = [h for h in habs if h.get("componente") == "computacao"]
    cont["computacao"] = {
        "total": len(comp),
        "por_etapa": dict(Counter(h.get("etapa", "?") for h in comp)),
        "por_eixo": dict(Counter(h.get("eixo") for h in comp if h.get("eixo"))),
    }
    cont["total_habilidades"] = len(habs)
    cont["total_competencias_gerais"] = len(snap.get("competencias_gerais", []))
    cont["total_competencias_especificas"] = len(snap.get("competencias_especificas", []))
    cont["total_unidades_tematicas"] = len(snap.get("unidades_tematicas", []))
    cont["total_objetos_conhecimento"] = len(snap.get("objetos_conhecimento", []))
    cont["total_campos_experiencia"] = len(snap.get("campos_experiencia", []))


def reconcile(snap: dict[str, Any], fixes: dict[str, Any]) -> dict[str, int]:
    habs = snap["habilidades"]
    by_code = {h["codigo"]: h for h in habs}
    stats = {"aplicadas": 0, "ja_ok": 0, "ausentes": 0, "inseridas": 0}

    for codigo, spec in fixes["descricoes"].items():
        h = by_code.get(codigo)
        if h is None:
            logger.warning("Fix para código ausente no snapshot: %s", codigo)
            stats["ausentes"] += 1
            continue
        alvo = _norm(spec["descricao"])
        if _norm(h["descricao"]) == alvo:
            stats["ja_ok"] += 1
        else:
            h["descricao"] = alvo
            stats["aplicadas"] += 1

    for ins in fixes.get("inserir", []):
        codigo = ins["codigo"]
        if codigo in by_code:
            stats["ja_ok"] += 1
            continue
        apos = ins.get("apos")
        nova = {k: v for k, v in ins.items() if k not in ("apos", "fonte", "motivo")}
        nova["descricao"] = _norm(nova["descricao"])
        idx = next((i for i, h in enumerate(habs) if h["codigo"] == apos), len(habs) - 1)
        habs.insert(idx + 1, nova)
        by_code[codigo] = nova
        stats["inseridas"] += 1
        logger.info("Inserido %s após %s.", codigo, apos)

    _recompute_counts(snap)
    return stats


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    path = Path(args[0]) if args else DEFAULT_SNAPSHOT
    if not path.exists():
        logger.error("Snapshot não encontrado: %s", path)
        return 2
    if not FIXES_FILE.exists():
        logger.error("Tabela de correções não encontrada: %s", FIXES_FILE)
        return 2

    snap = json.loads(path.read_text(encoding="utf-8"))
    fixes = json.loads(FIXES_FILE.read_text(encoding="utf-8"))
    stats = reconcile(snap, fixes)

    logger.info(
        "Reconciliação: %d aplicada(s), %d já OK, %d inserida(s), %d ausente(s).",
        stats["aplicadas"],
        stats["ja_ok"],
        stats["inseridas"],
        stats["ausentes"],
    )
    logger.info("Total de habilidades: %d", len(snap["habilidades"]))

    if dry:
        logger.info("--dry-run: snapshot NÃO gravado.")
        return 0

    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("Snapshot gravado: %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
