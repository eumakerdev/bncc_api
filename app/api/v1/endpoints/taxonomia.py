"""
Endpoint de Taxonomia da BNCC (US1, novo).

Expõe a estrutura navegável: etapas → áreas → componentes → unidades temáticas →
objetos de conhecimento, além dos campos de experiência (EI). Suporta a
documentação e a navegação (FR-005). Montado em `/api/v1/taxonomia`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import DeterministicRateLimited, get_bncc_service
from app.services.bncc_service import BNCCDataService

router = APIRouter()


@router.get("", summary="Árvore da taxonomia oficial da BNCC")
async def get_taxonomia(
    _: DeterministicRateLimited,
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> dict:
    return await bncc_service.get_taxonomia()
