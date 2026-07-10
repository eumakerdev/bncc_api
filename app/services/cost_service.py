"""
Serviço de agregação de custos de infraestrutura (transparência pública).

Espelha ``usage_service.account_analytics``: uma única varredura de ``cost_records``
monta a série mensal (gap-filled), o breakdown por serviço e os totais (mês corrente
e acumulado de todos os meses). Puro em relação a HTTP — recebe a sessão, devolve
modelos Pydantic. Em runtime só toca o banco; o BigQuery fica no job de ingestão.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import CostRecord, CostService
from app.models.cost import (
    SERVICE_LABELS,
    SERVICE_ORDER,
    CostMonthPoint,
    CostServiceAmount,
    CostSummary,
)

# Janela padrão do gráfico (últimos N meses, inclusive o mês corrente).
COST_WINDOW_MONTHS = 12


def _now() -> datetime:
    return datetime.now(UTC)


def _month_start(d: date) -> date:
    """Primeiro dia do mês de ``d``."""
    return date(d.year, d.month, 1)


def _add_months(first_of_month: date, delta: int) -> date:
    """Soma ``delta`` meses a um primeiro-dia-do-mês (delta pode ser negativo)."""
    index = first_of_month.month - 1 + delta
    year = first_of_month.year + index // 12
    month = index % 12 + 1
    return date(year, month, 1)


def _as_date(value: datetime | date) -> date:
    """Normaliza ``period_month`` (naive no SQLite, aware no Postgres) para ``date``."""
    return value.date() if isinstance(value, datetime) else value


def _breakdown(amounts: dict[CostService, float]) -> list[CostServiceAmount]:
    """Breakdown por serviço na ordem canônica (zeros preenchidos)."""
    return [
        CostServiceAmount(service=s, label=SERVICE_LABELS[s], amount=round(amounts.get(s, 0.0), 2))
        for s in SERVICE_ORDER
    ]


async def public_cost_summary(
    session: AsyncSession, months: int = COST_WINDOW_MONTHS
) -> CostSummary:
    """Série mensal + KPIs de custo para a seção pública da landing.

    ``total_to_date`` soma TODOS os ``cost_records`` (não só a janela) — é o "custo
    total até aqui". ``period_start`` é o mês mais antigo registrado, para rotular
    honestamente "desde <mês>". Sem registros, ``has_data`` é ``False`` e a seção
    não é exibida.
    """
    months = max(1, months)
    current_month = _month_start(_now().date())
    window_start = _add_months(current_month, -(months - 1))

    rows = (
        await session.execute(
            select(
                CostRecord.period_month,
                CostRecord.service,
                func.sum(CostRecord.amount),
            ).group_by(CostRecord.period_month, CostRecord.service)
        )
    ).all()

    per_month: dict[date, dict[CostService, float]] = {}
    to_date: dict[CostService, float] = dict.fromkeys(SERVICE_ORDER, 0.0)
    earliest: date | None = None
    for period_month, service, amount in rows:
        month = _month_start(_as_date(period_month))
        amt = float(amount or 0)
        bucket = per_month.setdefault(month, {})
        bucket[service] = bucket.get(service, 0.0) + amt
        to_date[service] = to_date.get(service, 0.0) + amt
        if earliest is None or month < earliest:
            earliest = month

    series: list[CostMonthPoint] = []
    for i in range(months):
        month = _add_months(window_start, i)
        by_service = _breakdown(per_month.get(month, {}))
        total = round(sum(item.amount for item in by_service), 2)
        series.append(CostMonthPoint(month=month, total=total, by_service=by_service))

    total_month = round(sum(per_month.get(current_month, {}).values()), 2)
    total_to_date = round(sum(to_date.values()), 2)

    return CostSummary(
        currency="BRL",
        window_months=months,
        has_data=total_to_date > 0,
        series=series,
        period_start=earliest,
        total_month=total_month,
        total_to_date=total_to_date,
        by_service_to_date=_breakdown(to_date),
    )
