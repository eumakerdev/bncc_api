"""
Endpoints de Habilidades da BNCC (US1, dados oficiais determinísticos).

Auth por API key + cota determinística (60/min) via `DeterministicRateLimited`.
Nos testes de US1 a auth é sobreposta pelo fixture `override_api_key_auth`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.deps import DeterministicRateLimited, get_bncc_service
from app.models.bncc import (
    AreaConhecimento,
    ComponenteCurricular,
    ErrorResponse,
    EtapaEnsino,
    Habilidade,
    HabilidadeFiltros,
    PaginatedResponse,
    is_valid_codigo,
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
    "",
    response_model=PaginatedResponse,
    summary="Listar habilidades com filtros e paginação",
    response_description="Página de habilidades que casam com os filtros informados.",
    description=(
        "Lista as habilidades oficiais da BNCC (EI/EF/EM), com filtros opcionais "
        "por etapa, ano, área, componente e competência geral. Requer API key "
        "(`Authorization: Bearer <key>`) e consome a cota determinística "
        "(60 req/min, burst 10)."
    ),
    responses=_AUTH_RESPONSES,
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
    response_description="Dados completos da habilidade.",
    description=(
        "Busca uma habilidade pelo código oficial (formatos EI##XX##, EF##XX## "
        "ou EM13XXX###/EM13XX##). Requer API key e consome a cota determinística "
        "(60 req/min, burst 10)."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Código malformado (não casa com nenhum formato oficial EI/EF/EM).",
        },
        404: {"model": ErrorResponse, "description": "Habilidade inexistente no snapshot."},
        **_AUTH_RESPONSES,
    },
)
async def get_habilidade(
    _: DeterministicRateLimited,
    codigo: str = Path(
        ...,
        description="Código oficial da habilidade (EI/EF/EM).",
        openapi_examples={
            "ensino_fundamental": {
                "summary": "Matemática — 5º ano",
                "value": "EF05MA07",
            },
        },
    ),
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
    response_description=(
        "Grafo de relações (competências gerais/específicas, objetos de "
        "conhecimento e habilidades correlatas) da habilidade."
    ),
    description=(
        "Retorna as relações navegáveis de uma habilidade — competências gerais "
        "e específicas associadas, objetos de conhecimento e demais vínculos "
        "curriculares (FR-005). Requer API key e consome a cota determinística."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Código malformado."},
        404: {"model": ErrorResponse, "description": "Habilidade inexistente no snapshot."},
        **_AUTH_RESPONSES,
    },
)
async def get_habilidade_relacoes(
    _: DeterministicRateLimited,
    codigo: str = Path(
        ...,
        description="Código oficial da habilidade (EI/EF/EM).",
        openapi_examples={
            "ensino_fundamental": {
                "summary": "Matemática — 5º ano",
                "value": "EF05MA07",
            },
        },
    ),
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
