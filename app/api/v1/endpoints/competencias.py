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
    ErrorResponse,
    EtapaEnsino,
)
from app.services.bncc_service import BNCCDataService

router = APIRouter()

_AUTH_RESPONSES: dict[int | str, dict] = {
    401: {
        "model": ErrorResponse,
        "description": "API key ausente, inválida ou revogada.",
    },
    429: {
        "model": ErrorResponse,
        "description": "Cota determinística excedida (60/min, burst 10).",
    },
}


@router.get(
    "/gerais",
    response_model=list[CompetenciaGeral],
    summary="Listar as 10 competências gerais",
    response_description="As 10 competências gerais da BNCC, transversais às três etapas.",
    description=(
        "Lista as 10 competências gerais oficiais da BNCC, aplicáveis a todas as "
        "etapas de ensino. Requer API key e consome a cota determinística."
    ),
    responses=_AUTH_RESPONSES,
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
    response_description="Dados completos da competência geral.",
    description=(
        "Busca uma das 10 competências gerais oficiais pelo número (1-10). "
        "Requer API key e consome a cota determinística."
    ),
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Número fora de 1-10 ou competência inexistente.",
        },
        **_AUTH_RESPONSES,
    },
)
async def get_competencia_geral(
    _: DeterministicRateLimited,
    numero: int = Path(
        ...,
        description="Número da competência geral (1-10)",
        openapi_examples={"exemplo": {"summary": "Competência 1 — Conhecimento", "value": 1}},
    ),
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
    response_description="Competências específicas que casam com os filtros informados.",
    description=(
        "Lista competências específicas de área/componente curricular, com "
        "filtros opcionais por área de conhecimento, componente e etapa de "
        "ensino. Requer API key e consome a cota determinística."
    ),
    responses=_AUTH_RESPONSES,
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
