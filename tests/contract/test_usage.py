"""
Testes de contrato de uso (T037).

Verifica os formatos de ``/api/v1/keys/{id}/usage`` (por bucket) e
``/api/v1/usage`` (agregado da conta), além da autorização por posse (404).
"""

from __future__ import annotations

import pytest
from app.core.security import create_access_token, hash_password
from app.db.tables import DeveloperAccount


def _session(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=account_id)}"}


@pytest.mark.asyncio
async def test_key_usage_shape(async_client, verified_account, api_key):
    _full_key, key = api_key
    r = await async_client.get(
        f"/api/v1/keys/{key.id}/usage", headers=_session(verified_account.id)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["api_key_id"] == key.id
    for bucket in ("deterministic", "ai"):
        assert bucket in body
        assert "used_this_minute" in body[bucket]
        assert "limit_per_minute" in body[bucket]
    # IA tem teto diário; determinístico não.
    assert body["ai"]["limit_per_day"] == 500


@pytest.mark.asyncio
async def test_key_usage_not_owned_404(async_client, api_key, db_session):
    _full_key, key = api_key
    # Outra conta real (sessão válida) tentando ver a key alheia → 404 por posse.
    other = DeveloperAccount(
        email="outra@example.com",
        password_hash=hash_password("senha-forte-123"),
        email_verified=True,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    r = await async_client.get(f"/api/v1/keys/{key.id}/usage", headers=_session(other.id))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_account_usage_shape(async_client, verified_account, api_key):
    r = await async_client.get("/api/v1/usage", headers=_session(verified_account.id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["account_id"] == verified_account.id
    assert body["total_keys"] >= 1
    assert body["deterministic_used_today"] >= 0
    assert body["ai_used_today"] >= 0
