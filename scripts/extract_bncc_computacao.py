"""
Extração determinística do Complemento de Computação à BNCC (Princípio IV).

Fonte oficial: `data/BNCCComputaoCompletodiagramado (1).pdf` — as *Normas sobre
Computação na Educação Básica* (Parecer CNE/CP 02/2022, homologado em 2022), que
complementam a BNCC com a Computação nas três etapas (EI/EF/EM). Todas as
habilidades usam o par de letras oficial **CO** (Computação):

    EI03CO##            (Educação Infantil, faixa 03)
    EF01CO## .. EF09CO##  (Ensino Fundamental, por ano)
    EF15CO## / EF69CO##   (blocos 1º-5º e 6º-9º)
    EM13CO##            (Ensino Médio)

**Fidelidade (Princípio IV).** As tabelas do documento diagramado guardam o texto
em células SEM caracteres de espaço (o espaçamento é posicional); por isso
recompomos as palavras por coordenada com `x_tolerance` calibrado (recupera os
espaços) e isolamos a coluna HABILIDADE pela borda esquerda do código `(E..CO..)`
— igual ao pipeline principal (`extract_bncc_data.py`). A organização por etapa é:

  * EI  — colunas ``EIXO | OBJETIVO DE APRENDIZAGEM``. O eixo é um rótulo
    horizontal em caixa-alta na coluna esquerda.
  * EF  — colunas ``EIXO | OBJETO DE CONHECIMENTO | HABILIDADE``. O eixo é um
    rótulo ROTACIONADO (90°) na margem esquerda; recuperado dos caracteres com
    ``upright=False``.
  * EM  — colunas ``COMPETÊNCIA ESPECÍFICA | HABILIDADE`` (o EM não é organizado
    por eixos, mas por competências específicas de Computação).

Os três eixos (Pensamento Computacional, Mundo Digital, Cultura Digital) aparecem
sempre nessa ordem e agrupam habilidades contíguas; cada habilidade é atribuída ao
rótulo de eixo verticalmente mais próximo (o rótulo fica centralizado no grupo).

**Escopo de fidelidade.** Extraímos apenas o que é reproduzível com fidelidade ao
documento: código, descrição (texto verbatim da coluna HABILIDADE), etapa, anos e
eixo (EI/EF). As colunas OBJETO DE CONHECIMENTO (EF) e COMPETÊNCIA ESPECÍFICA (EM)
são células mescladas cujo recorte por coordenada ainda não é determinístico o
bastante (contaminação por cabeçalhos e por fragmentos do rótulo de eixo); por
respeito ao Princípio IV, NÃO são servidas — melhor omitir do que servir dado
incorreto.

Blocos de EXEMPLOS e a "EXPLICAÇÃO DA HABILIDADE" NÃO são habilidades e não contêm
o marcador `(E..CO..)` no início de coluna, portanto são naturalmente ignorados. A
referência cruzada `EM13MAT315` (habilidade regular da BNCC citada no texto) é
descartada por não casar com o par `CO`.

Uso:
    python scripts/extract_bncc_computacao.py            # imprime estatísticas
    python scripts/extract_bncc_computacao.py --json OUT # grava a lista em OUT
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("extract_computacao")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
PDF_COMPUTACAO = DATA_DIR / "BNCCComputaoCompletodiagramado (1).pdf"

# Espaçamento posicional: recompõe palavras separadas por lacunas > 1.5pt.
X_TOLERANCE = 1.5

# --- Padrões de código -------------------------------------------------------
RE_CO = r"E[FMI]\d{2}CO\d{2}"
RE_CO_TOKEN = re.compile(r"^\(?(" + RE_CO + r")\)?[.,;:]?$")
RE_SPLIT_CO = re.compile(r"\((" + RE_CO + r")\)")

# --- Eixos (rótulos oficiais, comparados por multiconjunto de letras) ---------
EIXOS_CANON = {
    "PENSAMENTOCOMPUTACIONAL": "pensamento_computacional",
    "MUNDODIGITAL": "mundo_digital",
    "CULTURADIGITAL": "cultura_digital",
}
# Palavras isoladas que compõem os rótulos horizontais (Educação Infantil).
EIXO_WORDS = {"PENSAMENTO", "COMPUTACIONAL", "MUNDO", "CULTURA", "DIGITAL"}

# Ruído de cabeçalho/rodapé que pode contaminar a última habilidade da coluna.
NOISE_SENTINELS = re.compile(
    r"COMPUTA[ÇC][ÃA]O\s*-\s*(EDUCA|ENSINO)|EXPLICA[ÇC][ÃA]O DA HABILIDADE|"
    r"\bEXEMPLOS\b|OBJETO DE CONHE|OBJETIVODEAPRENDIZAGEM|COMPET[ÊE]NCIA ESPEC",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Utilitários
# --------------------------------------------------------------------------- #
def clean_description(raw: str) -> str:
    """Remove ruído de cabeçalho residual, nº de página ao final e normaliza espaços."""
    m = NOISE_SENTINELS.search(raw)
    if m and m.start() > 30:
        raw = raw[: m.start()]
    raw = re.sub(r"\s+\d{1,4}\s*$", "", raw)  # nº de página ao final
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def anos_from_code(codigo: str) -> list[str]:
    """Deriva os anos escolares a partir dos dígitos do código de Computação.

    EI03CO -> ['03']; EF01CO -> ['1']; EF15CO -> ['1'..'5']; EF69CO -> ['6'..'9'];
    EM13CO -> ['1','2','3'].
    """
    prefix, digits = codigo[:2], codigo[2:4]
    if prefix == "EI":
        return [digits]
    if prefix == "EM":
        return ["1", "2", "3"]
    a, b = int(digits[0]), int(digits[1])
    if a == 0:
        return [str(b)]
    if a <= b:
        return [str(y) for y in range(a, b + 1)]
    return [str(a), str(b)]


def etapa_from_code(codigo: str) -> str:
    return {
        "EI": "educacao_infantil",
        "EF": "ensino_fundamental",
        "EM": "ensino_medio",
    }[codigo[:2]]


def match_eixo(letters: str) -> str | None:
    """Casa um aglomerado de letras com o eixo canônico mais provável.

    Robusto ao intercalamento de caracteres de rótulos rotacionados: escolhe o
    eixo com maior interseção de multiconjunto de letras, penalizando diferença
    de comprimento (os três eixos têm comprimentos distintos: 22/12/14).
    """
    key = re.sub(r"[^A-Z]", "", letters.upper())
    if not key:
        return None
    kc = Counter(key)
    best: str | None = None
    best_score = -(10**9)
    for canon, val in EIXOS_CANON.items():
        inter = sum((Counter(canon) & kc).values())
        score = inter - abs(len(canon) - len(key))
        if score > best_score:
            best_score, best = score, val
    return best


# --------------------------------------------------------------------------- #
# Extração de rótulos de eixo (horizontais na EI, rotacionados no EF)
# --------------------------------------------------------------------------- #
def _eixo_labels_horizontal(
    words: list[dict[str, Any]], col_left: float
) -> list[tuple[float, str]]:
    """Rótulos horizontais em caixa-alta na coluna esquerda (Educação Infantil)."""
    lab_words = [w for w in words if w["x0"] < col_left - 5 and w["text"].upper() in EIXO_WORDS]
    if not lab_words:
        return []
    letters = "".join(w["text"] for w in lab_words)
    eixo = match_eixo(letters)
    if eixo is None:
        return []
    center = sum(w["top"] for w in lab_words) / len(lab_words)
    return [(center, eixo)]


def _eixo_labels_rotated(page: pdfplumber.page.Page) -> list[tuple[float, str]]:
    """Rótulos rotacionados (90°) na margem esquerda (Ensino Fundamental)."""
    rot = [c for c in page.chars if not c.get("upright", True)]
    if not rot:
        return []
    rot.sort(key=lambda c: c["top"])
    groups: list[list[dict[str, Any]]] = [[rot[0]]]
    for c in rot[1:]:
        if c["top"] - groups[-1][-1]["top"] > 20:
            groups.append([c])
        else:
            groups[-1].append(c)
    out: list[tuple[float, str]] = []
    for g in groups:
        eixo = match_eixo("".join(ch["text"] for ch in g))
        if eixo is None:
            continue
        center = sum(ch["top"] for ch in g) / len(g)
        out.append((center, eixo))
    return out


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def extract(pdf_path: Path = PDF_COMPUTACAO) -> list[dict[str, Any]]:
    """Extrai as habilidades de Computação de todas as etapas."""
    raw_habs: list[dict[str, Any]] = []
    eixo_labels: list[tuple[float, str]] = []  # (chave_global, eixo)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages):
            words = page.extract_words(
                use_text_flow=False, keep_blank_chars=False, x_tolerance=X_TOLERANCE
            )
            code_words = [w for w in words if RE_CO_TOKEN.match(w["text"])]
            if not code_words:
                continue
            col_left = min(w["x0"] for w in code_words) - 3.0

            # Rótulos de eixo desta página (rotacionados no EF; horizontais na EI).
            page_labels = _eixo_labels_rotated(page) or _eixo_labels_horizontal(words, col_left)
            for center, eixo in page_labels:
                eixo_labels.append((idx * 1000 + center, eixo))

            # Coluna HABILIDADE isolada por coordenada e fatiada por código — a
            # borda esquerda do código exclui as colunas EIXO e OBJETO/COMPETÊNCIA,
            # de modo que a descrição servida é o texto verbatim da coluna direita.
            right = [w for w in words if w["x0"] >= col_left]
            right.sort(key=lambda w: (round(w["top"]), w["x0"]))
            col_text = " ".join(w["text"] for w in right)

            # Topo (posição vertical) de cada código, para atribuir o eixo.
            code_top = {
                RE_CO_TOKEN.match(w["text"]).group(1): w["top"]  # type: ignore[union-attr]
                for w in code_words
            }

            for codigo, desc_raw in _split_by_codes(col_text):
                desc = clean_description(desc_raw)
                if len(desc) < 10:
                    continue
                top = code_top.get(codigo, 0.0)
                raw_habs.append(
                    {
                        "codigo": codigo,
                        "descricao": desc,
                        "etapa": etapa_from_code(codigo),
                        "anos": anos_from_code(codigo),
                        "area_conhecimento": "computacao",
                        "componente": "computacao",
                        "competencias_gerais": [],
                        "competencias_especificas": [],
                        "objetos_conhecimento": [],
                        "_global_key": idx * 1000 + top,
                    }
                )

    # Atribuição de eixo por proximidade global (rótulo centralizado no grupo). O
    # Ensino Médio não usa eixos (organizado por competências específicas).
    eixo_labels.sort()
    for h in raw_habs:
        h["eixo"] = (
            None if h["etapa"] == "ensino_medio" else _nearest_eixo(eixo_labels, h["_global_key"])
        )
        del h["_global_key"]

    return _dedup_longest(raw_habs)


def _split_by_codes(text: str) -> list[tuple[str, str]]:
    matches = list(RE_SPLIT_CO.finditer(text))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[start:end]))
    return out


def _nearest_eixo(labels: list[tuple[float, str]], key: float) -> str | None:
    if not labels:
        return None
    return min(labels, key=lambda kv: abs(kv[0] - key))[1]


def _dedup_longest(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for it in items:
        cur = best.get(it["codigo"])
        if cur is None or len(it["descricao"]) > len(cur["descricao"]):
            best[it["codigo"]] = it
    return sorted(best.values(), key=lambda h: h["codigo"])


def _stats(habs: list[dict[str, Any]]) -> dict[str, Any]:
    por_etapa = Counter(h["etapa"] for h in habs)
    por_eixo = Counter(h.get("eixo") for h in habs if h.get("eixo"))
    sem_eixo_ei_ef = [
        h["codigo"] for h in habs if h["etapa"] != "ensino_medio" and not h.get("eixo")
    ]
    return {
        "total": len(habs),
        "por_etapa": dict(por_etapa),
        "por_eixo": dict(por_eixo),
        "sem_eixo_ei_ef": sem_eixo_ei_ef,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrai o Complemento de Computação à BNCC.")
    parser.add_argument("--json", type=str, help="Grava a lista de habilidades no caminho dado.")
    args = parser.parse_args()

    if not PDF_COMPUTACAO.exists():
        logger.error("Fonte da Computação ausente: %s", PDF_COMPUTACAO)
        return 2

    habs = extract()
    stats = _stats(habs)
    logger.info("Habilidades de Computação extraídas: %s", json.dumps(stats, ensure_ascii=False))

    if args.json:
        Path(args.json).write_text(json.dumps(habs, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Gravado em %s", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
