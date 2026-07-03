"""
Endpoints de gestão de API keys (T046) — montados em ``/api/v1/keys``.

Exigem sessão do portal com **e-mail verificado** para criar (403 caso contrário).
O segredo completo aparece **uma única vez**, na criação.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Path, Response, status

from app.core.deps import CurrentAccount, SessionDep, VerifiedAccount
from app.models.bncc import ErrorResponse
from app.models.platform import (
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
)
from app.services import apikey_service

router = APIRouter()


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar uma nova API key",
    response_description="Key criada; o segredo completo (`key`) só aparece nesta resposta.",
    description=(
        "Gera uma nova API key para a conta autenticada. Exige sessão do portal "
        "**com e-mail verificado** (FR-007). O segredo completo é exibido "
        "**uma única vez**, nesta resposta — apenas o prefixo é recuperável depois."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
        403: {
            "model": ErrorResponse,
            "description": "E-mail não verificado — verifique o e-mail antes de criar keys.",
        },
    },
)
async def create_key(
    payload: Annotated[
        CreateApiKeyRequest,
        Body(
            openapi_examples={
                "padrao": {
                    "summary": "Key de produção",
                    "value": {"name": "Minha key de produção"},
                },
            },
        ),
    ],
    account: VerifiedAccount,
    session: SessionDep,
) -> ApiKeyCreatedResponse:
    key, full_key = await apikey_service.create(session, account, payload.name)
    return ApiKeyCreatedResponse(id=key.id, name=key.name, prefix=key.prefix, key=full_key)


@router.get(
    "",
    response_model=list[ApiKeyResponse],
    summary="Listar as API keys da conta",
    response_description="Keys da conta autenticada (sem segredo/hash).",
    description=(
        "Lista as API keys da conta autenticada (ativas e revogadas), sem "
        "expor segredo ou hash. Exige sessão do portal."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
    },
)
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
    summary="Revogar uma API key",
    response_description="Key revogada com sucesso (sem corpo).",
    description=(
        "Revoga (soft-delete) uma API key da conta autenticada. Apenas o "
        "proprietário da key pode revogá-la; keys de outras contas ou "
        "inexistentes retornam 404 (não confirma existência alheia)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
        404: {
            "model": ErrorResponse,
            "description": "API key inexistente ou pertencente a outra conta.",
        },
    },
)
async def revoke_key(
    account: CurrentAccount,
    session: SessionDep,
    key_id: str = Path(..., description="Identificador da API key a revogar."),
) -> Response:
    await apikey_service.revoke(session, account.id, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
