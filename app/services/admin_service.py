"""
Serviço de administração da plataforma (painel de admin).

Expõe agregações de toda a plataforma — contas, keys e uso — para o painel
interno. Segue a arquitetura em camadas (Princípio II): não conhece objetos HTTP
nem templates; apenas recebe uma sessão e retorna modelos de domínio.

Todos os dados são lidos do banco de plataforma (SQLite/Postgres). O painel de
admin não altera dados; é exclusivamente leitura. Todas as métricas são
determinísticas (Princípio VII): nenhuma depende da camada de IA.
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
    OAuthIdentity,
    OnboardingProfile,
    UsageBucket,
    UsageRecord,
)

# Janelas de período permitidas no painel (dias). O default é 30.
ALLOWED_WINDOWS: tuple[int, ...] = (7, 30, 90)
DEFAULT_WINDOW = 30


def normalize_window(days: int | None) -> int:
    """Restringe o período a uma das janelas permitidas (evita queries abertas)."""
    if days is not None and days in ALLOWED_WINDOWS:
        return days
    return DEFAULT_WINDOW


def _now() -> datetime:
    return datetime.now(UTC)


def _day_window_start(now: datetime | None = None) -> datetime:
    now = now or _now()
    return datetime(now.year, now.month, now.day, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Modelos de domínio (dataclasses — sem dependência de HTTP/ORM)
# --------------------------------------------------------------------------- #


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
class AccountComposition:
    """Composição da base de contas (adoção): como os usuários entraram."""

    total: int
    verified: int
    unverified: int
    with_password: int
    oauth_only: int
    onboarded: int
    active_last_7d: int  # contas com >=1 requisição nos últimos 7 dias


@dataclass
class UsageDailyPoint:
    """Ponto de série temporal de uso da plataforma (todos os usuários)."""

    date: date
    total: int
    ai: int
    deterministic: int
    errors: int

    @property
    def successful(self) -> int:
        return max(self.total - self.errors, 0)


@dataclass
class PlatformAnalytics:
    """Série diária de uso da plataforma inteira nos últimos N dias."""

    window_days: int
    series: list[UsageDailyPoint] = field(default_factory=list)
    total_requests: int = 0
    ai_requests: int = 0
    deterministic_requests: int = 0
    error_requests: int = 0

    @property
    def successful_requests(self) -> int:
        return max(self.total_requests - self.error_requests, 0)

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso (0–100). 100% quando não houve requisições."""
        if self.total_requests <= 0:
            return 100.0
        return round(self.successful_requests / self.total_requests * 100, 1)

    @property
    def ai_share(self) -> float:
        """Percentual de requisições que foram para a camada de IA (0–100)."""
        if self.total_requests <= 0:
            return 0.0
        return round(self.ai_requests / self.total_requests * 100, 1)


@dataclass
class TopConsumer:
    """Conta no ranking de maiores consumidores da janela."""

    account_id: str
    email: str
    requests: int
    ai: int
    deterministic: int
    errors: int
    active_keys: int

    @property
    def success_rate(self) -> float:
        if self.requests <= 0:
            return 100.0
        return round((self.requests - self.errors) / self.requests * 100, 1)


@dataclass
class KeyRow:
    """API key de uma conta, com uso na janela e total histórico."""

    key_id: str
    name: str
    prefix: str
    status: str
    created_at: datetime
    last_used_at: datetime | None
    requests_window: int
    requests_total: int


@dataclass
class AccountDetail:
    """Visão 360º de uma conta para a página de detalhe do admin."""

    account_id: str
    email: str
    email_verified: bool
    created_at: datetime
    has_password: bool
    oauth_providers: list[str]
    onboarding: OnboardingProfile | None
    total_keys: int
    active_keys: int
    window_days: int
    requests_window: int
    ai_window: int
    error_window: int
    requests_total: int
    keys: list[KeyRow] = field(default_factory=list)
    series: list[UsageDailyPoint] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.requests_window <= 0:
            return 100.0
        return round((self.requests_window - self.error_window) / self.requests_window * 100, 1)


# --------------------------------------------------------------------------- #
# Agregações auxiliares
# --------------------------------------------------------------------------- #


