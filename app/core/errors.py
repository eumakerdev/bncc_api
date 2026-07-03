"""
Handlers de erro globais (FR-024 / Princípio VI).

Respostas de erro NUNCA vazam stack trace, paths internos ou detalhes de
implementação. O corpo segue o schema estável { detail, error_code }.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("bncc.errors")


def _error_body(detail: str, error_code: str) -> dict[str, str]:
    return {"detail": detail, "error_code": error_code}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(str(exc.detail), f"http_{exc.status_code}"),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Mensagem clara, sem vazar internos (US1/AS4). Detalhes de campo são seguros.
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Requisição inválida.",
            "error_code": "validation_error",
            "errors": [
                {"campo": ".".join(str(p) for p in e.get("loc", [])), "msg": e.get("msg")}
                for e in exc.errors()
            ],
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Loga internamente (sem PII/segredos), responde genérico ao cliente.
    logger.error("Erro não tratado em %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("Erro interno do servidor.", "internal_error"),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Registra os handlers globais na aplicação."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
