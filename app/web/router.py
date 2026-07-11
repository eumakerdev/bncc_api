"""
Agregador de rotas server-rendered (SSR): landing, portal, docs.

Este módulo é o **seam compartilhado**. Cada história (US2 portal, US3 docs,
US5 landing) contribui um sub-router incluído aqui.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.core.config import settings

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _seo_context(request: Request) -> dict[str, str]:
    """Injeta `site_url`/`current_path` em todos os templates SSR.

    `site_url` prefere `settings.SITE_URL` (determinístico, domínio primário) e só
    cai para `request.base_url` quando não configurado (dev). Assim canonical/OG/
    sitemap nunca vazam a URL interna do Cloud Run quando servido atrás do Firebase
    Hosting (que entrega o `Host` do `.run.app` ao container)."""
    base = (settings.SITE_URL or str(request.base_url)).rstrip("/")
    return {"site_url": base, "current_path": request.url.path}


def _brl(value: object) -> str:
    """Filtro Jinja: formata um número como moeda pt-BR (R$ 1.234,56)."""
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    formatted = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _milhar(value: object) -> str:
    """Filtro Jinja: agrupa milhar no padrão pt-BR (2500 → '2.500')."""
    try:
        n = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return ""
    return f"{n:,}".replace(",", ".")


templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[_seo_context])
templates.env.filters["brl"] = _brl
templates.env.filters["milhar"] = _milhar

web_router = APIRouter()


def include_web_routers() -> None:
    """Inclui sub-routers das histórias, se presentes (import tardio p/ evitar acoplamento)."""
    try:
        from app.web.landing import router as landing_router

        web_router.include_router(landing_router)
    except ImportError:
        pass
    try:
        from app.web.portal import router as portal_router

        web_router.include_router(portal_router, prefix="/portal")
    except ImportError:
        pass
    try:
        from app.web.docs import router as docs_router

        web_router.include_router(docs_router)
    except ImportError:
        pass
    # Fronteira 1 (isolamento): o painel de admin só é MONTADO quando habilitado.
    # No deploy público de produção `admin_enabled` é False → não há rota `/admin`
    # (nem stub 404) nem em `bncc.api.br` nem na URL crua do `run.app`. A superfície
    # de admin pública fica inexistente; o acesso é local ou pelo serviço dedicado.
    if settings.admin_enabled:
        try:
            from app.web.admin import router as admin_router

            web_router.include_router(admin_router, prefix="/admin")
        except ImportError:
            pass


include_web_routers()
