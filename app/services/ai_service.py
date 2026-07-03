"""
Orquestracao RAG da busca semantica (US4 / P4).

Fluxo:
  1. Recupera fontes oficiais via `VectorStoreService.search` (limiar 0,70).
  2. Sem correspondencia confiavel -> resposta de "sem resultados" (nao inventa).
  3. Com fontes -> gera texto com LLM (timeout + teto de tokens); se o LLM nao
     estiver configurado ou falhar, degrada para um resumo deterministico das
     fontes oficiais. O texto e SEMPRE marcado como nao-oficial (FR-016).

Limites de custo (FR-019): `AI_REQUEST_TIMEOUT_SECONDS` e `AI_MAX_OUTPUT_TOKENS`.

`AIUnavailableError` e levantada quando a camada de recuperacao (embeddings/
ChromaDB) esta fora do ar, para o endpoint mapear em 503 acionavel (Principio VI).
Provedores de LLM sao importados preguicosamente.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.core.config import settings
from app.models.search import (
    AVISO_NAO_OFICIAL,
    BuscaSemanticaResponse,
    DocumentoFonte,
)

logger = logging.getLogger(__name__)


class AIUnavailableError(Exception):
    """Camada de IA (LLM/embeddings) indisponivel -> 503 acionavel."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


SEM_RESULTADOS = (
    "Nao encontrei na BNCC habilidades ou competencias com correspondencia "
    "confiavel para a sua pergunta. Tente reformular com termos mais especificos "
    "(por exemplo, citando o ano/etapa e o componente curricular). Nenhuma "
    "informacao foi inventada."
)


# --------------------------------------------------------------------------- #
# Provedor de LLM (opcional; import preguicoso)
# --------------------------------------------------------------------------- #
def _detect_llm_provider() -> str | None:
    """Retorna 'openai' | 'google' se houver key configurada, senao None."""
    if settings.OPENAI_API_KEY:
        return "openai"
    if settings.GOOGLE_API_KEY:
        return "google"
    return None


def _build_context(fontes: list[dict[str, Any]]) -> str:
    partes = []
    for f in fontes:
        codigo = f.get("codigo", "")
        descricao = f.get("descricao") or ""
        partes.append(f"[{codigo}] {descricao}".strip())
    return "\n".join(partes)


def _build_prompt(query: str, contexto: str) -> str:
    return (
        "Voce e um assistente especializado na BNCC do Brasil. Responda a "
        "pergunta USANDO APENAS o contexto oficial abaixo. Cite os codigos das "
        "habilidades/competencias relevantes. Nao invente informacoes.\n\n"
        f"PERGUNTA: {query}\n\n"
        f"CONTEXTO OFICIAL:\n{contexto}\n\n"
        "RESPOSTA (clara e educativa):"
    )


def _deterministic_answer(query: str, fontes: list[dict[str, Any]]) -> str:
    """Resumo deterministico das fontes (fallback sem LLM)."""
    linhas = [
        "Com base nas fontes oficiais da BNCC mais relevantes para a sua " "pergunta, destaco:",
        "",
    ]
    for f in fontes[:5]:
        codigo = f.get("codigo", "N/A")
        descricao = (f.get("descricao") or "").strip()
        if len(descricao) > 240:
            descricao = descricao[:240].rstrip() + "..."
        linhas.append(f"- {codigo}: {descricao}")
    linhas.append("")
    linhas.append(
        "Consulte os codigos acima nos endpoints deterministicos para o texto " "oficial completo."
    )
    return "\n".join(linhas)


def _call_openai_sync(prompt: str) -> str:
    from openai import OpenAI  # noqa: WPS433

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": "Voce e um assistente da BNCC."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def _call_google_sync(prompt: str) -> str:
    import google.generativeai as genai  # noqa: WPS433

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel(settings.LLM_MODEL)
    resp = model.generate_content(
        prompt,
        generation_config={
            "max_output_tokens": settings.AI_MAX_OUTPUT_TOKENS,
            "temperature": 0.2,
        },
    )
    return (resp.text or "").strip()


async def _generate_with_llm(query: str, fontes: list[dict[str, Any]]) -> str:
    """
    Gera a resposta com o LLM, respeitando timeout e teto de tokens.

    Em qualquer falha (lib ausente, erro de API, timeout), degrada para o resumo
    deterministico das fontes oficiais (Principio VII).
    """
    provider = _detect_llm_provider()
    if provider is None:
        logger.info("Nenhum LLM configurado; usando resumo deterministico.")
        return _deterministic_answer(query, fontes)

    prompt = _build_prompt(query, _build_context(fontes))
    caller = _call_openai_sync if provider == "openai" else _call_google_sync

    try:
        texto = await asyncio.wait_for(
            asyncio.to_thread(caller, prompt),
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        )
        if texto:
            return texto
        logger.warning("LLM retornou vazio; degradando para resumo deterministico.")
    except asyncio.TimeoutError:
        logger.warning(
            "LLM excedeu timeout de %ss; degradando.", settings.AI_REQUEST_TIMEOUT_SECONDS
        )
    except Exception as exc:  # noqa: BLE001 - degradacao graciosa
        logger.warning("Falha no LLM (%s); degradando.", type(exc).__name__)

    return _deterministic_answer(query, fontes)


# --------------------------------------------------------------------------- #
# Ponto de entrada RAG
# --------------------------------------------------------------------------- #
async def responder(
    query: str,
    max_resultados: int = 5,
    incluir_contexto: bool = True,
    vector_service: Any = None,
) -> BuscaSemanticaResponse:
    """
    Executa a busca semantica com resposta gerada (nao-oficial).

    Levanta `AIUnavailableError` quando a recuperacao (embeddings/ChromaDB) esta
    indisponivel. Retorna 200-equivalente (objeto) em todos os demais casos,
    incluindo ausencia de correspondencia confiavel.
    """
    start = time.perf_counter()

    if vector_service is None or not getattr(vector_service, "available", False):
        raise AIUnavailableError(
            "Camada de IA (embeddings/vetores) indisponivel. Os endpoints "
            "deterministicos permanecem funcionais. Tente novamente mais tarde "
            "ou consulte /api/v1/sistema/readiness."
        )

    try:
        fontes_raw = await vector_service.search(query, max_resultados)
    except AIUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AIUnavailableError(
            "Falha na recuperacao semantica (embeddings/vetores). Endpoints "
            "deterministicos nao sao afetados."
        ) from exc

    if not fontes_raw:
        return BuscaSemanticaResponse(
            resposta=SEM_RESULTADOS,
            fontes=[],
            documentos_consultados=0,
            tempo_processamento=round(time.perf_counter() - start, 3),
            oficial=False,
            aviso=AVISO_NAO_OFICIAL,
        )

    resposta_texto = await _generate_with_llm(query, fontes_raw)

    fontes = [
        DocumentoFonte(
            codigo=f.get("codigo", ""),
            tipo=f.get("tipo", "habilidade"),
            relevancia=float(f.get("relevancia", 0.0)),
            titulo=f.get("titulo"),
        )
        for f in fontes_raw
    ]

    return BuscaSemanticaResponse(
        resposta=resposta_texto,
        fontes=fontes,
        documentos_consultados=len(fontes_raw),
        tempo_processamento=round(time.perf_counter() - start, 3),
        oficial=False,
        aviso=AVISO_NAO_OFICIAL,
    )
