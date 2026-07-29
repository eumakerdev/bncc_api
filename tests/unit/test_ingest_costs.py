"""
Testes das funções puras do ingestor de custos (scripts/ingest_costs.py).

Cobre o mapeamento de serviço (com catch-all) e a agregação de linhas do BigQuery
por mês+bucket, incluindo conversão de moeda e custo líquido (créditos já aplicados
na coluna ``net``). Não toca o BigQuery — linhas são dicts fake.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from app.db.tables import CostService
from scripts import ingest_costs
from scripts.ingest_costs import aggregate_rows, bucket_service


def test_bucket_service_maps_known_services():
    assert bucket_service("Cloud SQL") == CostService.banco
    assert bucket_service("Cloud Run") == CostService.servidor
    assert bucket_service("Cloud Run Functions") == CostService.servidor
    assert bucket_service("Vertex AI") == CostService.ia
    assert bucket_service("Generative Language API") == CostService.ia


def test_bucket_service_catch_all():
    assert bucket_service("Artifact Registry") == CostService.outros
    assert bucket_service("Secret Manager") == CostService.outros
    assert bucket_service("") == CostService.outros
    assert bucket_service(None) == CostService.outros  # type: ignore[arg-type]


def test_aggregate_rows_sums_within_bucket():
    rows = [
        {"ym": "202606", "svc": "Cloud SQL", "currency": "BRL", "net": "52.30"},
        {"ym": "202606", "svc": "Cloud Run", "currency": "BRL", "net": "90.00"},
        {"ym": "202606", "svc": "Cloud Run Functions", "currency": "BRL", "net": "5.00"},
        {"ym": "202607", "svc": "Vertex AI", "currency": "BRL", "net": "12.00"},
    ]
    agg = aggregate_rows(rows)
    assert agg[(date(2026, 6, 1), CostService.banco)] == Decimal("52.30")
    # Cloud Run + Cloud Run Functions caem no mesmo bucket (servidor).
    assert agg[(date(2026, 6, 1), CostService.servidor)] == Decimal("95.00")
    assert agg[(date(2026, 7, 1), CostService.ia)] == Decimal("12.00")


def test_aggregate_rows_currency_conversion():
    rows = [{"ym": "202607", "svc": "Cloud Run", "currency": "USD", "net": "10.00"}]
    agg = aggregate_rows(rows, rate=5.0)
    assert agg[(date(2026, 7, 1), CostService.servidor)] == Decimal("50.00")


def test_aggregate_rows_keeps_net_credits_even_negative():
    # ``net`` já vem líquido de créditos; um mês fortemente creditado pode ser negativo.
    rows = [{"ym": "202607", "svc": "Cloud SQL", "currency": "BRL", "net": "-3.50"}]
    agg = aggregate_rows(rows)
    assert agg[(date(2026, 7, 1), CostService.banco)] == Decimal("-3.50")


def test_run_returns_error_when_bigquery_empty(monkeypatch):
    # Regressão: BigQuery sem linhas (export não habilitado/atrasado) deve retornar
    # código != 0 para o Scheduler alertar — não mascarar como sucesso.
    monkeypatch.setattr(ingest_costs, "_config_ok", lambda: True)
    monkeypatch.setattr(ingest_costs, "_fetch_rows", lambda since: [])
    code = asyncio.run(ingest_costs._run("202601", dry_run=False))
    assert code == 5


def test_check_since_accepts_current_and_past_months():
    current = ingest_costs._default_since(1)
    assert ingest_costs.check_since(current) is None
    assert ingest_costs.check_since(ingest_costs._default_since(13)) is None


def test_check_since_rejects_future_and_malformed():
    # Regressão do incidente de jul/2026: o job ficou fixado em --since 2026-08 (mês
    # futuro) e falhou 20 dias seguidos com a mensagem errada ("export não populado").
    future = f"{int(ingest_costs._default_since(1)[:4]) + 1}01"
    problem = ingest_costs.check_since(future)
    assert problem is not None and "futuro" in problem
    assert ingest_costs.check_since("2026-01") is not None  # não normalizado
    assert ingest_costs.check_since("202613") is not None  # mês inexistente


def test_main_rejects_future_since_without_touching_bigquery(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ingest_costs, "_config_ok", lambda: calls.append("config") or True)
    monkeypatch.setattr(ingest_costs, "_fetch_rows", lambda since: calls.append("bq") or [])
    year = int(ingest_costs._default_since(1)[:4]) + 1
    monkeypatch.setattr("sys.argv", ["ingest_costs.py", "--since", f"{year}-01"])
    assert ingest_costs.main() == 6
    assert calls == []
