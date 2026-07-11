"""
Testes de contrato para o painel de administração (/admin).

Verifica:
- Acesso sem senha configurada → 404 (admin desabilitado).
- Login com senha correta → redireciona para /admin/.
- Login com senha errada → 401.
- Dashboard com sessão válida → 200 e conteúdo esperado.
- Usuários com sessão válida → 200.
- Logout → limpa sessão.
- Rotas protegidas sem sessão → redirecionam para /admin/login.
"""

from __future__ import annotations

import pytest

ADMIN_PW = "admin-test-secret-123"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_admin_env(monkeypatch, pw: str = ADMIN_PW) -> None:
    """Habilita o admin por senha (dev) em tempo de teste."""
    monkeypatch.setattr("app.core.config.settings.ADMIN_MODE", True)
    monkeypatch.setattr("app.core.config.settings.ADMIN_PASSWORD", pw)


def _disable_admin(monkeypatch) -> None:
    """Desliga o painel (ADMIN_MODE=False) → rotas montadas retornam 404."""
    monkeypatch.setattr("app.core.config.settings.ADMIN_MODE", False)


async def _csrf_login(async_client, monkeypatch, pw: str = ADMIN_PW, follow_redirects=False):
    """Fluxo real de login por senha: GET (pega o CSRF) → POST com o token."""
    _set_admin_env(monkeypatch)
    await async_client.get("/admin/login")
    csrf = async_client.cookies.get("__admin_csrf")
    return await async_client.post(
        "/admin/login",
        data={"password": pw, "csrf_token": csrf or ""},
        follow_redirects=follow_redirects,
    )


