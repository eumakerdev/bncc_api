"""
Extração determinística do snapshot da BNCC (T026, Princípio IV).

Lê os PDFs oficiais em `data/` (Ensino Fundamental e Ensino Médio) com pdfplumber
e grava `data/bncc_v1.json` com metadados de rastreabilidade (versão, checksum
SHA-256 das fontes, contagens por etapa/componente).

**Fidelidade (Princípio IV / T029)**: as tabelas da BNCC têm 3 colunas
(UNIDADES TEMÁTICAS | OBJETOS DE CONHECIMENTO | HABILIDADES). Uma extração ingênua
com `extract_text()` intercala o texto das colunas da esquerda dentro da descrição
da habilidade. Para evitar essa contaminação, isolamos a **coluna HABILIDADES**
por coordenada horizontal (o código `(EFxxxx)` marca a borda esquerda da coluna) e
só então recompomos e fatiamos o texto por código.

Educação Infantil (T024 — BLOQUEIO): não há PDF dedicado da EI em `data/`. O parser
de EI existe e ativa apenas se a fonte aparecer; na ausência, emite WARN e registra
contagem 0 + `missing_sources: ["educacao_infantil"]`. **Nenhum dado de EI é
fabricado.**

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
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("extract_bncc")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
PDF_EF = DATA_DIR / "bncc_ensino_fundamental.pdf"
PDF_EM = DATA_DIR / "bncc_ensino_medio.pdf"
PDF_EI = DATA_DIR / "bncc_educacao_infantil.pdf"  # ausente (T024)
OUTPUT = DATA_DIR / "bncc_v1.json"

SNAPSHOT_VERSION = "v1"

# --- Padrões de código -------------------------------------------------------
RE_EF = r"EF\d{2}[A-Z]{2}\d{2}"
RE_EM_AREA = r"EM13[A-Z]{3}\d{3}"
RE_EM_LP = r"EM13[A-Z]{2}\d{2}"
RE_EI = r"EI\d{2}[A-Z]{2}\d{2}"

# Token isolado (palavra) que é um código, com ou sem parênteses.
RE_CODE_TOKEN = re.compile(r"^\(?(E[FMI]\d{2}[A-Z]{2,3}\d{2,3})\)?[.,;:]?$")
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
# página (a descrição oficial nunca contém estas expressões em maiúsculas).
NOISE_SENTINELS = re.compile(
    r"BASE NACIONAL|COMUM CURRICULAR|UNIDADES TEM|CAMPOS DE ATUA|"
    r"OBJETOS DE CONHE|\bHABILIDADES\b|COMPET[ÊE]NCIAS ESPEC|PR[ÁA]TICAS DE LINGUAGEM"
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


def clean_description(raw: str) -> str:
    """Corta ruído de cabeçalho, remove nº de rodapé residual e normaliza espaços."""
    m = NOISE_SENTINELS.search(raw)
    if m and m.start() > 30:
        raw = raw[: m.start()]
    raw = re.sub(r"\s+\d{1,4}\s*$", "", raw)  # nº de página ao final
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


# --------------------------------------------------------------------------- #
# Isolamento da coluna HABILIDADES (evita contaminação — fidelidade)
# --------------------------------------------------------------------------- #
def right_column_text(pdf_path: Path) -> str:
    """Concatena, em ordem de leitura, apenas a coluna direita (HABILIDADES)."""
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
            col_x = min(code_x0) - 3.0
            right = [w for w in words if w["x0"] >= col_x]
            right.sort(key=lambda w: (round(w["top"]), w["x0"]))
            parts.append(" ".join(w["text"] for w in right))
    return " ".join(parts)


def _split_by_codes(text: str, regex: re.Pattern) -> list[tuple[str, str]]:
    matches = list(regex.finditer(text))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[start:end]))
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

    if PDF_EF.exists():
        logger.info("Extraindo Ensino Fundamental de %s ...", PDF_EF.name)
        ef = parse_ef(right_column_text(PDF_EF))
        habilidades.extend(ef)
        checksums["ensino_fundamental"] = sha256_of(PDF_EF)
        logger.info("  -> %d habilidades EF", len(ef))
    else:
        logger.warning("Fonte do Ensino Fundamental ausente: %s", PDF_EF)
        missing_sources.append("ensino_fundamental")

    if PDF_EM.exists():
        logger.info("Extraindo Ensino Médio de %s ...", PDF_EM.name)
        em = parse_em(right_column_text(PDF_EM))
        habilidades.extend(em)
        checksums["ensino_medio"] = sha256_of(PDF_EM)
        logger.info("  -> %d habilidades EM", len(em))
    else:
        logger.warning("Fonte do Ensino Médio ausente: %s", PDF_EM)
        missing_sources.append("ensino_medio")

    if PDF_EI.exists():
        logger.info("Extraindo Educação Infantil de %s ...", PDF_EI.name)
        ei = parse_ei(right_column_text(PDF_EI))
        habilidades.extend(ei)
        checksums["educacao_infantil"] = sha256_of(PDF_EI)
        logger.info("  -> %d objetivos/habilidades EI", len(ei))
    else:
        logger.warning(
            "T024: fonte oficial da Educação Infantil AUSENTE (%s). "
            "Registrando contagem 0 + missing_sources; NENHUM dado de EI fabricado.",
            PDF_EI.name,
        )
        missing_sources.append("educacao_infantil")

    # Deduplicação global final por código.
    habilidades = _dedup_longest(habilidades)

    por_etapa: dict[str, int] = {
        "educacao_infantil": 0,
        "ensino_fundamental": 0,
        "ensino_medio": 0,
    }
    por_componente: dict[str, int] = {}
    for h in habilidades:
        por_etapa[h["etapa"]] = por_etapa.get(h["etapa"], 0) + 1
        comp = h.get("componente") or "sem_componente"
        por_componente[comp] = por_componente.get(comp, 0) + 1

    metadata = {
        "versao": SNAPSHOT_VERSION,
        "data_publicacao": date.today().isoformat(),
        "checksum_fontes": checksums,
        "missing_sources": missing_sources,
        "contagens": {
            "por_etapa": por_etapa,
            "por_componente": por_componente,
            "total_habilidades": len(habilidades),
            "total_competencias_gerais": len(COMPETENCIAS_GERAIS),
        },
    }
    return {
        "metadata": metadata,
        "competencias_gerais": COMPETENCIAS_GERAIS,
        "competencias_especificas": [],
        "campos_experiencia": [],
        "unidades_tematicas": [],
        "objetos_conhecimento": [],
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
        logger.warning("Educação Infantil com contagem 0 (T024 — fonte ausente).")
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
