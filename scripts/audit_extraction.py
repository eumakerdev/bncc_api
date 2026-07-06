"""
Auditoria de qualidade da extração do snapshot da BNCC (Princípio IV).

Diferente de `validate_bncc_coverage.py` (que checa códigos/contagens/integridade
referencial), esta ferramenta audita a QUALIDADE DO TEXTO extraído — a classe de
erro que passou despercebida: descrições truncadas, "blobs" que absorvem seções
não-tabela, contaminação por cabeçalhos/banners, fusão de habilidades e ruído nas
relações. É um portão versionado: rode a cada regeneração do snapshot.

Uso:
    python scripts/audit_extraction.py [caminho_do_snapshot] [--full]

Saída: exit code != 0 se houver achados de severidade ERROR. `--full` lista todos
os códigos afetados (por padrão mostra apenas amostras).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("audit_bncc")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT / "data" / "bncc_v1.json"

# Limites (ajustáveis). Descrições oficiais da BNCC ficam, na prática, entre ~40 e
# ~600 caracteres; fora disso é quase sempre corte ou absorção de outra seção.
# Piso de 28: a habilidade oficial mais curta ("Pontuar textos adequadamente.",
# EF67LP33) tem 29 caracteres; fragmentos de truncamento real ficam <20.
MIN_DESC = 28
MAX_DESC = 800

# Cabeçalho de componente / banner / texto explicativo que NUNCA faz parte de uma
# descrição de habilidade — se aparecer no meio/fim, é contaminação.
_CONTAM = re.compile(
    r"ENSINO\s+(FUNDAMENTAL|M[ÉE]DIO)|"
    r"CI[ÊE]NCIAS\s+(HUMANAS|DA\s+NATUREZA)|LINGUAGENS\s+E\s+SUAS|"
    r"CAMPO\s+DE\s+ATUA|PR[ÁA]TICAS\s+DE\s+LINGUAGEM|UNIDADES?\s+TEM[ÁA]TICA|"
    r"OBJETOS\s+DE\s+CONHE|COMPET[ÊE]NCIAS?\s+ESPEC|Compet[êe]ncias\s+Habilidades|"
    r"BASE\s+NACIONAL|OBJETIVOS\s+DE\s+APRENDIZAGEM|DE\s+EXPERI[ÊE]NCIAS"
)
# Ligadura fi/fl quebrada na extração ("classifi cá-la").
_LIG = re.compile(r"[a-zà-ú]f[il]\s+[a-zà-ú]", re.IGNORECASE)
# Outro código dentro da descrição (fusão de habilidades).
_INNER_CODE = re.compile(r"\((?:EF|EM|EI)\d{2}[A-Z]{2,3}\d{2,3}\)")
# Código de habilidade (para checagem de sequência).
_CODE = re.compile(r"^(E[FMI]\d{2}[A-Z]{2,3})(\d{2,3})$")
# Palavras (para detecção de duplicação por interleaving de coluna).
_WORD = re.compile(r"\w+", re.UNICODE)


def _adjacent_dup(desc: str, min_words: int = 4) -> str | None:
    """Duplicação adjacente: uma sequência de >= min_words palavras seguida
    imediatamente por si mesma (ex.: 'contexto de produção contexto de produção').

    É a assinatura de alta precisão do interleaving de coluna na extração de PDF
    multicoluna — não ocorre em prosa real. Retorna o trecho duplicado ou None.
    """
    w = _WORD.findall(desc.lower())
    for i in range(len(w)):
        for n in range(min_words, (len(w) - i) // 2 + 1):
            if w[i : i + n] == w[i + n : i + 2 * n]:
                return " ".join(w[i : i + n])
    return None


class Finding:
    __slots__ = ("check", "severity", "codigo", "detail")

    def __init__(self, check: str, severity: str, codigo: str, detail: str):
        self.check = check
        self.severity = severity
        self.codigo = codigo
        self.detail = detail


def _desc_checks(habs: list[dict[str, Any]]) -> list[Finding]:
    out: list[Finding] = []
    by_desc: dict[str, list[str]] = defaultdict(list)
    for h in habs:
        cod = str(h.get("codigo", "?"))
        desc = str(h.get("descricao", ""))
        by_desc[desc].append(cod)
        n = len(desc)
        if n > MAX_DESC:
            # >1500 é quase certamente absorção de seção (ERROR); 800–1500 pode ser
            # habilidade oficial longa (EM área/LP anos finais) — revisar (WARN).
            sev = "ERROR" if n > 1500 else "WARN"
            out.append(Finding("blob", sev, cod, f"{n} chars (absorveu outra seção?)"))
        elif n < MIN_DESC:
            out.append(Finding("truncada", "ERROR", cod, f"{n} chars: {desc!r}"))
        m = _CONTAM.search(desc)
        if m and m.start() > 40:
            out.append(
                Finding(
                    "contaminada", "ERROR", cod, f"...{desc[m.start() - 20 : m.start() + 40]!r}"
                )
            )
        if _INNER_CODE.search(desc):
            out.append(Finding("fusao", "ERROR", cod, "contém outro código de habilidade"))
        if _LIG.search(desc):
            out.append(Finding("ligadura", "ERROR", cod, "resíduo de ligadura fi/fl"))
        frag = _adjacent_dup(desc)
        if frag:
            out.append(
                Finding("interleaving", "ERROR", cod, f"trecho duplicado (coluna): {frag!r}")
            )
        if desc and not desc.rstrip().endswith((".", ")", ".”", "”", "!", "?", '."', ".’", "’")):
            out.append(Finding("sem_pontuacao", "WARN", cod, f"...{desc[-40:]!r}"))
    for desc, cods in by_desc.items():
        if len(cods) > 1 and len(desc) < 120:
            # O Complemento de Computação traz o currículo do EF em DUAS organizações
            # oficiais na mesma fonte: por ano (EF0xCO##) e por etapa/bloco
            # (EF15CO##/EF69CO##). Texto idêntico entre os esquemas é representação
            # dupla fiel ao documento — não defeito de extração (Princípio IV).
            if all(c[4:6] == "CO" for c in cods):
                continue
            out.append(
                Finding("duplicada", "WARN", cods[0], f"{len(cods)} códigos idênticos: {cods[:5]}")
            )
    return out


def _sequence_gaps(habs: list[dict[str, Any]]) -> list[Finding]:
    """Lacunas na numeração sequencial por prefixo.

    IMPORTANTE: no Ensino Médio por área (EM13LGG###) o número codifica
    competência+sequência (não é contínuo) — esses prefixos são ignorados para
    não gerar falso positivo.
    """
    out: list[Finding] = []
    seqs: dict[str, set[int]] = defaultdict(set)
    for h in habs:
        m = _CODE.match(str(h.get("codigo", "")))
        if m:
            seqs[m.group(1)].add(int(m.group(2)))
    for pref, nums in seqs.items():
        if pref.startswith("EM13") and len(pref) == 7:
            continue  # EM área: numeração competência+seq, não contínua
        mx = max(nums)
        missing = [n for n in range(1, mx + 1) if n not in nums]
        if missing:
            out.append(
                Finding(
                    "lacuna_seq", "WARN", pref, f"max={mx}, faltam {len(missing)}: {missing[:12]}"
                )
            )
    return out


def _relation_checks(snap: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    for u in snap.get("unidades_tematicas", []):
        nome = str(u.get("nome", ""))
        if len(nome) > 70:
            out.append(Finding("ut_longa", "WARN", nome[:30], f"{len(nome)} chars (bleed/prosa?)"))
        letras = [c for c in nome if c.isalpha()]
        if len(letras) >= 6 and sum(c.isupper() for c in letras) / len(letras) > 0.7:
            out.append(
                Finding("ut_caixa_alta", "WARN", nome[:30], "unidade temática em CAIXA ALTA")
            )
    for o in snap.get("objetos_conhecimento", []):
        nome = str(o.get("nome", ""))
        if len(nome) > 140:
            out.append(Finding("objeto_longo", "WARN", nome[:30], f"{len(nome)} chars (bleed?)"))
    return out


CHECKS: list[Callable[[dict[str, Any]], list[Finding]]] = []


def audit(snap: dict[str, Any]) -> list[Finding]:
    habs = snap.get("habilidades", [])
    findings: list[Finding] = []
    findings += _desc_checks(habs)
    findings += _sequence_gaps(habs)
    findings += _relation_checks(snap)
    return findings


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv
    path = Path(args[0]) if args else DEFAULT_SNAPSHOT
    if not path.exists():
        logger.error("Snapshot não encontrado: %s", path)
        return 2
    snap = json.loads(path.read_text(encoding="utf-8"))
    findings = audit(snap)

    by_check: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)

    errors = 0
    logger.info("=== Auditoria de extração: %s ===", path.name)
    for check in sorted(by_check, key=lambda c: (-len(by_check[c]), c)):
        items = by_check[check]
        n_err = sum(1 for it in items if it.severity == "ERROR")
        errors += n_err
        marker = "ERRO " if n_err else "aviso"
        suffix = f" ({n_err} ERROR)" if 0 < n_err < len(items) else ""
        logger.info("[%s] %-14s: %d%s", marker, check, len(items), suffix)
        shown = items if full else items[:5]
        for f in shown:
            logger.info("        %-12s %s", f.codigo, f.detail)
        if not full and len(items) > len(shown):
            logger.info("        ... (+%d; use --full)", len(items) - len(shown))

    if errors:
        logger.error("Auditoria: %d achado(s) de severidade ERROR.", errors)
        return 1
    logger.info("Auditoria: 0 erros graves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
