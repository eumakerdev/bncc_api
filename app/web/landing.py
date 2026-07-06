"""
Landing page pública + metadados de SEO (US5 — T067-T070).

Contribui ao seam compartilhado em `app.web.router` (ver docstring lá): expõe
`GET /` (landing), `GET /sitemap.xml` e `GET /robots.txt`. Não depende de
nenhuma API em runtime — conteúdo é estático/SSR (independente das demais
histórias, conforme tasks.md Fase 7).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from app.web.router import templates

router = APIRouter()

# Rotas públicas indexáveis (usadas pelo sitemap).
_PUBLIC_PATHS = [
    "/",
    "/guia",
    "/docs",
    "/portal/signup",
    "/portal/login",
]


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing(request: Request) -> Response:
    """Landing page: proposta de valor, recursos, público-alvo e CTA (SC-008)."""
    return templates.TemplateResponse(request, "landing.html")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request) -> Response:
    """Sitemap XML simples listando as rotas públicas indexáveis."""
    base = str(request.base_url).rstrip("/")
    urls = "\n".join(f"  <url><loc>{base}{path}</loc></url>" for path in _PUBLIC_PATHS)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
async def robots(request: Request) -> Response:
    """robots.txt permitindo indexação e apontando para o sitemap."""
    base = str(request.base_url).rstrip("/")
    body = "User-agent: *\n" "Allow: /\n" f"Sitemap: {base}/sitemap.xml\n"
    return Response(content=body, media_type="text/plain")
