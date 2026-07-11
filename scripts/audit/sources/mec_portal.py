"""
Adaptador da testemunha PORTAL MEC (`basenacionalcomum.mec.gov.br`).

Testemunha online, consultada por código e CACHEADA em
`audit/cache/mec_portal/{codigo}.json` — a rede é usada só na primeira vez; reruns
e execuções `--offline` leem exclusivamente o cache (reprodutibilidade e CI sem
rede). Sem cache e sem rede, degrada graciosamente (retorna None).

NOTA: o portal do MEC é uma aplicação JS e não expõe um endpoint por código
estável e verificado. Por isso este adaptador é dirigido pelo CACHE: a coleta
online fica atrás de `MecPortalSource._buscar_online`, um gancho a ser confirmado/
ajustado conforme a fonte disponível (ver `docs/auditoria-externa.md`). Enquanto
não confirmado, o adaptador opera apenas sobre entradas de cache já semeadas.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from scripts.audit.sources import SourceRecord

logger = logging.getLogger("audit_sources.mec_portal")

_ROOT = Path(__file__).resolve().parents[3]
_CACHE_PADRAO = _ROOT / "audit" / "cache"


class MecPortalSource:
    slug = "mec_portal"
    nome = "Portal BNCC/MEC (basenacionalcomum.mec.gov.br)"

    def __init__(self, offline: bool = False, cache_dir: Path | None = None):
        self._offline = offline
        self._cache_dir = (cache_dir or _CACHE_PADRAO) / "mec_portal"

    def disponivel(self) -> bool:
        # Disponível se há qualquer cache semeado, ou se podemos ir à rede.
        if self._cache_dir.is_dir() and any(self._cache_dir.glob("*.json")):
            return True
        return not self._offline

    def fetch(self, codigo: str) -> SourceRecord | None:
        cache = self._cache_dir / f"{codigo}.json"
        if cache.exists():
            dados = json.loads(cache.read_text(encoding="utf-8"))
            desc = (dados.get("descricao") or "").strip()
            if not desc:
                return None
            return SourceRecord(
                fonte=self.slug,
                codigo=codigo,
                descricao=desc,
                url=dados.get("url", ""),
                obtido_em=dados.get("obtido_em", ""),
            )
        if self._offline:
            return None
        return self._buscar_online(codigo)

    # -- interno -----------------------------------------------------------

    def _buscar_online(self, codigo: str) -> SourceRecord | None:
        """Gancho de coleta online (a confirmar). Grava no cache quando bem-sucedido.

        Mantido conservador: qualquer falha degrada para None sem propagar exceção,
        para que a auditoria continue com as demais fontes (Princípio VII).
        """
        try:
            registro = self._coletar(codigo)
        except Exception as exc:  # noqa: BLE001 — nunca derrubar a auditoria pela rede
            logger.info("MEC portal indisponível para %s: %s", codigo, exc)
            return None
        if registro is None:
            return None
        self._gravar_cache(registro)
        return registro

    def _coletar(self, codigo: str) -> SourceRecord | None:
        """Coleta real do portal. Sem endpoint por código confirmado, retorna None.

        Para habilitar: implementar a chamada (httpx) contra a fonte confirmada e
        montar o SourceRecord. Ver docs/auditoria-externa.md.
        """
        return None

    def _gravar_cache(self, rec: SourceRecord) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cache_dir / f"{rec.codigo}.json").write_text(
            json.dumps(
                {
                    "codigo": rec.codigo,
                    "descricao": rec.descricao,
                    "url": rec.url,
                    "obtido_em": rec.obtido_em or date.today().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
