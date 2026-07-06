"""
Extração determinística do snapshot da BNCC (T026, Princípio IV).

Lê os PDFs oficiais em `data/` (Educação Infantil, Ensino Fundamental e Ensino
Médio) com pdfplumber e grava `data/bncc_v1.json` com metadados de rastreabilidade
(versão, checksum SHA-256 das fontes, contagens por etapa/componente).

**Fidelidade (Princípio IV / T029)**: as tabelas da BNCC têm colunas. No EF/EM são 3
colunas (UNIDADES TEMÁTICAS | OBJETOS DE CONHECIMENTO | HABILIDADES) e uma extração
ingênua com `extract_text()` intercala o texto das colunas da esquerda dentro da
descrição da habilidade; por isso isolamos a **coluna HABILIDADES** por coordenada
horizontal (o código `(EFxxxx)` marca a borda esquerda da coluna) e só então
recompomos e fatiamos o texto por código.

Educação Infantil (T024): a fonte oficial completa é `data/BNCC_20dez_site.pdf` (as
três etapas em um único PDF, 472 páginas). Sua árvore de páginas está comprimida e o
pdfplumber sozinho enxerga apenas 1 página; por isso normalizamos o PDF com
**pikepdf** (reescreve o arquivo → pdfplumber passa a ler as 472 páginas COM
coordenadas). A EI é uma tabela de 3 colunas = as três faixas etárias (01/02/03).
Cada coluna é isolada pela borda esquerda do código `(EIxxYYnn)` — igual ao EF/EM,
mas processada por faixa. O PDF normalizado é temporário e nunca é versionado; o
checksum registrado é o do `BNCC_20dez_site.pdf` ORIGINAL (proveniência).

Uso:
    python scripts/extract_bncc_data.py [--validate]
"""

from __future__ import annotations

# E501: as 10 competências gerais são texto OFICIAL fixo — quebrá-las alteraria o
# dado (Princípio IV); mantê-las em linha única é intencional.
# ruff: noqa: E501
import argparse
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
import pikepdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("extract_bncc")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
PDF_EF = DATA_DIR / "bncc_ensino_fundamental.pdf"
PDF_EM = DATA_DIR / "bncc_ensino_medio.pdf"
# Fonte oficial completa (3 etapas em 1 PDF) — usada para a Educação Infantil.
PDF_EI_SITE = DATA_DIR / "BNCC_20dez_site.pdf"
# Fallback opcional: PDF dedicado da EI (mesma estrutura de 3 colunas por faixa).
PDF_EI = DATA_DIR / "bncc_educacao_infantil.pdf"
# Complemento de Computação à BNCC (Normas de Computação na Educação Básica).
PDF_COMPUTACAO = DATA_DIR / "BNCCComputaoCompletodiagramado (1).pdf"
OUTPUT = DATA_DIR / "bncc_v1.json"

# EI: no `BNCC_20dez_site.pdf` as tabelas de objetivos ficam além do prefácio; a
# página-exemplo (que ilustra o código EI02TS01 em prosa) está no material
# explicativo inicial. Pulamos o prefácio por índice e, por segurança, também
# ignoramos qualquer página que contenha os marcadores do texto-exemplo.
EI_FRONTMATTER_SKIP_PAGES = 40
EI_EXPLANATION_SENTINELS = re.compile(
    r"exemplo apresentado|par de letras indica|c[óo]digo alfanum[ée]rico",
    re.IGNORECASE,
)

SNAPSHOT_VERSION = "v1"

# --- Padrões de código -------------------------------------------------------
RE_EF = r"EF\d{2}[A-Z]{2}\d{2}"
RE_EM_AREA = r"EM13[A-Z]{3}\d{3}"
RE_EM_LP = r"EM13[A-Z]{2}\d{2}"
RE_EI = r"EI\d{2}[A-Z]{2}\d{2}"

# Token isolado (palavra) que é um código, com ou sem parênteses.
RE_CODE_TOKEN = re.compile(r"^\(?(E[FMI]\d{2}[A-Z]{2,3}\d{2,3})\)?[.,;:]?$")
# Idem, restrito à Educação Infantil (usado para agrupar as 3 colunas por faixa).
RE_EI_CODE_TOKEN = re.compile(r"^\(?(" + RE_EI + r")\)?[.,;:]?$")
# Divisor de habilidades no fluxo textual já isolado da coluna direita.
RE_SPLIT_EF = re.compile(r"\((" + RE_EF + r")\)")
RE_SPLIT_EM = re.compile(r"\((" + RE_EM_AREA + r"|" + RE_EM_LP + r")\)")
RE_SPLIT_EI = re.compile(r"\((" + RE_EI + r")\)")

# --- Mapeamentos determinísticos ---------------------------------------------
EF_COMPONENTE = {
    "LP": ("lingua_portuguesa", "linguagens"),
    "LI": ("lingua_inglesa", "linguagens"),
    "AR": ("arte", "linguagens"),
    "EF": ("educacao_fisica", "linguagens"),
    "MA": ("matematica", "matematica"),
    "CI": ("ciencias", "ciencias_natureza"),
    "GE": ("geografia", "ciencias_humanas"),
    "HI": ("historia", "ciencias_humanas"),
    "ER": ("ensino_religioso", "ensino_religioso"),
}
EM_AREA = {
    "LGG": "linguagens",
    "MAT": "matematica",
    "CNT": "ciencias_natureza",
    "CHS": "ciencias_humanas",
}
EI_CAMPO = {
    "EO": "O eu, o outro e o nós",
    "CG": "Corpo, gestos e movimentos",
    "TS": "Traços, sons, cores e formas",
    "EF": "Escuta, fala, pensamento e imaginação",
    "ET": "Espaços, tempos, quantidades, relações e transformações",
}

# Sentinelas de cabeçalho/rodapé que podem contaminar a última habilidade da
# página (a descrição oficial nunca contém estas expressões em CAIXA ALTA). Além
# dos rótulos de coluna, inclui os cabeçalhos correntes de componente/etapa
# ("CIÊNCIAS HUMANAS – GEOGRAFIA ENSINO FUNDAMENTAL", "LINGUAGENS E SUAS
# TECNOLOGIAS – LÍNGUA PORTUGUESA ENSINO MÉDIO") e marcadores do prefácio/EI que
# vazavam no fim/meio da descrição. Case-sensitive de propósito: menções em texto
# corrente ("Ensino Fundamental") são caixa Título e não devem cortar.
NOISE_SENTINELS = re.compile(
    r"BASE NACIONAL|COMUM CURRICULAR|UNIDADES TEM|CAMPOS? DE ATUA|"
    r"OBJETOS DE CONHE|\bHABILIDADES\b|COMPET[ÊE]NCIAS ESPEC|PR[ÁA]TICAS DE LINGUAGEM|"
    r"ENSINO FUNDAMENTAL|ENSINO M[ÉE]DIO|CI[ÊE]NCIAS HUMANAS|CI[ÊE]NCIAS DA NATUREZA|"
    r"LINGUAGENS E SUAS|OBJETIVOS DE APRENDIZAGEM|EDUCA[ÇC][ÃA]O INFANTIL|"
    r"DE EXPERI[ÊE]NCIAS|Compet[êe]ncias Habilidades|[1-9]\s*[ºo°]\s+ANO\b|"
    # Cabeçalho corrente "ÁREA – COMPONENTE" do Ensino Fundamental e o nome do
    # componente em CAIXA ALTA sozinho no fim (ex.: "...variadas. MATEMÁTICA").
    r"LINGUAGENS\s*[–-]|CI[ÊE]NCIAS\s*[–-]|ENSINO RELIGIOSO|"
    r"\bMATEM[ÁA]TICA\b|\bGEOGRAFIA\b|\bHIST[ÓO]RIA\b|"
    # Bleed do bloco de prática/cabeçalho da Língua Portuguesa do Ensino Médio.
    r"lingu[íi]stica/sem[íi][óo]tica Habilidades|Habilidades\s+espec[íi]ficas"
)


