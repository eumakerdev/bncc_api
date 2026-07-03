"""
Endpoints de métricas de uso (T047).

Incluídos por ``api.py`` com prefixo **vazio** — por isso definem caminhos
completos: ``/keys/{id}/usage`` (por key) e ``/usage`` (agregado da conta).
Exigem sessão do portal; a key consultada deve pertencer à conta (404 se não).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentAccount, SessionDep
from app.models.platform import AccountUsageResponse, KeyUsageResponse
from app.services import apikey_service, usage_service

router = APIRouter()


@router.get("/keys/{key_id}/usage", response_model=KeyUsageResponse, tags=["Uso"])
async def key_usage(key_id: str, account: CurrentAccount, session: SessionDep) -> KeyUsageResponse:
    # Garante posse (404 se a key não for da conta).
    await apikey_service.get_owned_key(session, account.id, key_id)
    return await usage_service.key_usage(session, key_id)


@router.get("/usage", response_model=AccountUsageResponse, tags=["Uso"])
async def account_usage(account: CurrentAccount, session: SessionDep) -> AccountUsageResponse:
    return await usage_service.account_usage(session, account.id)
