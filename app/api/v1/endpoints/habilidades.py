"""
Endpoints de Habilidades da BNCC (US1, dados oficiais determinísticos).

Auth por API key + cota determinística (60/min) via `DeterministicRateLimited`.
Nos testes de US1 a auth é sobreposta pelo fixture `override_api_key_auth`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DeterministicRateLimited, get_bncc_service
from app.models.bncc import (
    AreaConhecimento,
    ComponenteCurricular,
    EtapaEnsino,
    Habilidade,
    HabilidadeFiltros,
    PaginatedResponse,
    is_valid_codigo,
)
from app.services.bncc_service import BNCCDataService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="Listar habilidades com filtros e paginação",
)
async def list_habilidades(
    _: DeterministicRateLimited,
    etapa: EtapaEnsino | None = Query(None, description="Etapa de ensino"),
    ano: str | None = Query(None, description="Ano escolar (ex.: '5')"),
    area_conhecimento: AreaConhecimento | None = Query(None, description="Área de conhecimento"),
    componente: ComponenteCurricular | None = Query(None, description="Componente curricular"),
    competencia_geral: int
    | None = Query(None, ge=1, le=10, description="Competência geral (1-10)"),
    page: int = Query(1, ge=1, description="Página (>=1)"),
    size: int = Query(20, ge=1, le=100, description="Itens por página (1-100)"),
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> PaginatedResponse:
    filtros = HabilidadeFiltros(
        etapa=etapa,
        ano=ano,
        area_conhecimento=area_conhecimento,
        componente=componente,
        competencia_geral=competencia_geral,
    )
    skip = (page - 1) * size
    habilidades = await bncc_service.search_habilidades(filtros, skip=skip, limit=size)
    total = await bncc_service.count_habilidades(filtros)
    pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(items=habilidades, total=total, page=page, size=size, pages=pages)


@router.get(
    "/{codigo}",
    response_model=Habilidade,
    summary="Buscar habilidade por código oficial (EI/EF/EM)",
)
async def get_habilidade(
    codigo: str,
    _: DeterministicRateLimited,
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> Habilidade:
    if not is_valid_codigo(codigo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Código '{codigo}' malformado. Formatos aceitos: "
                "EI (EI##XX##), EF (EF##XX##), EM (EM13XXX###)."
            ),
        )
    habilidade = await bncc_service.get_habilidade_by_codigo(codigo)
    if habilidade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habilidade '{codigo.upper()}' não encontrada.",
        )
    return habilidade


@router.get(
    "/{codigo}/relacoes",
    summary="Relações navegáveis de uma habilidade (FR-005)",
)
async def get_habilidade_relacoes(
    codigo: str,
    _: DeterministicRateLimited,
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> dict:
    if not is_valid_codigo(codigo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Código '{codigo}' malformado.",
        )
    relacoes = await bncc_service.get_relacoes(codigo)
    if relacoes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habilidade '{codigo.upper()}' não encontrada.",
        )
    return relacoes
