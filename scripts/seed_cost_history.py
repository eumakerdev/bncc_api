"""
Semeadura manual do histórico de custos em ``cost_records`` a partir do CSV do
relatório de Faturamento do GCP (console → Billing → Reports → "Baixar o CSV").

Motivo (fidelidade + Princípio VII): o BigQuery billing export **não faz backfill**
— só entrega dados a partir da data em que foi habilitado. Os meses anteriores só
existem no relatório de Faturamento do console. Como a landing lê apenas
``cost_records`` (nunca o BigQuery em runtime), este utilitário permite semear esses
meses históricos com ``source="manual"``, distinguindo-os claramente da ingestão
automática (``source="bigquery"``), sem violar a fronteira de dados.

Espelha ``scripts/ingest_costs.py``: mesma classificação de serviço em buckets
(``bucket_service``), mesmo grão ``(period_month, service)``, mesmo upsert idempotente
— só muda a origem (CSV do console em vez do BigQuery) e o ``source``.

CADA CSV cobre UM mês. O mês é inferido do nome do arquivo (padrão do console
``... 2026-07-01 — 2026-07-31.csv``) ou informado com ``--month YYYY-MM``.

Uso:
    python scripts/seed_cost_history.py "reports_2026-06.csv"          # 1 mês (do nome)
    python scripts/seed_cost_history.py *.csv                          # vários meses
    python scripts/seed_cost_history.py julho.csv --month 2026-07      # mês explícito
    python scripts/seed_cost_history.py "reports_2026-06.csv" --dry-run

Para semear PRODUÇÃO, aponte ``DATABASE_URL`` para o Cloud SQL (via Cloud SQL Auth
Proxy) antes de rodar — o script grava no banco de ``app.db.base``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import re
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Raiz do projeto no sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_cost_history")

from app.db.tables import CostService  # noqa: E402  (após ajuste do sys.path)

from scripts.ingest_costs import _CENTS, bucket_service  # noqa: E402  (reuso da classificação)

# Mês no nome do arquivo: "...YYYY-MM-DD — ...csv" (padrão do console) ou "...YYYY-MM...".
_MONTH_IN_NAME = re.compile(r"(\d{4})-(\d{2})(?:-\d{2})?")


# --------------------------------------------------------------------------- #
# Parsing puro (testável sem banco)
# --------------------------------------------------------------------------- #
def parse_brl(value: str) -> Decimal:
    """Converte um número no formato pt-BR do CSV ('1.234,56', '- 30,73', '—') em Decimal.

    ``.`` é separador de milhar e ``,`` é decimal. Traço/em-dash e vazio viram 0.
    """
    s = (value or "").strip().replace("R$", "").replace("—", "").replace(" ", "")
    if not s or s == "-":
        return Decimal("0")
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        logger.warning("Valor não numérico ignorado: %r", value)
        return Decimal("0")


def month_from_filename(name: str) -> date | None:
    """Extrai o 1º dia do mês do nome do arquivo do console (1ª data encontrada)."""
    m = _MONTH_IN_NAME.search(name)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), 1)


def _find_column(header: list[str], *needles: str) -> int:
    """Índice da 1ª coluna cujo cabeçalho contém um dos ``needles`` (case-insensitive)."""
    low = [h.strip().lower().lstrip("﻿") for h in header]
    for needle in needles:
        for i, h in enumerate(low):
            if needle in h:
                return i
    return -1


def aggregate_csv(text: str) -> dict[CostService, Decimal]:
    """Agrega o CSV de um mês (por serviço) em custo líquido por bucket, em BRL.

    Usa a coluna "Subtotal não arredondado" (custo líquido = custo + economias, já
    aplicadas as economias), mantendo precisão total — o arredondamento a centavos
    acontece só na gravação, como no ingestor. Linhas de rodapé (Subtotal/Tributo/
    Total filtrado, sem descrição de serviço) são ignoradas.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {}
    header = rows[0]
    svc_i = _find_column(header, "descrição do serviço", "serviço", "service")
    net_i = _find_column(header, "arredondado", "subtotal")
    if svc_i < 0 or net_i < 0:
        raise ValueError(
            "CSV não reconhecido: faltam colunas de serviço e/ou subtotal "
            f"(cabeçalho: {header!r})"
        )

    agg: dict[CostService, Decimal] = {}
    for row in rows[1:]:
        if len(row) <= max(svc_i, net_i):
            continue
        service_desc = row[svc_i].strip()
        if not service_desc:  # rodapé (Subtotal/Tributo/Total filtrado)
            continue
        bucket = bucket_service(service_desc)
        agg[bucket] = agg.get(bucket, Decimal("0")) + parse_brl(row[net_i])
    return agg