# --------------------------------------------------------------------------- #
# Utilitários
# --------------------------------------------------------------------------- #
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def anos_from_ef(digits: str) -> list[str]:
    """ "05"→['5']; "67"→['6','7']; "15"→['1'..'5']; "89"→['8','9']."""
    a, b = int(digits[0]), int(digits[1])
    if a == 0:
        return [str(b)] if b != 0 else []
    if a <= b:
        return [str(y) for y in range(a, b + 1)]
    return [str(a), str(b)]


_EMBEDDED_CODE = re.compile(r"\((?:EF|EM|EI)\d{2}[A-Z]{2,3}\d{2,3}\)")


def clean_description(raw: str) -> str:
    """Corta ruído de cabeçalho, remove nº de rodapé residual e normaliza espaços."""
    m = NOISE_SENTINELS.search(raw)
    if m and m.start() > 30:
        raw = raw[: m.start()]
    # Um código de habilidade embutido marca o início da PRÓXIMA habilidade (fusão);
    # corta ali (o código da própria já foi removido pelo split). Ex.: Computação
    # EF05CO10 absorvia "(EF05CO011) Identificar...".
    cm = _EMBEDDED_CODE.search(raw)
    if cm and cm.start() > 30:
        raw = raw[: cm.start()]
    raw = re.sub(r"\s+\d{1,4}\s*$", "", raw)  # nº de página ao final
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


# --------------------------------------------------------------------------- #
# Isolamento da coluna HABILIDADES (evita contaminação — fidelidade)
# --------------------------------------------------------------------------- #
def _code_clusters(values: list[float], gap: float = 120.0) -> list[tuple[float, int]]:
    """Agrupa x0 de códigos em colunas → [(borda_esquerda, nº de códigos), ...]."""
    vals = sorted(values)
    groups: list[list[float]] = [[vals[0]]]
    for v in vals[1:]:
        if v - groups[-1][-1] > gap:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [(min(g), len(g)) for g in groups]


def _ends_sentence(t: str) -> bool:
    return t.rstrip().endswith((".", ")", "!", "?", ".”", "”", '."'))


_SENT_END = re.compile(r"[.!?][)”\"]?(?=\s)")


def _trim_to_sentence(t: str) -> str:
    """Corta a frase incompleta ao final (bleed da célula seguinte)."""
    if _ends_sentence(t):
        return t
    ms = list(_SENT_END.finditer(t))
    return t[: ms[-1].end()].rstrip() if ms else t


def recover_descriptions(pdf_path: Path, habilidades: list[dict[str, Any]]) -> int:
    """Recupera, por isolamento de CÉLULA, descrições sinalizadas como ruins.

    Casos-limite (fronteira de seção, mis-split) que o fluxo por coluna não resolve:
    reextrai a habilidade a partir da sua célula exata (coluna pelo cluster de
    código mais próximo; linhas entre este código e o próximo da mesma coluna).
    Entre páginas espelhadas escolhe o candidato mais CURTO que termina em
    pontuação de frase (o mais longo costuma invadir a célula seguinte). Só
    substitui quando o recuperado é claramente melhor — nunca degrada os bons.
    """

    def _is_bad(d: str) -> bool:
        return (
            len(d) < 40
            or len(d) > 1000
            or bool(NOISE_SENTINELS.search(d[40:]))
            or bool(re.search(r"\((?:EF|EM|EI)\d{2}[A-Z]{2,3}\d{2,3}\)", d))  # fusão de códigos
            or not _ends_sentence(d)  # sem pontuação final → provável truncamento
        )

    bad = {h["codigo"]: h for h in habilidades if _is_bad(h["descricao"])}
    if not bad:
        return 0

    cands: dict[str, list[str]] = {c: [] for c in bad}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            try:
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            except Exception:  # pragma: no cover
                continue
            code_ws = [
                (m.group(1), w) for w in words if (m := RE_CODE_TOKEN.match(w["text"])) is not None
            ]
            present = [c for c, _ in code_ws if c in bad]
            if not present:
                continue
            lefts = _code_clusters([w["x0"] for _, w in code_ws], gap=100.0)
            col_lefts = [left for left, _ in lefts]
            for codigo in present:
                cw = next(w for c, w in code_ws if c == codigo)
                my = max(cl for cl in col_lefts if cl <= cw["x0"] + 6)
                mi = col_lefts.index(my)
                col_right = col_lefts[mi + 1] if mi + 1 < len(col_lefts) else my + 10000.0
                mt = cw["top"]
                col_tops = [w["top"] for _, w in code_ws if my - 6 <= w["x0"] < col_right]
                next_top = min((t for t in col_tops if t > mt + 2), default=1e9)
                cell = [
                    w
                    for w in words
                    if my - 6 <= w["x0"] < col_right
                    and mt - 2 <= w["top"] < next_top
                    and not RE_CODE_TOKEN.match(w["text"])
                    and (w["top"] > mt + 3 or w["x0"] > cw["x0"])
                ]
                cell.sort(key=lambda w: (round(w["top"]), w["x0"]))
                cands[codigo].append(clean_description(" ".join(w["text"] for w in cell)))

    fixed = 0
    for codigo, h in bad.items():
        best = ""
        for t in cands[codigo]:
            # Habilidade oficial SEMPRE começa por verbo capitalizado; um candidato
            # que começa minúsculo é fragmento de apêndice/exemplo — descartar.
            if not t[:1].isupper():
                continue
            tt = _trim_to_sentence(t)  # remove o bleed da célula seguinte
            if (
                _ends_sentence(tt)
                and 40 <= len(tt) <= 1000
                and not NOISE_SENTINELS.search(tt[40:])
                and len(tt) > len(best)
            ):
                best = tt
        # Só substitui se recuperou algo válido E diferente da descrição atual ruim.
        if best and best != h["descricao"]:
            h["descricao"] = best
            fixed += 1
    return fixed


