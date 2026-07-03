"""
Endpoint da Busca Semantica com IA (US4 / P4).

POST /api/v1/busca-semantica
- Auth: API key (Bearer) + cota de IA (bucket `ai`: 20/min + teto 500/dia) via
  a dependencia `AiRateLimited` (deps.py).
- 200: resposta gerada (nao-oficial) + fontes oficiais rastreaveis, ou mensagem
  de "sem resultados confiaveis" quando abaixo do limiar (nao inventa).
- 400: query invalida/vazia/curta/longa -> tratado pelos validators do schema
  (RequestValidationError -> 400 no handler global) + sanitizacao.
- 429: cota de IA excedida -> tratado por AiRateLimited.
- 503: camada de IA indisponivel -> AIUnavailableError mapeada com detalhe
  acionavel; NAO afeta endpoints deterministicos (SC-009).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.core.deps import AiRateLimited
from app.models.search import BuscaSemanticaRequest, BuscaSemanticaResponse

router = APIRouter()
logger = logging.getLogger("bncc.busca")


@router.post(
    "",
    response_model=BuscaSemanticaResponse,
    summary="Busca semantica com IA (conteudo nao-oficial)",
    responses={
        400: {"description": "Query invalida (vazia/curta/longa) ou payload invalido."},
        429: {"description": "Cota de IA excedida (bucket ai: 20/min ou 500/dia)."},
        503: {"description": "Camada de IA indisponivel (acionavel)."},
    },
    description=(
        "Responde uma pergunta em linguagem natural com texto **gerado por IA** "
        "(claramente marcado como **nao-oficial**, `oficial=false`) acompanhado "
        "das **fontes oficiais rastreaveis** da BNCC (codigo + relevancia). "
        "Correspondencias abaixo do limiar de similaridade nao sao apresentadas "
        "como oficiais; na ausencia de correspondencia confiavel a resposta "
        "sinaliza isso em vez de inventar."
    ),
)
async def busca_semantica(
    payload: BuscaSemanticaRequest,
    _api_key: AiRateLimited,
    request: Request,
) -> BuscaSemanticaResponse:
    # Import preguicoso: mantem o app importavel mesmo sem libs de IA.
    from app.services.ai_service import AIUnavailableError, responder

    vector_service = getattr(request.app.state, "vector_service", None)

    try:
        return await responder(
            query=payload.query,
            max_resultados=payload.max_resultados,
            incluir_contexto=payload.incluir_contexto,
            vector_service=vector_service,
        )
    except AIUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.detail,
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - nunca vaza stack trace ao cliente
        logger.error("Erro inesperado na busca semantica: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Camada de IA temporariamente indisponivel. Endpoints "
                "deterministicos nao sao afetados."
            ),
        ) from exc
