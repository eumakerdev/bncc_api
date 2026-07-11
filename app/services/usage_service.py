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

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.tables import ApiKey, ApiKeyStatus, UsageBucket, UsageRecord
from app.models.platform import (
    AccountAnalyticsResponse,
    AccountUsageResponse,
    BucketUsage,
    KeyUsageResponse,
    PublicUsagePoint,
    PublicUsageSummary,
    PublicUsageWindow,
    UsageDailyPoint,
)

# Janela padrão do painel de BI (últimos N dias, inclusive hoje).
ANALYTICS_WINDOW_DAYS = 30

# Janelas oferecidas no filtro público da landing (dias). Todas são pré-computadas
# de uma vez; o cliente alterna sem requisição nova.
PUBLIC_USAGE_WINDOWS: tuple[int, ...] = (7, 30, 90)
PUBLIC_USAGE_DEFAULT_WINDOW = 30


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


async def record_error(session: AsyncSession, api_key_id: str, bucket: UsageBucket) -> None:
    """Marca uma chamada do dia como malsucedida (desfecho >= 400).

    Incrementa ``error_count`` na linha diária já criada pelo registro do total
    (o middleware só chama isto para requisições que passaram no rate limit e,
    portanto, já tiveram ``count`` contabilizado). O ramo defensivo cria a linha
    caso, por corrida, ainda não exista — mantendo ``error_count <= count``.
    """
    window_start = _day_window_start()
    record = (
        await session.execute(
            select(UsageRecord).where(
                UsageRecord.api_key_id == api_key_id,
                UsageRecord.bucket == bucket,
                UsageRecord.window_start == window_start,
            )
        )
    ).scalar_one_or_none()

    if record is None:  # defensivo — não deveria ocorrer no fluxo normal
        record = UsageRecord(
            api_key_id=api_key_id,
            bucket=bucket,
            window_start=window_start,
            count=1,
            error_count=1,
        )
        session.add(record)
        try:
            await session.commit()
            return
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

    record.error_count += 1
    await session.commit()


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


def _as_date(value: datetime | date) -> date:
    """Normaliza ``window_start`` (naive no SQLite, aware no Postgres) para ``date``."""
    return value.date() if isinstance(value, datetime) else value


async def account_analytics(
    session: AsyncSession,
    account_id: str,
    days: int = ANALYTICS_WINDOW_DAYS,
) -> AccountAnalyticsResponse:
    """Série diária + KPIs de BI para o painel (todas as keys da conta).

    Uma única varredura de ``usage_records`` cobre a janela atual **e** a anterior
    (para o delta percentual). ``total`` = chamadas autorizadas do dia; ``successful``
    = ``total - error_count``. Sem tráfego, ``success_rate`` é ``None`` (o painel
    mostra "—" em vez de forçar 0%/100%).
    """
    days = max(1, days)
    now = _now()
    today = _day_window_start(now)
    window_start = today - timedelta(days=days - 1)
    prev_window_start = window_start - timedelta(days=days)

    rows = (
        await session.execute(
            select(
                UsageRecord.window_start,
                UsageRecord.bucket,
                func.sum(UsageRecord.count),
                func.sum(UsageRecord.error_count),
            )
            .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
            .where(
                ApiKey.account_id == account_id,
                UsageRecord.window_start >= prev_window_start,
            )
            .group_by(UsageRecord.window_start, UsageRecord.bucket)
        )
    ).all()

    # Agrega por dia (total/erros/IA/determinístico) para a janela atual e a anterior.
    per_day: dict[date, dict[str, int]] = {}
    prev_total = 0
    cur_start_date = window_start.date()
    for ws, bucket, total, errors in rows:
        d = _as_date(ws)
        total = int(total or 0)
        errors = int(errors or 0)
        if d < cur_start_date:
            prev_total += total
            continue
        day = per_day.setdefault(d, {"total": 0, "errors": 0, "ai": 0, "det": 0})
        day["total"] += total
        day["errors"] += errors
        if bucket == UsageBucket.ai:
            day["ai"] += total
        else:
            day["det"] += total

    series: list[UsageDailyPoint] = []
    total_requests = 0
    failed_requests = 0
    ai_requests = 0
    deterministic_requests = 0
    for i in range(days):
        d = (window_start + timedelta(days=i)).date()
        day = per_day.get(d, {"total": 0, "errors": 0, "ai": 0, "det": 0})
        total = day["total"]
        failed = min(day["errors"], total)
        series.append(
            UsageDailyPoint(date=d, total=total, successful=total - failed, failed=failed)
        )
        total_requests += total
        failed_requests += failed
        ai_requests += day["ai"]
        deterministic_requests += day["det"]

    successful_requests = total_requests - failed_requests
    success_rate = (successful_requests / total_requests) if total_requests else None
    delta_pct = ((total_requests - prev_total) / prev_total * 100.0) if prev_total else None

    active_keys = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ApiKey)
                .where(
                    ApiKey.account_id == account_id,
                    ApiKey.status == ApiKeyStatus.active,
                )
            )
        ).scalar_one()
        or 0
    )
    week_ago = now - timedelta(days=7)
    new_keys_last_7d = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ApiKey)
                .where(
                    ApiKey.account_id == account_id,
                    ApiKey.status == ApiKeyStatus.active,
                    ApiKey.created_at >= week_ago,
                )
            )
        ).scalar_one()
        or 0
    )

    return AccountAnalyticsResponse(
        account_id=account_id,
        window_days=days,
        series=series,
        total_requests=total_requests,
        successful_requests=successful_requests,
        failed_requests=failed_requests,
        success_rate=success_rate,
        total_requests_prev=prev_total,
        total_requests_delta_pct=delta_pct,
        ai_requests=ai_requests,
        deterministic_requests=deterministic_requests,
        active_keys=active_keys,
        new_keys_last_7d=new_keys_last_7d,
    )