def right_column_text(pdf_path: Path) -> str:
    """Concatena, em ordem de leitura, a(s) coluna(s) de HABILIDADES.

    Em alguns spreads a coluna HABILIDADES aparece em DUAS sub-colunas lado a lado
    (duas habilidades em paralelo, p.ex. Língua Portuguesa dos anos iniciais). Um
    sort global por (top, x0) intercalaria as sub-colunas e truncaria a descrição
    no código vizinho. Por isso: só tratamos como sub-colunas quando há DUAS
    "colunas" de códigos, cada uma com ≥2 códigos (um código solto e distante é
    ruído, não uma sub-coluna). Fora esse caso, lemos uma única coluna sem limite
    de largura à direita — a contaminação de cabeçalho é removida por
    `clean_description` (NOISE_SENTINELS), evitando o truncamento de descrições
    largas de coluna única.
    """
    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            try:
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            except Exception as e:  # pragma: no cover - página problemática
                logger.warning("Falha ao ler página em %s: %s", pdf_path.name, e)
                continue
            if not words:
                continue
            code_x0 = [w["x0"] for w in words if RE_CODE_TOKEN.match(w["text"])]
            if not code_x0:
                continue
            clusters = _code_clusters(code_x0)
            sub_cols = [left for left, count in clusters if count >= 2]
            if len(sub_cols) < 2:
                # Coluna única: da borda esquerda do código mais à esquerda em diante.
                sub_cols = [min(left for left, _ in clusters)]
            for i, left in enumerate(sub_cols):
                col_left = left - 3.0
                # Direita = próxima sub-coluna; a última/única é ilimitada.
                col_right = (sub_cols[i + 1] - 3.0) if i + 1 < len(sub_cols) else float("inf")
                col = [w for w in words if col_left <= w["x0"] < col_right]
                col.sort(key=lambda w: (round(w["top"]), w["x0"]))
                parts.append(" ".join(w["text"] for w in col))
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Isolamento das 3 colunas da Educação Infantil (uma coluna por faixa etária)
# --------------------------------------------------------------------------- #
def _ei_page_column_texts(words: list[dict[str, Any]]) -> list[str]:
    """Reconstroi, em ordem de leitura, o texto de cada coluna (faixa etária) de
    uma página de tabela da EI.

    A borda esquerda de cada coluna é dada pelo x0 do código `(EIxxYYnn)` (faixa =
    dígitos 01/02/03). Como o texto justificado de uma coluna transborda a metade
    do vão até quase a borda esquerda da coluna seguinte, associar por *ponto médio*
    embaralharia as colunas; por isso cada palavra é atribuída à coluna cuja borda
    esquerda é a MAIOR que ainda seja <= x0 da palavra (com pequena tolerância).

    Retorna uma lista de strings — uma por faixa (esquerda→direita). Cada string é
    fatiada por código separadamente pelo chamador, para que a última descrição de
    uma coluna não absorva o cabeçalho da coluna seguinte.
    """
    code_words = [w for w in words if RE_EI_CODE_TOKEN.match(w["text"])]
    if not code_words:
        return []
    # Borda esquerda por faixa (mínimo x0 dos códigos daquela faixa na página).
    left_by_faixa: dict[str, float] = {}
    for w in code_words:
        m = RE_EI_CODE_TOKEN.match(w["text"])
        faixa = m.group(1)[2:4]
        if faixa not in left_by_faixa or w["x0"] < left_by_faixa[faixa]:
            left_by_faixa[faixa] = w["x0"]
    lefts = sorted(left_by_faixa.items(), key=lambda kv: kv[1])  # [(faixa, x0), ...]

    cols: dict[str, list[dict[str, Any]]] = {faixa: [] for faixa, _ in lefts}
    for w in words:
        chosen: str | None = None
        for faixa, left in lefts:
            if w["x0"] >= left - 6.0:
                chosen = faixa
        if chosen is not None:
            cols[chosen].append(w)

    texts: list[str] = []
    for faixa, _ in lefts:
        ordered = sorted(cols[faixa], key=lambda w: (round(w["top"]), w["x0"]))
        texts.append(" ".join(w["text"] for w in ordered))
    return texts


def ei_column_texts(original_pdf: Path) -> list[str]:
    """Normaliza o PDF oficial completo com pikepdf e devolve o texto de cada coluna
    (faixa) das páginas de tabela da EI.

    O `BNCC_20dez_site.pdf` tem a árvore de páginas comprimida — o pdfplumber sozinho
    enxerga só 1 página. Reescrevê-lo com pikepdf destrava a leitura das 472 páginas
    com coordenadas. O arquivo normalizado é temporário e removido ao final (nunca é
    versionado).
    """
    fd, norm_name = tempfile.mkstemp(prefix="bncc_norm_", suffix=".pdf")
    os.close(fd)
    norm_path = Path(norm_name)
    out: list[str] = []
    try:
        # pikepdf pode logar "Error occurred parsing XMP" — inofensivo (só metadados).
        with pikepdf.open(str(original_pdf)) as pk:
            pk.save(str(norm_path))
        with pdfplumber.open(str(norm_path)) as pdf:
            for idx, page in enumerate(pdf.pages):
                if idx < EI_FRONTMATTER_SKIP_PAGES:
                    continue  # prefácio/material explicativo (inclui o exemplo EI02TS01)
                try:
                    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
                except Exception as e:  # pragma: no cover - página problemática
                    logger.warning("Falha ao ler página %d da EI: %s", idx, e)
                    continue
                if not any(RE_EI_CODE_TOKEN.match(w["text"]) for w in words):
                    continue
                page_text = " ".join(w["text"] for w in words)
                if EI_EXPLANATION_SENTINELS.search(page_text):
                    continue  # guarda contra a página-exemplo (código ilustrativo)
                out.extend(_ei_page_column_texts(words))
    finally:
        try:
            norm_path.unlink()
        except OSError:  # pragma: no cover
            pass
    return out


def _split_by_codes(text: str, regex: re.Pattern) -> list[tuple[str, str]]:
    matches = list(regex.finditer(text))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[start:end]))
    return out


