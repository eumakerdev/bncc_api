"""
Testes de integração da seção "Transparência" (uso) na landing.

Cobre: a seção de uso aparece com dados agregados quando há tráfego; o filtro de
janela (7/30/90) é renderizado; e uma falha ao montar o uso NÃO derruba a landing
(degradação graciosa — Princípio VII). A taxa de erro nunca aparece na página
pública (fica no /admin).
"""

from __future__ import annotations

from app.core.security import generate_api_key, hash_password
from app.db.base import async_session_factory
from app.db.tables import ApiKey, ApiKeyStatus, DeveloperAccount, UsageBucket, UsageRecord
from app.services.usage_service import _day_window_start


async def _seed_usage() -> None:
    async with async_session_factory() as session:
        account = DeveloperAccount(
            email="uso@example.com",
            password_hash=hash_password("senha-forte-123"),
            email_verified=True,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)

        _full, prefix, key_hash = generate_api_key()
        key = ApiKey(
            account_id=account.id,
            name="k",
            prefix=prefix,
            key_hash=key_hash,
            status=ApiKeyStatus.active,
        )
        session.add(key)
        await session.commit()
        await session.refresh(key)

        session.add(
            UsageRecord(
                api_key_id=key.id,
                bucket=UsageBucket.deterministic,
                window_start=_day_window_start(),
                count=1234,
            )
        )
        await session.commit()


async def test_landing_shows_usage_section_when_seeded(async_client):
    await _seed_usage()
    resp = await async_client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert 'id="transparencia"' in body
    assert "Uso da plataforma" in body
    # Filtro de janela renderizado no servidor (sem depender de JS).
    assert 'data-window-btn="7"' in body
    assert 'data-window-btn="90"' in body
    # Volume agregado formatado em pt-BR.
    assert "1.234" in body
    # A página pública NÃO expõe taxa de erro/sucesso (fica no /admin).
    assert "taxa de sucesso" not in body.lower()


async def test_landing_hides_usage_section_when_empty(async_client):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "Uso da plataforma" not in resp.text


async def test_landing_resilient_to_usage_failure(async_client, monkeypatch):
    await _seed_usage()

    async def _boom(*args, **kwargs):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr("app.services.usage_service.public_usage_summary", _boom)
    resp = await async_client.get("/")
    # A landing continua respondendo 200, apenas sem a seção de uso.
    assert resp.status_code == 200
    assert "Uso da plataforma" not in resp.text
