"""
Painel de administração da plataforma — montado em ``/admin``.

Isolado do portal do desenvolvedor e do runtime público: o router só é MONTADO
quando ``settings.admin_enabled`` (ver ``app/web/router.py``). Não é publicado no
OpenAPI nem indexado por buscadores.

Autenticação (Fronteira 2 do plano de segurança):
- **Produção/remoto**: apenas **Google Sign-In** restrito à allowlist
  ``ADMIN_ALLOWED_EMAILS`` (identidade por pessoa; MFA vem da conta Google).
- **Dev local**: além do Google, aceita a senha ``ADMIN_PASSWORD`` por conveniência
  (``admin_password_enabled`` é False em produção).

Hardening (Fronteira 3): rate limit por IP nas tentativas de auth (``AdminRateLimited``),
CSRF double-submit no POST de senha, e logs estruturados de toda tentativa.

Princípios observados:
- II: camada web não conhece ORM — delega tudo ao ``admin_service``.
- III: ver ``tests/contract/test_admin.py``.
- V: auth obrigatória; cookies httponly; sem segredo hardcoded; obscuridade não é defesa.
"""

from __future__ import annotations

import hmac
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.deps import AdminRateLimited, get_http_client
from app.core.security import create_access_token, decode_access_token
from app.db.base import async_session_factory
from app.services import oauth_service
from app.web.router import templates

router = APIRouter(include_in_schema=False)
logger = logging.getLogger("bncc.admin")

_ADMIN_COOKIE = "__admin_session"
# Sessão curta (2h): o painel é sensível e o acesso é interativo (sem "lembre de mim").
_ADMIN_SESSION_MINUTES = 2 * 60
# Cookie transitório do state OAuth (double-submit anti-CSRF) e do token CSRF do
# formulário de senha. O admin nunca roda atrás do Firebase Hosting (que só preserva
# `__session`), então nomes dedicados são seguros aqui.
_ADMIN_STATE_COOKIE = "__admin_oauth_state"
_ADMIN_CSRF_COOKIE = "__admin_csrf"
_ADMIN_STATE_TTL_MINUTES = 10
# Caminho de callback do OAuth admin (deve estar registrado no cliente Google).
_ADMIN_CALLBACK_PATH = "/admin/auth/google/callback"


# --------------------------------------------------------------------------- #
# Helpers internos
# --------------------------------------------------------------------------- #


def _admin_enabled() -> bool:
    return settings.admin_enabled


def _log_ip(request: Request) -> str:
    """IP para log de auditoria (best-effort; honra X-Forwarded-For em produção)."""
    if settings.is_production:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip() or "?"
    return request.client.host if request.client else "?"


def _check_password(candidate: str) -> bool:
    """Compara ``candidate`` com ADMIN_PASSWORD em tempo constante (anti-timing)."""
    return hmac.compare_digest(settings.ADMIN_PASSWORD.encode(), candidate.encode())


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


def _issue_admin_session(subject: str) -> RedirectResponse:
    """Monta o redirect autenticado (cookie de sessão) para ``subject`` (e-mail/dev)."""
    token = create_access_token(
        subject=subject,
        expires_minutes=_ADMIN_SESSION_MINUTES,
        role="admin",
    )
    response = RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    _set_admin_session(response, token)
    return response


def _not_found():
    """Retorna 404 quando o painel está desabilitado (sem vazar rotas)."""
    raise HTTPException(status_code=404, detail="Not Found")


# --------------------------------------------------------------------------- #
# Login (página + caminhos: Google Sign-In e senha dev-only)
# --------------------------------------------------------------------------- #


@router.get("/login")
async def admin_login_page(request: Request, error: str | None = None):
    if not _admin_enabled():
        _not_found()
    if _admin_from_request(request):
        return RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)

    # Emite um token CSRF para o formulário de senha (double-submit).
    csrf = secrets.token_urlsafe(24)
    ctx = {
        "error": error,
        "google_enabled": settings.admin_google_enabled,
        "password_enabled": settings.admin_password_enabled,
        "csrf_token": csrf,
    }
    response = templates.TemplateResponse(request, "admin/login.html", ctx)
    response.set_cookie(
        _ADMIN_CSRF_COOKIE,
        csrf,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=_ADMIN_STATE_TTL_MINUTES * 60,
    )
    return response


