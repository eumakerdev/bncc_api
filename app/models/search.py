"""
Schemas Pydantic v2 da Busca Semantica com IA (US4 / P4).

Definidos aqui (e nao em `app/models/bncc.py`, que pertence a US1) para manter a
propriedade de arquivos por historia. Regras do contrato
(`contracts/semantic-search.md`):

- Entrada validada **e sanitizada** (tamanho 3-500, tipo, anti-injecao basica).
- Saida marca **claramente** o conteudo gerado como **nao-oficial** (FR-016):
  `oficial=False` + `aviso`.
- Fontes rastreaveis: cada `DocumentoFonte` traz `codigo`, `tipo`, `relevancia`
  (SC-006).
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------- #
# Sanitizacao de entrada (Principio V - input validado/sanitizado)
# --------------------------------------------------------------------------- #

# Caracteres de controle C0/C1 e DEL. Removidos (NUL e afins poderiam ser usados
# para poluicao/injecao). Tab/newline/CR sao tratados depois pelo colapso de
# whitespace, entao nao precisam constar aqui.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Marcadores comuns de tentativa de prompt-injection. Neutralizados (removidos)
# de forma conservadora - nao confiamos na entrada para instruir o LLM.
_INJECTION_PATTERNS = re.compile(
    r"(?i)\b(ignore\s+(all\s+)?previous\s+instructions"
    r"|disregard\s+(the\s+)?above"
    r"|system\s*prompt"
    r"|desconsidere\s+as\s+instrucoes"
    r"|ignore\s+as\s+instrucoes)\b"
)


def sanitize_query(value: str) -> str:
    """
    Sanitiza a query do usuario antes da validacao de tamanho.

    - Normaliza Unicode (NFKC) e remove caracteres de controle.
    - Colapsa espacos em branco redundantes.
    - Neutraliza marcadores obvios de prompt-injection.
    - Faz `strip()` das bordas.

    Retorna a string limpa; a validacao de tamanho (3-500) e aplicada depois
    pelo `Field`, de modo que entrada vazia/curta/longa vira erro 400.
    """
    if not isinstance(value, str):
        raise ValueError("query deve ser uma string")

    text = unicodedata.normalize("NFKC", value)
    text = _CONTROL_CHARS.sub(" ", text)
    text = _INJECTION_PATTERNS.sub(" ", text)
    # Colapsa qualquer whitespace (inclui tab/newline) em um unico espaco.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class BuscaSemanticaRequest(BaseModel):
    """Corpo da requisicao de busca semantica."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Pergunta ou busca em linguagem natural (3-500 caracteres).",
    )
    max_resultados: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Numero maximo de fontes a considerar (1-20).",
    )
    incluir_contexto: bool = Field(
        default=True,
        description="Se verdadeiro, enriquece a resposta com o contexto das fontes.",
    )

    @field_validator("query", mode="before")
    @classmethod
    def _sanitize_query(cls, v: object) -> object:
        if isinstance(v, str):
            return sanitize_query(v)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Qual habilidade de matematica do 5o ano aborda fracoes?",
                "max_resultados": 5,
                "incluir_contexto": True,
            }
        }
    }


class DocumentoFonte(BaseModel):
    """
    Fonte oficial rastreavel citada na resposta.

    Definicao propria de US4 (nao importar de `app/models/bncc.py`).
    """

    codigo: str = Field(..., description="Codigo oficial da habilidade/competencia.")
    tipo: str = Field(..., description="Tipo do documento (habilidade | competencia).")
    relevancia: float = Field(..., ge=0.0, le=1.0, description="Similaridade coseno (0-1).")
    titulo: str | None = Field(
        default=None, description="Titulo legivel do documento (quando disponivel)."
    )


# Aviso padrao anexado a toda resposta gerada por IA (FR-016 / US4-AS4).
AVISO_NAO_OFICIAL = (
    "Conteudo gerado por IA a partir de fontes oficiais da BNCC. "
    "A redacao da resposta NAO e um documento oficial - consulte os codigos "
    "citados em `fontes` para o texto oficial."
)


class BuscaSemanticaResponse(BaseModel):
    """Resposta da busca semantica - conteudo gerado, marcado como nao-oficial."""

    resposta: str = Field(..., description="Texto gerado (nao-oficial) pela IA.")
    fontes: list[DocumentoFonte] = Field(
        default_factory=list,
        description="Documentos oficiais rastreaveis usados/citados.",
    )
    documentos_consultados: int = Field(
        default=0, description="Total de documentos considerados na recuperacao."
    )
    tempo_processamento: float | None = Field(
        default=None, description="Tempo de processamento em segundos."
    )
    oficial: bool = Field(
        default=False,
        description="Sempre False: o texto gerado NAO e dado oficial (FR-016).",
    )
    aviso: str = Field(
        default=AVISO_NAO_OFICIAL,
        description="Aviso de nao-oficialidade do conteudo gerado.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "resposta": (
                    "As habilidades relacionadas a fracoes no 5o ano incluem a "
                    "EF05MA03... (conteudo nao-oficial gerado por IA)"
                ),
                "fontes": [
                    {
                        "codigo": "EF05MA03",
                        "tipo": "habilidade",
                        "relevancia": 0.91,
                        "titulo": "Habilidade EF05MA03 - Matematica",
                    }
                ],
                "documentos_consultados": 5,
                "tempo_processamento": 1.23,
                "oficial": False,
                "aviso": AVISO_NAO_OFICIAL,
            }
        }
    }