# ---------------------------------------------------------------------------
# Painel desabilitado (ADMIN_PASSWORD vazio, default)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_disabled_login_returns_404(async_client, monkeypatch):
    _disable_admin(monkeypatch)
    r = await async_client.get("/admin/login")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_disabled_dashboard_returns_404(async_client, monkeypatch):
    _disable_admin(monkeypatch)
    r = await async_client.get("/admin/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_disabled_users_returns_404(async_client, monkeypatch):
    _disable_admin(monkeypatch)
    r = await async_client.get("/admin/users")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_login_page_200_when_enabled(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.get("/admin/login")
    assert r.status_code == 200
    assert "Painel de Administração" in r.text


@pytest.mark.asyncio
async def test_admin_login_wrong_password_returns_401(async_client, monkeypatch):
    r = await _csrf_login(async_client, monkeypatch, pw="senha-errada")
    assert r.status_code == 401
    assert "Senha incorreta" in r.text


@pytest.mark.asyncio
async def test_admin_login_correct_password_redirects(async_client, monkeypatch):
    r = await _csrf_login(async_client, monkeypatch)
    assert r.status_code == 303
    assert r.headers["location"] in ("/admin/", "http://test/admin/")


@pytest.mark.asyncio
async def test_admin_login_sets_cookie(async_client, monkeypatch):
    r = await _csrf_login(async_client, monkeypatch)
    assert "__admin_session" in r.cookies


@pytest.mark.asyncio
async def test_admin_login_bad_csrf_returns_403(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    await async_client.get("/admin/login")  # define o cookie CSRF
    r = await async_client.post(
        "/admin/login",
        data={"password": ADMIN_PW, "csrf_token": "token-forjado"},
        follow_redirects=False,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_password_blocked_in_production(async_client, monkeypatch):
    """Em produção o caminho de senha não existe (só Google), mesmo com senha setada."""
    # Painel habilitado por Google (para a página existir), mas em produção.
    _enable_google(monkeypatch)
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "production")
    monkeypatch.setattr("app.core.config.settings.ADMIN_PASSWORD", ADMIN_PW)
    await async_client.get("/admin/login")  # 200 (Google), define o cookie CSRF
    csrf = async_client.cookies.get("__admin_csrf")
    r = await async_client.post(
        "/admin/login",
        data={"password": ADMIN_PW, "csrf_token": csrf or ""},
        follow_redirects=False,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Dashboard e Usuários (sessão válida)
# ---------------------------------------------------------------------------


async def _login(async_client, monkeypatch) -> dict:
    """Faz login de admin (senha dev, com CSRF) e retorna os cookies da sessão."""
    r = await _csrf_login(async_client, monkeypatch)
    return dict(r.cookies)


@pytest.mark.asyncio
async def test_admin_dashboard_returns_200(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/", cookies=cookies)
    assert r.status_code == 200
    assert "Dashboard da Plataforma" in r.text


@pytest.mark.asyncio
async def test_admin_users_returns_200(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/users", cookies=cookies)
    assert r.status_code == 200
    assert "Usuários da Plataforma" in r.text


@pytest.mark.asyncio
async def test_admin_dashboard_shows_kpis(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/", cookies=cookies)
    assert r.status_code == 200
    assert "Contas cadastradas" in r.text
    assert "API Keys ativas" in r.text
    assert "Requisições hoje" in r.text


# ---------------------------------------------------------------------------
# Proteção: sem sessão redireciona para /admin/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_dashboard_without_session_redirects(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.get("/admin/", follow_redirects=False)
    assert r.status_code == 303
    assert "login" in r.headers["location"]


@pytest.mark.asyncio
async def test_admin_users_without_session_redirects(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.get("/admin/users", follow_redirects=False)
    assert r.status_code == 303
    assert "login" in r.headers["location"]


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_logout_clears_cookie(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/logout", cookies=cookies, follow_redirects=False)
    assert r.status_code == 303
    # Após logout a sessão deve estar removida (cookie com max_age=0 ou ausente).
    assert "__admin_session" not in r.cookies or r.cookies.get("__admin_session") == ""


@pytest.mark.asyncio
async def test_admin_login_page_redirects_when_already_logged_in(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/login", cookies=cookies, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] in ("/admin/", "http://test/admin/")


# ---------------------------------------------------------------------------
# Dados com usuário cadastrado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_users_shows_account_in_table(async_client, monkeypatch, verified_account):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/users", cookies=cookies)
    assert r.status_code == 200
    assert verified_account.email in r.text


@pytest.mark.asyncio
async def test_admin_dashboard_counts_account(async_client, monkeypatch, verified_account):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/", cookies=cookies)
    assert r.status_code == 200
    # Com 1 conta cadastrada a KPI deve mostrar "1" em algum lugar.
    assert "1" in r.text


# ---------------------------------------------------------------------------
# BI: período, top consumidores, composição, detalhe, custos
# ---------------------------------------------------------------------------


async def _seed_usage(db_session, api_key, days_ago: int, count: int, errors: int, bucket):
    """Insere um UsageRecord para a key numa janela diária no passado."""
    from datetime import UTC, datetime, timedelta

    from app.db.tables import UsageRecord

    _, key = api_key
    window = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days_ago
    )
    db_session.add(
        UsageRecord(
            api_key_id=key.id,
            bucket=bucket,
            window_start=window,
            count=count,
            error_count=errors,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_admin_dashboard_accepts_period(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    for days in (7, 30, 90):
        r = await async_client.get(f"/admin/?days={days}", cookies=cookies)
        assert r.status_code == 200
        assert f"últimos {days} dias" in r.text


@pytest.mark.asyncio
async def test_admin_dashboard_invalid_period_falls_back(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/?days=999", cookies=cookies)
    assert r.status_code == 200
    # Janela inválida cai no default de 30 dias.
    assert "últimos 30 dias" in r.text


@pytest.mark.asyncio
async def test_admin_dashboard_has_bi_sections(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/", cookies=cookies)
    assert r.status_code == 200
    assert "Maiores consumidores" in r.text
    assert "Composição da base" in r.text
    assert "Taxa de sucesso" in r.text


@pytest.mark.asyncio
async def test_admin_dashboard_ranks_consumer(
    async_client, monkeypatch, db_session, api_key, verified_account
):
    from app.db.tables import UsageBucket

    await _seed_usage(db_session, api_key, days_ago=1, count=42, errors=2, bucket=UsageBucket.ai)
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/?days=30", cookies=cookies)
    assert r.status_code == 200
    # A conta com uso aparece no ranking, com link para o detalhe.
    assert verified_account.email in r.text
    assert f"/admin/users/{verified_account.id}" in r.text


@pytest.mark.asyncio
async def test_admin_user_detail_returns_200(
    async_client, monkeypatch, db_session, api_key, verified_account
):
    from app.db.tables import UsageBucket

    await _seed_usage(
        db_session, api_key, days_ago=2, count=10, errors=1, bucket=UsageBucket.deterministic
    )
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get(f"/admin/users/{verified_account.id}", cookies=cookies)
    assert r.status_code == 200
    assert verified_account.email in r.text
    assert "API Keys" in r.text


@pytest.mark.asyncio
async def test_admin_user_detail_unknown_returns_404(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/users/nao-existe", cookies=cookies)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_user_detail_without_session_redirects(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.get("/admin/users/qualquer", follow_redirects=False)
    assert r.status_code == 303
    assert "login" in r.headers["location"]


@pytest.mark.asyncio
async def test_admin_costs_returns_200(async_client, monkeypatch):
    cookies = await _login(async_client, monkeypatch)
    r = await async_client.get("/admin/costs", cookies=cookies)
    assert r.status_code == 200
    assert "Custos de Infraestrutura" in r.text


@pytest.mark.asyncio
async def test_admin_costs_without_session_redirects(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.get("/admin/costs", follow_redirects=False)
    assert r.status_code == 303
    assert "login" in r.headers["location"]


# ---------------------------------------------------------------------------
# Serviço (unitário): métricas de BI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_top_accounts_and_success_rate(db_session, api_key, verified_account):
    from app.db.tables import UsageBucket
    from app.services import admin_service

    await _seed_usage(db_session, api_key, days_ago=1, count=100, errors=10, bucket=UsageBucket.ai)
    top = await admin_service.get_top_accounts(db_session, days=30)
    assert len(top) == 1
    assert top[0].account_id == verified_account.id
    assert top[0].requests == 100
    assert top[0].ai == 100
    assert top[0].success_rate == 90.0


@pytest.mark.asyncio
async def test_service_account_detail(db_session, api_key, verified_account):
    from app.db.tables import UsageBucket
    from app.services import admin_service

    await _seed_usage(
        db_session, api_key, days_ago=3, count=20, errors=0, bucket=UsageBucket.deterministic
    )
    detail = await admin_service.get_account_detail(db_session, verified_account.id, days=30)
    assert detail is not None
    assert detail.email == verified_account.email
    assert detail.requests_window == 20
    assert detail.total_keys == 1
    assert detail.keys[0].requests_window == 20


@pytest.mark.asyncio
async def test_service_account_detail_missing_returns_none(db_session):
    from app.services import admin_service

    assert await admin_service.get_account_detail(db_session, "inexistente") is None


@pytest.mark.asyncio
async def test_service_composition(db_session, verified_account):
    from app.services import admin_service

    comp = await admin_service.get_account_composition(db_session)
    assert comp.total >= 1
    assert comp.with_password >= 1  # verified_account tem senha
    assert comp.verified >= 1


@pytest.mark.asyncio
async def test_service_normalize_window():
    from app.services import admin_service

    assert admin_service.normalize_window(7) == 7
    assert admin_service.normalize_window(90) == 90
    assert admin_service.normalize_window(999) == admin_service.DEFAULT_WINDOW
    assert admin_service.normalize_window(None) == admin_service.DEFAULT_WINDOW


# ---------------------------------------------------------------------------
# Fronteira 2: Google Sign-In + allowlist
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "admin@allowed.com"


def _enable_google(monkeypatch, allowed=(ADMIN_EMAIL,)) -> None:
    monkeypatch.setattr("app.core.config.settings.ADMIN_MODE", True)
    monkeypatch.setattr("app.core.config.settings.GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr("app.core.config.settings.GOOGLE_OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(
        "app.core.config.settings.ADMIN_ALLOWED_EMAILS", [e.lower() for e in allowed]
    )


def _mock_google_identity(monkeypatch, email: str) -> None:
    from app.services.oauth_service import OAuthUserInfo

    async def _fake_exchange(*a, **k):
        return "access-token"

    async def _fake_fetch(*a, **k):
        return OAuthUserInfo(
            provider="google", provider_account_id="g-1", email=email, email_verified=True
        )

    monkeypatch.setattr("app.services.oauth_service.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.services.oauth_service.fetch_identity", _fake_fetch)


async def _google_state(async_client) -> str:
    """Inicia o fluxo Google e devolve o nonce (state) do redirect."""
    from urllib.parse import parse_qs, urlparse

    r = await async_client.get("/admin/auth/google", follow_redirects=False)
    assert r.status_code == 303
    qs = parse_qs(urlparse(r.headers["location"]).query)
    return qs["state"][0]


@pytest.mark.asyncio
async def test_admin_login_shows_google_when_enabled(async_client, monkeypatch):
    _enable_google(monkeypatch)
    r = await async_client.get("/admin/login")
    assert r.status_code == 200
    assert "/admin/auth/google" in r.text
    assert "Entrar com Google" in r.text


@pytest.mark.asyncio
async def test_admin_google_start_redirects_to_google(async_client, monkeypatch):
    _enable_google(monkeypatch)
    r = await async_client.get("/admin/auth/google", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("https://accounts.google.com/")
    assert "__admin_oauth_state" in r.cookies


@pytest.mark.asyncio
async def test_admin_google_callback_allows_listed_email(async_client, monkeypatch):
    _enable_google(monkeypatch, allowed=(ADMIN_EMAIL,))
    _mock_google_identity(monkeypatch, ADMIN_EMAIL)
    state = await _google_state(async_client)
    r = await async_client.get(
        f"/admin/auth/google/callback?code=abc&state={state}", follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] in ("/admin/", "http://test/admin/")
    assert "__admin_session" in r.cookies


@pytest.mark.asyncio
async def test_admin_google_callback_rejects_unlisted_email(async_client, monkeypatch):
    _enable_google(monkeypatch, allowed=(ADMIN_EMAIL,))
    _mock_google_identity(monkeypatch, "intruso@evil.com")
    state = await _google_state(async_client)
    r = await async_client.get(
        f"/admin/auth/google/callback?code=abc&state={state}", follow_redirects=False
    )
    assert r.status_code == 403
    assert "__admin_session" not in r.cookies


@pytest.mark.asyncio
async def test_admin_google_callback_bad_state_rejected(async_client, monkeypatch):
    _enable_google(monkeypatch)
    _mock_google_identity(monkeypatch, ADMIN_EMAIL)
    await _google_state(async_client)  # cria o cookie de state válido
    r = await async_client.get(
        "/admin/auth/google/callback?code=abc&state=nonce-errado", follow_redirects=False
    )
    assert r.status_code == 403
    assert "__admin_session" not in r.cookies


@pytest.mark.asyncio
async def test_admin_auth_rate_limited(async_client, monkeypatch):
    _enable_google(monkeypatch)
    codes = []
    for _ in range(8):
        r = await async_client.get("/admin/auth/google", follow_redirects=False)
        codes.append(r.status_code)
    # Limite admin = 5/min → alguma tentativa além disso recebe 429.
    assert 429 in codes
