"""
Agregador de rotas server-rendered (SSR): landing, portal, docs.

Este módulo é o **seam compartilhado**. Cada história (US2 portal, US3 docs,
US5 landing) contribui um sub-router incluído aqui.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

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


include_web_routers()