# --------------------------------------------------------------------------- #
# Persistência (upsert idempotente — padrão de ingest_costs._upsert, source=manual)
# --------------------------------------------------------------------------- #
async def _upsert(session, month: date, service: CostService, amount: Decimal, source: str) -> None:
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
            period_month=dt, service=service, amount=value, currency="BRL", source=source
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
    record.source = source
    await session.commit()


async def _persist(months: dict[date, dict[CostService, Decimal]], source: str) -> int:
    from app.db.base import async_session_factory

    written = 0
    async with async_session_factory() as session:
        for month in sorted(months):
            for service, amount in sorted(months[month].items(), key=lambda kv: kv[0].value):
                if amount.quantize(_CENTS) == Decimal("0.00"):
                    continue  # não polui o breakdown com buckets zerados
                await _upsert(session, month, service, amount, source)
                written += 1
    return written


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def _resolve_month(path: Path, override: date | None) -> date:
    if override is not None:
        return override
    month = month_from_filename(path.name)
    if month is None:
        raise SystemExit(
            f"Não consegui inferir o mês de {path.name!r}. "
            "Renomeie no padrão do console (…YYYY-MM-DD — …) ou passe --month YYYY-MM."
        )
    return month


async def _run(paths: list[Path], override: date | None, source: str, dry_run: bool) -> int:
    months: dict[date, dict[CostService, Decimal]] = {}
    if override is not None and len(paths) > 1:
        raise SystemExit("--month só é válido com um único CSV (cada arquivo é um mês).")

    for path in paths:
        if not path.exists():
            raise SystemExit(f"Arquivo não encontrado: {path}")
        month = _resolve_month(path, override)
        agg = aggregate_csv(path.read_text(encoding="utf-8-sig"))
        if not agg:
            logger.warning("%s: nenhuma linha de serviço reconhecida.", path.name)
            continue
        # Se dois CSVs cairem no mesmo mês, soma (não deveria acontecer no fluxo normal).
        bucket = months.setdefault(month, {})
        total = Decimal("0")
        for service, amount in agg.items():
            bucket[service] = bucket.get(service, Decimal("0")) + amount
            total += amount
        logger.info(
            "%s  total R$ %s  (%s)",
            month.isoformat(),
            total.quantize(_CENTS),
            ", ".join(
                f"{s.value}={a.quantize(_CENTS)}"
                for s, a in sorted(agg.items(), key=lambda kv: kv[0].value)
            ),
        )

    if not months:
        logger.warning("Nada a gravar.")
        return 0

    if dry_run:
        logger.info("[dry-run] %d mês(es) agregado(s) — nada gravado.", len(months))
        return 0

    written = await _persist(months, source)
    logger.info("Gravadas %d linhas em cost_records (source=%s).", written, source)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Semeia o histórico de custos em cost_records a partir do CSV do console GCP."
    )
    parser.add_argument("csv", nargs="+", help="Um ou mais CSVs do relatório de Faturamento.")
    parser.add_argument("--month", help="Mês YYYY-MM (só com um CSV; sobrepõe o nome do arquivo).")
    parser.add_argument(
        "--source", default="manual", help="Valor do campo source (padrão 'manual')."
    )
    parser.add_argument("--dry-run", action="store_true", help="Só agrega e imprime; não grava.")
    args = parser.parse_args()

    override: date | None = None
    if args.month:
        y, m = args.month.split("-")
        override = date(int(y), int(m), 1)

    paths = [Path(p) for p in args.csv]
    return asyncio.run(_run(paths, override, args.source, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
