"""
Testes unitários do serviço de login social (oauth_service).

Cobrem a montagem da URL de autorização, a troca de code→token, a normalização
do perfil (Google e GitHub, incluindo e-mail primário verificado) e a regra de
find-or-create/auto-link — tudo com um cliente HTTP falso (sem rede).
"""

from __future__ import annotations

import pytest
from app.core.config import settings
from app.db.tables import DeveloperAccount, OAuthIdentity
from app.services import oauth_service
from app.services.oauth_service import OAuthError, OAuthUserInfo
from sqlalchemy import func, select


class _FakeResponse:
    def __init__(self, data: object) -> None:
        self._data = data

    def json(self) -> object:
        return self._data


class _FakeClient:
    """Cliente httpx falso: `post_data` para o token, `get_map` por substring de URL."""

    def __init__(self, post_data: object = None, get_map: dict | None = None) -> None:
        self._post_data = post_data
        self._get_map = get_map or {}

    async def post(self, url, data=None, headers=None):  # noqa: ANN001
        return _FakeResponse(self._post_data)

    async def get(self, url, headers=None):  # noqa: ANN001
        for fragment, payload in self._get_map.items():
            if fragment in url:
                return _FakeResponse(payload)
        raise AssertionError(f"GET inesperado: {url}")


# --------------------------------------------------------------------------- #
# URL de autorização
# --------------------------------------------------------------------------- #
def test_build_authorize_url_google(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "gid-123")
    monkeypatch.setattr(settings, "OAUTH_REDIRECT_BASE_URL", "https://app.example")

    url = oauth_service.build_authorize_url("google", state="nonce-xyz")

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=gid-123" in url
    assert "state=nonce-xyz" in url
    assert "response_type=code" in url
    assert "portal%2Fauth%2Fgoogle%2Fcallback" in url


# --------------------------------------------------------------------------- #
# Troca de código
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_exchange_code_returns_access_token(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "gid")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
    client = _FakeClient(post_data={"access_token": "tok-abc"})

    token = await oauth_service.exchange_code("google", "the-code", client)

    assert token == "tok-abc"


@pytest.mark.asyncio
async def test_exchange_code_without_token_raises(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "csecret")
    client = _FakeClient(post_data={"error": "bad_verification_code"})

    with pytest.raises(OAuthError):
        await oauth_service.exchange_code("github", "bad", client)


# --------------------------------------------------------------------------- #
# Perfil normalizado — Google
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fetch_google_identity_verified():
    client = _FakeClient(
        get_map={
            "userinfo": {
                "sub": "10101",
                "email": "Ana@Gmail.com",
                "email_verified": True,
                "name": "Ana",
            }
        }
    )
    info = await oauth_service.fetch_identity("google", "tok", client)

    assert info.provider == "google"
    assert info.provider_account_id == "10101"
    assert info.email == "Ana@Gmail.com"
    assert info.email_verified is True


@pytest.mark.asyncio
async def test_fetch_google_unverified_raises():
    client = _FakeClient(
        get_map={"userinfo": {"sub": "1", "email": "x@y.com", "email_verified": False}}
    )
    with pytest.raises(OAuthError):
        await oauth_service.fetch_identity("google", "tok", client)


# --------------------------------------------------------------------------- #
# Perfil normalizado — GitHub (e-mail vem de /user/emails)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fetch_github_identity_primary_verified():
    client = _FakeClient(
        get_map={
            "/user/emails": [
                {"email": "secundario@dev.com", "primary": False, "verified": True},
                {"email": "principal@dev.com", "primary": True, "verified": True},
            ],
            "/user": {"id": 777, "login": "dev", "name": "Dev Silva", "email": None},
        }
    )
    info = await oauth_service.fetch_identity("github", "tok", client)

    assert info.provider_account_id == "777"
    assert info.email == "principal@dev.com"
    assert info.email_verified is True
    assert info.name == "Dev Silva"


@pytest.mark.asyncio
async def test_fetch_github_no_verified_email_raises():
    client = _FakeClient(
        get_map={
            "/user/emails": [{"email": "x@dev.com", "primary": True, "verified": False}],
            "/user": {"id": 5, "login": "dev"},
        }
    )
    with pytest.raises(OAuthError):
        await oauth_service.fetch_identity("github", "tok", client)


# --------------------------------------------------------------------------- #
# find-or-create / auto-link
# --------------------------------------------------------------------------- #
def _info(email: str, pid: str = "P1", provider: str = "google") -> OAuthUserInfo:
    return OAuthUserInfo(
        provider=provider, provider_account_id=pid, email=email, email_verified=True
    )


@pytest.mark.asyncio
async def test_find_or_create_creates_new_account(db_session):
    account = await oauth_service.find_or_create_account(db_session, _info("novo@social.com"))

    assert account.email == "novo@social.com"
    assert account.email_verified is True
    assert account.password_hash is None  # conta só-social não tem senha
    identities = (await db_session.execute(select(OAuthIdentity))).scalars().all()
    assert len(identities) == 1
    assert identities[0].provider == "google"


@pytest.mark.asyncio
async def test_find_or_create_links_existing_account(db_session, verified_account):
    # verified_account.email == dev@example.com (senha). Login Google com o mesmo
    # e-mail verificado deve VINCULAR, não criar outra conta.
    account = await oauth_service.find_or_create_account(db_session, _info(verified_account.email))

    assert account.id == verified_account.id
    total = (
        await db_session.execute(select(func.count()).select_from(DeveloperAccount))
    ).scalar_one()
    assert total == 1
    identity = (await db_session.execute(select(OAuthIdentity))).scalar_one()
    assert identity.account_id == verified_account.id


@pytest.mark.asyncio
async def test_find_or_create_is_idempotent(db_session):
    first = await oauth_service.find_or_create_account(db_session, _info("again@social.com"))
    second = await oauth_service.find_or_create_account(db_session, _info("again@social.com"))

    assert first.id == second.id
    identities = (await db_session.execute(select(OAuthIdentity))).scalars().all()
    assert len(identities) == 1
