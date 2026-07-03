"""
Endpoints de Sistema (US1): versão de dados, health e readiness.

`/versao-dados` expõe metadados do snapshot (versão, checksum das fontes,
contagens por etapa/componente — FR-025). `/health` é um liveness simples e
público; `/readiness` verifica dependências (DB) de forma best-effort.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.deps import DeterministicRateLimited, get_bncc_service
from app.models.bncc import ErrorResponse, SnapshotMetadata
from app.services.bncc_service import BNCCDataService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/versao-dados",
    response_model=SnapshotMetadata,
    summary="Metadados do snapshot da BNCC (versão, checksum, contagens)",
    response_description="Versão do snapshot, checksums das fontes oficiais e contagens (FR-025).",
    description=(
        "Expõe metadados de rastreabilidade do snapshot estático da BNCC "
        "(FR-025): versão, data de publicação, checksum SHA-256 de cada fonte "
        "oficial e contagens por etapa/componente. Requer API key e consome a "
        "cota determinística."
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
async def get_versao_dados(
    _: DeterministicRateLimited,
    bncc_service: BNCCDataService = Depends(get_bncc_service),
) -> SnapshotMetadata:
    return await bncc_service.get_snapshot_metadata()


@router.get(
    "/health",
    summary="Liveness check (público)",
    response_description="Indicador simples de que o processo está no ar.",
    description=(
        "Verificação de vivacidade (liveness) simples e pública — não requer "
        "API key nem autenticação. Não verifica dependências externas; use "
        "`/readiness` para isso."
    ),
)
async def health() -> dict:
    return {"status": "ok"}


@router.get(
    "/readiness",
    summary="Readiness check (DB best-effort)",
    response_description="Status agregado de prontidão e status por componente.",
    description=(
        "Verificação de prontidão pública — checa o banco da plataforma e o "
        "snapshot da BNCC de forma best-effort. A camada de IA (ChromaDB/"
        "embeddings) é reportada separadamente e sua indisponibilidade **não** "
        "torna o serviço `not_ready`, pois os endpoints determinísticos "
        "permanecem 100% funcionais (Princípio VII / SC-009)."
    ),
)
async def readiness() -> dict:
    components: dict[str, str] = {}
    ready = True

    # Banco da plataforma (best-effort).
    try:
        from app.db.base import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception as e:  # pragma: no cover - depende de ambiente
        logger.warning("Readiness: banco indisponível: %s", type(e).__name__)
        components["database"] = "unavailable"
        ready = False

    # Snapshot da BNCC.
    try:
        service = get_bncc_service()
        meta = await service.get_snapshot_metadata()
        total = meta.contagens.get("total_habilidades", 0)
        components["bncc_snapshot"] = "ok" if total > 0 else "empty"
    except Exception:  # pragma: no cover
        components["bncc_snapshot"] = "error"

    # Camada de IA (ChromaDB/embeddings) — OPCIONAL (Princípio VII): sua
    # indisponibilidade é reportada mas NÃO torna o serviço "not_ready", pois os
    # endpoints determinísticos permanecem 100% funcionais (T064 distingue
    # "IA indisponível" de "serviço fora"; SC-009).
    try:
        from app.main import app as _app

        vector = getattr(_app.state, "vector_service", None)
        if vector is not None and getattr(vector, "available", False):
            components["ai"] = "available"
        else:
            components["ai"] = "unavailable"  # degrada graciosamente
    except Exception:  # pragma: no cover
        components["ai"] = "unavailable"

    return {"status": "ready" if ready else "not_ready", "components": components}
