"""
Modelos Pydantic (v2) do domínio BNCC (dados oficiais, read-only em runtime).

Cobre as três etapas — Educação Infantil (EI), Ensino Fundamental (EF) e Ensino
Médio (EM) — e os metadados do snapshot versionado. O validador de código aceita
os três formatos oficiais (data-model.md §A / FR-002).

As classes `HabilidadeFiltros`, `PaginatedResponse`, `ErrorResponse` e as legadas
`BuscaSemanticaRequest`/`BuscaSemanticaResponse`/`DocumentoFonte` são preservadas
sem alteração de contrato — outros módulos as importam.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, validator

# --------------------------------------------------------------------------- #
# Padrões oficiais de código (FR-002) — três etapas
# --------------------------------------------------------------------------- #
CODE_PATTERN_EI = re.compile(r"^EI\d{2}[A-Z]{2}\d{2}$")
CODE_PATTERN_EF = re.compile(r"^EF\d{2}[A-Z]{2}\d{2}$")
CODE_PATTERN_EM = re.compile(r"^EM13[A-Z]{3}\d{3}$")
# Variante oficial do Ensino Médio para Língua Portuguesa (2 letras + 2 dígitos),
# ex.: EM13LP01. É um código oficial da BNCC; aceito para preservar ~53
# habilidades de LP do EM (fidelidade — Princípio IV). Não conflita com o padrão
# de área (3 letras + 3 dígitos).
CODE_PATTERN_EM_LP = re.compile(r"^EM13[A-Z]{2}\d{2}$")


def is_valid_codigo(codigo: str) -> bool:
    """True se o código casa com um dos formatos oficiais (EI/EF/EM).

    Aceita os três formatos canônicos (EI/EF/EM área) e a variante oficial do
    Ensino Médio para Língua Portuguesa (EM13LP##).
    """
    if not codigo:
        return False
    c = codigo.strip().upper()
    return bool(
        CODE_PATTERN_EI.match(c)
        or CODE_PATTERN_EF.match(c)
        or CODE_PATTERN_EM.match(c)
        or CODE_PATTERN_EM_LP.match(c)
    )


def etapa_from_codigo(codigo: str) -> str | None:
    """Deriva a etapa a partir do prefixo do código (determinístico)."""
    if not codigo:
        return None
    c = codigo.strip().upper()
    if not is_valid_codigo(c):
        return None
    if c.startswith("EI"):
        return EtapaEnsino.EDUCACAO_INFANTIL.value
    if c.startswith("EF"):
        return EtapaEnsino.ENSINO_FUNDAMENTAL.value
    if c.startswith("EM"):
        return EtapaEnsino.ENSINO_MEDIO.value
    return None


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class EtapaEnsino(str, Enum):
    """Etapas de ensino da BNCC."""

    EDUCACAO_INFANTIL = "educacao_infantil"
    ENSINO_FUNDAMENTAL = "ensino_fundamental"
    ENSINO_MEDIO = "ensino_medio"


class AreaConhecimento(str, Enum):
    """Áreas de conhecimento da BNCC."""

    LINGUAGENS = "linguagens"
    MATEMATICA = "matematica"
    CIENCIAS_NATUREZA = "ciencias_natureza"
    CIENCIAS_HUMANAS = "ciencias_humanas"
    ENSINO_RELIGIOSO = "ensino_religioso"


class ComponenteCurricular(str, Enum):
    """Componentes curriculares da BNCC."""

    LINGUA_PORTUGUESA = "lingua_portuguesa"
    ARTE = "arte"
    EDUCACAO_FISICA = "educacao_fisica"
    LINGUA_INGLESA = "lingua_inglesa"
    MATEMATICA = "matematica"
    CIENCIAS = "ciencias"
    GEOGRAFIA = "geografia"
    HISTORIA = "historia"
    ENSINO_RELIGIOSO = "ensino_religioso"


# --------------------------------------------------------------------------- #
# Educação Infantil (novo)
# --------------------------------------------------------------------------- #
class ObjetivoAprendizagem(BaseModel):
    """Objetivo de aprendizagem e desenvolvimento (Educação Infantil)."""

    codigo: str = Field(..., description="Código do objetivo (ex.: EI03EO01)")
    descricao: str = Field(..., description="Descrição oficial do objetivo")


class CampoExperiencia(BaseModel):
    """Campo de Experiência da Educação Infantil (novo)."""

    codigo: str = Field(..., description="Código do campo (ex.: EO, CG, TS, EF, ET)")
    nome: str = Field(..., description="Nome do campo de experiência")
    objetivos_aprendizagem: list[ObjetivoAprendizagem] = Field(
        default_factory=list, description="Objetivos de aprendizagem associados"
    )


# --------------------------------------------------------------------------- #
# Estrutura curricular navegável (novo)
# --------------------------------------------------------------------------- #
class UnidadeTematica(BaseModel):
    """Unidade Temática — agrupa objetos de conhecimento (novo)."""

    nome: str = Field(..., description="Nome da unidade temática")
    componente: ComponenteCurricular | None = Field(None, description="Componente curricular")
    etapa: EtapaEnsino = Field(..., description="Etapa de ensino")


class ObjetoConhecimento(BaseModel):
    """Objeto de Conhecimento — entidade navegável (novo)."""

    nome: str = Field(..., description="Nome do objeto de conhecimento")
    unidade_tematica: str | None = Field(
        None, description="Unidade temática que agrupa este objeto"
    )
    componente: ComponenteCurricular | None = Field(None, description="Componente curricular")
    etapa: EtapaEnsino = Field(..., description="Etapa de ensino")


# --------------------------------------------------------------------------- #
# Competências
# --------------------------------------------------------------------------- #
class CompetenciaGeral(BaseModel):
    """Competência geral da BNCC (1..10, transversal às etapas)."""

    numero: int = Field(..., ge=1, le=10, description="Número da competência (1-10)")
    titulo: str = Field(..., description="Título da competência")
    descricao: str = Field(..., description="Descrição completa da competência")

    model_config = {
        "json_schema_extra": {
            "example": {
                "numero": 1,
                "titulo": "Conhecimento",
                "descricao": "Valorizar e utilizar os conhecimentos historicamente "
                "construídos sobre o mundo físico, social, cultural e digital...",
            }
        }
    }


class CompetenciaEspecifica(BaseModel):
    """Competência específica de área/componente (EI/EF/EM)."""

    codigo: str = Field(..., description="Código único da competência específica")
    numero: int = Field(..., description="Número dentro da área/componente")
    area_conhecimento: AreaConhecimento = Field(..., description="Área de conhecimento")
    componente: ComponenteCurricular | None = Field(
        None, description="Componente curricular (se aplicável)"
    )
    descricao: str = Field(..., description="Descrição da competência específica")
    etapa: EtapaEnsino = Field(..., description="Etapa de ensino")

    model_config = {
        "json_schema_extra": {
            "example": {
                "codigo": "EFMAT01",
                "numero": 1,
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "descricao": "Reconhecer que a Matemática é uma ciência humana...",
                "etapa": "ensino_fundamental",
            }
        }
    }


# --------------------------------------------------------------------------- #
# Habilidade (entidade central)
# --------------------------------------------------------------------------- #
class Habilidade(BaseModel):
    """Habilidade da BNCC — suporta EI, EF e EM."""

    codigo: str = Field(..., description="Código oficial (EI/EF/EM)")
    descricao: str = Field(..., description="Descrição completa da habilidade")
    etapa: EtapaEnsino = Field(..., description="Etapa de ensino")
    anos: list[str] = Field(default_factory=list, description="Anos escolares")
    area_conhecimento: AreaConhecimento = Field(..., description="Área de conhecimento")
    componente: ComponenteCurricular | None = Field(
        None, description="Componente curricular (ausente no EM, organizado por área)"
    )
    competencias_gerais: list[int] = Field(
        default_factory=list, description="Competências gerais relacionadas (1-10)"
    )
    competencias_especificas: list[str] = Field(
        default_factory=list, description="Códigos de competências específicas"
    )
    objetos_conhecimento: list[str] = Field(
        default_factory=list, description="Objetos de conhecimento relacionados"
    )
    # Campos opcionais por etapa (oficiais quando presentes)
    campo_experiencia: str | None = Field(
        None, description="Campo de experiência (Educação Infantil)"
    )
    itinerario: str | None = Field(None, description="Itinerário formativo (Ensino Médio)")
    unidade_tematica: str | None = Field(None, description="Unidade temática (Ensino Fundamental)")

    @field_validator("codigo")
    @classmethod
    def validate_codigo(cls, v: str) -> str:
        """Aceita os três formatos oficiais de código (EI/EF/EM)."""
        if not v:
            raise ValueError("Código é obrigatório")
        c = v.strip().upper()
        if not is_valid_codigo(c):
            raise ValueError(
                "Código inválido: deve casar com EI (EI##XX##), " "EF (EF##XX##) ou EM (EM13XXX###)"
            )
        return c

    @field_validator("competencias_gerais")
    @classmethod
    def validate_competencias_gerais(cls, v: list[int]) -> list[int]:
        for comp in v:
            if comp < 1 or comp > 10:
                raise ValueError("Competências gerais devem estar entre 1 e 10")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "codigo": "EF05MA07",
                "descricao": "Resolver e elaborar problemas de adição e subtração...",
                "etapa": "ensino_fundamental",
                "anos": ["5"],
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "competencias_gerais": [1, 2, 4],
                "competencias_especificas": [],
                "objetos_conhecimento": [],
            }
        }
    }


# --------------------------------------------------------------------------- #
# Metadados do snapshot (novo)
# --------------------------------------------------------------------------- #
class SnapshotMetadata(BaseModel):
    """Metadados de rastreabilidade do snapshot versionado (FR-025)."""

    versao: str = Field(..., description="Versão do snapshot (ex.: v1)")
    data_publicacao: str = Field(..., description="Data de publicação (ISO)")
    checksum_fontes: dict[str, str] = Field(
        default_factory=dict, description="SHA-256 de cada fonte oficial"
    )
    contagens: dict[str, Any] = Field(
        default_factory=dict, description="Contagens por etapa/componente"
    )
    missing_sources: list[str] = Field(
        default_factory=list, description="Fontes oficiais ausentes (ex.: educacao_infantil)"
    )


# --------------------------------------------------------------------------- #
# Filtros / envelopes (PRESERVADOS — outros módulos importam)
# --------------------------------------------------------------------------- #
class HabilidadeFiltros(BaseModel):
    """Filtros para busca de habilidades."""

    etapa: EtapaEnsino | None = Field(None, description="Filtrar por etapa de ensino")
    ano: str | None = Field(None, description="Filtrar por ano escolar")
    area_conhecimento: AreaConhecimento | None = Field(
        None, description="Filtrar por área de conhecimento"
    )
    componente: ComponenteCurricular | None = Field(
        None, description="Filtrar por componente curricular"
    )
    competencia_geral: int | None = Field(None, description="Filtrar por competência geral (1-10)")

    @validator("competencia_geral")
    def validate_competencia_geral(cls, v):
        """Valida que a competência geral está no range 1-10."""
        if v is not None and (v < 1 or v > 10):
            raise ValueError("Competência geral deve estar entre 1 e 10")
        return v


class BuscaSemanticaRequest(BaseModel):
    """Request para busca semântica."""

    query: str = Field(
        ..., min_length=3, max_length=500, description="Pergunta em linguagem natural"
    )
    max_resultados: int | None = Field(5, ge=1, le=20, description="Número máximo de resultados")
    incluir_contexto: bool | None = Field(
        True, description="Incluir contexto adicional na resposta"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Qual habilidade de matemática do 5º ano aborda frações?",
                "max_resultados": 5,
                "incluir_contexto": True,
            }
        }


class DocumentoFonte(BaseModel):
    """Documento fonte usado na resposta da busca semântica."""

    codigo: str = Field(..., description="Código da habilidade/competência")
    tipo: str = Field(..., description="Tipo do documento (habilidade/competencia)")
    relevancia: float = Field(..., ge=0, le=1, description="Score de relevância (0-1)")
    titulo: str | None = Field(None, description="Título do documento")


class BuscaSemanticaResponse(BaseModel):
    """Response da busca semântica."""

    resposta: str = Field(..., description="Resposta gerada pela IA")
    fontes: list[DocumentoFonte] = Field(..., description="Documentos fontes utilizados")
    documentos_consultados: int = Field(..., description="Total de documentos consultados")
    tempo_processamento: float | None = Field(
        None, description="Tempo de processamento em segundos"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "resposta": "Para o 5º ano, a habilidade EF05MA03 aborda frações...",
                "fontes": [
                    {
                        "codigo": "EF05MA03",
                        "tipo": "habilidade",
                        "relevancia": 0.95,
                        "titulo": "Identificar e representar frações",
                    }
                ],
                "documentos_consultados": 3,
                "tempo_processamento": 0.85,
            }
        }


class ErrorResponse(BaseModel):
    """Modelo padrão para respostas de erro."""

    detail: str = Field(..., description="Descrição do erro")
    error_code: str | None = Field(None, description="Código interno do erro")
    timestamp: str | None = Field(None, description="Timestamp do erro")


class PaginatedResponse(BaseModel):
    """Resposta paginada genérica."""

    items: list[Any] = Field(..., description="Items da página atual")
    total: int = Field(..., description="Total de items")
    page: int = Field(..., description="Página atual")
    size: int = Field(..., description="Tamanho da página")
    pages: int = Field(..., description="Total de páginas")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "size": 20,
                "pages": 5,
            }
        }
