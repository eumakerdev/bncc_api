"""
Superfícies de documentação (US3).

Duas páginas complementares, ambas alimentadas pelo **mesmo contrato OpenAPI**
(`/api/v1/openapi.json`, gerado em `app/main.py`) — nada de endpoints escritos à
mão que possam divergir do código (Princípio I):

- ``/guia``  — hub de conteúdo (início rápido, autenticação, paginação, erros,
  limites, busca semântica, versionamento) no design system compartilhado.
- ``/docs``  — referência interativa renderizada pelo **Scalar** (3 colunas,
  dark mode, exemplos multi-linguagem, "Try it"). O bundle é **self-hosted** em
  ``/static/vendor/`` (sem CDN — Princípio V), apontando para o OpenAPI vivo.

ReDoc continua disponível em ``/redoc`` como fallback leve (ver ``app/main.py``).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from app.web.router import templates

router = APIRouter()


@router.get("/guia", response_class=HTMLResponse, include_in_schema=False)
async def guia(request: Request) -> Response:
    """Hub de documentação: início rápido, autenticação, limites e versionamento."""
    return templates.TemplateResponse(request, "docs.html")


@router.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def api_reference(request: Request) -> Response:
    """Referência interativa da API renderizada pelo Scalar (self-hosted)."""
    return templates.TemplateResponse(request, "reference.html")
