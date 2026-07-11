"""
Injeção de dependências (Princípio II).

Provê: sessão de banco, serviços de domínio, autenticação por sessão (portal) e
por API key (API), e o enforcement de rate limiting por bucket. As dependências
de auth/limite são projetadas para serem **sobrepostas por fixtures** nos testes
de US1 (a auth real chega em US2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import decode_access_token, hash_api_key
from app.db.base import get_session
from app.db.tables import ApiKey, ApiKeyStatus, DeveloperAccount

# --------------------------------------------------------------------------- #
# Banco
# --------------------------------------------------------------------------- #
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# --------------------------------------------------------------------------- #
# Limitadores por bucket (instância única — módulo global)
# --------------------------------------------------------------------------- #
deterministic_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_DETERMINISTIC_PER_MIN,
    window_seconds=60,
    burst=settings.RATE_LIMIT_DETERMINISTIC_BURST,
)
ai_limiter = SlidingWindowLimiter(max_requests=settings.RATE_LIMIT_AI_PER_MIN, window_seconds=60)

# Limitadores por IP dos endpoints de sessão (login/signup/verify-email não usam
# API key, então não passam pelos limitadores acima — força bruta e spam de
# contas ficariam sem nenhuma cota sem isto).
login_ip_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_LOGIN_PER_MIN, window_seconds=60
)
signup_ip_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_SIGNUP_PER_MIN, window_seconds=60
)
verify_ip_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_VERIFY_PER_MIN, window_seconds=60
)
oauth_ip_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_OAUTH_PER_MIN, window_seconds=60
)
forgot_ip_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_FORGOT_PER_MIN, window_seconds=60
)
# Painel admin: cota por IP para tentativas de auth (senha dev e callback OAuth).
admin_ip_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_ADMIN_PER_MIN, window_seconds=60
)


# --------------------------------------------------------------------------- #
# Serviços de domínio
# --------------------------------------------------------------------------- #
def get_bncc_service():
    from app.services.bncc_service import get_bncc_service as _get

    return _get()


async def get_vector_service():
    from app.main import app

    if not hasattr(app.state, "vector_service"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camada de IA indisponível.",
        )
    return app.state.vector_service


# --------------------------------------------------------------------------- #
# Auth por sessão do portal (JWT)
# --------------------------------------------------------------------------- #
_session_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="SessionAuth",
    description=(
        "JWT de sessão do portal (login self-service). Não usar para chamadas de "
        "API de dados/IA — use ApiKeyAuth."
    ),
)


async def get_current_account(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_session_bearer)] = None,
    request: Request = None,  # type: ignore[assignment]
) -> DeveloperAccount:
    """Resolve a conta do desenvolvedor a partir do JWT de sessão (header ou cookie)."""
    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    elif request is not None:
        token = request.cookies.get("__session")

    payload = decode_access_token(token) if token else None
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada."
        )

    account = await session.get(DeveloperAccount, payload["sub"])
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada."
        )
    return account


CurrentAccount = Annotated[DeveloperAccount, Depends(get_current_account)]


async def require_verified_account(account: CurrentAccount) -> DeveloperAccount:
    """Exige e-mail verificado para gerar/gerenciar keys (FR-007)."""
    if not account.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-mail não verificado. Confirme seu e-mail para gerenciar API keys.",
        )
    return account


VerifiedAccount = Annotated[DeveloperAccount, Depends(require_verified_account)]


# --------------------------------------------------------------------------- #
# Auth por API key (Bearer) — usado pelos endpoints de dados/IA
# --------------------------------------------------------------------------- #
_api_key_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="ApiKeyAuth",
    description=(
        "API key gerada no portal self-service, enviada como 'Authorization: "
        "Bearer <key>'. Requerida pelos endpoints de dados e busca semântica."
    ),
)


async def require_api_key(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_api_key_bearer)] = None,
) -> ApiKey:
    """
    Autentica a requisição por API key (Authorization: Bearer <key>).

    Lookup por hash SHA-256; key ausente/inválida/revogada → 401 imediato (FR-009).
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key ausente. Envie 'Authorization: Bearer <sua-key>'.",
        )

    key_hash = hash_api_key(credentials.credentials)
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()
    if api_key is None or api_key.status != ApiKeyStatus.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou revogada.",
        )

    api_key.last_used_at = datetime.now(UTC)
    return api_key


ApiKeyAuth = Annotated[ApiKey, Depends(require_api_key)]


# --------------------------------------------------------------------------- #
# Rate limiting por bucket
# --------------------------------------------------------------------------- #
def _enforce(limiter: SlidingWindowLimiter, api_key: ApiKey, bucket: str) -> None:
    allowed, retry_after = limiter.check(f"{bucket}:{api_key.id}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de requisições excedido.",
            headers={"Retry-After": str(retry_after)},
        )


def _mark_usage(request: Request | None, api_key_id: str, bucket: str) -> None:
    """Sinaliza no ``request.state`` a key/bucket cujo ``count`` já foi contabilizado.

    O ``UsageOutcomeMiddleware`` lê estes campos após a resposta e, se o status for
    de erro (>= 400), incrementa ``error_count`` da mesma linha diária. Só marcamos
    depois do registro do total — assim taxa de sucesso e total ficam consistentes,
    e requisições barradas por 429 (sem total) não entram na conta de erros.
    """
    if request is not None:
        request.state.usage_api_key_id = api_key_id
        request.state.usage_bucket = bucket


