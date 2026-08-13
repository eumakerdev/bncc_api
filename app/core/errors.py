"""
Handlers de erro globais (FR-024 / Princípio VI).

Respostas de erro NUNCA vazam stack trace, paths internos ou detalhes de
implementação. O corpo segue o schema estável ``ErrorResponse``
{ detail, error_code, timestamp } — e, na validação de requisição,
``ValidationErrorResponse``, que acrescenta ``errors`` (campo a campo).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

logger = logging.getLogger("bncc.errors")


def _now() -> str:
    """Instante do erro em ISO-8601 UTC — o ``timestamp`` que o contrato declara."""
    return datetime.now(UTC).isoformat()


def _error_body(detail: str, error_code: str) -> dict[str, str]:
    return {"detail": detail, "error_code": error_code, "timestamp": _now()}


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if (
        exc.status_code == status.HTTP_404_NOT_FOUND
        and not request.url.path.startswith("/api")
        and "text/html" in request.headers.get("accept", "")
    ):
        # 404 amigável para rotas web (navegador); o contrato JSON de /api fica intacto.
        # Import tardio: evita acoplar o tratamento de erros ao seam web no import.
        from app.web.jinja import templates

        return templates.TemplateResponse(
            request, "404.html", status_code=exc.status_code, headers=headers
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(str(exc.detail), f"http_{exc.status_code}"),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Mensagem clara, sem vazar internos (US1/AS4). Detalhes de campo são seguros.
    # O status é 400 — e não o 422 que o FastAPI injetaria: é o que a v1 publicada
    # sempre devolveu, e mudá-lo quebraria consumidores (Princípio I). O contrato
    # OpenAPI é alinhado a este comportamento em `app/api/openapi.py`.
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            **_error_body("Requisição inválida.", "validation_error"),
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
