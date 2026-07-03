"""
Agregador de routers da API v1 (seam compartilhado — NÃO editado pelos agentes).

Inclusão resiliente: cada módulo de endpoint é incluído se importável. Assim o
app sempre sobe mesmo com histórias parcialmente implementadas, e os testes de
contrato (escritos primeiro) falham por 404/ausência — não por erro de import.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger("bncc.api")

api_router = APIRouter()

# (módulo, prefixo, tags)
_ROUTES = [
    ("habilidades", "/habilidades", ["Habilidades"]),
    ("competencias", "/competencias", ["Competências"]),
    ("taxonomia", "/taxonomia", ["Taxonomia"]),
    ("sistema", "/sistema", ["Sistema"]),
    ("auth", "/auth", ["Autenticação"]),
    ("keys", "/keys", ["API Keys"]),
    ("usage", "", ["Uso"]),  # define seus próprios prefixos (/keys/{id}/usage, /usage)
    ("busca", "/busca-semantica", ["Busca Semântica"]),
]


def _wire() -> None:
    import importlib

    for module_name, prefix, tags in _ROUTES:
        try:
            module = importlib.import_module(f"app.api.v1.endpoints.{module_name}")
            router = module.router
        except Exception as e:  # módulo ainda não pronto ou dep ausente → pula
            logger.info("Router '%s' não incluído (%s)", module_name, type(e).__name__)
            continue
        if prefix:
            api_router.include_router(router, prefix=prefix, tags=tags)
        else:
            api_router.include_router(router, tags=tags)


_wire()