def _bucketize(rows: list, days: int, window_start: datetime) -> list[UsageDailyPoint]:
    """Converte linhas ``(window_start, bucket, sum_count, sum_error)`` numa série
    diária densa (todos os dias da janela, zeros preenchidos)."""
    per_day: dict[date, dict[str, int]] = {}
    for ws, bucket, total, errors in rows:
        d = ws.date() if isinstance(ws, datetime) else ws
        total = int(total or 0)
        errors = int(errors or 0)
        day = per_day.setdefault(d, {"total": 0, "ai": 0, "det": 0, "err": 0})
        day["total"] += total
        day["err"] += errors
        if bucket == UsageBucket.ai:
            day["ai"] += total
        else:
            day["det"] += total

    series: list[UsageDailyPoint] = []
    for i in range(days):
        d = (window_start + timedelta(days=i)).date()
        day = per_day.get(d, {"total": 0, "ai": 0, "det": 0, "err": 0})
        series.append(
            UsageDailyPoint(
                date=d,
                total=day["total"],
                ai=day["ai"],
                deterministic=day["det"],
                errors=day["err"],
            )
        )
    return series


# --------------------------------------------------------------------------- #
# KPIs de topo
# --------------------------------------------------------------------------- #


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


async def get_account_composition(session: AsyncSession) -> AccountComposition:
    """Composição da base: verificadas, com senha vs. só-OAuth, onboardadas, ativas."""
    total = int(
        (await session.execute(select(func.count()).select_from(DeveloperAccount))).scalar_one()
        or 0
    )
    verified = int(
        (
            await session.execute(
                select(func.count())
                .select_from(DeveloperAccount)
                .where(DeveloperAccount.email_verified.is_(True))
            )
        ).scalar_one()
        or 0
    )
    with_password = int(
        (
            await session.execute(
                select(func.count())
                .select_from(DeveloperAccount)
                .where(DeveloperAccount.password_hash.is_not(None))
            )
        ).scalar_one()
        or 0
    )
    onboarded = int(
        (
            await session.execute(
                select(func.count())
                .select_from(OnboardingProfile)
                .where(OnboardingProfile.completed_at.is_not(None))
            )
        ).scalar_one()
        or 0
    )
    week_ago = _now() - timedelta(days=7)
    active_last_7d = int(
        (
            await session.execute(
                select(func.count(func.distinct(ApiKey.account_id)))
                .select_from(UsageRecord)
                .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
                .where(UsageRecord.window_start >= _day_window_start(week_ago))
            )
        ).scalar_one()
        or 0
    )
    return AccountComposition(
        total=total,
        verified=verified,
        unverified=max(total - verified, 0),
        with_password=with_password,
        oauth_only=max(total - with_password, 0),
        onboarded=onboarded,
        active_last_7d=active_last_7d,
    )


# --------------------------------------------------------------------------- #
# Listagens e séries
# --------------------------------------------------------------------------- #


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
    days: int = DEFAULT_WINDOW,
) -> PlatformAnalytics:
    """Série diária de uso da plataforma inteira nos últimos N dias."""
    days = normalize_window(days)
    today = _day_window_start()
    window_start = today - timedelta(days=days - 1)

    rows = (
        await session.execute(
            select(
                UsageRecord.window_start,
                UsageRecord.bucket,
                func.sum(UsageRecord.count),
                func.sum(UsageRecord.error_count),
            )
            .where(UsageRecord.window_start >= window_start)
            .group_by(UsageRecord.window_start, UsageRecord.bucket)
        )
    ).all()

    series = _bucketize(list(rows), days, window_start)

    total = sum(p.total for p in series)
    ai = sum(p.ai for p in series)
    det = sum(p.deterministic for p in series)
    err = sum(p.errors for p in series)

    return PlatformAnalytics(
        window_days=days,
        series=series,
        total_requests=total,
        ai_requests=ai,
        deterministic_requests=det,
        error_requests=err,
    )


