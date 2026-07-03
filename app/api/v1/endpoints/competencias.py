"""
Endpoints de Competências da BNCC (US1, dados oficiais determinísticos).

Auth por API key + cota determinística via `DeterministicRateLimited`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.deps import DeterministicRateLimited, get_bncc_service
from app.models.bncc import (
    AreaConhecimento,
    CompetenciaEspecifica,
    CompetenciaGeral,
    ComponenteCurricular,
    EtapaEnsino,
)
from app.services.bncc_service import BNCCDataService

router = APIRouter()


@router.get(
    "/gerais",
    response_model=list[CompetenciaGeral],
    summary="Listar as 10 competências gerais",
)
async def get_competencias_gerais(
    _: DeterministicRateLimited,
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> list[CompetenciaGeral]:
    return await bncc_service.get_competencias_gerais()


@router.get(
    "/gerais/{numero}",
    response_model=CompetenciaGeral,
    summary="Buscar competência geral por número (1-10)",
)
async def get_competencia_geral(
    _: DeterministicRateLimited,
    numero: int = Path(..., description="Número da competência geral (1-10)"),
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> CompetenciaGeral:
    # numero fora de 1-10 (ou inexistente) → 404 (contrato bncc-data.md).
    competencia = await bncc_service.get_competencia_geral_by_numero(numero)
    if competencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Competência geral {numero} não encontrada.",
        )
    return competencia


@router.get(
    "/especificas",
    response_model=list[CompetenciaEspecifica],
    summary="Listar competências específicas (filtros: area/componente/etapa)",
)
async def get_competencias_especificas(
    _: DeterministicRateLimited,
    area: AreaConhecimento | None = Query(None, description="Área de conhecimento"),
    componente: ComponenteCurricular | None = Query(None, description="Componente curricular"),
    etapa: EtapaEnsino | None = Query(None, description="Etapa de ensino"),
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> list[CompetenciaEspecifica]:
    return await bncc_service.get_competencias_especificas(
        area=area, componente=componente, etapa=etapa
    )
