"""
Ambiente Jinja compartilhado do seam SSR (``app/web``).

Vive fora de ``app/web/router.py`` para quebrar o ciclo de importação
router → {landing, portal, docs, admin} → router (todas as sub-rotas importam
``templates``). Sub-rotas e demais consumidores importam daqui; este módulo não
importa nada de ``app.web`` de volta.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
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
