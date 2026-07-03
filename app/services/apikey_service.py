"""
Serviço de API keys (T042).

Cria/lista/revoga keys. O segredo completo é gerado e devolvido **uma única vez**
na criação; apenas ``prefix`` (não sensível) e ``key_hash`` (SHA-256) são
persistidos. Autorização por posse: um dev só enxerga/gerencia suas próprias keys.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key
from app.db.tables import ApiKey, ApiKeyStatus, DeveloperAccount


def _now() -> datetime:
    return datetime.now(UTC)


async def create(session: AsyncSession, account: DeveloperAccount, name: str) -> tuple[ApiKey, str]:
    """Cria uma nova API key ativa. Retorna ``(ApiKey, full_key)``."""
    full_key, prefix, key_hash = generate_api_key()
    key = ApiKey(
        account_id=account.id,
        name=name,
        prefix=prefix,
        key_hash=key_hash,
        status=ApiKeyStatus.active,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key, full_key


async def list_keys(session: AsyncSession, account_id: str) -> list[ApiKey]:
    """Lista as keys da conta (o segredo/hash nunca é exposto por schema)."""
    result = await session.execute(
        select(ApiKey).where(ApiKey.account_id == account_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke(session: AsyncSession, account_id: str, key_id: str) -> ApiKey:
    """
    Revoga uma key da conta (owner-only).

    Key inexistente ou de outra conta → 404 (não confirma existência alheia).
    """
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.account_id == account_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key não encontrada.")

    key.status = ApiKeyStatus.revoked
    key.revoked_at = _now()
    await session.commit()
    await session.refresh(key)
    return key


async def get_owned_key(session: AsyncSession, account_id: str, key_id: str) -> ApiKey:
    """Recupera uma key garantindo posse; 404 se inexistente/de outra conta."""
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.account_id == account_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key não encontrada.")
    return key
