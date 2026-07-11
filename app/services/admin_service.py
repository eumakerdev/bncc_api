"""
Serviço de administração da plataforma (painel de admin).

Expõe agregações de toda a plataforma — contas, keys e uso — para o painel
interno. Segue a arquitetura em camadas (Princípio II): não conhece objetos HTTP
nem templates; apenas recebe uma sessão e retorna modelos de domínio.

Todos os dados são lidos do banco de plataforma (SQLite/Postgres). O painel de
admin não altera dados; é exclusivamente leitura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import (
    ApiKey,
    ApiKeyStatus,
    DeveloperAccount,
    UsageBucket,
    UsageRecord,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _day_window_start(now: datetime | None = None) -> datetime:
    now = now or _now()
    return datetime(now.year, now.month, now.day, tzinfo=UTC)


@dataclass
class AccountRow:
    """Linha de uma conta de desenvolvedor no painel de admin."""

    account_id: str
    email: str
    email_verified: bool
    created_at: datetime
    total_keys: int
    active_keys: int
    requests_today: int


@dataclass
class PlatformOverview:
    """KPIs de plataforma para o cabeçalho do painel de admin."""

    total_accounts: int
    verified_accounts: int
    total_keys: int
    active_keys: int
    requests_today: int
    requests_yesterday: int
    ai_requests_today: int
    new_accounts_last_7d: int


@dataclass
class UsageDailyPoint:
    """Ponto de série temporal de uso da plataforma (todos os usuários)."""

    date: date
    total: int
    ai: int
    deterministic: int


@dataclass
class PlatformAnalytics:
    """Série diária de uso da plataforma (todos os usuários, últimos N dias)."""

    window_days: int
    series: list[UsageDailyPoint] = field(default_factory=list)
    total_requests: int = 0
    ai_requests: int = 0
    deterministic_requests: int = 0


async def get_overview(session: AsyncSession) -> PlatformOverview:
    """KPIs de plataforma: contas, keys e uso do dia/ontem."""
    today = _day_window_start()
    yesterday = today - timedelta(days=1)
    week_ago = _now() - timedelta(days=7)

    total_accounts = int(
        (await session.execute(select(func.count()).select_from(DeveloperAccount))).scalar_one()
        or 0
    )
    verified_accounts = int(
        (
            await session.execute(
                select(func.count())
                .select_from(DeveloperAccount)
                .where(DeveloperAccount.email_verified.is_(True))
            )
        ).scalar_one()
        or 0
    )
    total_keys = int(
        (await session.execute(select(func.count()).select_from(ApiKey))).scalar_one() or 0
    )
    active_keys = int(
        (
            await session.execute(
                select(func.count()).select_from(ApiKey).where(ApiKey.status == ApiKeyStatus.active)
            )
        ).scalar_one()
        or 0
    )
    new_accounts_last_7d = int(
        (
            await session.execute(
                select(func.count())
                .select_from(DeveloperAccount)
                .where(DeveloperAccount.created_at >= week_ago)
            )
        ).scalar_one()
        or 0
    )

    async def _sum_day(bucket: UsageBucket | None, window: datetime) -> int:
        q = select(func.coalesce(func.sum(UsageRecord.count), 0)).where(
            UsageRecord.window_start == window
        )
        if bucket is not None:
            q = q.where(UsageRecord.bucket == bucket)
        return int((await session.execute(q)).scalar_one() or 0)

    requests_today = await _sum_day(None, today)
    requests_yesterday = await _sum_day(None, yesterday)
    ai_requests_today = await _sum_day(UsageBucket.ai, today)

    return PlatformOverview(
        total_accounts=total_accounts,
        verified_accounts=verified_accounts,
        total_keys=total_keys,
        active_keys=active_keys,
        requests_today=requests_today,
        requests_yesterday=requests_yesterday,
        ai_requests_today=ai_requests_today,
        new_accounts_last_7d=new_accounts_last_7d,
    )


async def list_accounts(session: AsyncSession, limit: int = 200) -> list[AccountRow]:
    """Lista contas de desenvolvedor com métricas básicas (mais recentes primeiro)."""
    today = _day_window_start()

    accounts = (
        (
            await session.execute(
                select(DeveloperAccount).order_by(DeveloperAccount.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )

    rows: list[AccountRow] = []
    for acc in accounts:
        total_keys = int(
            (
                await session.execute(
                    select(func.count()).select_from(ApiKey).where(ApiKey.account_id == acc.id)
                )
            ).scalar_one()
            or 0
        )
        active_keys = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(ApiKey)
                    .where(
                        ApiKey.account_id == acc.id,
                        ApiKey.status == ApiKeyStatus.active,
                    )
                )
            ).scalar_one()
            or 0
        )
        requests_today = int(
            (
                await session.execute(
                    select(func.coalesce(func.sum(UsageRecord.count), 0))
                    .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
                    .where(
                        ApiKey.account_id == acc.id,
                        UsageRecord.window_start == today,
                    )
                )
            ).scalar_one()
            or 0
        )
        rows.append(
            AccountRow(
                account_id=acc.id,
                email=acc.email,
                email_verified=acc.email_verified,
                created_at=acc.created_at,
                total_keys=total_keys,
                active_keys=active_keys,
                requests_today=requests_today,
            )
        )
    return rows


async def get_platform_analytics(
    session: AsyncSession,
    days: int = 30,
) -> PlatformAnalytics:
    """Série diária de uso da plataforma inteira nos últimos N dias."""
    days = max(1, min(days, 90))
    today = _day_window_start()
    window_start = today - timedelta(days=days - 1)

    rows = (
        await session.execute(
            select(
                UsageRecord.window_start,
                UsageRecord.bucket,
                func.sum(UsageRecord.count),
            )
            .where(UsageRecord.window_start >= window_start)
            .group_by(UsageRecord.window_start, UsageRecord.bucket)
        )
    ).all()

    # Indexa por data.
    per_day: dict[date, dict[str, int]] = {}
    for ws, bucket, total in rows:
        d = ws.date() if isinstance(ws, datetime) else ws
        total = int(total or 0)
        day = per_day.setdefault(d, {"total": 0, "ai": 0, "det": 0})
        day["total"] += total
        if bucket == UsageBucket.ai:
            day["ai"] += total
        else:
            day["det"] += total

    series: list[UsageDailyPoint] = []
    total_requests = 0
    ai_requests = 0
    det_requests = 0
    for i in range(days):
        d = (window_start + timedelta(days=i)).date()
        day = per_day.get(d, {"total": 0, "ai": 0, "det": 0})
        series.append(
            UsageDailyPoint(
                date=d,
                total=day["total"],
                ai=day["ai"],
                deterministic=day["det"],
            )
        )
        total_requests += day["total"]
        ai_requests += day["ai"]
        det_requests += day["det"]

    return PlatformAnalytics(
        window_days=days,
        series=series,
        total_requests=total_requests,
        ai_requests=ai_requests,
        deterministic_requests=det_requests,
    )
