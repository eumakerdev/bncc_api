"""
Agregador de rotas server-rendered (SSR): landing, portal, docs.

Este módulo é o **seam compartilhado**. Cada história (US2 portal, US3 docs,
US5 landing) contribui um sub-router incluído aqui. O ambiente Jinja compartilhado
vive em `app.web.jinja` — fora daqui — para quebrar o ciclo de importação
router ↔ sub-rotas (todas importam ``templates``).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

web_router = APIRouter()


def include_web_routers() -> None:
    """Inclui sub-routers das histórias, se presentes (import tardio p/ evitar acoplamento)."""
    try:
        from app.web.landing import router as landing_router

        web_router.include_router(landing_router)
    except ImportError:
        # Landing ausente (história não construída) — seam segue sem a rota.
        pass
    try:
        from app.web.portal import router as portal_router

        web_router.include_router(portal_router, prefix="/portal")
    except ImportError:
        # Portal ausente (história não construída) — seam segue sem a rota.
        pass
    try:
        from app.web.docs import router as docs_router

        web_router.include_router(docs_router)
    except ImportError:
        # Docs ausentes (história não construída) — seam segue sem a rota.
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
            # Admin ausente/desabilitado — seam segue sem a rota.
            pass


include_web_routers()
