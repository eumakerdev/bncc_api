"""
Portal SSR self-service (T049/T050/T051) — montado em ``/portal``.

Páginas Jinja para login, cadastro e dashboard (keys + consumo). A sessão usa o
mesmo JWT do portal, guardado em cookie httponly ``session``. Sem sessão válida,
``/portal/dashboard`` redireciona para o login.

Import tardio dos serviços/deps para não acoplar o web router à camada de dados
na importação (ver app/web/router.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.base import async_session_factory
from app.db.tables import DeveloperAccount
from app.services import account_service, apikey_service, usage_service
from app.web.router import templates

router = APIRouter()

_SESSION_COOKIE = "session"


def _set_session(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def _account_from_request(request: Request) -> DeveloperAccount | None:
    token = request.cookies.get(_SESSION_COOKIE)
    payload = decode_access_token(token) if token else None
    if not payload or "sub" not in payload:
        return None
    async with async_session_factory() as session:
        return await session.get(DeveloperAccount, payload["sub"])


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #
@router.get("/login")
async def login_page(request: Request, error: str | None = None):
    return templates.TemplateResponse("portal/login.html", {"request": request, "error": error})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    async with async_session_factory() as session:
        try:
            token = await account_service.login(session, email, password)
        except Exception:
            return templates.TemplateResponse(
                "portal/login.html",
                {
                    "request": request,
                    "error": "Credenciais inválidas ou e-mail não verificado.",
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
    response = RedirectResponse(url="/portal/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    _set_session(response, token)
    return response


# --------------------------------------------------------------------------- #
# Signup
# --------------------------------------------------------------------------- #
@router.get("/signup")
async def signup_page(request: Request, error: str | None = None):
    return templates.TemplateResponse("portal/signup.html", {"request": request, "error": error})


@router.post("/signup")
async def signup_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    async with async_session_factory() as session:
        try:
            await account_service.signup(session, email, password)
        except Exception:
            return templates.TemplateResponse(
                "portal/signup.html",
                {
                    "request": request,
                    "error": "Não foi possível concluir o cadastro.",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    return templates.TemplateResponse(
        "portal/login.html",
        {
            "request": request,
            "info": "Cadastro criado. Verifique seu e-mail para liberar as API keys.",
        },
    )


# --------------------------------------------------------------------------- #
# Verificação de e-mail (link enviado por e-mail aponta para cá)
# --------------------------------------------------------------------------- #
@router.get("/verify-email")
async def verify_email_page(request: Request, token: str | None = None):
    if not token:
        return templates.TemplateResponse(
            "portal/login.html",
            {"request": request, "error": "Token de verificação ausente."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    async with async_session_factory() as session:
        try:
            await account_service.verify_email(session, token)
        except Exception:
            return templates.TemplateResponse(
                "portal/login.html",
                {
                    "request": request,
                    "error": "Token de verificação inválido, expirado ou já usado.",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    return templates.TemplateResponse(
        "portal/login.html",
        {"request": request, "info": "E-mail verificado. Faça login para continuar."},
    )


# --------------------------------------------------------------------------- #
# Dashboard (requer sessão)
# --------------------------------------------------------------------------- #
@router.get("/dashboard")
async def dashboard(request: Request):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)

    async with async_session_factory() as session:
        keys = await apikey_service.list_keys(session, account.id)
        usage = await usage_service.account_usage(session, account.id)

    return templates.TemplateResponse(
        "portal/dashboard.html",
        {
            "request": request,
            "account": account,
            "keys": keys,
            "usage": usage,
            "new_key": request.query_params.get("new_key"),
        },
    )


@router.post("/keys")
async def dashboard_create_key(request: Request, name: str = Form(...)):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    if not account.email_verified:
        return RedirectResponse(url="/portal/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    async with async_session_factory() as session:
        _key, full_key = await apikey_service.create(session, account, name)
    return RedirectResponse(
        url=f"/portal/dashboard?new_key={full_key}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/keys/{key_id}/revoke")
async def dashboard_revoke_key(request: Request, key_id: str):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    async with async_session_factory() as session:
        try:
            await apikey_service.revoke(session, account.id, key_id)
        except Exception:
            pass
    return RedirectResponse(url="/portal/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(_SESSION_COOKIE)
    return response
