"""
Serviço de dados da BNCC (leitura do snapshot versionado, read-only em runtime).

Carrega `data/bncc_v1.json` (caminho em `settings.BNCC_DATA_PATH`), oferecendo:
get-por-código, busca filtrada + paginada, resolução de relações navegáveis,
árvore de taxonomia e metadados do snapshot. Nunca lança se o snapshot estiver
ausente — nesse caso opera com dados vazios (Princípio VII, degradação graciosa).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models.bncc import (
    AreaConhecimento,
    CompetenciaEspecifica,
    CompetenciaGeral,
    ComponenteCurricular,
    EtapaEnsino,
    Habilidade,
    HabilidadeFiltros,
    SnapshotMetadata,
)

logger = logging.getLogger(__name__)

_EMPTY: dict[str, Any] = {
    "metadata": {},
    "competencias_gerais": [],
    "competencias_especificas": [],
    "campos_experiencia": [],
    "unidades_tematicas": [],
    "objetos_conhecimento": [],
    "habilidades": [],
}


class BNCCDataService:
    """Acesso e filtragem dos dados oficiais da BNCC."""

    def __init__(self, data: dict[str, Any] | None = None):
        if data is not None:
            self.data = self._normalize(data)
        else:
            self.data = self._load_data()

    # ------------------------------------------------------------------ #
    # Carga
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(_EMPTY)
        merged.update(data or {})
        # Garante que as chaves de lista existam.
        for key, default in _EMPTY.items():
            merged.setdefault(key, default)
        return merged

    def _load_data(self) -> dict[str, Any]:
        try:
            data_path = Path(settings.BNCC_DATA_PATH)
            if not data_path.exists():
                logger.warning("Snapshot da BNCC não encontrado em %s", data_path)
                return dict(_EMPTY)
            with open(data_path, encoding="utf-8") as f:
                raw = json.load(f)
            data = self._normalize(raw)
            logger.info(
                "Snapshot BNCC carregado: %d habilidades, %d comp. gerais, " "%d comp. específicas",
                len(data["habilidades"]),
                len(data["competencias_gerais"]),
                len(data["competencias_especificas"]),
            )
            return data
        except Exception as e:  # pragma: no cover - defensivo
            logger.error("Erro ao carregar snapshot da BNCC: %s", e)
            return dict(_EMPTY)

    # ------------------------------------------------------------------ #
    # Habilidades
    # ------------------------------------------------------------------ #
    async def get_habilidade_by_codigo(self, codigo: str) -> Habilidade | None:
        codigo = (codigo or "").upper().strip()
        for hab in self.data.get("habilidades", []):
            if str(hab.get("codigo", "")).upper() == codigo:
                try:
                    return Habilidade(**hab)
                except Exception as e:  # pragma: no cover - snapshot inconsistente
                    logger.warning("Habilidade inválida no snapshot (%s): %s", codigo, e)
                    return None
        return None

    def _match(self, hab: dict[str, Any], f: HabilidadeFiltros) -> bool:
        if f.etapa and hab.get("etapa") != f.etapa.value:
            return False
        if f.ano and f.ano not in (hab.get("anos") or []):
            return False
        if f.area_conhecimento and hab.get("area_conhecimento") != f.area_conhecimento.value:
            return False
        if f.componente and hab.get("componente") != f.componente.value:
            return False
        if f.competencia_geral and f.competencia_geral not in (
            hab.get("competencias_gerais") or []
        ):
            return False
        if f.eixo and hab.get("eixo") != f.eixo.value:
            return False
        return True

    def _filtered_raw(self, f: HabilidadeFiltros) -> list[dict[str, Any]]:
        return [h for h in self.data.get("habilidades", []) if self._match(h, f)]

    async def search_habilidades(
        self, filtros: HabilidadeFiltros, skip: int = 0, limit: int = 100
    ) -> list[Habilidade]:
        resultado: list[Habilidade] = []
        for hab in sorted(self._filtered_raw(filtros), key=lambda h: str(h.get("codigo", ""))):
            try:
                resultado.append(Habilidade(**hab))
            except Exception as e:
                logger.warning("Ignorando habilidade inválida no snapshot: %s", e)
        return resultado[skip : skip + limit]

    async def count_habilidades(self, filtros: HabilidadeFiltros) -> int:
        return len(self._filtered_raw(filtros))

    async def get_relacoes(self, codigo: str) -> dict[str, Any] | None:
        """Resolve as relações navegáveis de uma habilidade (FR-005)."""
        habilidade = await self.get_habilidade_by_codigo(codigo)
        if habilidade is None:
            return None

        gerais = [
            c
            for c in await self.get_competencias_gerais()
            if c.numero in habilidade.competencias_gerais
        ]
        esp_index = {
            str(c.get("codigo", "")).upper(): c
            for c in self.data.get("competencias_especificas", [])
        }
        especificas: list[CompetenciaEspecifica] = []
        for cod in habilidade.competencias_especificas:
            item = esp_index.get(str(cod).upper())
            if item:
                try:
                    especificas.append(CompetenciaEspecifica(**item))
                except Exception:  # pragma: no cover
                    continue

        # Unidades temáticas associadas aos objetos de conhecimento da habilidade.
        obj_index = {o.get("nome"): o for o in self.data.get("objetos_conhecimento", [])}
        unidades: list[str] = []
        for nome in habilidade.objetos_conhecimento:
            obj = obj_index.get(nome)
            if obj and obj.get("unidade_tematica"):
                ut = obj["unidade_tematica"]
                if ut not in unidades:
                    unidades.append(ut)
        if habilidade.unidade_tematica and habilidade.unidade_tematica not in unidades:
            unidades.append(habilidade.unidade_tematica)

        return {
            "codigo": habilidade.codigo,
            "competencias_gerais": [c.model_dump() for c in gerais],
            "competencias_especificas": [c.model_dump() for c in especificas],
            "objetos_conhecimento": habilidade.objetos_conhecimento,
            "unidades_tematicas": unidades,
        }

    # ------------------------------------------------------------------ #
    # Competências
    # ------------------------------------------------------------------ #
    async def get_competencias_gerais(self) -> list[CompetenciaGeral]:
        resultado: list[CompetenciaGeral] = []
        for comp in self.data.get("competencias_gerais", []):
            try:
                resultado.append(CompetenciaGeral(**comp))
            except Exception as e:
                logger.warning("Competência geral inválida no snapshot: %s", e)
        resultado.sort(key=lambda x: x.numero)
        return resultado

    async def get_competencia_geral_by_numero(self, numero: int) -> CompetenciaGeral | None:
        for comp in self.data.get("competencias_gerais", []):
            if comp.get("numero") == numero:
                return CompetenciaGeral(**comp)
        return None

    async def get_competencias_especificas(
        self,
        area: AreaConhecimento | None = None,
        componente: ComponenteCurricular | None = None,
        etapa: EtapaEnsino | None = None,
    ) -> list[CompetenciaEspecifica]:
        resultado: list[CompetenciaEspecifica] = []
        for comp in self.data.get("competencias_especificas", []):
            if area and comp.get("area_conhecimento") != area.value:
                continue
            if componente and comp.get("componente") != componente.value:
                continue
            if etapa and comp.get("etapa") != etapa.value:
                continue
            try:
                resultado.append(CompetenciaEspecifica(**comp))
            except Exception as e:
                logger.warning("Competência específica inválida no snapshot: %s", e)
        resultado.sort(key=lambda x: (x.area_conhecimento.value, x.numero))
        return resultado

    async def get_competencia_especifica_by_codigo(
        self, codigo: str
    ) -> CompetenciaEspecifica | None:
        codigo = (codigo or "").upper().strip()
        for comp in self.data.get("competencias_especificas", []):
            if str(comp.get("codigo", "")).upper() == codigo:
                return CompetenciaEspecifica(**comp)
        return None

    # ------------------------------------------------------------------ #
    # Taxonomia
    # ------------------------------------------------------------------ #
    async def get_taxonomia(self) -> dict[str, Any]:
        """Árvore navegável: etapas → áreas → componentes → un. temáticas → objetos.

        Também expõe os campos de experiência da Educação Infantil.
        """
        tree: dict[str, Any] = {}
        habs = self.data.get("habilidades", [])

        # Estrutura por etapa/área/componente derivada das habilidades.
        for hab in habs:
            etapa = hab.get("etapa", "desconhecida")
            area = hab.get("area_conhecimento", "desconhecida")
            componente = hab.get("componente") or "sem_componente"
            etapa_node = tree.setdefault(etapa, {"areas": {}})
            area_node = etapa_node["areas"].setdefault(area, {"componentes": {}})
            comp_node = area_node["componentes"].setdefault(componente, {"unidades_tematicas": {}})
            ut = hab.get("unidade_tematica")
            if ut:
                comp_node["unidades_tematicas"].setdefault(ut, {"objetos": set()})

        # Objetos de conhecimento -> unidades temáticas.
        for obj in self.data.get("objetos_conhecimento", []):
            etapa = obj.get("etapa")
            componente = obj.get("componente") or "sem_componente"
            ut = obj.get("unidade_tematica")
            nome = obj.get("nome")
            if not (etapa and ut and nome):
                continue
            for area_node in tree.get(etapa, {}).get("areas", {}).values():
                comp_node = area_node["componentes"].get(componente)
                if comp_node is None:
                    continue
                ut_node = comp_node["unidades_tematicas"].setdefault(ut, {"objetos": set()})
                ut_node["objetos"].add(nome)

        # Converte sets em listas ordenadas (JSON-serializável).
        for etapa_node in tree.values():
            for area_node in etapa_node["areas"].values():
                for comp_node in area_node["componentes"].values():
                    for ut_node in comp_node["unidades_tematicas"].values():
                        ut_node["objetos"] = sorted(ut_node["objetos"])

        campos = self.data.get("campos_experiencia", [])
        return {"etapas": tree, "campos_experiencia": campos}

    # ------------------------------------------------------------------ #
    # Metadados do snapshot
    # ------------------------------------------------------------------ #
    def _counts_por_etapa(self) -> dict[str, int]:
        counts: dict[str, int] = {
            EtapaEnsino.EDUCACAO_INFANTIL.value: 0,
            EtapaEnsino.ENSINO_FUNDAMENTAL.value: 0,
            EtapaEnsino.ENSINO_MEDIO.value: 0,
        }
        for hab in self.data.get("habilidades", []):
            etapa = hab.get("etapa")
            if etapa in counts:
                counts[etapa] += 1
            elif etapa:
                counts[etapa] = counts.get(etapa, 0) + 1
        return counts

    def _counts_por_componente(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for hab in self.data.get("habilidades", []):
            comp = hab.get("componente") or "sem_componente"
            counts[comp] = counts.get(comp, 0) + 1
        return counts

    async def get_snapshot_metadata(self) -> SnapshotMetadata:
        meta = dict(self.data.get("metadata", {}) or {})
        contagens = dict(meta.get("contagens", {}) or {})
        contagens.setdefault("por_etapa", self._counts_por_etapa())
        contagens.setdefault("por_componente", self._counts_por_componente())
        contagens["total_habilidades"] = len(self.data.get("habilidades", []))
        contagens["total_competencias_gerais"] = len(self.data.get("competencias_gerais", []))
        contagens["total_competencias_especificas"] = len(
            self.data.get("competencias_especificas", [])
        )
        return SnapshotMetadata(
            versao=str(meta.get("versao", "desconhecida")),
            data_publicacao=str(meta.get("data_publicacao", "")),
            checksum_fontes=meta.get("checksum_fontes", {}) or {},
            contagens=contagens,
            missing_sources=meta.get("missing_sources", []) or [],
        )

    # ------------------------------------------------------------------ #
    # Compatibilidade (usado por endpoints legados de sistema)
    # ------------------------------------------------------------------ #
    async def get_statistics(self) -> dict[str, Any]:
        return {
            "total_habilidades": len(self.data.get("habilidades", [])),
            "total_competencias_gerais": len(self.data.get("competencias_gerais", [])),
            "total_competencias_especificas": len(self.data.get("competencias_especificas", [])),
            "etapas": self._counts_por_etapa(),
            "componentes": self._counts_por_componente(),
        }


# --------------------------------------------------------------------------- #
# Singleton de módulo (deps.py importa get_bncc_service)
# --------------------------------------------------------------------------- #
_bncc_service: BNCCDataService | None = None


def get_bncc_service() -> BNCCDataService:
    """Instância global do serviço (carrega o snapshot uma vez)."""
    global _bncc_service
    if _bncc_service is None:
        _bncc_service = BNCCDataService()
    return _bncc_service