# --------------------------------------------------------------------------- #
# Relações do Ensino Fundamental: unidade temática + objeto de conhecimento
# --------------------------------------------------------------------------- #
# As tabelas do EF têm 3 colunas: a esquerda agrupa (UNIDADES TEMÁTICAS, ou
# PRÁTICAS DE LINGUAGEM/CAMPOS DE ATUAÇÃO em Língua Portuguesa, ou EIXOS em Língua
# Inglesa), a do meio traz os OBJETOS DE CONHECIMENTO e a direita as HABILIDADES.
# `right_column_text` já isola a descrição das habilidades; aqui reconstruímos as
# duas colunas da esquerda alinhadas por linha para associar cada código à sua
# unidade temática e ao seu objeto de conhecimento (relação navegável — FR-005).
# Coordenadas: cada "spread" oficial aparece como duas páginas espelhadas (uma
# deslocada ~-595pt); o cabeçalho se repete em ambas, então usamos a posição dos
# rótulos do cabeçalho para delimitar as colunas em qualquer página.
RE_CODE_EF = re.compile(r"^\(?(" + RE_EF + r")\)?[.,;:]?$")
# Rótulo do cabeçalho na coluna da esquerda (varia por componente).
_LEFT_HEADER = {"UNIDADES", "PRÁTICAS", "CAMPOS", "EIXOS", "EIXO"}
# Ruído que nunca é nome de unidade temática/objeto (cabeçalho/rodapé/seção).
_REL_NOISE = re.compile(
    r"BASE NACIONAL|COMUM CURRICULAR|UNIDADES TEM|OBJETOS DE CONHE|^HABILIDADES$|"
    r"COMPET[ÊE]NCIAS|PR[ÁA]TICAS DE LINGUAGEM|CAMPOS? DE ATUA|^EIXOS?$|"
    r"ENSINO\s+FUNDAMENTAL|ANO$|^\d+.?$"
)
# Faixas/banners que atravessam a coluna esquerda mas NÃO são unidade temática:
# campos de atuação (Língua Portuguesa), eixos (Língua Inglesa), o rótulo "UNIDADE
# TEMÁTICA" repetido e títulos de seção. O nome real da unidade temática é sempre
# em caixa Título (ex.: "Números", "Interação discursiva"); banners e cabeçalhos de
# componente vêm em CAIXA ALTA — usamos isso como sinal robusto.
_REL_BANNER = re.compile(
    r"^\s*(CAMPO\b|TODOS OS CAMPOS|EIXO\b|UNIDADE[S]?\s+TEM[ÁA]TICA|"
    r"PR[ÁA]TICAS\s+DE\s+LINGUAGEM|OBJETOS?\s+DE\s+CONHE)",
    re.IGNORECASE,
)
_REL_SECTION = re.compile(r"\d\.\d")
# Nome do EIXO (Língua Inglesa): "EIXO ORALIDADE – ..." → "ORALIDADE". O eixo é o
# organizador que o usuário pede como unidade temática da Língua Inglesa; os 5 são
# ORALIDADE, LEITURA, ESCRITA, CONHECIMENTOS LINGUÍSTICOS, DIMENSÃO INTERCULTURAL.
_EIXO_RE = re.compile(r"^EIXO\s+([A-ZÀ-Ú][A-ZÀ-Ú\s]+?)(?=\s+[–-]|\s+[a-zà-ú]|$)")


def _is_rel_noise(s: str) -> bool:
    """True se `s` for banner/cabeçalho/rótulo — não um nome de unidade/objeto."""
    if not s:
        return True
    if _REL_NOISE.search(s) or _REL_BANNER.match(s) or _REL_SECTION.search(s):
        return True
    if "DE ATUA" in s.upper():
        return True
    letters = [c for c in s if c.isalpha()]
    # Cabeçalho de componente / banner em CAIXA ALTA (ex.: "LÍNGUA PORTUGUESA – 3º",
    # "EIXO ORALIDADE", "CAMPO DA VIDA COTIDIANA"). Unidades reais são caixa Título.
    if len(letters) >= 6 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        return True
    return False


def _clean_rel(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    # Cabeçalhos de continuação de página repetem o nome como "(Continuação) X" —
    # remove o prefixo para não duplicar a unidade temática/objeto.
    s = re.sub(r"^\(\s*continua[çc][ãa]o\s*\)\s*", "", s, flags=re.IGNORECASE)
    return s


def _ef_header_bounds(words: list[dict[str, Any]]) -> tuple[float, float, float] | None:
    """Deriva (x da coluna esquerda, x de OBJETOS, x de HABILIDADES) do cabeçalho."""
    by_line: dict[int, dict[str, float]] = {}
    for w in words:
        t = w["text"].upper()
        line = by_line.setdefault(round(w["top"]), {})
        if t in _LEFT_HEADER:
            line.setdefault("ut", w["x0"])
        elif t == "OBJETOS":
            line["obj"] = w["x0"]
        elif t == "HABILIDADES":
            line["hab"] = w["x0"]
    for d in by_line.values():
        if "obj" in d and "hab" in d:
            return d.get("ut", d["obj"] - 230.0), d["obj"], d["hab"]
    return None


def _group_by_line(words: list[dict[str, Any]], tol: int = 3) -> list[list[dict[str, Any]]]:
    lines: dict[int, list[dict[str, Any]]] = {}
    for w in words:
        lines.setdefault(round(w["top"] / tol), []).append(w)
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in sorted(lines.items())]


def ef_relations(pdf_path: Path) -> dict[str, tuple[str, str]]:
    """Mapeia cada código EF -> (unidade_tematica, objeto_conhecimento).

    Reconstrói as colunas esquerda/meio por coordenada (cabeçalho define as bordas;
    reaproveitado entre páginas quando ausente) e faz fluxo vertical: a unidade
    temática e o objeto "grudam" para baixo até surgir um novo valor na coluna;
    o objeto acumula linhas até o código a que pertence (nomes multi-linha).
    """
    assoc: dict[str, tuple[str, str]] = {}
    carry: tuple[float, float, float] | None = None
    # cur_ut/cur_eixo são "carregados" ENTRE páginas (a coluna da esquerda pode ter o
    # rótulo em uma página e as habilidades na seguinte). Só zeramos quando o
    # componente muda, para não vazar a unidade temática de um componente no outro.
    cur_ut = ""
    cur_eixo = ""
    prev_comp: str | None = None
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            try:
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            except Exception as e:  # pragma: no cover - página problemática
                logger.warning("Falha ao ler página de relações EF: %s", e)
                continue
            page_codes = [w for w in words if RE_CODE_EF.match(w["text"])]
            if not page_codes:
                continue
            bounds = _ef_header_bounds(words)
            if bounds:
                carry = bounds
            if carry is None:
                continue
            ut_x, obj_x, hab_x = carry
            page_comp = RE_CODE_EF.match(page_codes[0]["text"]).group(1)[4:6]  # type: ignore[union-attr]
            if page_comp != prev_comp:
                cur_ut = ""
                cur_eixo = ""
            prev_comp = page_comp
            ut_parts: list[str] = []
            obj_parts: list[str] = []
            ut_emitted = False
            obj_emitted = False
            for ws in _group_by_line(words):
                ut = _clean_rel(" ".join(w["text"] for w in ws if ut_x - 6 <= w["x0"] < obj_x - 6))
                obj = _clean_rel(
                    " ".join(w["text"] for w in ws if obj_x - 6 <= w["x0"] < hab_x - 6)
                )
                codes = [
                    RE_CODE_EF.match(w["text"]).group(1)  # type: ignore[union-attr]
                    for w in ws
                    if RE_CODE_EF.match(w["text"]) and w["x0"] >= hab_x - 6
                ]
                eixo_m = _EIXO_RE.match(ut)
                if eixo_m:
                    # Banner de EIXO (Língua Inglesa): guarda o nome, não é unidade.
                    cur_eixo = eixo_m.group(1).strip().title()
                elif ut.startswith("(") and cur_ut and not _is_rel_noise(ut):
                    # Qualificador entre parênteses (ex.: prática "Análise
                    # linguística/semiótica (Alfabetização)"/"(Ortografização)",
                    # "Leitura/escuta (compartilhada e autônoma)"): anexa ao nome
                    # base, substituindo um qualificador anterior se houver.
                    base = re.sub(r"\s*\([^)]*\)\s*$", "", cur_ut).strip()
                    cur_ut = _clean_rel(f"{base} {ut}")
                    ut_parts = [cur_ut]
                elif ut and not _is_rel_noise(ut):
                    if ut_emitted:
                        ut_parts = []
                        ut_emitted = False
                    ut_parts.append(ut)
                    cur_ut = _clean_rel(" ".join(ut_parts))
                if obj and not _is_rel_noise(obj):
                    if obj_emitted:
                        obj_parts = []
                        obj_emitted = False
                    obj_parts.append(obj)
                if codes:
                    cur_obj = _clean_rel(" ".join(obj_parts))
                    for c in codes:
                        # Língua Inglesa: o organizador pedido é o EIXO; demais
                        # componentes usam a coluna da esquerda (unidade temática ou,
                        # em Língua Portuguesa, a prática de linguagem).
                        ut_val = cur_eixo if c[4:6] == "LI" else cur_ut
                        assoc.setdefault(c, (ut_val, cur_obj))
                    ut_emitted = True
                    obj_emitted = True
    return assoc


