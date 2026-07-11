"""
Camada de fontes da auditoria externa de fidelidade da BNCC.

Cada fonte é uma TESTEMUNHA INDEPENDENTE do texto oficial da BNCC. Nenhuma é
tratada como verdade final — elas apenas informam os relatórios de auditoria; a
decisão de corrigir o snapshot é sempre humana (Princípios IV e VII). Todo
adaptador implementa a interface `Source`: declara `disponivel()` e resolve
`fetch(codigo) -> SourceRecord | None`, degradando graciosamente quando a fonte,
os arquivos ou a rede estão ausentes.

Precedência de referência (ver CLAUDE.md): o PDF árbitro
`BNCC_EI_EF_110518_versaofinal_site.pdf` é a testemunha primária em EI/EF; para o
Ensino Médio a seção do PDF é rascunho de mai/2018, então lá a referência é o
CSV/snapshot homologado, nunca o PDF.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger("audit_sources")

# Slugs das fontes da allowlist, em ordem de precedência de referência.
FONTES_PADRAO: tuple[str, ...] = ("arbiter_pdf", "bncc_mcp_csv", "mec_portal")


@dataclass(frozen=True)
class SourceRecord:
    """Uma testemunha do texto de uma habilidade, vinda de uma fonte externa."""

    fonte: str  # slug da fonte (ex.: "arbiter_pdf")
    codigo: str
    descricao: str
    url: str  # proveniência: caminho do arquivo ou URL
    obtido_em: str  # data ISO-8601 (AAAA-MM-DD)


@runtime_checkable
class Source(Protocol):
    """Contrato de um adaptador de fonte independente."""

    slug: str
    nome: str

    def disponivel(self) -> bool:
        """True se a fonte pode responder consultas (arquivos/cache/rede prontos)."""
        ...

    def fetch(self, codigo: str) -> SourceRecord | None:
        """Retorna a testemunha da fonte para `codigo`, ou None se ausente."""
        ...


def carregar_fontes(
    slugs: tuple[str, ...] | list[str] | None = None,
    *,
    offline: bool = False,
    cache_dir: Path | None = None,
) -> list[Source]:
    """Instancia os adaptadores pedidos, pulando (com aviso) os indisponíveis.

    Import de cada adaptador é preguiçoso para que uma dependência ausente
    (ex.: pdfplumber) desabilite só aquela fonte, sem derrubar as demais.
    """
    escolhidos = tuple(slugs) if slugs else FONTES_PADRAO
    fontes: list[Source] = []
    for slug in escolhidos:
        try:
            fonte = _instanciar(slug, offline=offline, cache_dir=cache_dir)
        except ImportError as exc:
            logger.warning("Fonte %s indisponível (dependência ausente): %s", slug, exc)
            continue
        except Exception as exc:  # noqa: BLE001 — degradação graciosa por fonte
            logger.warning("Fonte %s falhou ao inicializar: %s", slug, exc)
            continue
        if fonte is None:
            logger.warning("Fonte desconhecida ignorada: %s", slug)
            continue
        if not fonte.disponivel():
            logger.info("Fonte %s indisponível nesta execução (sem arquivos/cache).", slug)
            continue
        fontes.append(fonte)
    return fontes


def _instanciar(slug: str, *, offline: bool, cache_dir: Path | None) -> Source | None:
    if slug == "arbiter_pdf":
        from scripts.audit.sources.arbiter_pdf import ArbiterPdfSource

        return ArbiterPdfSource(cache_dir=cache_dir)
    if slug == "bncc_mcp_csv":
        from scripts.audit.sources.bncc_mcp_csv import BnccMcpCsvSource

        return BnccMcpCsvSource()
    if slug == "mec_portal":
        from scripts.audit.sources.mec_portal import MecPortalSource

        return MecPortalSource(offline=offline, cache_dir=cache_dir)
    return None
