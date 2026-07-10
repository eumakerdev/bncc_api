"""
Testes de integração da seção "Transparência de custos" na landing.

Cobre: a seção aparece com valores quando há custos registrados; some quando não
há; e uma falha ao montar os custos NÃO derruba a landing (degradação graciosa —
Princípio VII).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.db.base import async_session_factory
from app.db.tables import CostRecord, CostService
from app.services.cost_service import _month_start, _now


async def _seed_current_month_costs() -> None:
    current = _month_start(_now().date())
    period = datetime(current.year, current.month, 1, tzinfo=UTC)
    async with async_session_factory() as session:
        session.add(
            CostRecord(
                period_month=period,
                service=CostService.banco,
                amount=Decimal("52.30"),
                currency="BRL",
                source="test",
            )
        )
        session.add(
            CostRecord(
                period_month=period,
                service=CostService.servidor,
                amount=Decimal("90.00"),
                currency="BRL",
                source="test",
            )
        )
        await session.commit()


async def test_landing_shows_cost_section_when_seeded(async_client):
    await _seed_current_month_costs()
    resp = await async_client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert 'id="transparencia"' in body
    assert "Transparência de custos" in body
    # Total acumulado formatado em BRL (52,30 + 90,00).
    assert "R$ 142,30" in body


async def test_landing_hides_cost_section_when_empty(async_client):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert 'id="transparencia"' not in resp.text


async def test_landing_resilient_to_cost_failure(async_client, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr("app.services.cost_service.public_cost_summary", _boom)
    resp = await async_client.get("/")
    # A landing continua respondendo 200, apenas sem a seção de custos.
    assert resp.status_code == 200
    assert 'id="transparencia"' not in resp.text
