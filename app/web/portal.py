"""
Portal SSR self-service (T049/T050/T051) — montado em ``/portal``.

Páginas Jinja para login, cadastro e dashboard (keys + consumo). A sessão usa o
mesmo JWT do portal, guardado em cookie httponly ``session``. Sem sessão válida,
``/portal/dashboard`` redireciona para o login.

Import tardio dos serviços/deps para não acoplar o web router à camada de dados
na importação (ver app/web/router.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.deps import rate_limit_login_ip, rate_limit_signup_ip
from app.core.security import decode_access_token
from app.db.base import async_session_factory
from app.db.tables import DeveloperAccount
from app.services import account_service, apikey_service, onboarding_service, usage_service
from app.web.router import templates

router = APIRouter()

_SESSION_COOKIE = "session"
# Cookie de "flash" de uso único para exibir a API key recém-criada sem
# colocá-la na URL (histórico do navegador, logs de acesso, header Referer).
_FLASH_NEW_KEY_COOKIE = "flash_new_key"


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
    return templates.TemplateResponse(request, "portal/login.html", {"error": error})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    _rate_limit: None = Depends(rate_limit_login_ip),
):
    async with async_session_factory() as session:
        try:
            token = await account_service.login(session, email, password)
        except Exception:
            return templates.TemplateResponse(
                request,
                "portal/login.html",
                {"error": "Credenciais inválidas ou e-mail não verificado."},
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
    return templates.TemplateResponse(request, "portal/signup.html", {"error": error})


@router.post("/signup")
async def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    _rate_limit: None = Depends(rate_limit_signup_ip),
):
    async with async_session_factory() as session:
        try:
            await account_service.signup(session, email, password)
        except Exception:
            return templates.TemplateResponse(
                request,
                "portal/signup.html",
                {"error": "Não foi possível concluir o cadastro."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    return templates.TemplateResponse(
        request,
        "portal/login.html",
        {"info": "Cadastro criado. Verifique seu e-mail para liberar as API keys."},
    )


# --------------------------------------------------------------------------- #
# Verificação de e-mail (link enviado por e-mail aponta para cá)
# --------------------------------------------------------------------------- #
@router.get("/verify-email")
async def verify_email_page(request: Request, token: str | None = None):
    if not token:
        return templates.TemplateResponse(
            request,
            "portal/login.html",
            {"error": "Token de verificação ausente."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    async with async_session_factory() as session:
        try:
            await account_service.verify_email(session, token)
        except Exception:
            return templates.TemplateResponse(
                request,
                "portal/login.html",
                {"error": "Token de verificação inválido, expirado ou já usado."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    return templates.TemplateResponse(
        request,
        "portal/login.html",
        {"info": "E-mail verificado. Faça login para continuar."},
    )


# --------------------------------------------------------------------------- #
# Onboarding (requer sessão; obrigatório antes do dashboard)
# --------------------------------------------------------------------------- #
def _onboarding_context(
    question: onboarding_service.OnboardingQuestion,
    selected: list[str],
    error: str | None = None,
) -> dict:
    total = onboarding_service.TOTAL_STEPS
    return {
        "question": question,
        "step": question.step,
        "total": total,
        "progress_pct": round((question.step - 1) * 100 / total),
        "is_last": question.step == total,
        "selected": selected,
        "error": error,
    }


async def _onboarding_pending(account_id: str) -> bool:
    """True quando a conta ainda não concluiu o onboarding (gate do portal)."""
    async with async_session_factory() as session:
        profile = await onboarding_service.get_or_create_profile(session, account_id)
    return not onboarding_service.is_complete(profile)


@router.get("/onboarding")
async def onboarding_page(request: Request, step: int | None = None):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)

    async with async_session_factory() as session:
        profile = await onboarding_service.get_or_create_profile(session, account.id)

    pending = onboarding_service.first_pending_step(profile)
    if pending is None:
        return RedirectResponse(url="/portal/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    # Revisitar passos já respondidos é permitido; pular à frente, não.
    current = step if step is not None and 1 <= step <= pending else pending
    question = onboarding_service.get_question(current)
    selected = onboarding_service.saved_values(profile, question)
    return templates.TemplateResponse(
        request, "portal/onboarding.html", _onboarding_context(question, selected)
    )


@router.post("/onboarding")
async def onboarding_submit(
    request: Request,
    step: int = Form(...),
    resposta: list[str] = Form(default=[]),
):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    if not 1 <= step <= onboarding_service.TOTAL_STEPS:
        return RedirectResponse(url="/portal/onboarding", status_code=status.HTTP_303_SEE_OTHER)

    async with async_session_factory() as session:
        profile = await onboarding_service.get_or_create_profile(session, account.id)
        try:
            await onboarding_service.save_answer(session, profile, step, resposta)
        except ValueError as exc:
            question = onboarding_service.get_question(step)
            return templates.TemplateResponse(
                request,
                "portal/onboarding.html",
                _onboarding_context(question, resposta, error=str(exc)),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    # GET decide o próximo passo (ou dashboard, se concluído) — padrão PRG.
    return RedirectResponse(url="/portal/onboarding", status_code=status.HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Dashboard (requer sessão + onboarding concluído)
# --------------------------------------------------------------------------- #
@router.get("/dashboard")
async def dashboard(request: Request):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    if await _onboarding_pending(account.id):
        return RedirectResponse(url="/portal/onboarding", status_code=status.HTTP_303_SEE_OTHER)

    async with async_session_factory() as session:
        keys = await apikey_service.list_keys(session, account.id)
        usage = await usage_service.account_usage(session, account.id)

    response = templates.TemplateResponse(
        request,
        "portal/dashboard.html",
        {
            "account": account,
            "keys": keys,
            "usage": usage,
            "new_key": request.cookies.get(_FLASH_NEW_KEY_COOKIE),
        },
    )
    # Uso único: some da tela ao próximo carregamento, mesmo com F5/voltar.
    if _FLASH_NEW_KEY_COOKIE in request.cookies:
        response.delete_cookie(_FLASH_NEW_KEY_COOKIE)
    return response


@router.post("/keys")
async def dashboard_create_key(request: Request, name: str = Form(...)):
    account = await _account_from_request(request)
    if account is None:
        return RedirectResponse(url="/portal/login", status_code=status.HTTP_303_SEE_OTHER)
    if await _onboarding_pending(account.id):
        return RedirectResponse(url="/portal/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    if not account.email_verified:
        return RedirectResponse(url="/portal/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    async with async_session_factory() as session:
        _key, full_key = await apikey_service.create(session, account, name)
    # A key completa NUNCA vai na URL (histórico do navegador, logs de acesso,
    # header Referer) — trafega só via cookie httponly de uso único.
    response = RedirectResponse(url="/portal/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        _FLASH_NEW_KEY_COOKIE,
        full_key,
        httponly=True,
        samesite="lax",
        max_age=30,
    )
    return response


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
