"""
Testes do serviço de agregação de custos (app/services/cost_service.py).

Cobre: resumo vazio, agregação por mês+serviço, total acumulado (sobre TODOS os
registros, não só a janela), mês de início e total do mês corrente.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.db.tables import CostRecord, CostService
from app.services import cost_service
from app.services.cost_service import _month_start, _now


async def _seed(session, year: int, month: int, service: CostService, amount: float) -> None:
    session.add(
        CostRecord(
            period_month=datetime(year, month, 1, tzinfo=UTC),
            service=service,
            amount=Decimal(str(amount)),
            currency="BRL",
            source="test",
        )
    )


async def test_empty_summary(db_session):
    summary = await cost_service.public_cost_summary(db_session)
    assert summary.has_data is False
    assert summary.total_to_date == 0.0
    assert summary.total_month == 0.0
    assert summary.period_start is None
    # A série é sempre preenchida (gap-fill) mesmo sem dados.
    assert len(summary.series) == cost_service.COST_WINDOW_MONTHS
    assert all(point.total == 0.0 for point in summary.series)


async def test_summary_aggregates_by_month_and_service(db_session):
    await _seed(db_session, 2026, 1, CostService.banco, 50)
    await _seed(db_session, 2026, 1, CostService.servidor, 90)
    await _seed(db_session, 2026, 2, CostService.banco, 52)
    await db_session.commit()

    summary = await cost_service.public_cost_summary(db_session, months=12)
    assert summary.total_to_date == pytest.approx(192.0)
    assert summary.period_start == date(2026, 1, 1)

    by_service = {item.service: item.amount for item in summary.by_service_to_date}
    assert by_service[CostService.banco] == pytest.approx(102.0)
    assert by_service[CostService.servidor] == pytest.approx(90.0)
    assert by_service[CostService.ia] == pytest.approx(0.0)


async def test_current_month_total_and_last_point(db_session):
    current = _month_start(_now().date())
    await _seed(db_session, current.year, current.month, CostService.ia, 33)
    await db_session.commit()

    summary = await cost_service.public_cost_summary(db_session)
    assert summary.has_data is True
    assert summary.total_month == pytest.approx(33.0)
    # O último ponto da série é sempre o mês corrente.
    assert summary.series[-1].month == current
    assert summary.series[-1].total == pytest.approx(33.0)
