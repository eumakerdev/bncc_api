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
_session_bearer = HTTPBearer(auto_error=False)


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
        token = request.cookies.get("session")

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
_api_key_bearer = HTTPBearer(auto_error=False)


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


async def rate_limit_deterministic(api_key: ApiKeyAuth) -> ApiKey:
    """Cota determinística: 60/min + burst 10 (FR-010)."""
    _enforce(deterministic_limiter, api_key, "deterministic")
    return api_key


async def rate_limit_ai(api_key: ApiKeyAuth, session: SessionDep) -> ApiKey:
    """
    Cota de IA: 20/min (in-process) + teto diário de 500/dia durável (FR-010a).

    O teto diário é delegado ao usage_service (US2), quando presente.
    """
    _enforce(ai_limiter, api_key, "ai")
    try:
        from app.services.usage_service import check_and_record_daily_ai

        await check_and_record_daily_ai(session, api_key.id)
    except ImportError:
        # usage_service ainda não implementado (antes de US2) — janela/min já protege.
        pass
    return api_key


DeterministicRateLimited = Annotated[ApiKey, Depends(rate_limit_deterministic)]
AiRateLimited = Annotated[ApiKey, Depends(rate_limit_ai)]
