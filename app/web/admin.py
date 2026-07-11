"""
Painel de administração da plataforma — montado em ``/admin``.

Isolado do portal do desenvolvedor. Protegido por senha de administrador definida
em ``settings.ADMIN_PASSWORD`` (variável de ambiente). Vazio = painel desabilitado
(retorna 404). Não publicado no OpenAPI nem indexado por buscadores.

Uso exclusivamente local: não é exposto publicamente em produção sem configuração
explícita de rede (reverse proxy / firewall).

Princípios observados:
- II: camada web não conhece ORM — delega tudo ao ``admin_service``.
- III: ver ``tests/contract/test_admin.py``.
- V: autenticação obrigatória; cookie httponly; sem senha hardcoded.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.db.base import async_session_factory
from app.web.router import templates

router = APIRouter(include_in_schema=False)
logger = logging.getLogger("bncc.admin")

_ADMIN_COOKIE = "__admin_session"
# Duração da sessão de admin: 8 horas (uso local/interativo, sem "lembre de mim").
_ADMIN_SESSION_MINUTES = 8 * 60


# --------------------------------------------------------------------------- #
# Helpers internos
# --------------------------------------------------------------------------- #


def _admin_enabled() -> bool:
    return settings.admin_enabled


def _check_password(candidate: str) -> bool:
    """Compara ``candidate`` com ADMIN_PASSWORD em tempo constante (anti-timing)."""
    expected = settings.ADMIN_PASSWORD.encode()
    given = candidate.encode()
    return hmac.compare_digest(
        hashlib.sha256(expected).digest(),
        hashlib.sha256(given).digest(),
    )


def _set_admin_session(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        _ADMIN_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=_ADMIN_SESSION_MINUTES * 60,
    )


def _clear_admin_session(response: RedirectResponse) -> None:
    response.delete_cookie(_ADMIN_COOKIE)


def _admin_from_request(request: Request) -> bool:
    """Valida o cookie de sessão de admin; retorna True se autenticado."""
    if not _admin_enabled():
        return False
    token = request.cookies.get(_ADMIN_COOKIE)
    if not token:
        return False
    payload = decode_access_token(token)
    return bool(payload and payload.get("role") == "admin")


def _not_found():
    """Retorna 404 quando o painel está desabilitado (sem vazar rotas)."""
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Not Found")


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


@router.get("/login")
async def admin_login_page(request: Request, error: str | None = None):
    if not _admin_enabled():
        _not_found()
    if _admin_from_request(request):
        return RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "admin/login.html", {"error": error})


@router.post("/login")
async def admin_login_submit(
    request: Request,
    password: str = Form(...),
):
    if not _admin_enabled():
        _not_found()
    if not _check_password(password):
        client_host = request.client.host if request.client else "?"
        logger.warning("Tentativa de login de admin falhou (IP=%s)", client_host)
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": "Senha incorreta."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    token = create_access_token(
        subject="admin",
        expires_minutes=_ADMIN_SESSION_MINUTES,
        role="admin",
    )
    response = RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    _set_admin_session(response, token)
    logger.info("Login de admin bem-sucedido (IP=%s)", request.client and request.client.host)
    return response


@router.get("/logout")
async def admin_logout(request: Request):
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    _clear_admin_session(response)
    return response


# --------------------------------------------------------------------------- #
# Dashboard (overview)
# --------------------------------------------------------------------------- #


@router.get("/")
async def admin_dashboard(request: Request):
    if not _admin_enabled():
        _not_found()
    if not _admin_from_request(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    from app.models.platform import UsageDailyPoint as ModelPoint
    from app.services import admin_service
    from app.web.charts import build_usage_chart

    async with async_session_factory() as session:
        overview = await admin_service.get_overview(session)
        analytics = await admin_service.get_platform_analytics(session, days=30)

    # Adapta a série do admin_service para o build_usage_chart existente.
    chart_series = [
        ModelPoint(date=p.date, total=p.total, successful=p.total, failed=0)
        for p in analytics.series
    ]
    chart = build_usage_chart(chart_series)

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "overview": overview,
            "analytics": analytics,
            "chart": chart,
        },
    )


# --------------------------------------------------------------------------- #
# Usuários
# --------------------------------------------------------------------------- #


@router.get("/users")
async def admin_users(request: Request):
    if not _admin_enabled():
        _not_found()
    if not _admin_from_request(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    from app.services import admin_service

    async with async_session_factory() as session:
        accounts = await admin_service.list_accounts(session)

    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {"accounts": accounts},
    )
