"""
Testes de integração do fluxo de login social no portal (SSR).

Exercitam start→redirect com state, o callback feliz (conta nova e auto-link),
a proteção anti-CSRF (state inválido), provedor desabilitado e erro do provedor —
com as chamadas ao provedor mockadas via monkeypatch (sem rede).
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from app.core.config import settings
from app.db.base import async_session_factory
from app.db.tables import DeveloperAccount, OAuthIdentity
from app.services import oauth_service
from app.services.oauth_service import OAuthError, OAuthUserInfo
from sqlalchemy import func, select


@pytest.fixture
def google_enabled(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "gid-test")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "gsecret-test")
    monkeypatch.setattr(settings, "OAUTH_REDIRECT_BASE_URL", "http://test")


def _mock_provider(monkeypatch, info: OAuthUserInfo) -> None:
    async def fake_exchange(provider, code, client):  # noqa: ANN001
        return "access-token"

    async def fake_identity(provider, token, client):  # noqa: ANN001
        return info

    monkeypatch.setattr(oauth_service, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth_service, "fetch_identity", fake_identity)


async def _start(async_client, provider: str = "google") -> str:
    """Inicia o fluxo e devolve o `state` (nonce); o cookie fica no jar do client."""
    r = await async_client.get(f"/portal/auth/{provider}")
    assert r.status_code == 303, r.text
    location = r.headers["location"]
    assert location.startswith(oauth_service.PROVIDERS[provider]["authorize_url"])
    assert "oauth_state=" in r.headers.get("set-cookie", "")
    return parse_qs(urlparse(location).query)["state"][0]


# --------------------------------------------------------------------------- #
# Start
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_start_redirects_to_provider(async_client, google_enabled):
    state = await _start(async_client, "google")
    assert state


@pytest.mark.asyncio
async def test_start_disabled_provider_redirects_to_login(async_client):
    # Sem credenciais configuradas, o provedor está desabilitado.
    r = await async_client.get("/portal/auth/google")
    assert r.status_code == 303
    assert r.headers["location"].startswith("/portal/login")


# --------------------------------------------------------------------------- #
# Callback — sucesso
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_callback_creates_account_and_session(async_client, google_enabled, monkeypatch):
    state = await _start(async_client, "google")
    _mock_provider(
        monkeypatch,
        OAuthUserInfo("google", "G-1", "brandnew@social.com", email_verified=True),
    )

    r = await async_client.get(f"/portal/auth/google/callback?code=abc&state={state}")

    assert r.status_code == 303
    assert r.headers["location"] == "/portal/dashboard"
    assert "session=" in r.headers.get("set-cookie", "")

    async with async_session_factory() as session:
        account = (
            await session.execute(
                select(DeveloperAccount).where(DeveloperAccount.email == "brandnew@social.com")
            )
        ).scalar_one()
        assert account.password_hash is None
        assert account.email_verified is True


@pytest.mark.asyncio
async def test_callback_auto_links_existing_password_account(
    async_client, google_enabled, monkeypatch, verified_account
):
    state = await _start(async_client, "google")
    _mock_provider(
        monkeypatch,
        OAuthUserInfo("google", "G-2", verified_account.email, email_verified=True),
    )

    r = await async_client.get(f"/portal/auth/google/callback?code=abc&state={state}")
    assert r.status_code == 303
    assert r.headers["location"] == "/portal/dashboard"

    async with async_session_factory() as session:
        total = (
            await session.execute(select(func.count()).select_from(DeveloperAccount))
        ).scalar_one()
        assert total == 1  # vinculou, não criou outra conta
        identity = (await session.execute(select(OAuthIdentity))).scalar_one()
        assert identity.account_id == verified_account.id


# --------------------------------------------------------------------------- #
# Callback — falhas
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_callback_bad_state_rejected(async_client, google_enabled, monkeypatch):
    await _start(async_client, "google")
    _mock_provider(monkeypatch, OAuthUserInfo("google", "G-3", "x@social.com", email_verified=True))

    # state divergente do cookie → CSRF; volta ao login sem sessão.
    r = await async_client.get("/portal/auth/google/callback?code=abc&state=forjado")

    assert r.status_code == 303
    assert r.headers["location"].startswith("/portal/login")
    assert "session=" not in r.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_callback_provider_error_redirects_to_login(
    async_client, google_enabled, monkeypatch
):
    state = await _start(async_client, "google")

    async def boom(provider, code, client):  # noqa: ANN001
        raise OAuthError("token exchange falhou")

    monkeypatch.setattr(oauth_service, "exchange_code", boom)

    r = await async_client.get(f"/portal/auth/google/callback?code=abc&state={state}")

    assert r.status_code == 303
    assert r.headers["location"].startswith("/portal/login")
    assert "session=" not in r.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_login_page_shows_social_button_when_enabled(async_client, google_enabled):
    r = await async_client.get("/portal/login")
    assert r.status_code == 200
    assert "/portal/auth/google" in r.text
