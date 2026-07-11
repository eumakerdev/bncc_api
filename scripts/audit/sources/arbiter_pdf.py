"""
Adaptador da testemunha ÁRBITRO: o documento oficial homologado
`data/BNCC_EI_EF_110518_versaofinal_site.pdf` (EI+EF+EM, 600 págs.).

É a testemunha primária em Educação Infantil e Ensino Fundamental. Para o Ensino
Médio a seção deste PDF é o rascunho de mai/2018 (pré-homologação) — por isso
`fetch()` NÃO retorna códigos de EM (a referência de EM é o CSV/snapshot
homologado; ver CLAUDE.md e `bncc_mcp_csv`).

Extração: como o page tree do PDF impede o pdfplumber direto, normaliza-se com
pikepdf em memória; o texto de todas as páginas é concatenado em ordem de leitura
e fatiado pelos marcadores de código `(EFxxYY##)`/`(EIxxYY##)` — a descrição de um
código é o texto entre o seu marcador e o próximo. É melhor-esforço: a diagramação
multicoluna pode trazer "bleed" de coluna vizinha, então a testemunha serve para
SINALIZAR divergências para revisão humana, não como recorte perfeito. O mapa
código→texto é cacheado em `audit/cache/arbiter_pdf.json` (extração única; reruns
e execuções offline leem o cache).
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from datetime import date
from pathlib import Path

from scripts.audit.sources import SourceRecord

logger = logging.getLogger("audit_sources.arbiter_pdf")

_ROOT = Path(__file__).resolve().parents[3]
_PDF_PADRAO = _ROOT / "data" / "BNCC_EI_EF_110518_versaofinal_site.pdf"
_CACHE_PADRAO = _ROOT / "audit" / "cache"

# Marcador de código entre parênteses (EI/EF); EM é deliberadamente ignorado.
_MARCADOR = re.compile(r"\((E[IF]\d{2}[A-Z]{2,3}\d{2,3})\)")
_MAX_CAPTURA = 600  # descrições oficiais raramente passam disso; corta bleed grande.


class ArbiterPdfSource:
    slug = "arbiter_pdf"
    nome = "PDF oficial homologado (árbitro EI/EF)"

    def __init__(self, pdf: Path | None = None, cache_dir: Path | None = None):
        self._pdf = pdf or _PDF_PADRAO
        self._cache = (cache_dir or _CACHE_PADRAO) / "arbiter_pdf.json"
        self._mapa: dict[str, str] | None = None

    def disponivel(self) -> bool:
        return self._cache.exists() or self._pdf.exists()

    def fetch(self, codigo: str) -> SourceRecord | None:
        if codigo.startswith("EM"):
            return None  # seção de EM do PDF é rascunho — não é testemunha válida
        mapa = self._carregar()
        desc = mapa.get(codigo)
        if not desc:
            return None
        return SourceRecord(
            fonte=self.slug,
            codigo=codigo,
            descricao=desc,
            url=f"{self._pdf.name}#(codigo)",
            obtido_em=date.today().isoformat(),
        )

    # -- interno -----------------------------------------------------------

    def _carregar(self) -> dict[str, str]:
        if self._mapa is not None:
            return self._mapa
        if self._cache.exists():
            dados = json.loads(self._cache.read_text(encoding="utf-8"))
            self._mapa = dict(dados.get("descricoes", {}))
            return self._mapa
        self._mapa = self._extrair()
        self._cache.parent.mkdir(parents=True, exist_ok=True)
        self._cache.write_text(
            json.dumps(
                {
                    "gerado_em": date.today().isoformat(),
                    "fonte_pdf": self._pdf.name,
                    "descricoes": self._mapa,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        logger.info("Cache do árbitro gravado: %s (%d códigos)", self._cache, len(self._mapa))
        return self._mapa

    def _extrair(self) -> dict[str, str]:
        import io

        import pdfplumber
        import pikepdf

        logger.info("Extraindo texto do árbitro %s (pode levar ~1 min)...", self._pdf.name)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pdf = pikepdf.open(self._pdf)
            buf = io.BytesIO()
            pdf.save(buf)
            pdf.close()
            buf.seek(0)
            partes: list[str] = []
            with pdfplumber.open(buf) as doc:
                for pg in doc.pages:
                    partes.append(pg.extract_text() or "")
        texto = "\n".join(partes)

        mapa: dict[str, str] = {}
        marcas = list(_MARCADOR.finditer(texto))
        for i, m in enumerate(marcas):
            codigo = m.group(1)
            fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
            trecho = re.sub(r"\s+", " ", texto[m.end() : fim]).strip()
            if len(trecho) > _MAX_CAPTURA:
                trecho = trecho[:_MAX_CAPTURA].rsplit(" ", 1)[0]
            # Guarda o trecho mais longo por código (evita capturas de citação curta).
            if trecho and len(trecho) > len(mapa.get(codigo, "")):
                mapa[codigo] = trecho
        return mapa