async def public_usage_summary(
    session: AsyncSession,
    windows: tuple[int, ...] = PUBLIC_USAGE_WINDOWS,
    default_window: int = PUBLIC_USAGE_DEFAULT_WINDOW,
) -> PublicUsageSummary:
    """Séries por janela + KPIs de adoção para a seção "Transparência" da landing.

    Espelha ``cost_service.public_cost_summary``: uma única varredura de
    ``usage_records`` (na maior janela pedida) monta a série diária agregada de TODA
    a plataforma, da qual fatiamos cada janela (7/30/90). Só totais agregados —
    nunca por conta/IP/key e **sem taxa de erro** (sinal operacional; fica no /admin).
    Puro em relação a HTTP: recebe a sessão, devolve o modelo Pydantic.
    """
    windows = tuple(sorted({w for w in windows if w > 0})) or (default_window,)
    today = _day_window_start()
    max_days = max(windows)
    max_start = today - timedelta(days=max_days - 1)

    # Uma varredura: total diário da plataforma (soma dos dois buckets) na maior janela.
    rows = (
        await session.execute(
            select(UsageRecord.window_start, func.sum(UsageRecord.count))
            .where(UsageRecord.window_start >= max_start)
            .group_by(UsageRecord.window_start)
        )
    ).all()
    per_day: dict[date, int] = {}
    for ws, total in rows:
        d = _as_date(ws)
        per_day[d] = per_day.get(d, 0) + int(total or 0)

    def _window(days: int) -> PublicUsageWindow:
        start = (today - timedelta(days=days - 1)).date()
        series = [
            PublicUsagePoint(date=d, total=per_day.get(d, 0))
            for d in (start + timedelta(days=i) for i in range(days))
        ]
        total = sum(p.total for p in series)
        return PublicUsageWindow(
            days=days,
            series=series,
            total_requests=total,
            daily_average=round(total / days) if days else 0,
            peak=max((p.total for p in series), default=0),
        )

    window_models = [_window(d) for d in windows]

    # Totais all-time e adoção (agregações enxutas, uma linha cada).
    total_to_date = int(
        (await session.execute(select(func.coalesce(func.sum(UsageRecord.count), 0)))).scalar_one()
        or 0
    )
    earliest = (await session.execute(select(func.min(UsageRecord.window_start)))).scalar_one()
    developers = int(
        (
            await session.execute(
                select(func.count(func.distinct(ApiKey.account_id)))
                .select_from(UsageRecord)
                .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
            )
        ).scalar_one()
        or 0
    )
    active_keys = int(
        (
            await session.execute(
                select(func.count()).select_from(ApiKey).where(ApiKey.status == ApiKeyStatus.active)
            )
        ).scalar_one()
        or 0
    )

    return PublicUsageSummary(
        has_data=total_to_date > 0,
        default_window=default_window if default_window in windows else windows[0],
        windows=window_models,
        total_to_date=total_to_date,
        period_start=_as_date(earliest) if earliest is not None else None,
        developers=developers,
        active_keys=active_keys,
    )
