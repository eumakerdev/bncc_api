"""
Auditoria externa e incremental de fidelidade da BNCC — gerador de relatórios.

NÃO altera dados (Princípios IV/VII): seleciona um lote de habilidades do snapshot,
cruza cada uma contra fontes independentes (ver `scripts/audit/sources/`) por
similaridade determinística e emite um RELATÓRIO em Markdown para decisão humana.
Mantém um ledger (`audit/ledger.json`) do que já foi auditado — permitindo cobrir
o corpus (~1.717 habilidades) aos poucos — e regenera um índice `audit/PROGRESSO.md`.

Uso:
    python scripts/audit_external.py --lote 25            # próximos 25 não auditados
    python scripts/audit_external.py --codigos EF01CI01,EF01CI02
    python scripts/audit_external.py --lote 25 --reauditar  # revisita já auditados
    python scripts/audit_external.py --lote 25 --offline    # só cache/arquivos locais

As divergências são ACHADOS para o relatório (não erros): exit code 0 mesmo com
divergências; != 0 apenas em erro de execução (snapshot ausente etc.).
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("audit_external")

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

from scripts.audit.engine import (  # noqa: E402
    LIMIAR_PADRAO,
    STATUS_CONCORDANTE,
    STATUS_DIVERGENTE,
    STATUS_SEM_FONTES,
    ResultadoCodigo,
    comparar,
)
from scripts.audit.sources import Source, carregar_fontes  # noqa: E402

DEFAULT_SNAPSHOT = ROOT / "data" / "bncc_v1.json"
AUDIT_DIR = ROOT / "audit"
LEDGER_PATH = AUDIT_DIR / "ledger.json"
RELATORIOS_DIR = AUDIT_DIR / "relatorios"
PROGRESSO_PATH = AUDIT_DIR / "PROGRESSO.md"

_STATUS_ICON = {
    STATUS_CONCORDANTE: "✅ concordante",
    STATUS_DIVERGENTE: "⚠️ divergente",
    STATUS_SEM_FONTES: "— sem fontes",
}


# --------------------------------------------------------------------------
# Ledger (estado incremental por código)
# --------------------------------------------------------------------------
def carregar_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"gerado_em": "", "snapshot_versao": "", "codigos": {}}


def proximo_lote(ledger: dict[str, Any]) -> int:
    lotes = [e.get("lote", 0) for e in ledger.get("codigos", {}).values()]
    return (max(lotes) + 1) if lotes else 1


def atualizar_ledger(
    ledger: dict[str, Any],
    resultados: list[ResultadoCodigo],
    lote: int,
    hoje: str,
    snapshot_versao: str,
) -> dict[str, Any]:
    """Aplica os vereditos ao ledger. Idempotente: mesmos argumentos → mesmo estado."""
    ledger["gerado_em"] = hoje
    ledger["snapshot_versao"] = snapshot_versao
    cods = ledger.setdefault("codigos", {})
    for r in resultados:
        cods[r.codigo] = {
            "veredito": r.status,
            "lote": lote,
            "ultima_auditoria": hoje,
            "fontes_consultadas": [f.fonte for f in r.fontes],
            "melhor_cobertura": r.melhor_cobertura,
        }
    return ledger


# --------------------------------------------------------------------------
# Seleção de lote
# --------------------------------------------------------------------------
def selecionar(
    habs: list[dict[str, Any]],
    ledger: dict[str, Any],
    *,
    n: int | None,
    codigos: list[str] | None,
    reauditar: bool,
) -> list[dict[str, Any]]:
    por_codigo = {h["codigo"]: h for h in habs}
    if codigos:
        return [por_codigo[c] for c in codigos if c in por_codigo]
    auditados = set(ledger.get("codigos", {}))
    candidatos = sorted(habs, key=lambda h: h["codigo"])
    if not reauditar:
        candidatos = [h for h in candidatos if h["codigo"] not in auditados]
    return candidatos[: (n or 0)]


# --------------------------------------------------------------------------
# Execução da auditoria de um lote
# --------------------------------------------------------------------------
def auditar(
    selecao: list[dict[str, Any]],
    fontes: list[Source],
    *,
    limiar: float,
) -> list[ResultadoCodigo]:
    resultados: list[ResultadoCodigo] = []
    for hab in selecao:
        registros = {f.slug: f.fetch(hab["codigo"]) for f in fontes}
        resultados.append(comparar(hab, registros, limiar=limiar))
    return resultados


# --------------------------------------------------------------------------
# Renderização do relatório Markdown
# --------------------------------------------------------------------------
def _pct(sim: float | None) -> str:
    return f"{sim * 100:.1f}%" if sim is not None else "—"


def render_relatorio(
    resultados: list[ResultadoCodigo],
    *,
    lote: int,
    hoje: str,
    fontes: list[Source],
    limiar: float,
    snapshot_meta: dict[str, Any],
) -> str:
    slugs = [f.slug for f in fontes]
    n = len(resultados)
    n_conc = sum(1 for r in resultados if r.status == STATUS_CONCORDANTE)
    n_div = sum(1 for r in resultados if r.status == STATUS_DIVERGENTE)
    n_sem = sum(1 for r in resultados if r.status == STATUS_SEM_FONTES)
    faixa = f"{resultados[0].codigo} … {resultados[-1].codigo}" if resultados else "—"

    L: list[str] = []
    L.append(f"# Auditoria externa de fidelidade — lote {lote:04d}")
    L.append("")
    L.append(f"- **Data:** {hoje}")
    L.append(f"- **Códigos:** {n} ({faixa})")
    L.append(f"- **Fontes consultadas:** {', '.join(f'`{s}`' for s in slugs) or '_nenhuma_'}")
    L.append(f"- **Limiar de concordância:** {limiar:.2f}")
    L.append(f"- **Snapshot:** versão `{snapshot_meta.get('versao', '?')}`")
    checks = snapshot_meta.get("checksum_fontes", {})
    if checks:
        L.append(f"- **checksum_fontes:** `{json.dumps(checks, ensure_ascii=False)[:120]}…`")
    L.append("")
    L.append("> ⚠️ Nenhuma fonte é tratada como verdade final. Este relatório apenas")
    L.append("> **informa** a decisão humana. Correções aprovadas entram pelo fluxo")
    L.append("> `scripts/reconcile_bncc_descriptions.py` (nunca automaticamente).")
    L.append("")
    L.append("## Resumo")
    L.append("")
    L.append("| Auditados | ✅ Concordantes | ⚠️ Divergentes | — Sem fontes |")
    L.append("|---:|---:|---:|---:|")
    L.append(f"| {n} | {n_conc} | {n_div} | {n_sem} |")
    L.append("")

    # Tabela por código
    L.append("## Por código")
    L.append("")
    L.append(
        "_Percentual = **cobertura**: quanto do texto do snapshot está sustentado "
        "pela fonte (extra na fonte não penaliza)._"
    )
    L.append("")
    cab = ["Código", "Etapa/Comp.", "Status"] + [f"`{s}`" for s in slugs]
    L.append("| " + " | ".join(cab) + " |")
    L.append("|" + "|".join(["---"] * len(cab)) + "|")
    for r in resultados:
        comp = r.componente or (r.etapa.split("_")[-1] if r.etapa else "—")
        sims = {f.fonte: f for f in r.fontes}
        cells = [f"`{r.codigo}`", comp, _STATUS_ICON.get(r.status, r.status)]
        for s in slugs:
            f = sims.get(s)
            cells.append(_pct(f.cobertura) if f and f.presente else "ausente")
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    # Divergências detalhadas
    divergentes = [r for r in resultados if r.status == STATUS_DIVERGENTE]
    L.append(f"## Divergências detalhadas ({len(divergentes)})")
    L.append("")
    if not divergentes:
        L.append("_Nenhuma divergência acima do limiar neste lote._")
        L.append("")
    for r in divergentes:
        L.append(f"### `{r.codigo}` — {r.etapa}")
        L.append("")
        L.append("**Snapshot atual:**")
        L.append("")
        L.append(f"> {r.descricao_snapshot}")
        L.append("")
        for f in r.fontes:
            if not f.presente:
                L.append(f"- `{f.fonte}`: _código ausente nesta fonte._")
                continue
            L.append(
                f"**`{f.fonte}`** (cobertura {_pct(f.cobertura)}, "
                f"similaridade {_pct(f.similaridade)}) — {f.url}:"
            )
            L.append("")
            L.append(f"> {f.descricao_fonte}")
            L.append("")
        L.append(
            "**Análise do assessor:** _(a preencher pelo agente — ver `docs/auditoria-externa.md`)_"
        )
        L.append("")
        L.append(
            "**Proposta de correção:** _(a preencher; citar a fonte/página árbitro e a confiança)_"
        )
        L.append("")

    # Rodapé: bloco copiável para bncc_description_fixes.json
    L.append("## Propostas para `scripts/bncc_description_fixes.json`")
    L.append("")
    L.append("Preencher apenas as aprovadas por revisão humana, então rodar")
    L.append("`python scripts/reconcile_bncc_descriptions.py`.")
    L.append("")
    L.append("```json")
    exemplo = {
        r.codigo: {
            "descricao": "<texto oficial adjudicado>",
            "fonte": "arbiter_pdf",
            "motivo": "<...>",
        }
        for r in divergentes
    }
    L.append(json.dumps({"descricoes": exemplo}, ensure_ascii=False, indent=2))
    L.append("```")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# Índice de progresso
# --------------------------------------------------------------------------
def render_progresso(
    ledger: dict[str, Any],
    habs: list[dict[str, Any]],
    relatorios_dir: Path,
) -> str:
    total = len(habs)
    cods = ledger.get("codigos", {})
    auditados = len(cods)
    por_etapa_total: dict[str, int] = {}
    por_etapa_aud: dict[str, int] = {}
    for h in habs:
        et = h.get("etapa", "?")
        por_etapa_total[et] = por_etapa_total.get(et, 0) + 1
        if h["codigo"] in cods:
            por_etapa_aud[et] = por_etapa_aud.get(et, 0) + 1
    n_div = sum(1 for e in cods.values() if e.get("veredito") == STATUS_DIVERGENTE)

    L: list[str] = []
    L.append("# Progresso da auditoria externa de fidelidade")
    L.append("")
    pct = (auditados / total * 100) if total else 0.0
    L.append(
        f"**{auditados}/{total} habilidades auditadas ({pct:.1f}%)** · "
        f"⚠️ {n_div} divergência(s) registrada(s)."
    )
    L.append("")
    L.append("| Etapa | Auditadas | Total | % |")
    L.append("|---|---:|---:|---:|")
    for et in sorted(por_etapa_total):
        a = por_etapa_aud.get(et, 0)
        t = por_etapa_total[et]
        L.append(f"| {et} | {a} | {t} | {(a / t * 100) if t else 0:.1f}% |")
    L.append("")
    L.append("## Relatórios por lote")
    L.append("")
    relatorios = sorted(relatorios_dir.glob("*-lote-*.md")) if relatorios_dir.exists() else []
    if not relatorios:
        L.append("_Nenhum relatório gerado ainda._")
    for rel in relatorios:
        L.append(f"- [`{rel.name}`](relatorios/{rel.name})")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Auditoria externa de fidelidade da BNCC (relatórios)."
    )
    ap.add_argument(
        "--lote", type=int, default=None, help="Nº de habilidades a auditar neste lote."
    )
    ap.add_argument(
        "--codigos", type=str, default=None, help="Lista de códigos (vírgula) a auditar."
    )
    ap.add_argument("--reauditar", action="store_true", help="Revisita códigos já auditados.")
    ap.add_argument("--offline", action="store_true", help="Só cache/arquivos locais (sem rede).")
    ap.add_argument("--limiar", type=float, default=LIMIAR_PADRAO, help="Limiar de concordância.")
    ap.add_argument("--snapshot", type=str, default=None, help="Caminho do snapshot.")
    args = ap.parse_args()

    snap_path = Path(args.snapshot) if args.snapshot else DEFAULT_SNAPSHOT
    if not snap_path.exists():
        logger.error("Snapshot não encontrado: %s", snap_path)
        return 2
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    habs = snap["habilidades"]
    snap_meta = snap.get("metadata", {})

    codigos = [c.strip() for c in args.codigos.split(",")] if args.codigos else None
    if not codigos and not args.lote:
        logger.error("Informe --lote N ou --codigos A,B,...")
        return 2

    ledger = carregar_ledger()
    selecao = selecionar(habs, ledger, n=args.lote, codigos=codigos, reauditar=args.reauditar)
    if not selecao:
        logger.info("Nada a auditar (corpus coberto ou seleção vazia).")
        return 0

    fontes = carregar_fontes(offline=args.offline)
    if not fontes:
        logger.warning("Nenhuma fonte disponível — o relatório sairá sem testemunhas.")

    resultados = auditar(selecao, fontes, limiar=args.limiar)
    hoje = date.today().isoformat()
    lote = proximo_lote(ledger)

    RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    rel_path = RELATORIOS_DIR / f"{hoje}-lote-{lote:04d}.md"
    rel_path.write_text(
        render_relatorio(
            resultados,
            lote=lote,
            hoje=hoje,
            fontes=fontes,
            limiar=args.limiar,
            snapshot_meta=snap_meta,
        ),
        encoding="utf-8",
    )

    atualizar_ledger(ledger, resultados, lote, hoje, snap_meta.get("versao", ""))
    LEDGER_PATH.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    PROGRESSO_PATH.write_text(render_progresso(ledger, habs, RELATORIOS_DIR), encoding="utf-8")

    n_div = sum(1 for r in resultados if r.status == STATUS_DIVERGENTE)
    logger.info(
        "Lote %04d: %d auditados, %d divergência(s). Relatório: %s",
        lote,
        len(resultados),
        n_div,
        rel_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
