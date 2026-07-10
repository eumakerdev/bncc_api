"""
Testes de contrato da gestão de senha (trocar + esqueci/redefinir).

Cobre ``/api/v1/auth/change-password``, ``/forgot-password`` e ``/reset-password``:
formatos, autorização por sessão, política de senha e anti-enumeração.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import (
    create_access_token,
    hash_password,
    hash_verification_token,
)
from app.db.tables import DeveloperAccount, PasswordResetToken
from app.services import account_service


def _session(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=account_id)}"}


# --------------------------------------------------------------------------- #
# Trocar senha (logado)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_change_password_happy(async_client, verified_account):
    r = await async_client.post(
        "/api/v1/auth/change-password",
        headers=_session(verified_account.id),
        json={"current_password": "senha-forte-123", "new_password": "NovaSenha456"},
    )
    assert r.status_code == 200, r.text

    # A nova senha passa a valer; a antiga não.
    ok = await async_client.post(
        "/api/v1/auth/login",
        json={"email": verified_account.email, "password": "NovaSenha456"},
    )
    assert ok.status_code == 200, ok.text
    old = await async_client.post(
        "/api/v1/auth/login",
        json={"email": verified_account.email, "password": "senha-forte-123"},
    )
    assert old.status_code == 401


@pytest.mark.asyncio
async def test_change_password_wrong_current_400(async_client, verified_account):
    r = await async_client.post(
        "/api/v1/auth/change-password",
        headers=_session(verified_account.id),
        json={"current_password": "errada-000000", "new_password": "NovaSenha456"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_change_password_weak_new_422(async_client, verified_account):
    r = await async_client.post(
        "/api/v1/auth/change-password",
        headers=_session(verified_account.id),
        json={"current_password": "senha-forte-123", "new_password": "curta"},
    )
    # O handler global normaliza erros de validação (Pydantic) para 400 (ver
    # app/core/errors.py), como no signup.
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_change_password_requires_session_401(async_client, verified_account):
    r = await async_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "senha-forte-123", "new_password": "NovaSenha456"},
    )
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# Esqueci a senha (anti-enumeração)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_forgot_password_is_neutral(async_client, verified_account):
    exists = await async_client.post(
        "/api/v1/auth/forgot-password", json={"email": verified_account.email}
    )
    missing = await async_client.post(
        "/api/v1/auth/forgot-password", json={"email": "ninguem@example.com"}
    )
    assert exists.status_code == 200
    assert missing.status_code == 200
    # Corpo idêntico — não revela se a conta existe.
    assert exists.json() == missing.json()


# --------------------------------------------------------------------------- #
# Redefinir senha (consumo do token)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_reset_password_happy(async_client, verified_account, db_session):
    token = await account_service.request_password_reset(db_session, verified_account.email)
    assert token  # emitido para conta existente

    r = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "OutraSenha789"},
    )
    assert r.status_code == 200, r.text

    ok = await async_client.post(
        "/api/v1/auth/login",
        json={"email": verified_account.email, "password": "OutraSenha789"},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token_400(async_client, verified_account):
    r = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "nao-existe-token-000", "new_password": "OutraSenha789"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_used_token_410(async_client, verified_account, db_session):
    token = await account_service.request_password_reset(db_session, verified_account.email)
    first = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "OutraSenha789"},
    )
    assert first.status_code == 200
    again = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "MaisUmaSenha1"},
    )
    assert again.status_code == 410  # token de uso único já consumido


@pytest.mark.asyncio
async def test_reset_password_expired_token_410(async_client, db_session):
    account = DeveloperAccount(
        email="exp@example.com",
        password_hash=hash_password("senha-forte-123"),
        email_verified=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    # Token com expiração no passado (fabricado direto no banco).
    plain = "token-expirado-abcdef"
    db_session.add(
        PasswordResetToken(
            account_id=account.id,
            token_hash=hash_verification_token(plain),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await db_session.commit()

    r = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain, "new_password": "OutraSenha789"},
    )
    assert r.status_code == 410
