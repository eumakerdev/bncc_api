"""
Cobertura direta dos serviços de uso e e-mail (T073 / Phase 8).
"""

import pytest
from app.core.config import settings
from app.services import email_service, usage_service


@pytest.mark.asyncio
async def test_email_console_backend_logs(caplog):
    # Backend console (padrão de teste) apenas registra o link — sem rede.
    with caplog.at_level("INFO", logger="bncc.email"):
        await email_service.send_verification_email("a@example.com", "tok123")
    assert any("a@example.com" in m for m in caplog.messages)


def test_verification_link_appends_query(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_BASE_URL", "http://x/verify")
    assert email_service._verification_link("tok") == "http://x/verify?token=tok"
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_BASE_URL", "http://x/verify?ref=1")
    assert "&token=tok" in email_service._verification_link("tok")


@pytest.mark.asyncio
async def test_email_smtp_backend_invokes_aiosmtplib(monkeypatch):
    sent = {}

    async def fake_send(message, **kwargs):
        sent["to"] = message["To"]
        sent["kwargs"] = kwargs

    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "smtp")
    await email_service.send_verification_email("smtp@example.com", "tokabc")
    assert sent["to"] == "smtp@example.com"


@pytest.mark.asyncio
async def test_daily_ai_counter_and_cap(db_session, api_key, monkeypatch):
    _full, key = api_key
    # abaixo do teto: contabiliza sem erro
    monkeypatch.setattr(settings, "RATE_LIMIT_AI_PER_DAY", 3)
    for _ in range(3):
        await usage_service.check_and_record_daily_ai(db_session, key.id)
    # atingido o teto → 429
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await usage_service.check_and_record_daily_ai(db_session, key.id)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


@pytest.mark.asyncio
async def test_record_deterministic_and_key_usage(db_session, api_key):
    _full, key = api_key
    await usage_service.record_deterministic(db_session, key.id)
    await usage_service.record_deterministic(db_session, key.id)
    usage = await usage_service.key_usage(db_session, key.id)
    assert usage.api_key_id == key.id
    assert usage.deterministic.used_today == 2
    assert usage.ai.limit_per_day == settings.RATE_LIMIT_AI_PER_DAY


@pytest.mark.asyncio
async def test_account_usage_aggregate(db_session, api_key, verified_account):
    _full, key = api_key
    await usage_service.check_and_record_daily_ai(db_session, key.id)
    agg = await usage_service.account_usage(db_session, verified_account.id)
    assert agg.account_id == verified_account.id
    assert agg.total_keys >= 1
    assert agg.ai_used_today >= 1


def test_seconds_to_midnight_positive():
    assert usage_service._seconds_to_midnight() > 0
