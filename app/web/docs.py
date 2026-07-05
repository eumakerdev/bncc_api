"""
Guia de documentação estilizado (US3 — T054/T056).

FastAPI já expõe o Swagger UI em `/docs` e o ReDoc em `/redoc` a partir do
OpenAPI gerado (`/api/v1/openapi.json`, ver `app/main.py`) — este módulo **não**
sobrescreve `/docs`. Em vez disso, expõe `/guia`: uma página estática no design
system compartilhado com o guia de início rápido (autenticação, limites,
versionamento) e links para o Swagger/ReDoc reais, deixando claro que ambos
são gerados automaticamente a partir do mesmo contrato OpenAPI (FR-013/FR-015).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from app.web.router import templates

router = APIRouter()


@router.get("/guia", response_class=HTMLResponse, include_in_schema=False)
async def guia(request: Request) -> Response:
    """Página de documentação: guia de início rápido + link ao Swagger/ReDoc."""
    return templates.TemplateResponse(request, "docs.html")
