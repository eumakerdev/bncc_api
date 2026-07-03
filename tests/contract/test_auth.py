"""
Testes de contrato de autenticação do portal (T035).

Cobre signup (201 unverified), e-mail duplicado (409 neutro), verify-email
(200/400), login antes/depois da verificação (401/200) e /me com sessão (200).
"""

from __future__ import annotations

import pytest
from app.core.security import create_access_token
from app.services import account_service

VALID_PW = "senha-forte-123"


def _bearer(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=account_id)}"}


@pytest.mark.asyncio
async def test_signup_returns_201_unverified(async_client):
    r = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "novo@example.com", "password": VALID_PW},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "novo@example.com"
    assert body["email_verified"] is False
    assert body["account_id"]


@pytest.mark.asyncio
async def test_signup_weak_password_400(async_client):
    r = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "x@example.com", "password": "curta"},  # pragma: allowlist secret
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_email_returns_409_neutral(async_client):
    await async_client.post(
        "/api/v1/auth/signup", json={"email": "dup@example.com", "password": VALID_PW}
    )
    r = await async_client.post(
        "/api/v1/auth/signup", json={"email": "dup@example.com", "password": VALID_PW}
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Não foi possível concluir o cadastro."


@pytest.mark.asyncio
async def test_verify_email_valid_token_200(async_client, db_session):
    _account, token = await account_service.signup(db_session, "verify@example.com", VALID_PW)
    r = await async_client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["email_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_bad_token_rejected(async_client):
    r = await async_client.post("/api/v1/auth/verify-email", json={"token": "token-invalido-xyz"})
    assert r.status_code in (400, 410)


@pytest.mark.asyncio
async def test_login_before_verify_401(async_client, db_session):
    await account_service.signup(db_session, "unv@example.com", VALID_PW)
    r = await async_client.post(
        "/api/v1/auth/login", json={"email": "unv@example.com", "password": VALID_PW}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciais inválidas ou e-mail não verificado."


@pytest.mark.asyncio
async def test_login_after_verify_200(async_client, db_session):
    _account, token = await account_service.signup(db_session, "ok@example.com", VALID_PW)
    await account_service.verify_email(db_session, token)

    r = await async_client.post(
        "/api/v1/auth/login", json={"email": "ok@example.com", "password": VALID_PW}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_me_with_session_200(async_client, verified_account):
    r = await async_client.get("/api/v1/auth/me", headers=_bearer(verified_account.id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["account_id"] == verified_account.id
    assert body["email_verified"] is True


@pytest.mark.asyncio
async def test_me_without_session_401(async_client):
    r = await async_client.get("/api/v1/auth/me")
    assert r.status_code == 401
