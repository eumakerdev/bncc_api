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
    """Sobrescreve ADMIN_PASSWORD nas settings em tempo de teste."""
    monkeypatch.setattr("app.core.config.settings.ADMIN_PASSWORD", pw)
    monkeypatch.setattr("app.web.admin.settings.ADMIN_PASSWORD", pw)


# ---------------------------------------------------------------------------
# Painel desabilitado (ADMIN_PASSWORD vazio, default)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_disabled_login_returns_404(async_client):
    r = await async_client.get("/admin/login")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_disabled_dashboard_returns_404(async_client):
    r = await async_client.get("/admin/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_disabled_users_returns_404(async_client):
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
    _set_admin_env(monkeypatch)
    r = await async_client.post(
        "/admin/login",
        data={"password": "senha-errada"},
        follow_redirects=False,
    )
    assert r.status_code == 401
    assert "Senha incorreta" in r.text


@pytest.mark.asyncio
async def test_admin_login_correct_password_redirects(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.post(
        "/admin/login",
        data={"password": ADMIN_PW},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] in ("/admin/", "http://test/admin/")


@pytest.mark.asyncio
async def test_admin_login_sets_cookie(async_client, monkeypatch):
    _set_admin_env(monkeypatch)
    r = await async_client.post(
        "/admin/login",
        data={"password": ADMIN_PW},
        follow_redirects=False,
    )
    assert "__admin_session" in r.cookies


# ---------------------------------------------------------------------------
# Dashboard e Usuários (sessão válida)
# ---------------------------------------------------------------------------


async def _login(async_client, monkeypatch) -> dict:
    """Faz login de admin e retorna os cookies da sessão."""
    _set_admin_env(monkeypatch)
    r = await async_client.post(
        "/admin/login",
        data={"password": ADMIN_PW},
        follow_redirects=False,
    )
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