# --------------------------------------------------------------------------- #
# Competências específicas (catálogo oficial por área/componente)
# --------------------------------------------------------------------------- #
# As competências específicas aparecem em seções com cabeçalho em CAIXA ALTA
# "COMPETÊNCIAS ESPECÍFICAS DE <área/componente> ... PARA O ENSINO <etapa>",
# seguidas de uma lista numerada (1..N). Diferente das tabelas de habilidades, o
# texto em prosa dessas seções sofre corrupção de ligaduras fi/fl na extração
# (ex.: "classifi cá-la"); reparamos isso para restaurar o texto oficial fiel.
_CE_HEAD = re.compile(
    r"COMPET[ÊE]NCIAS?\s+ESPEC[ÍI]FICAS?\s+DE\s+(.+?)\s+PARA\s+O\s+ENSINO", re.IGNORECASE | re.S
)
_CE_NUM = re.compile(r"(?ms)^\s*(\d{1,2})\.\s+(.+?)(?=^\s*\d{1,2}\.\s|\Z)")
_CE_FOOTER = re.compile(
    r"BASE NACIONAL|COMUM CURRICULAR|^\d{1,4}$|ENSINO\s+M[ÉE]DIO$|"
    r"ENSINO\s+FUNDAMENTAL$|E SUAS TECNOLOGIAS$|SOCIAIS APLICADAS$",
    re.IGNORECASE,
)
_LIG1 = re.compile(r"([a-zá-úâ-ûà-ù0-9])f([il])\s+([a-zá-úâ-ûà-ù])", re.IGNORECASE)
_LIG2 = re.compile(r"([a-zá-úâ-ûà-ù])-\s*f([il])\s+([a-zá-úâ-ûà-ù])", re.IGNORECASE)


def _fix_ligatures(s: str) -> str:
    """Rejunta palavras quebradas pela falha de ligadura fi/fl na extração."""
    prev = None
    while prev != s:
        prev = s
        s = _LIG1.sub(r"\1f\2\3", s)
        s = _LIG2.sub(r"\1f\2\3", s)
    s = re.sub(r"\bfl\s+([a-zá-úâ-û])", r"fl\1", s, flags=re.IGNORECASE)
    return s


# Cabeçalho (normalizado, sem acentos-issue) -> (área, componente, tag do código).
# O tag do Ensino Médio coincide com o trigrama do código (LGG/MAT/CNT/CHS) para
# permitir o vínculo determinístico habilidade→competência.
_CE_MAP: dict[str, tuple[str, str | None, str]] = {
    # Ensino Médio (áreas)
    "LINGUAGENS E SUAS TECNOLOGIAS": ("linguagens", None, "LGG"),
    "MATEMÁTICA E SUAS TECNOLOGIAS": ("matematica", None, "MAT"),
    "CIÊNCIAS DA NATUREZA E SUAS TECNOLOGIAS": ("ciencias_natureza", None, "CNT"),
    "CIÊNCIAS HUMANAS E SOCIAIS APLICADAS": ("ciencias_humanas", None, "CHS"),
    # Ensino Fundamental (áreas)
    "LINGUAGENS": ("linguagens", None, "LGG"),
    "MATEMÁTICA": ("matematica", None, "MAT"),
    "CIÊNCIAS DA NATUREZA": ("ciencias_natureza", None, "CNT"),
    "CIÊNCIAS HUMANAS": ("ciencias_humanas", None, "CHS"),
    # Ensino Fundamental (componentes)
    "LÍNGUA PORTUGUESA": ("linguagens", "lingua_portuguesa", "LP"),
    "ARTE": ("linguagens", "arte", "AR"),
    "EDUCAÇÃO FÍSICA": ("linguagens", "educacao_fisica", "EF"),
    "LÍNGUA INGLESA": ("linguagens", "lingua_inglesa", "LI"),
    "GEOGRAFIA": ("ciencias_humanas", "geografia", "GE"),
    "HISTÓRIA": ("ciencias_humanas", "historia", "HI"),
    "CIÊNCIAS": ("ciencias_natureza", "ciencias", "CI"),
    "ENSINO RELIGIOSO": ("ensino_religioso", "ensino_religioso", "ER"),
}


def extract_competencias_especificas(pdf_path: Path, etapa: str) -> list[dict[str, Any]]:
    """Extrai o catálogo oficial de competências específicas por área/componente.

    Retorna entidades navegáveis (código, número, área, componente, etapa,
    descrição). NÃO afirma vínculo por habilidade — a fonte não o codifica para
    EF/EM-Língua Portuguesa (Princípio IV; escolha "catálogo sem vínculo").
    """
    prefix = "EM" if etapa == "ensino_medio" else "EF"
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, txt in enumerate(pages):
        m = _CE_HEAD.search(txt.replace("\n", " "))
        if not m:
            continue
        area_txt = _fix_ligatures(re.sub(r"\s+", " ", m.group(1)).strip()).upper()
        mapping = _CE_MAP.get(area_txt)
        if not mapping:
            logger.warning("Cabeçalho de competência específica não mapeado: %r", area_txt)
            continue
        area, componente, tag = mapping
        if tag in seen:
            continue  # primeira ocorrência (cabeçalho pode repetir em páginas de tabela)
        # Acumula o texto do cabeçalho por algumas páginas, parando nas habilidades.
        buf: list[str] = []
        for j in range(i, min(i + 5, len(pages))):
            stop = False
            for line in pages[j].split("\n"):
                if re.search(r"\((?:EM|EF)\d", line):
                    stop = True
                    break
                if _CE_FOOTER.search(line.strip()):
                    continue
                buf.append(line)
            if stop:
                break
        # Começa a leitura na LINHA do cabeçalho em CAIXA ALTA (a prosa introdutória
        # usa "competências específicas" em minúsculas; o cabeçalho real é maiúsculo).
        # Não ancoramos em "PARA O ENSINO": quando o cabeçalho quebra em duas linhas,
        # a 2ª ("ENSINO FUNDAMENTAL/MÉDIO") é removida como rodapé e a âncora falharia.
        start = 0
        for k, line in enumerate(buf):
            if re.match(r"\s*COMPET[ÊE]NCIAS?\s+ESPEC[ÍI]FICAS?\b", line):
                start = k
                break
        chunk = "\n".join(buf[start:])
        numero = 0
        for n_str, raw in _CE_NUM.findall(chunk):
            desc = _fix_ligatures(re.sub(r"\s+", " ", raw).strip())
            if int(n_str) != numero + 1 or len(desc) < 40:
                break  # lista deve ser consecutiva 1..N; corta ruído
            numero += 1
            out.append(
                {
                    "codigo": f"{prefix}{tag}{numero:02d}",
                    "numero": numero,
                    "area_conhecimento": area,
                    "componente": componente,
                    "descricao": desc,
                    "etapa": etapa,
                }
            )
        if numero:
            seen.add(tag)
    return out