async def rate_limit_deterministic(
    api_key: ApiKeyAuth, session: SessionDep, request: Request = None  # type: ignore[assignment]
) -> ApiKey:
    """Cota determinística: 60/min + burst 10 (FR-010).

    Além do enforcement em memória (janela/min), contabiliza a chamada no bucket
    ``deterministic`` de ``usage_records`` (métrica durável do painel do portal —
    US2). Espelha o path de IA; a gravação vem DEPOIS do ``_enforce`` para não
    contar requisições rejeitadas por 429.
    """
    _enforce(deterministic_limiter, api_key, "deterministic")
    try:
        from app.services.usage_service import record_deterministic

        await record_deterministic(session, api_key.id)
        _mark_usage(request, api_key.id, "deterministic")
    except ImportError:
        # usage_service ainda não implementado (antes de US2) — janela/min já protege.
        pass
    return api_key


async def rate_limit_ai(
    api_key: ApiKeyAuth, session: SessionDep, request: Request = None  # type: ignore[assignment]
) -> ApiKey:
    """
    Cota de IA: 20/min (in-process) + teto diário de 500/dia durável (FR-010a).

    O teto diário é delegado ao usage_service (US2), quando presente.
    """
    _enforce(ai_limiter, api_key, "ai")
    try:
        from app.services.usage_service import check_and_record_daily_ai

        await check_and_record_daily_ai(session, api_key.id)
        _mark_usage(request, api_key.id, "ai")
    except ImportError:
        # usage_service ainda não implementado (antes de US2) — janela/min já protege.
        pass
    return api_key


DeterministicRateLimited = Annotated[ApiKey, Depends(rate_limit_deterministic)]
AiRateLimited = Annotated[ApiKey, Depends(rate_limit_ai)]


# --------------------------------------------------------------------------- #
# Rate limiting por IP (endpoints de sessão — sem API key)
# --------------------------------------------------------------------------- #
def _client_ip(request: Request) -> str:
    """IP do cliente para as cotas por IP.

    Atrás do Cloud Run/Firebase, ``request.client.host`` é o IP do balanceador —
    o que faria todas as requisições caírem no mesmo balde de rate limit. Em
    produção, o front-end do Google popula ``X-Forwarded-For`` como
    ``<cliente>, <proxies…>``; usamos o primeiro item (o cliente original). Fora de
    produção não há proxy confiável, então mantemos ``request.client.host``."""
    if settings.is_production:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else "unknown"


def _enforce_ip(limiter: SlidingWindowLimiter, bucket: str, request: Request) -> None:
    allowed, retry_after = limiter.check(f"{bucket}:{_client_ip(request)}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Tente novamente mais tarde.",
            headers={"Retry-After": str(retry_after)},
        )


async def rate_limit_login_ip(request: Request) -> None:
    """Cota por IP para login (força bruta de credenciais)."""
    _enforce_ip(login_ip_limiter, "login-ip", request)


async def rate_limit_signup_ip(request: Request) -> None:
    """Cota por IP para signup (spam/esgotamento de contas)."""
    _enforce_ip(signup_ip_limiter, "signup-ip", request)


async def rate_limit_verify_ip(request: Request) -> None:
    """Cota por IP para verify-email (higiene contra DoS; token já é inadivinhável)."""
    _enforce_ip(verify_ip_limiter, "verify-ip", request)


async def rate_limit_oauth_ip(request: Request) -> None:
    """Cota por IP para o início do fluxo OAuth (evita spam de redirects/state)."""
    _enforce_ip(oauth_ip_limiter, "oauth-ip", request)


async def rate_limit_forgot_ip(request: Request) -> None:
    """Cota por IP para "esqueci a senha" (coíbe spam de e-mail e enumeração)."""
    _enforce_ip(forgot_ip_limiter, "forgot-ip", request)


async def rate_limit_admin_ip(request: Request) -> None:
    """Cota por IP para auth do painel admin (força bruta de senha/spam de OAuth)."""
    _enforce_ip(admin_ip_limiter, "admin-ip", request)


LoginRateLimited = Annotated[None, Depends(rate_limit_login_ip)]
SignupRateLimited = Annotated[None, Depends(rate_limit_signup_ip)]
VerifyRateLimited = Annotated[None, Depends(rate_limit_verify_ip)]
OAuthRateLimited = Annotated[None, Depends(rate_limit_oauth_ip)]
ForgotRateLimited = Annotated[None, Depends(rate_limit_forgot_ip)]
AdminRateLimited = Annotated[None, Depends(rate_limit_admin_ip)]


# --------------------------------------------------------------------------- #
# Cliente HTTP de saída (login social) — injetável para ser mockável em teste
# --------------------------------------------------------------------------- #
async def get_http_client():
    """Fornece um ``httpx.AsyncClient`` para chamadas OAuth aos provedores.

    Provido via ``Depends`` para que os testes o sobreponham com um cliente falso
    (``app.dependency_overrides``), sem tocar a rede.
    """
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client
