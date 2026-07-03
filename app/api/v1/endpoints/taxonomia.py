"""
Endpoint de Taxonomia da BNCC (US1, novo).

Expõe a estrutura navegável: etapas → áreas → componentes → unidades temáticas →
objetos de conhecimento, além dos campos de experiência (EI). Suporta a
documentação e a navegação (FR-005). Montado em `/api/v1/taxonomia`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import DeterministicRateLimited, get_bncc_service
from app.models.bncc import ErrorResponse
from app.services.bncc_service import BNCCDataService

router = APIRouter()


@router.get(
    "",
    summary="Árvore da taxonomia oficial da BNCC",
    response_description=(
        "Estrutura navegável completa: etapas → áreas → componentes → unidades "
        "temáticas/objetos de conhecimento (e campos de experiência na EI)."
    ),
    description=(
        "Retorna a árvore de taxonomia oficial da BNCC, usada para navegação e "
        "documentação (FR-005): etapas de ensino, áreas de conhecimento, "
        "componentes curriculares, unidades temáticas e objetos de conhecimento, "
        "além dos campos de experiência da Educação Infantil. Requer API key e "
        "consome a cota determinística (60 req/min, burst 10)."
    ),
    responses={
        401: {
            "model": ErrorResponse,
            "description": "API key ausente, inválida ou revogada.",
        },
        429: {
            "model": ErrorResponse,
            "description": "Cota determinística excedida (60/min, burst 10).",
        },
    },
)
async def get_taxonomia(
    _: DeterministicRateLimited,
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> dict:
    return await bncc_service.get_taxonomia()
