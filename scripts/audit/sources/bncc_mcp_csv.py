"""
Adaptador da testemunha CSV `github.com/dfdb76/bncc-mcp` (versão final homologada).

Os CSVs casam 100% com o PDF árbitro nos códigos de EI+EF e foram usados na
reconciliação de 2026-07-06. Aqui servem como SEGUNDA testemunha independente e,
para o Ensino Médio, como referência preferencial (a seção de EM do PDF é rascunho).

Bootstrap (passo único, offline depois): baixe os CSVs do repositório para
`audit/fontes/bncc_mcp/` — ver `docs/auditoria-externa.md`. O adaptador é flexível
quanto ao layout: varre todos os `.csv` da pasta e detecta as colunas de código e
descrição pelo cabeçalho. Sem a pasta/arquivos, degrada graciosamente (indisponível).
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import date
from pathlib import Path

from scripts.audit.sources import SourceRecord

logger = logging.getLogger("audit_sources.bncc_mcp_csv")

_ROOT = Path(__file__).resolve().parents[3]
_DIR_PADRAO = _ROOT / "audit" / "fontes" / "bncc_mcp"

_CODIGO = re.compile(r"^E[IFM]\d{2}[A-Z]{2,3}\d{2,3}$")
_HDR_CODIGO = ("codigo", "código", "code", "cod")
_HDR_DESC = ("descricao", "descrição", "habilidade", "description", "texto")


def _col(headers: list[str], candidatos: tuple[str, ...]) -> str | None:
    for h in headers:
        hl = h.strip().lower()
        if any(c in hl for c in candidatos):
            return h
    return None


class BnccMcpCsvSource:
    slug = "bncc_mcp_csv"
    nome = "CSV bncc-mcp (versão final homologada)"

    def __init__(self, diretorio: Path | None = None):
        self._dir = diretorio or _DIR_PADRAO
        self._mapa: dict[str, str] | None = None

    def disponivel(self) -> bool:
        return self._dir.is_dir() and any(self._dir.glob("*.csv"))

    def fetch(self, codigo: str) -> SourceRecord | None:
        desc = self._carregar().get(codigo)
        if not desc:
            return None
        return SourceRecord(
            fonte=self.slug,
            codigo=codigo,
            descricao=desc,
            url="github.com/dfdb76/bncc-mcp",
            obtido_em=date.today().isoformat(),
        )

    def _carregar(self) -> dict[str, str]:
        if self._mapa is not None:
            return self._mapa
        mapa: dict[str, str] = {}
        for arq in sorted(self._dir.glob("*.csv")):
            try:
                self._ler_csv(arq, mapa)
            except Exception as exc:  # noqa: BLE001 — degradação por arquivo
                logger.warning("Falha lendo %s: %s", arq.name, exc)
        self._mapa = mapa
        return mapa

    @staticmethod
    def _ler_csv(arq: Path, mapa: dict[str, str]) -> None:
        with arq.open(encoding="utf-8-sig", newline="") as fh:
            amostra = fh.read(2048)
            fh.seek(0)
            try:
                dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
            except csv.Error:
                dialeto = csv.excel
            leitor = csv.DictReader(fh, dialect=dialeto)
            if not leitor.fieldnames:
                return
            col_cod = _col(list(leitor.fieldnames), _HDR_CODIGO)
            col_desc = _col(list(leitor.fieldnames), _HDR_DESC)
            if not col_cod or not col_desc:
                return
            for linha in leitor:
                cod = (linha.get(col_cod) or "").strip()
                desc = (linha.get(col_desc) or "").strip()
                if _CODIGO.match(cod) and desc and cod not in mapa:
                    mapa[cod] = desc
