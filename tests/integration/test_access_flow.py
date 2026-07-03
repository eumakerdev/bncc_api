"""
Teste de integração do fluxo de acesso self-service (T039).

signup → verify-email → login → criar key → chamada autenticada (200);
sem key → 401; acima da cota determinística → 429 com Retry-After.

O token de verificação em claro é obtido chamando ``account_service.signup``
diretamente (mesmo comportamento do backend de console em dev).
"""

from __future__ import annotations

import pytest
from app.core.deps import (
    deterministic_limiter,
    rate_limit_deterministic,
    require_api_key,
)
from app.db.tables import ApiKey
from app.main import app
from app.services import account_service
from fastapi import Depends

VALID_PW = "senha-forte-123"

# Rotas-sonda protegidas (independem de US1 estar mesclada).
if not any(getattr(r, "path", None) == "/__flow_apikey" for r in app.routes):

    @app.get("/__flow_apikey")
    async def _flow_apikey(key: ApiKey = Depends(require_api_key)):
        return {"ok": True}

    @app.get("/__flow_limited")
    async def _flow_limited(key: ApiKey = Depends(rate_limit_deterministic)):
        return {"ok": True}


@pytest.mark.asyncio
async def test_full_access_flow(async_client, db_session):
    email = "fluxo@example.com"

    # 1) signup (obtém o token em claro, como no backend de console).
    _account, token = await account_service.signup(db_session, email, VALID_PW)

    # 2) verify-email via HTTP.
    v = await async_client.post("/api/v1/auth/verify-email", json={"token": token})
    assert v.status_code == 200, v.text

    # 3) login via HTTP → JWT de sessão.
    login = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": VALID_PW}
    )
    assert login.status_code == 200, login.text
    jwt = login.json()["access_token"]
    session_headers = {"Authorization": f"Bearer {jwt}"}

    # 4) criar API key com a sessão.
    created = await async_client.post(
        "/api/v1/keys", json={"name": "fluxo-key"}, headers=session_headers
    )
    assert created.status_code == 201, created.text
    full_key = created.json()["key"]
    key_headers = {"Authorization": f"Bearer {full_key}"}

    # 5) chamada autenticada com a key → 200.
    ok = await async_client.get("/__flow_apikey", headers=key_headers)
    assert ok.status_code == 200

    # 6) sem key → 401.
    no_key = await async_client.get("/__flow_apikey")
    assert no_key.status_code == 401


@pytest.mark.asyncio
async def test_deterministic_rate_limit_429(async_client, api_key):
    full_key, _key = api_key
    key_headers = {"Authorization": f"Bearer {full_key}"}

    # Janela limpa para tornar o teste determinístico.
    deterministic_limiter.reset()

    # 60/min + burst 10 = 70 permitidas.
    for i in range(70):
        r = await async_client.get("/__flow_limited", headers=key_headers)
        assert r.status_code == 200, f"chamada {i}: {r.text}"

    blocked = await async_client.get("/__flow_limited", headers=key_headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