async def get_top_accounts(
    session: AsyncSession,
    days: int = DEFAULT_WINDOW,
    limit: int = 10,
) -> list[TopConsumer]:
    """Ranking das contas por volume de requisições na janela (maiores primeiro)."""
    days = normalize_window(days)
    window_start = _day_window_start() - timedelta(days=days - 1)

    rows = (
        await session.execute(
            select(
                ApiKey.account_id,
                UsageRecord.bucket,
                func.sum(UsageRecord.count),
                func.sum(UsageRecord.error_count),
            )
            .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
            .where(UsageRecord.window_start >= window_start)
            .group_by(ApiKey.account_id, UsageRecord.bucket)
        )
    ).all()

    agg: dict[str, dict[str, int]] = {}
    for account_id, bucket, total, errors in rows:
        total = int(total or 0)
        errors = int(errors or 0)
        a = agg.setdefault(account_id, {"requests": 0, "ai": 0, "det": 0, "err": 0})
        a["requests"] += total
        a["err"] += errors
        if bucket == UsageBucket.ai:
            a["ai"] += total
        else:
            a["det"] += total

    if not agg:
        return []

    # Resolve e-mails e keys ativas das contas do ranking.
    account_ids = list(agg.keys())
    email_rows = (
        await session.execute(
            select(DeveloperAccount.id, DeveloperAccount.email).where(
                DeveloperAccount.id.in_(account_ids)
            )
        )
    ).all()
    emails: dict[str, str] = {row[0]: row[1] for row in email_rows}
    active_keys_by_acc: dict[str, int] = {
        acc_id: int(count or 0)
        for acc_id, count in (
            await session.execute(
                select(ApiKey.account_id, func.count())
                .where(
                    ApiKey.account_id.in_(account_ids),
                    ApiKey.status == ApiKeyStatus.active,
                )
                .group_by(ApiKey.account_id)
            )
        ).all()
    }

    consumers = [
        TopConsumer(
            account_id=acc_id,
            email=emails.get(acc_id, "(conta removida)"),
            requests=a["requests"],
            ai=a["ai"],
            deterministic=a["det"],
            errors=a["err"],
            active_keys=active_keys_by_acc.get(acc_id, 0),
        )
        for acc_id, a in agg.items()
    ]
    consumers.sort(key=lambda c: c.requests, reverse=True)
    return consumers[:limit]


async def get_account_detail(
    session: AsyncSession,
    account_id: str,
    days: int = DEFAULT_WINDOW,
) -> AccountDetail | None:
    """Visão 360º de uma conta: identidade, keys e série de uso. ``None`` se ausente."""
    days = normalize_window(days)
    window_start = _day_window_start() - timedelta(days=days - 1)

    account = (
        await session.execute(select(DeveloperAccount).where(DeveloperAccount.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        return None

    providers = list(
        (
            await session.execute(
                select(OAuthIdentity.provider)
                .where(OAuthIdentity.account_id == account_id)
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    onboarding = (
        await session.execute(
            select(OnboardingProfile).where(OnboardingProfile.account_id == account_id)
        )
    ).scalar_one_or_none()

    keys = (
        (
            await session.execute(
                select(ApiKey)
                .where(ApiKey.account_id == account_id)
                .order_by(ApiKey.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    # Uso por key: janela e total histórico (duas agregações enxutas).
    window_by_key: dict[str, int] = {
        k: int(v or 0)
        for k, v in (
            await session.execute(
                select(UsageRecord.api_key_id, func.sum(UsageRecord.count))
                .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
                .where(
                    ApiKey.account_id == account_id,
                    UsageRecord.window_start >= window_start,
                )
                .group_by(UsageRecord.api_key_id)
            )
        ).all()
    }
    total_by_key: dict[str, int] = {
        k: int(v or 0)
        for k, v in (
            await session.execute(
                select(UsageRecord.api_key_id, func.sum(UsageRecord.count))
                .join(ApiKey, ApiKey.id == UsageRecord.api_key_id)
                .where(ApiKey.account_id == account_id)
                .group_by(UsageRecord.api_key_id)
            )
        ).all()
    }

    key_rows = [
        KeyRow(
            key_id=k.id,
            name=k.name,
            prefix=k.prefix,
            status=k.status.value if hasattr(k.status, "value") else str(k.status),
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            requests_window=window_by_key.get(k.id, 0),
            requests_total=total_by_key.get(k.id, 0),
        )
        for k in keys
    ]

    # Série de uso da conta (por dia/bucket na janela).
    usage_rows = (
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
                UsageRecord.window_start >= window_start,
            )
            .group_by(UsageRecord.window_start, UsageRecord.bucket)
        )
    ).all()
    series = _bucketize(list(usage_rows), days, window_start)

    return AccountDetail(
        account_id=account.id,
        email=account.email,
        email_verified=account.email_verified,
        created_at=account.created_at,
        has_password=account.password_hash is not None,
        oauth_providers=providers,
        onboarding=onboarding,
        total_keys=len(key_rows),
        active_keys=sum(1 for k in key_rows if k.status == ApiKeyStatus.active.value),
        window_days=days,
        requests_window=sum(p.total for p in series),
        ai_window=sum(p.ai for p in series),
        error_window=sum(p.errors for p in series),
        requests_total=sum(total_by_key.values()),
        keys=key_rows,
        series=series,
    )
