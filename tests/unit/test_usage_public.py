"""
Testes do resumo público de uso (app/services/usage_service.public_usage_summary).

Cobre: resumo vazio (has_data False, séries gap-filled), agregação por janela
(7/30/90 a partir de uma única varredura), total acumulado, dia de início e KPIs
de adoção. Nunca expõe taxa de erro (só ``count``).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from app.db.tables import UsageBucket, UsageRecord
from app.services import usage_service
from app.services.usage_service import _day_window_start

pytestmark = pytest.mark.asyncio


async def _seed(session, api_key_id: str, days_ago: int, bucket: UsageBucket, count: int) -> None:
    session.add(
        UsageRecord(
            api_key_id=api_key_id,
            bucket=bucket,
            window_start=_day_window_start() - timedelta(days=days_ago),
            count=count,
        )
    )


async def test_empty_summary(db_session):
    summary = await usage_service.public_usage_summary(db_session)
    assert summary.has_data is False
    assert summary.total_to_date == 0
    assert summary.period_start is None
    assert summary.developers == 0
    assert {w.days for w in summary.windows} == {7, 30, 90}
    # Séries sempre preenchidas (gap-fill), com tamanho == dias da janela.
    for w in summary.windows:
        assert len(w.series) == w.days
        assert all(p.total == 0 for p in w.series)


async def test_windows_slice_from_single_scan(db_session, api_key):
    _full_key, key = api_key
    await _seed(db_session, key.id, 0, UsageBucket.deterministic, 100)
    await _seed(db_session, key.id, 0, UsageBucket.ai, 20)  # mesmo dia, outro bucket
    await _seed(db_session, key.id, 3, UsageBucket.deterministic, 50)  # dentro de 7d
    await _seed(db_session, key.id, 20, UsageBucket.deterministic, 200)  # dentro de 30d
    await _seed(db_session, key.id, 45, UsageBucket.deterministic, 300)  # dentro de 90d
    await db_session.commit()

    summary = await usage_service.public_usage_summary(db_session)
    by_days = {w.days: w for w in summary.windows}

    assert by_days[7].total_requests == 170  # 120 + 50
    assert by_days[30].total_requests == 370  # + 200
    assert by_days[90].total_requests == 670  # + 300

    assert summary.has_data is True
    assert summary.total_to_date == 670
    assert summary.period_start == (_day_window_start() - timedelta(days=45)).date()
    assert summary.developers == 1
    assert summary.active_keys == 1
    # O último ponto de cada série é sempre hoje.
    for w in summary.windows:
        assert w.series[-1].date == _day_window_start().date()


async def test_default_window_is_valid(db_session):
    summary = await usage_service.public_usage_summary(db_session)
    assert summary.default_window in {w.days for w in summary.windows}
