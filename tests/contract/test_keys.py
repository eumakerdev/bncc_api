"""
Testes de contrato de API keys (T036).

Cobre criação (201 com segredo exibido uma vez), 403 se não verificado, listagem
sem segredo, e revogação (204) que invalida a key na auth por Bearer (401).
"""

from __future__ import annotations

import pytest
from app.core.deps import require_api_key
from app.core.security import create_access_token, hash_password
from app.db.tables import ApiKey, DeveloperAccount
from app.main import app
from fastapi import Depends

# Rota-sonda protegida por API key (independe de US1 estar mesclada).
if not any(getattr(r, "path", None) == "/__probe_apikey" for r in app.routes):

    @app.get("/__probe_apikey")
    async def _probe_apikey(key: ApiKey = Depends(require_api_key)):
        return {"ok": True, "key_id": key.id}


def _session(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=account_id)}"}


@pytest.mark.asyncio
async def test_create_key_verified_201_with_secret_once(async_client, verified_account):
    r = await async_client.post(
        "/api/v1/keys", json={"name": "minha-key"}, headers=_session(verified_account.id)
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "minha-key"
    assert body["key"].startswith("bncc_live_")
    assert body["prefix"]
    assert body["id"]


@pytest.mark.asyncio
async def test_create_key_unverified_403(async_client, db_session):
    account = DeveloperAccount(
        email="unverified@example.com",
        password_hash=hash_password("senha-forte-123"),
        email_verified=False,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    r = await async_client.post("/api/v1/keys", json={"name": "x"}, headers=_session(account.id))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_keys_omits_secret(async_client, verified_account):
    await async_client.post(
        "/api/v1/keys", json={"name": "k1"}, headers=_session(verified_account.id)
    )
    r = await async_client.get("/api/v1/keys", headers=_session(verified_account.id))
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert "key" not in item
    assert "key_hash" not in item
    assert item["prefix"]
    assert item["status"] == "active"


@pytest.mark.asyncio
async def test_revoke_key_204_then_auth_fails_401(async_client, verified_account):
    created = await async_client.post(
        "/api/v1/keys", json={"name": "revogar"}, headers=_session(verified_account.id)
    )
    full_key = created.json()["key"]
    key_id = created.json()["id"]

    # Key ativa autentica na rota-sonda.
    ok = await async_client.get("/__probe_apikey", headers={"Authorization": f"Bearer {full_key}"})
    assert ok.status_code == 200

    # Revoga.
    deleted = await async_client.delete(
        f"/api/v1/keys/{key_id}", headers=_session(verified_account.id)
    )
    assert deleted.status_code == 204

    # Uso posterior da key revogada → 401 imediato.
    after = await async_client.get(
        "/__probe_apikey", headers={"Authorization": f"Bearer {full_key}"}
    )
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_revoke_other_account_key_404(async_client, verified_account, db_session):
    other = DeveloperAccount(
        email="other@example.com",
        password_hash=hash_password("senha-forte-123"),
        email_verified=True,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    created = await async_client.post(
        "/api/v1/keys", json={"name": "da-outra"}, headers=_session(other.id)
    )
    key_id = created.json()["id"]

    r = await async_client.delete(f"/api/v1/keys/{key_id}", headers=_session(verified_account.id))
    assert r.status_code == 404
