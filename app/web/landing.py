"""
Landing page pública + metadados de SEO (US5 — T067-T070).

Contribui ao seam compartilhado em `app.web.router` (ver docstring lá): expõe
`GET /` (landing), `GET /sitemap.xml` e `GET /robots.txt`. Não depende de
nenhuma API em runtime — conteúdo é estático/SSR (independente das demais
histórias, conforme tasks.md Fase 7).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from app.core.config import settings
from app.web.router import templates

router = APIRouter()
logger = logging.getLogger("bncc.landing")

# Cache conservador (a CDN do Firebase Hosting cacheia por variante de
# accept-encoding e a purga exige redeploy do hosting — TTL curto limita o raio).
_CACHE_1H = "public, max-age=3600"
_CACHE_1D = "public, max-age=86400"

_FAVICON_ICO = Path(__file__).parent / "static" / "favicon.ico"


class _SitemapEntry(NamedTuple):
    path: str
    priority: str | None = None


# Rotas públicas indexáveis (lista curada; login/dashboard/onboarding são noindex).
_SITEMAP_ENTRIES = [
    _SitemapEntry("/", priority="1.0"),
    _SitemapEntry("/guia", priority="0.8"),
    _SitemapEntry("/docs", priority="0.8"),
    _SitemapEntry("/portal/signup", priority="0.6"),
]


async def _cost_context() -> dict:
    """Monta o contexto da seção "Transparência de custos" de forma resiliente.

    Lê apenas o banco (nunca o BigQuery). Qualquer falha (banco indisponível,
    tabela vazia) degrada para uma landing sem a seção — nunca quebra a página
    pública (Princípio VII). Import tardio para não acoplar o web router à camada
    de dados na importação.
    """
    try:
        from app.db.base import async_session_factory
        from app.services import cost_service
        from app.web.charts import build_cost_chart

        async with async_session_factory() as session:
            summary = await cost_service.public_cost_summary(session)
        return {"cost_summary": summary, "cost_chart": build_cost_chart(summary.series)}
    except Exception:
        logger.exception("Falha ao montar a transparência de custos")
        return {"cost_summary": None, "cost_chart": None}


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing(request: Request) -> Response:
    """Landing page: proposta de valor, recursos, público-alvo e CTA (SC-008)."""
    return templates.TemplateResponse(request, "landing.html", await _cost_context())


@router.get("/favicon.ico", include_in_schema=False)
@router.head("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Favicon no caminho padrão pedido por navegadores e crawlers."""
    return FileResponse(
        _FAVICON_ICO, media_type="image/x-icon", headers={"Cache-Control": _CACHE_1D}
    )


def _sitemap_url(base: str, entry: _SitemapEntry) -> str:
    parts = f"<loc>{base}{entry.path}</loc>"
    if entry.priority:
        parts += f"<priority>{entry.priority}</priority>"
    return f"  <url>{parts}</url>"


@router.get("/sitemap.xml", include_in_schema=False)
@router.head("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request) -> Response:
    """Sitemap XML listando as rotas públicas indexáveis."""
    base = (settings.SITE_URL or str(request.base_url)).rstrip("/")
    urls = "\n".join(_sitemap_url(base, entry) for entry in _SITEMAP_ENTRIES)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml", headers={"Cache-Control": _CACHE_1H})


@router.get("/robots.txt", include_in_schema=False)
@router.head("/robots.txt", include_in_schema=False)
async def robots(request: Request) -> Response:
    """robots.txt: bloqueia superfícies sem valor de indexação e aponta o sitemap.

    `/api/` é JSON autenticado e `/portal/auth/` são redirects OAuth (queimam
    rate limit); `/redoc` duplica `/docs`. `/portal/login` fica crawleável de
    propósito — o Google precisa ler a página para ver o meta noindex.
    """
    base = (settings.SITE_URL or str(request.base_url)).rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /portal/auth/\n"
        "Disallow: /redoc\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(content=body, media_type="text/plain", headers={"Cache-Control": _CACHE_1H})
