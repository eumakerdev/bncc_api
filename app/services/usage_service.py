"""
Serviço de uso e cota diária durável (T043).

Duas cotas (FR-010/FR-010a):
- **Por minuto** (in-process): mantida pelos ``SlidingWindowLimiter`` de
  ``app.core.deps`` (determinístico 60/min+burst 10; IA 20/min). Só leitura aqui.
- **Diária durável** de IA (500/dia): contabilizada em ``usage_records`` (SQLite),
  com janela diária em UTC. ``check_and_record_daily_ai`` é o enforcement chamado
  por ``app.core.deps.rate_limit_ai``.

Métricas expostas por key e agregadas por conta alimentam o painel do portal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.tables import ApiKey, UsageBucket, UsageRecord
from app.models.platform import (
    AccountUsageResponse,
    BucketUsage,
    KeyUsageResponse,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _day_window_start(now: datetime | None = None) -> datetime:
    """Início do dia corrente em UTC (janela diária durável)."""
    now = now or _now()
    return datetime(now.year, now.month, now.day, tzinfo=UTC)


def _seconds_to_midnight(now: datetime | None = None) -> int:
    now = now or _now()
    next_midnight = _day_window_start(now) + timedelta(days=1)
    return max(int((next_midnight - now).total_seconds()), 1)


async def _daily_count(
    session: AsyncSession,
    api_key_id: str,
    bucket: UsageBucket,
    window_start: datetime | None = None,
) -> int:
    window_start = window_start or _day_window_start()
    result = await session.execute(
        select(UsageRecord.count).where(
            UsageRecord.api_key_id == api_key_id,
            UsageRecord.bucket == bucket,
            UsageRecord.window_start == window_start,
        )
    )
    return int(result.scalar_one_or_none() or 0)


async def _record(session: AsyncSession, api_key_id: str, bucket: UsageBucket) -> int:
    """
    Incrementa (upsert) o contador da janela diária corrente e retorna o novo total.

    Upsert por ``(api_key_id, bucket, window_start)`` — a UniqueConstraint garante
    unicidade; corrida rara cai no ramo de leitura+incremento.
    """
    window_start = _day_window_start()
    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.api_key_id == api_key_id,
            UsageRecord.bucket == bucket,
            UsageRecord.window_start == window_start,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = UsageRecord(
            api_key_id=api_key_id, bucket=bucket, window_start=window_start, count=1
        )
        session.add(record)
        try:
            await session.commit()
            return 1
        except IntegrityError:
            await session.rollback()
            record = (
                await session.execute(
                    select(UsageRecord).where(
                        UsageRecord.api_key_id == api_key_id,
                        UsageRecord.bucket == bucket,
                        UsageRecord.window_start == window_start,
                    )
                )
            ).scalar_one()

    record.count += 1
    await session.commit()
    return record.count


async def check_and_record_daily_ai(session: AsyncSession, api_key_id: str) -> None:
    """
    Enforcement do teto diário de IA (500/dia — settings.RATE_LIMIT_AI_PER_DAY).

    Se o consumo do dia já atingiu o limite, levanta 429 com ``Retry-After`` em
    segundos até a meia-noite UTC; caso contrário, contabiliza mais uma chamada.
    """
    limit = settings.RATE_LIMIT_AI_PER_DAY
    used = await _daily_count(session, api_key_id, UsageBucket.ai)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Teto diário de IA excedido.",
            headers={"Retry-After": str(_seconds_to_midnight())},
        )
    await _record(session, api_key_id, UsageBucket.ai)


async def record_deterministic(session: AsyncSession, api_key_id: str) -> None:
    """Contabiliza uma chamada determinística na janela diária (métrica de painel)."""
    await _record(session, api_key_id, UsageBucket.deterministic)


async def key_usage(session: AsyncSession, api_key_id: str) -> KeyUsageResponse:
    """Métricas de consumo de uma key: minuto (limiters) + dia (DB) + limites."""
    from app.core.deps import ai_limiter, deterministic_limiter

    det_minute = deterministic_limiter.current(f"deterministic:{api_key_id}")
    ai_minute = ai_limiter.current(f"ai:{api_key_id}")
    det_daily = await _daily_count(session, api_key_id, UsageBucket.deterministic)
    ai_daily = await _daily_count(session, api_key_id, UsageBucket.ai)

    return KeyUsageResponse(
        api_key_id=api_key_id,
        deterministic=BucketUsage(
            used_this_minute=det_minute,
            limit_per_minute=settings.RATE_LIMIT_DETERMINISTIC_PER_MIN
            + settings.RATE_LIMIT_DETERMINISTIC_BURST,
            used_today=det_daily,
            limit_per_day=None,
        ),
        ai=BucketUsage(
            used_this_minute=ai_minute,
            limit_per_minute=settings.RATE_LIMIT_AI_PER_MIN,
            used_today=ai_daily,
            limit_per_day=settings.RATE_LIMIT_AI_PER_DAY,
        ),
    )


async def account_usage(session: AsyncSession, account_id: str) -> AccountUsageResponse:
    """Consumo agregado do dia (todas as keys da conta), por bucket."""
    window_start = _day_window_start()

    total_keys = int(
        (
            await session.execute(
                select(func.count()).select_from(ApiKey).where(ApiKey.account_id == account_id)
            )
        ).scalar_one()
        or 0
    )

    async def _sum(bucket: UsageBucket) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(UsageRecord.count), 0))
            .select_from(UsageRecord)
            .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
            .where(
                ApiKey.account_id == account_id,
                UsageRecord.bucket == bucket,
                UsageRecord.window_start == window_start,
            )
        )
        return int(result.scalar_one() or 0)

    return AccountUsageResponse(
        account_id=account_id,
        total_keys=total_keys,
        deterministic_used_today=await _sum(UsageBucket.deterministic),
        ai_used_today=await _sum(UsageBucket.ai),
    )