# --------------------------------------------------------------------------- #
# Parsers por etapa
# --------------------------------------------------------------------------- #
def _dedup_longest(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for it in items:
        cur = best.get(it["codigo"])
        if cur is None or len(it["descricao"]) > len(cur["descricao"]):
            best[it["codigo"]] = it
    return sorted(best.values(), key=lambda h: h["codigo"])


def parse_ef(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for codigo, raw in _split_by_codes(text, RE_SPLIT_EF):
        mapping = EF_COMPONENTE.get(codigo[4:6])
        if not mapping:
            continue
        componente, area = mapping
        desc = clean_description(raw)
        if len(desc) < 12:
            continue
        out.append(
            {
                "codigo": codigo,
                "descricao": desc,
                "etapa": "ensino_fundamental",
                "anos": anos_from_ef(codigo[2:4]),
                "area_conhecimento": area,
                "componente": componente,
                "competencias_gerais": [],
                "competencias_especificas": [],
                "objetos_conhecimento": [],
            }
        )
    return _dedup_longest(out)


def parse_em(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for codigo, raw in _split_by_codes(text, RE_SPLIT_EM):
        if len(codigo) == 10:  # EM13 + 3 letras + 3 dígitos (por área)
            area = EM_AREA.get(codigo[4:7])
            componente = None
        else:  # EM13 + 2 letras + 2 dígitos (Língua Portuguesa)
            area = "linguagens"
            componente = "lingua_portuguesa"
        if not area:
            continue
        desc = clean_description(raw)
        if len(desc) < 12:
            continue
        out.append(
            {
                "codigo": codigo,
                "descricao": desc,
                "etapa": "ensino_medio",
                "anos": ["1", "2", "3"],
                "area_conhecimento": area,
                "componente": componente,
                "competencias_gerais": [],
                "competencias_especificas": [],
                "objetos_conhecimento": [],
            }
        )
    return _dedup_longest(out)


def parse_ei(text: str) -> list[dict[str, Any]]:
    """Parser da Educação Infantil (ativa apenas com fonte dedicada — T024)."""
    out: list[dict[str, Any]] = []
    for codigo, raw in _split_by_codes(text, RE_SPLIT_EI):
        desc = clean_description(raw)
        if len(desc) < 12:
            continue
        campo = codigo[4:6]
        out.append(
            {
                "codigo": codigo,
                "descricao": desc,
                "etapa": "educacao_infantil",
                "anos": [codigo[2:4]],
                "area_conhecimento": "linguagens",
                "componente": None,
                "competencias_gerais": [],
                "competencias_especificas": [],
                "objetos_conhecimento": [],
                "campo_experiencia": EI_CAMPO.get(campo, campo),
            }
        )
    return _dedup_longest(out)


# --------------------------------------------------------------------------- #
# Competências gerais (texto oficial fixo — 10 registros, SC-001)
# --------------------------------------------------------------------------- #
COMPETENCIAS_GERAIS: list[dict[str, Any]] = [
    {
        "numero": 1,
        "titulo": "Conhecimento",
        "descricao": "Valorizar e utilizar os conhecimentos historicamente construídos sobre o mundo físico, social, cultural e digital para entender e explicar a realidade, continuar aprendendo e colaborar para a construção de uma sociedade justa, democrática e inclusiva.",  # noqa: E501
    },
    {
        "numero": 2,
        "titulo": "Pensamento científico, crítico e criativo",
        "descricao": "Exercitar a curiosidade intelectual e recorrer à abordagem própria das ciências, incluindo a investigação, a reflexão, a análise crítica, a imaginação e a criatividade, para investigar causas, elaborar e testar hipóteses, formular e resolver problemas e criar soluções (inclusive tecnológicas) com base nos conhecimentos das diferentes áreas.",  # noqa: E501
    },
    {
        "numero": 3,
        "titulo": "Repertório cultural",
        "descricao": "Valorizar e fruir as diversas manifestações artísticas e culturais, das locais às mundiais, e também participar de práticas diversificadas da produção artístico-cultural.",  # noqa: E501
    },
    {
        "numero": 4,
        "titulo": "Comunicação",
        "descricao": "Utilizar diferentes linguagens – verbal (oral ou visual-motora, como Libras, e escrita), corporal, visual, sonora e digital –, bem como conhecimentos das linguagens artística, matemática e científica, para se expressar e partilhar informações, experiências, ideias e sentimentos em diferentes contextos e produzir sentidos que levem ao entendimento mútuo.",  # noqa: E501
    },
    {
        "numero": 5,
        "titulo": "Cultura digital",
        "descricao": "Compreender, utilizar e criar tecnologias digitais de informação e comunicação de forma crítica, significativa, reflexiva e ética nas diversas práticas sociais (incluindo as escolares) para se comunicar, acessar e disseminar informações, produzir conhecimentos, resolver problemas e exercer protagonismo e autoria na vida pessoal e coletiva.",  # noqa: E501
    },
    {
        "numero": 6,
        "titulo": "Trabalho e projeto de vida",
        "descricao": "Valorizar a diversidade de saberes e vivências culturais e apropriar-se de conhecimentos e experiências que lhe possibilitem entender as relações próprias do mundo do trabalho e fazer escolhas alinhadas ao exercício da cidadania e ao seu projeto de vida, com liberdade, autonomia, consciência crítica e responsabilidade.",  # noqa: E501
    },
    {
        "numero": 7,
        "titulo": "Argumentação",
        "descricao": "Argumentar com base em fatos, dados e informações confiáveis, para formular, negociar e defender ideias, pontos de vista e decisões comuns que respeitem e promovam os direitos humanos, a consciência socioambiental e o consumo responsável em âmbito local, regional e global, com posicionamento ético em relação ao cuidado de si mesmo, dos outros e do planeta.",  # noqa: E501
    },
    {
        "numero": 8,
        "titulo": "Autoconhecimento e autocuidado",
        "descricao": "Conhecer-se, apreciar-se e cuidar de sua saúde física e emocional, compreendendo-se na diversidade humana e reconhecendo suas emoções e as dos outros, com autocrítica e capacidade para lidar com elas.",  # noqa: E501
    },
    {
        "numero": 9,
        "titulo": "Empatia e cooperação",
        "descricao": "Exercitar a empatia, o diálogo, a resolução de conflitos e a cooperação, fazendo-se respeitar e promovendo o respeito ao outro e aos direitos humanos, com acolhimento e valorização da diversidade de indivíduos e de grupos sociais, seus saberes, identidades, culturas e potencialidades, sem preconceitos de qualquer natureza.",  # noqa: E501
    },
    {
        "numero": 10,
        "titulo": "Responsabilidade e cidadania",
        "descricao": "Agir pessoal e coletivamente com autonomia, responsabilidade, flexibilidade, resiliência e determinação, tomando decisões com base em princípios éticos, democráticos, inclusivos, sustentáveis e solidários.",  # noqa: E501
    },
]


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def build_snapshot() -> dict[str, Any]:
    habilidades: list[dict[str, Any]] = []
    checksums: dict[str, str] = {}
    missing_sources: list[str] = []
    competencias_especificas: list[dict[str, Any]] = []

    if PDF_EF.exists():
        logger.info("Extraindo Ensino Fundamental de %s ...", PDF_EF.name)
        ef = parse_ef(right_column_text(PDF_EF))
        # Associa unidade temática + objeto de conhecimento (relações navegáveis).
        rel = ef_relations(PDF_EF)
        n_ut = 0
        for h in ef:
            ut, obj = rel.get(h["codigo"], ("", ""))
            if ut:
                h["unidade_tematica"] = ut
                n_ut += 1
            if obj:
                h["objetos_conhecimento"] = [obj]
        n_rec = recover_descriptions(PDF_EF, ef)
        if n_rec:
            logger.info("  -> %d descrições EF recuperadas por célula", n_rec)
        habilidades.extend(ef)
        # Catálogo de competências específicas do EF (sem vínculo por habilidade).
        ce_ef = extract_competencias_especificas(PDF_EF, "ensino_fundamental")
        competencias_especificas.extend(ce_ef)
        checksums["ensino_fundamental"] = sha256_of(PDF_EF)
        logger.info(
            "  -> %d habilidades EF (%d com unidade temática); %d competências específicas",
            len(ef),
            n_ut,
            len(ce_ef),
        )
    else:
        logger.warning("Fonte do Ensino Fundamental ausente: %s", PDF_EF)
        missing_sources.append("ensino_fundamental")

    if PDF_EM.exists():
        logger.info("Extraindo Ensino Médio de %s ...", PDF_EM.name)
        em = parse_em(right_column_text(PDF_EM))
        # Competência específica por código: EM13AAAn## → competência n da área AAA.
        # (EM Língua Portuguesa — EM13LP## — não codifica a competência; fica sem
        # vínculo, mas o catálogo de Linguagens está disponível para navegação.)
        for h in em:
            c = h["codigo"]
            if len(c) == 10:
                h["competencias_especificas"] = [f"EM{c[4:7]}{int(c[7]):02d}"]
        n_rec = recover_descriptions(PDF_EM, em)
        if n_rec:
            logger.info("  -> %d descrições EM recuperadas por célula", n_rec)
        habilidades.extend(em)
        ce_em = extract_competencias_especificas(PDF_EM, "ensino_medio")
        competencias_especificas.extend(ce_em)
        checksums["ensino_medio"] = sha256_of(PDF_EM)
        logger.info(
            "  -> %d habilidades EM; %d competências específicas de área", len(em), len(ce_em)
        )
    else:
        logger.warning("Fonte do Ensino Médio ausente: %s", PDF_EM)
        missing_sources.append("ensino_medio")

    # Complemento de Computação à BNCC (Parecer CNE/CP 02/2022) — habilidades das
    # três etapas com o par oficial `CO`. Extração isolada em módulo próprio.
    if PDF_COMPUTACAO.exists():
        from scripts.extract_bncc_computacao import extract as extract_computacao

        logger.info("Extraindo Complemento de Computação de %s ...", PDF_COMPUTACAO.name)
        comp = extract_computacao(PDF_COMPUTACAO)
        n_rec = recover_descriptions(PDF_COMPUTACAO, comp)
        if n_rec:
            logger.info("  -> %d descrições de Computação recuperadas por célula", n_rec)
        habilidades.extend(comp)
        checksums["computacao"] = sha256_of(PDF_COMPUTACAO)
        logger.info("  -> %d habilidades de Computação", len(comp))
    else:
        logger.warning("Fonte da Computação ausente: %s", PDF_COMPUTACAO)
        missing_sources.append("computacao")

    ei_source = PDF_EI_SITE if PDF_EI_SITE.exists() else (PDF_EI if PDF_EI.exists() else None)
    if ei_source is not None:
        logger.info(
            "Extraindo Educação Infantil de %s (normalizado via pikepdf) ...",
            ei_source.name,
        )
        # Cada coluna (faixa) é fatiada por código separadamente e depois combinada;
        # assim a última descrição de uma coluna não absorve o cabeçalho da seguinte.
        ei: list[dict[str, Any]] = []
        for col_text in ei_column_texts(ei_source):
            ei.extend(parse_ei(col_text))
        ei = _dedup_longest(ei)
        habilidades.extend(ei)
        checksums["educacao_infantil"] = sha256_of(ei_source)  # proveniência do original
        logger.info("  -> %d objetivos/habilidades EI", len(ei))
    else:
        logger.warning(
            "Fonte oficial da Educação Infantil AUSENTE (%s). "
            "Registrando contagem 0 + missing_sources; NENHUM dado de EI fabricado.",
            PDF_EI_SITE.name,
        )
        missing_sources.append("educacao_infantil")

    # Deduplicação global final por código.
    habilidades = _dedup_longest(habilidades)

    # Rede de segurança (qualquer fonte): um código de habilidade embutido marca o
    # início da próxima (fusão) — corta ali. Cobre também a Computação, cuja
    # extração é feita em módulo próprio.
    for h in habilidades:
        cm = _EMBEDDED_CODE.search(h["descricao"])
        if cm and cm.start() > 30:
            h["descricao"] = h["descricao"][: cm.start()].rstrip()

    # ------------------------------------------------------------------ #
    # Coleções navegáveis de topo, derivadas das relações das habilidades.
    # ------------------------------------------------------------------ #
    unidades_tematicas: list[dict[str, Any]] = []
    objetos_conhecimento: list[dict[str, Any]] = []
    seen_ut: set[tuple[str, str | None, str]] = set()
    seen_obj: set[tuple[str, str, str | None, str]] = set()
    for h in habilidades:
        etapa = h["etapa"]
        comp = h.get("componente")
        ut = h.get("unidade_tematica")
        if ut:
            key_ut = (ut, comp, etapa)
            if key_ut not in seen_ut:
                seen_ut.add(key_ut)
                unidades_tematicas.append({"nome": ut, "componente": comp, "etapa": etapa})
        for obj in h.get("objetos_conhecimento") or []:
            key_obj = (obj, ut or "", comp, etapa)
            if key_obj not in seen_obj:
                seen_obj.add(key_obj)
                objetos_conhecimento.append(
                    {
                        "nome": obj,
                        "unidade_tematica": ut,
                        "componente": comp,
                        "etapa": etapa,
                    }
                )
    unidades_tematicas.sort(key=lambda u: (u["etapa"], u["componente"] or "", u["nome"]))
    objetos_conhecimento.sort(
        key=lambda o: (o["etapa"], o["componente"] or "", o["unidade_tematica"] or "", o["nome"])
    )

    # Campos de experiência da Educação Infantil (com seus objetivos).
    nome_para_cod = {v: k for k, v in EI_CAMPO.items()}
    objetivos_por_campo: dict[str, list[dict[str, str]]] = {}
    for h in habilidades:
        if h["etapa"] != "educacao_infantil":
            continue
        nome = h.get("campo_experiencia")
        if not nome:
            continue
        objetivos_por_campo.setdefault(nome, []).append(
            {"codigo": h["codigo"], "descricao": h["descricao"]}
        )
    campos_experiencia: list[dict[str, Any]] = []
    for nome, objetivos in objetivos_por_campo.items():
        campos_experiencia.append(
            {
                "codigo": nome_para_cod.get(nome, nome),
                "nome": nome,
                "objetivos_aprendizagem": sorted(objetivos, key=lambda o: o["codigo"]),
            }
        )
    campos_experiencia.sort(key=lambda c: c["codigo"])

    por_etapa: dict[str, int] = {
        "educacao_infantil": 0,
        "ensino_fundamental": 0,
        "ensino_medio": 0,
    }
    por_componente: dict[str, int] = {}
    computacao_por_etapa: dict[str, int] = {}
    computacao_por_eixo: dict[str, int] = {}
    for h in habilidades:
        por_etapa[h["etapa"]] = por_etapa.get(h["etapa"], 0) + 1
        comp = h.get("componente") or "sem_componente"
        por_componente[comp] = por_componente.get(comp, 0) + 1
        if h.get("componente") == "computacao":
            computacao_por_etapa[h["etapa"]] = computacao_por_etapa.get(h["etapa"], 0) + 1
            if h.get("eixo"):
                computacao_por_eixo[h["eixo"]] = computacao_por_eixo.get(h["eixo"], 0) + 1

    metadata = {
        "versao": SNAPSHOT_VERSION,
        "data_publicacao": date.today().isoformat(),
        "checksum_fontes": checksums,
        "missing_sources": missing_sources,
        "contagens": {
            "por_etapa": por_etapa,
            "por_componente": por_componente,
            "computacao": {
                "total": sum(computacao_por_etapa.values()),
                "por_etapa": computacao_por_etapa,
                "por_eixo": computacao_por_eixo,
            },
            "total_habilidades": len(habilidades),
            "total_competencias_gerais": len(COMPETENCIAS_GERAIS),
            "total_competencias_especificas": len(competencias_especificas),
            "total_unidades_tematicas": len(unidades_tematicas),
            "total_objetos_conhecimento": len(objetos_conhecimento),
            "total_campos_experiencia": len(campos_experiencia),
        },
    }
    return {
        "metadata": metadata,
        "competencias_gerais": COMPETENCIAS_GERAIS,
        "competencias_especificas": competencias_especificas,
        "campos_experiencia": campos_experiencia,
        "unidades_tematicas": unidades_tematicas,
        "objetos_conhecimento": objetos_conhecimento,
        "habilidades": habilidades,
    }


def validate_snapshot(snapshot: dict[str, Any]) -> int:
    """Validação leve inline (--validate). Retorna nº de erros graves."""
    from app.models.bncc import is_valid_codigo

    errors = 0
    habs = snapshot["habilidades"]
    codigos = [h["codigo"] for h in habs]
    dups = {c for c in codigos if codigos.count(c) > 1}
    if dups:
        logger.error("Códigos duplicados: %s", sorted(dups)[:10])
        errors += len(dups)
    malformed = [c for c in codigos if not is_valid_codigo(c)]
    if malformed:
        logger.error("Códigos malformados: %s", malformed[:10])
        errors += len(malformed)

    counts = snapshot["metadata"]["contagens"]["por_etapa"]
    logger.info("Contagens por etapa: %s", counts)
    if counts.get("ensino_fundamental", 0) == 0:
        logger.error("Cobertura zero para ensino_fundamental")
        errors += 1
    if counts.get("ensino_medio", 0) == 0:
        logger.error("Cobertura zero para ensino_medio")
        errors += 1
    if counts.get("educacao_infantil", 0) == 0:
        logger.error("Cobertura zero para educacao_infantil (SC-001, três etapas).")
        errors += 1
    if len(snapshot["competencias_gerais"]) != 10:
        logger.error("Competências gerais != 10")
        errors += 1

    logger.info("Validação inline: %d erro(s) grave(s).", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrai o snapshot da BNCC.")
    parser.add_argument("--validate", action="store_true", help="Valida o snapshot após extrair.")
    args = parser.parse_args()

    snapshot = build_snapshot()
    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Snapshot gravado em %s (%d habilidades).",
        OUTPUT,
        len(snapshot["habilidades"]),
    )

    if args.validate:
        return 1 if validate_snapshot(snapshot) > 0 else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Metadados auxiliares expostos para testes unitários de parsing (T022).
def metadata_from_codigo(codigo: str) -> dict[str, Any] | None:
    """Deriva (etapa, anos, área, componente) do código — helper testável."""
    c = codigo.strip().upper()
    if re.fullmatch(RE_EF, c):
        mapping = EF_COMPONENTE.get(c[4:6])
        if not mapping:
            return None
        componente, area = mapping
        return {
            "etapa": "ensino_fundamental",
            "anos": anos_from_ef(c[2:4]),
            "area_conhecimento": area,
            "componente": componente,
        }
    if re.fullmatch(RE_EM_AREA, c):
        area = EM_AREA.get(c[4:7])
        return (
            None
            if not area
            else {
                "etapa": "ensino_medio",
                "anos": ["1", "2", "3"],
                "area_conhecimento": area,
                "componente": None,
            }
        )
    if re.fullmatch(RE_EM_LP, c):
        return {
            "etapa": "ensino_medio",
            "anos": ["1", "2", "3"],
            "area_conhecimento": "linguagens",
            "componente": "lingua_portuguesa",
        }
    if re.fullmatch(RE_EI, c):
        return {
            "etapa": "educacao_infantil",
            "anos": [c[2:4]],
            "area_conhecimento": "linguagens",
            "componente": None,
        }
    return None
