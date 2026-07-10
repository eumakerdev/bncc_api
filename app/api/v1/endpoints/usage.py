"""
Endpoints de métricas de uso (T047).

Incluídos por ``api.py`` com prefixo **vazio** — por isso definem caminhos
completos: ``/keys/{id}/usage`` (por key) e ``/usage`` (agregado da conta).
Exigem sessão do portal; a key consultada deve pertencer à conta (404 se não).
"""

from __future__ import annotations

from fastapi import APIRouter, Path

from app.core.deps import CurrentAccount, SessionDep
from app.models.bncc import ErrorResponse
from app.models.platform import (
    AccountAnalyticsResponse,
    AccountUsageResponse,
    KeyUsageResponse,
)
from app.services import apikey_service, usage_service

router = APIRouter()


@router.get(
    "/keys/{key_id}/usage",
    response_model=KeyUsageResponse,
    tags=["Uso"],
    summary="Uso por API key (buckets determinístico/IA)",
    response_description="Contadores de uso e limites por bucket (determinístico e IA) da key.",
    description=(
        "Retorna as métricas de uso da API key informada, por bucket "
        "(`deterministic` e `ai`): consumo na janela atual e no dia, e os "
        "limites vigentes. A key consultada deve pertencer à conta autenticada. "
        "Exige sessão do portal."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
        404: {
            "model": ErrorResponse,
            "description": "API key inexistente ou pertencente a outra conta.",
        },
    },
)
async def key_usage(
    account: CurrentAccount,
    session: SessionDep,
    key_id: str = Path(..., description="Identificador da API key."),
) -> KeyUsageResponse:
    # Garante posse (404 se a key não for da conta).
    await apikey_service.get_owned_key(session, account.id, key_id)
    return await usage_service.key_usage(session, key_id)


@router.get(
    "/usage",
    response_model=AccountUsageResponse,
    tags=["Uso"],
    summary="Uso agregado da conta",
    response_description="Total de keys e consumo agregado (determinístico e IA) do dia.",
    description=(
        "Retorna o uso agregado do dia corrente para todas as API keys da "
        "conta autenticada (consumo determinístico e de IA). Exige sessão do "
        "portal."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
    },
)
async def account_usage(account: CurrentAccount, session: SessionDep) -> AccountUsageResponse:
    return await usage_service.account_usage(session, account.id)


@router.get(
    "/usage/analytics",
    response_model=AccountAnalyticsResponse,
    tags=["Uso"],
    summary="Analytics de uso da conta (série diária + KPIs)",
    response_description=(
        "Série diária dos últimos 30 dias (total vs. bem-sucedidas) e KPIs "
        "agregados: total de requisições e variação, taxa de sucesso, uso de IA, "
        "keys ativas."
    ),
    description=(
        "Retorna o BI de uso da conta autenticada: uma série diária dos últimos 30 "
        "dias (chamadas totais vs. bem-sucedidas) e indicadores agregados para o "
        "painel do portal (total de requisições com variação vs. período anterior, "
        "taxa de sucesso, chamadas de IA e determinísticas, keys ativas e novas). "
        "Exige sessão do portal."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
    },
)
async def account_analytics(
    account: CurrentAccount, session: SessionDep
) -> AccountAnalyticsResponse:
    return await usage_service.account_analytics(session, account.id)
