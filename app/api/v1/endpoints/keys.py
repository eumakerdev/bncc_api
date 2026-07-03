"""
Endpoints de gestão de API keys (T046) — montados em ``/api/v1/keys``.

Exigem sessão do portal com **e-mail verificado** para criar (403 caso contrário).
O segredo completo aparece **uma única vez**, na criação.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentAccount, SessionDep, VerifiedAccount
from app.models.platform import (
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
)
from app.services import apikey_service

router = APIRouter()


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: CreateApiKeyRequest, account: VerifiedAccount, session: SessionDep
) -> ApiKeyCreatedResponse:
    key, full_key = await apikey_service.create(session, account, payload.name)
    return ApiKeyCreatedResponse(id=key.id, name=key.name, prefix=key.prefix, key=full_key)


@router.get("", response_model=list[ApiKeyResponse])
async def list_keys(account: CurrentAccount, session: SessionDep) -> list[ApiKeyResponse]:
    keys = await apikey_service.list_keys(session, account.id)
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            status=k.status.value,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def revoke_key(key_id: str, account: CurrentAccount, session: SessionDep) -> Response:
    await apikey_service.revoke(session, account.id, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
