"""
Rotas de infraestrutura da documentação versionada (fora do contrato de dados).

Servem, por **versão de caminho** e por **release histórica**, o mesmo OpenAPI
enriquecido que alimenta o Scalar — para que ``/docs/{versao}`` possam coexistir e
o histórico de releases congeladas (ver ``scripts/freeze_openapi.py``) fique
navegável no seletor de versão.

Todas as rotas ficam **fora do schema** (``include_in_schema=False``): são
superfícies de documentação, não endpoints de dados. Note que ``/api/v1/openapi.json``
continua sendo servido pela rota nativa do FastAPI (registrada primeiro); a rota
parametrizada abaixo cobre as demais versões e, no futuro, ``/api/v2`` etc.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import versions as vreg
from app.api.openapi import frozen_openapi, openapi_for_version, release_manifest

router = APIRouter()


@router.get("/api/versions", include_in_schema=False)
async def api_versions() -> JSONResponse:
    """Manifesto das versões da API (para o seletor de versão do Scalar e clientes)."""
    payload = {
        "latest": vreg.LATEST_SLUG,
        "versions": [
            {
                "slug": v.slug,
                "release": v.release,
                "status": v.status,
                "title": v.title,
                "summary": v.summary,
                "openapi_url": v.openapi_url,
                "docs_url": v.docs_url,
                "releases": release_manifest(v.slug),
            }
            for v in vreg.list_versions()
        ],
    }
    return JSONResponse(payload)


@router.get("/api/{slug}/openapi.json", include_in_schema=False)
async def versioned_openapi(slug: str, request: Request) -> JSONResponse:
    """OpenAPI vivo de uma versão registrada (``/api/v1/openapi.json`` vem do FastAPI)."""
    if not vreg.is_known_version(slug):
        raise HTTPException(status_code=404, detail="Versão de API desconhecida.")
    return JSONResponse(openapi_for_version(request.app, slug))


@router.get("/api/{slug}/releases/{release}/openapi.json", include_in_schema=False)
async def frozen_release_openapi(slug: str, release: str) -> JSONResponse:
    """OpenAPI congelado de uma release específica de uma versão (histórico)."""
    if not vreg.is_known_version(slug):
        raise HTTPException(status_code=404, detail="Versão de API desconhecida.")
    doc = frozen_openapi(slug, release)
    if doc is None:
        raise HTTPException(status_code=404, detail="Release não arquivada para esta versão.")
    return JSONResponse(doc)