@router.post("/login")
async def admin_login_submit(
    request: Request,
    _rate_limit: AdminRateLimited,
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    """Login por senha — habilitado APENAS fora de produção (dev local)."""
    if not _admin_enabled():
        _not_found()
    if not settings.admin_password_enabled:
        # Em produção não existe caminho de senha; não vaza que ele existiria.
        _not_found()

    # CSRF double-submit: o token do form precisa bater com o cookie httponly.
    cookie_csrf = request.cookies.get(_ADMIN_CSRF_COOKIE)
    if not cookie_csrf or not hmac.compare_digest(cookie_csrf, csrf_token):
        logger.warning("Login admin (senha) rejeitado por CSRF (IP=%s)", _log_ip(request))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF inválido")

    if not _check_password(password):
        logger.warning("Tentativa de login admin (senha) falhou (IP=%s)", _log_ip(request))
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {
                "error": "Senha incorreta.",
                "google_enabled": settings.admin_google_enabled,
                "password_enabled": settings.admin_password_enabled,
                "csrf_token": csrf_token,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    logger.info("Login admin (senha, dev) bem-sucedido (IP=%s)", _log_ip(request))
    return _issue_admin_session("dev-local")


@router.get("/auth/google")
async def admin_google_start(request: Request, _rate_limit: AdminRateLimited):
    """Inicia o Google Sign-In do admin (gera state anti-CSRF e redireciona)."""
    if not _admin_enabled():
        _not_found()
    if not settings.admin_google_enabled:
        _not_found()

    nonce = secrets.token_urlsafe(16)
    authorize_url = oauth_service.build_authorize_url(
        "google", state=nonce, callback_path=_ADMIN_CALLBACK_PATH
    )
    response = RedirectResponse(url=authorize_url, status_code=status.HTTP_303_SEE_OTHER)
    state_token = create_access_token(
        subject=nonce,
        expires_minutes=_ADMIN_STATE_TTL_MINUTES,
        purpose="admin_oauth_state",
    )
    response.set_cookie(
        _ADMIN_STATE_COOKIE,
        state_token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=_ADMIN_STATE_TTL_MINUTES * 60,
    )
    return response


@router.get("/auth/google/callback")
async def admin_google_callback(
    request: Request,
    _rate_limit: AdminRateLimited,
    code: str | None = None,
    state: str | None = None,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Recebe o retorno do Google: valida state, resolve identidade e checa allowlist."""
    if not _admin_enabled():
        _not_found()
    if not settings.admin_google_enabled:
        _not_found()

    def _fail(msg: str):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {
                "error": msg,
                "google_enabled": settings.admin_google_enabled,
                "password_enabled": settings.admin_password_enabled,
                "csrf_token": secrets.token_urlsafe(24),
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Anti-CSRF: cookie de state (JWT assinado) precisa existir e ter `sub` == ?state=.
    state_cookie = request.cookies.get(_ADMIN_STATE_COOKIE)
    payload = decode_access_token(state_cookie) if state_cookie else None
    if (
        not code
        or not state
        or not payload
        or payload.get("purpose") != "admin_oauth_state"
        or payload.get("sub") != state
    ):
        logger.warning("Callback admin OAuth com state inválido (IP=%s)", _log_ip(request))
        return _fail("Falha na autenticação. Tente novamente.")

    try:
        access_token = await oauth_service.exchange_code(
            "google", code, client, callback_path=_ADMIN_CALLBACK_PATH
        )
        info = await oauth_service.fetch_identity("google", access_token, client)
    except oauth_service.OAuthError:
        logger.warning("Callback admin OAuth falhou na troca/identidade (IP=%s)", _log_ip(request))
        return _fail("Falha na autenticação. Tente novamente.")
    except Exception:
        logger.exception("Erro inesperado no callback admin OAuth (IP=%s)", _log_ip(request))
        return _fail("Falha na autenticação. Tente novamente.")

    # Autorização: e-mail verificado E na allowlist. Fora dela → 403 auditado.
    if not settings.is_admin_email(info.email):
        logger.warning(
            "Acesso admin NEGADO: %s fora da allowlist (IP=%s)", info.email, _log_ip(request)
        )
        return _fail("Esta conta Google não tem acesso ao painel.")

    logger.info("Login admin (Google) bem-sucedido: %s (IP=%s)", info.email, _log_ip(request))
    response = _issue_admin_session(info.email)
    response.delete_cookie(_ADMIN_STATE_COOKIE)
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
async def admin_dashboard(request: Request, days: int = 30):
    if not _admin_enabled():
        _not_found()
    if not _admin_from_request(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    from app.services import admin_service
    from app.web.charts import build_usage_chart

    window = admin_service.normalize_window(days)

    async with async_session_factory() as session:
        overview = await admin_service.get_overview(session)
        composition = await admin_service.get_account_composition(session)
        analytics = await admin_service.get_platform_analytics(session, days=window)
        top_accounts = await admin_service.get_top_accounts(session, days=window, limit=10)

    # A série do admin_service já expõe .total/.successful/.date → alimenta o chart
    # existente (total vs. bem-sucedidas), tornando o gap de erro visível.
    chart = build_usage_chart(analytics.series)

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "overview": overview,
            "composition": composition,
            "analytics": analytics,
            "top_accounts": top_accounts,
            "chart": chart,
            "window": window,
            "windows": admin_service.ALLOWED_WINDOWS,
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


@router.get("/users/{account_id}")
async def admin_user_detail(request: Request, account_id: str, days: int = 30):
    if not _admin_enabled():
        _not_found()
    if not _admin_from_request(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    from fastapi import HTTPException

    from app.services import admin_service
    from app.web.charts import build_usage_chart

    window = admin_service.normalize_window(days)

    async with async_session_factory() as session:
        detail = await admin_service.get_account_detail(session, account_id, days=window)

    if detail is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    chart = build_usage_chart(detail.series)

    return templates.TemplateResponse(
        request,
        "admin/user_detail.html",
        {
            "detail": detail,
            "chart": chart,
            "window": window,
            "windows": admin_service.ALLOWED_WINDOWS,
        },
    )


# --------------------------------------------------------------------------- #
# Custos de infraestrutura
# --------------------------------------------------------------------------- #


@router.get("/costs")
async def admin_costs(request: Request):
    if not _admin_enabled():
        _not_found()
    if not _admin_from_request(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    from app.services import cost_service
    from app.web.charts import build_cost_chart

    async with async_session_factory() as session:
        summary = await cost_service.public_cost_summary(session)

    chart = build_cost_chart(summary.series)

    return templates.TemplateResponse(
        request,
        "admin/costs.html",
        {"summary": summary, "chart": chart},
    )
