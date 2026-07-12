"""
Ingestão de custos de infraestrutura do BigQuery billing export → cost_records.

Único ponto do sistema que fala com o BigQuery (Princípio VII): agrega o export de
faturamento do GCP por mês e serviço, custo líquido (cost + credits), e faz upsert
idempotente em ``cost_records``. A landing lê apenas o banco — nunca o BQ. Rodado por
um Cloud Run Job agendado (Cloud Scheduler), ou manualmente para backfill.

Degrada graciosamente: sem `GCP_*` configurado ou sem a lib instalada, encerra com
mensagem clara e código de saída != 0 (sem stack trace ruidoso).

Uso:
    python scripts/ingest_costs.py                 # últimos ~13 meses
    python scripts/ingest_costs.py --since 2026-01 # a partir de jan/2026
    python scripts/ingest_costs.py --dry-run       # só agrega e imprime; não grava
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

# Raiz do projeto no sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingest_costs")

from app.db.tables import CostService  # noqa: E402  (após ajuste do sys.path)

_CENTS = Decimal("0.01")


# --------------------------------------------------------------------------- #
# Transformação pura (testável sem BigQuery)
# --------------------------------------------------------------------------- #
def bucket_service(description: str) -> CostService:
    """Mapeia ``service.description`` do export do GCP para um bucket curado.

    Catch-all em ``outros`` — nada é descartado, então a soma dos buckets iguala
    sempre o total faturado.
    """
    d = (description or "").lower()
    if "cloud sql" in d or "cloud spanner" in d or "memorystore" in d:
        return CostService.banco
    if "cloud run" in d or "app engine" in d or "compute engine" in d:
        return CostService.servidor
    if "vertex" in d or "generative language" in d or "gemini" in d or "aiplatform" in d:
        return CostService.ia
    return CostService.outros


def _month_from_ym(ym: str) -> date:
    """'YYYYMM' (invoice.month) → 1º dia do mês."""
    ym = str(ym)
    return date(int(ym[:4]), int(ym[4:6]), 1)


def _to_brl(amount: Decimal, currency: str, rate: float) -> Decimal:
    """Converte para BRL se a moeda do export não for BRL e houver taxa configurada."""
    if currency and currency.upper() != "BRL":
        if rate and rate > 0:
            return amount * Decimal(str(rate))
        logger.warning("Moeda %s sem USD_BRL_RATE definido; usando valor bruto.", currency)
    return amount


def _row_get(row: object, key: str) -> object:
    """Acesso uniforme a linhas do BigQuery (Row) e a dicts (testes)."""
    if isinstance(row, Mapping):
        return row.get(key)
    return row[key]  # google.cloud.bigquery.table.Row suporta acesso por chave


def aggregate_rows(rows: Iterable, rate: float = 0.0) -> dict[tuple[date, CostService], Decimal]:
    """Agrega linhas (ym, svc, currency, net) por (mês, bucket) em BRL."""
    agg: dict[tuple[date, CostService], Decimal] = {}
    for row in rows:
        ym = _row_get(row, "ym")
        svc = str(_row_get(row, "svc") or "")
        currency = str(_row_get(row, "currency") or "BRL")
        net = Decimal(str(_row_get(row, "net") or 0))
        net = _to_brl(net, currency, rate)
        key = (_month_from_ym(ym), bucket_service(svc))
        agg[key] = agg.get(key, Decimal("0")) + net
    return agg


# --------------------------------------------------------------------------- #
# Configuração + BigQuery (isolados p/ os testes injetarem linhas)
# --------------------------------------------------------------------------- #
def _config_ok() -> bool:
    from app.core.config import settings

    missing = [
        name
        for name, value in (
            ("GCP_PROJECT", settings.GCP_PROJECT),
            ("GCP_BILLING_DATASET", settings.GCP_BILLING_DATASET),
            ("GCP_BILLING_TABLE", settings.GCP_BILLING_TABLE),
        )
        if not value
    ]
    if missing:
        logger.error("Configuração de billing ausente: %s", ", ".join(missing))
        logger.error("Defina GCP_PROJECT / GCP_BILLING_DATASET / GCP_BILLING_TABLE.")
        return False
    return True


def _fetch_rows(since_ym: str) -> list:
    """Consulta o billing export (custo líquido por mês+serviço a partir de since_ym)."""
    from app.core.config import settings
    from google.cloud import bigquery  # import lazy (lib só do job)

    table = f"`{settings.GCP_PROJECT}.{settings.GCP_BILLING_DATASET}.{settings.GCP_BILLING_TABLE}`"
    query = f"""
        SELECT invoice.month AS ym,
               service.description AS svc,
               currency,
               SUM(cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net
        FROM {table}
        WHERE invoice.month >= @since
        GROUP BY ym, svc, currency
    """
    client = bigquery.Client(project=settings.GCP_PROJECT)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("since", "STRING", since_ym)]
    )
    return list(client.query(query, job_config=job_config).result())


# --------------------------------------------------------------------------- #
# Persistência (upsert idempotente — padrão de usage_service._record)
# --------------------------------------------------------------------------- #
async def _upsert(session, month: date, service: CostService, amount: Decimal) -> None:
    from app.db.tables import CostRecord
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    dt = datetime(month.year, month.month, month.day, tzinfo=UTC)
    value = amount.quantize(_CENTS)

    def _query():
        return select(CostRecord).where(
            CostRecord.period_month == dt, CostRecord.service == service
        )

    record = (await session.execute(_query())).scalar_one_or_none()
    if record is None:
        record = CostRecord(
            period_month=dt, service=service, amount=value, currency="BRL", source="bigquery"
        )
        session.add(record)
        try:
            await session.commit()
            return
        except IntegrityError:
            await session.rollback()
            record = (await session.execute(_query())).scalar_one()

    record.amount = value
    record.currency = "BRL"
    record.source = "bigquery"
    await session.commit()


async def _persist(agg: dict[tuple[date, CostService], Decimal]) -> int:
    from app.db.base import async_session_factory

    written = 0
    async with async_session_factory() as session:
        for (month, service), amount in sorted(agg.items()):
            await _upsert(session, month, service, amount)
            written += 1
    return written


async def _run(since_ym: str, dry_run: bool) -> int:
    if not _config_ok():
        return 2
    try:
        rows = _fetch_rows(since_ym)
    except ImportError:
        logger.error("google-cloud-bigquery não instalado (pip install google-cloud-bigquery).")
        return 3
    except Exception as exc:  # rede/permissão/SQL — mensagem clara, sem stack trace
        logger.error("Falha ao consultar o BigQuery: %s", exc)
        return 4

    from app.core.config import settings

    agg = aggregate_rows(rows, rate=settings.USD_BRL_RATE)
    if not agg:
        # Zero linhas é anômalo para um projeto com gasto: sinaliza export de billing
        # não habilitado/atrasado ou tabela errada. Retorna != 0 para o Cloud Scheduler
        # acusar falha (alerta), em vez de "sucesso" mascarar a landing vazia por dias.
        logger.error(
            "Nenhuma linha de custo retornada (since=%s). Verifique se o BigQuery billing "
            "export está habilitado e populado para %s.",
            since_ym,
            since_ym,
        )
        return 5

    for (month, service), amount in sorted(agg.items()):
        logger.info("%s  %-9s  R$ %s", month.isoformat(), service.value, amount.quantize(_CENTS))

    if dry_run:
        logger.info("[dry-run] %d linhas agregadas — nada gravado.", len(agg))
        return 0

    written = await _persist(agg)
    logger.info("Gravadas %d linhas em cost_records (since=%s).", written, since_ym)
    return 0


def _default_since(months: int) -> str:
    """'YYYYMM' de ``months`` meses atrás (inclusive o mês corrente)."""
    today = datetime.now(UTC).date()
    index = today.year * 12 + (today.month - 1) - (max(1, months) - 1)
    year, month = divmod(index, 12)
    return f"{year:04d}{month + 1:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingesta custos do BigQuery billing export para cost_records."
    )
    parser.add_argument("--since", help="Mês inicial YYYY-MM (inclusive).")
    parser.add_argument(
        "--months", type=int, default=13, help="Meses para trás quando --since ausente (padrão 13)."
    )
    parser.add_argument("--dry-run", action="store_true", help="Só agrega e imprime; não grava.")
    args = parser.parse_args()

    since_ym = args.since.replace("-", "") if args.since else _default_since(args.months)
    return asyncio.run(_run(since_ym, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
