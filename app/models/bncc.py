"""
Pydantic models for BNCC data structures
"""

from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator


class EtapaEnsino(str, Enum):
    """Etapas de ensino da BNCC"""
    EDUCACAO_INFANTIL = "educacao_infantil"
    ENSINO_FUNDAMENTAL = "ensino_fundamental"
    ENSINO_MEDIO = "ensino_medio"


class AreaConhecimento(str, Enum):
    """Áreas de conhecimento da BNCC"""
    LINGUAGENS = "linguagens"
    MATEMATICA = "matematica"
    CIENCIAS_NATUREZA = "ciencias_natureza"
    CIENCIAS_HUMANAS = "ciencias_humanas"
    ENSINO_RELIGIOSO = "ensino_religioso"


class ComponenteCurricular(str, Enum):
    """Componentes curriculares da BNCC"""
    LINGUA_PORTUGUESA = "lingua_portuguesa"
    ARTE = "arte"
    EDUCACAO_FISICA = "educacao_fisica"
    LINGUA_INGLESA = "lingua_inglesa"
    MATEMATICA = "matematica"
    CIENCIAS = "ciencias"
    GEOGRAFIA = "geografia"
    HISTORIA = "historia"
    ENSINO_RELIGIOSO = "ensino_religioso"


class CompetenciaGeral(BaseModel):
    """Modelo para competência geral da BNCC"""
    numero: int = Field(..., description="Número da competência (1-10)")
    titulo: str = Field(..., description="Título da competência")
    descricao: str = Field(..., description="Descrição completa da competência")
    
    class Config:
        json_schema_extra = {
            "example": {
                "numero": 1,
                "titulo": "Conhecimento",
                "descricao": "Valorizar e utilizar os conhecimentos historicamente construídos..."
            }
        }


class CompetenciaEspecifica(BaseModel):
    """Modelo para competência específica de área/componente"""
    codigo: str = Field(..., description="Código único da competência específica")
    numero: int = Field(..., description="Número da competência dentro da área/componente")
    area_conhecimento: AreaConhecimento = Field(..., description="Área de conhecimento")
    componente: Optional[ComponenteCurricular] = Field(None, description="Componente curricular (se aplicável)")
    descricao: str = Field(..., description="Descrição da competência específica")
    etapa: EtapaEnsino = Field(..., description="Etapa de ensino")
    
    class Config:
        json_schema_extra = {
            "example": {
                "codigo": "EFMAT01",
                "numero": 1,
                "area_conhecimento": "matematica",
                "componente": "matematica",
                "descricao": "Reconhecer que a Matemática é uma ciência humana...",
                "etapa": "ensino_fundamental"
            }
        }


class Habilidade(BaseModel):
    """Modelo para habilidade da BNCC"""
    codigo: str = Field(..., description="Código único da habilidade (ex: EF67EF01)")
    descricao: str = Field(..., description="Descrição completa da habilidade")
    etapa: EtapaEnsino = Field(..., description="Etapa de ensino")
    anos: List[str] = Field(..., description="Anos escolares (ex: ['6', '7'])")
    area_conhecimento: AreaConhecimento = Field(..., description="Área de conhecimento")
    componente: ComponenteCurricular = Field(..., description="Componente curricular")
    competencias_gerais: List[int] = Field(..., description="Lista de competências gerais relacionadas")
    competencias_especificas: List[str] = Field(..., description="Lista de códigos de competências específicas")
    objetos_conhecimento: List[str] = Field(default=[], description="Objetos de conhecimento relacionados")
    
    @validator('codigo')
    def validate_codigo(cls, v):
        """Valida o formato do código da habilidade"""
        if not v or len(v) < 6:
            raise ValueError('Código deve ter pelo menos 6 caracteres')
        return v.upper()
    
    @validator('competencias_gerais')
    def validate_competencias_gerais(cls, v):
        """Valida que as competências gerais estão no range 1-10"""
        for comp in v:
            if comp < 1 or comp > 10:
                raise ValueError('Competências gerais devem estar entre 1 e 10')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "codigo": "EF67EF01",
                "descricao": "Experimentar, desfrutar, apreciar e criar diferentes brincadeiras...",
                "etapa": "ensino_fundamental",
                "anos": ["6", "7"],
                "area_conhecimento": "linguagens",
                "componente": "educacao_fisica",
                "competencias_gerais": [1, 4, 8],
                "competencias_especificas": ["EFEF01", "EFEF02"],
                "objetos_conhecimento": ["Brincadeiras e jogos", "Jogos eletrônicos"]
            }
        }


class HabilidadeFiltros(BaseModel):
    """Filtros para busca de habilidades"""
    etapa: Optional[EtapaEnsino] = Field(None, description="Filtrar por etapa de ensino")
    ano: Optional[str] = Field(None, description="Filtrar por ano escolar")
    area_conhecimento: Optional[AreaConhecimento] = Field(None, description="Filtrar por área de conhecimento")
    componente: Optional[ComponenteCurricular] = Field(None, description="Filtrar por componente curricular")
    competencia_geral: Optional[int] = Field(None, description="Filtrar por competência geral (1-10)")
    
    @validator('competencia_geral')
    def validate_competencia_geral(cls, v):
        """Valida que a competência geral está no range 1-10"""
        if v is not None and (v < 1 or v > 10):
            raise ValueError('Competência geral deve estar entre 1 e 10')
        return v


class BuscaSemanticaRequest(BaseModel):
    """Request para busca semântica"""
    query: str = Field(..., min_length=3, max_length=500, description="Pergunta ou busca em linguagem natural")
    max_resultados: Optional[int] = Field(5, ge=1, le=20, description="Número máximo de resultados")
    incluir_contexto: Optional[bool] = Field(True, description="Incluir contexto adicional na resposta")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Qual habilidade de matemática do 5º ano aborda frações?",
                "max_resultados": 5,
                "incluir_contexto": True
            }
        }


class DocumentoFonte(BaseModel):
    """Documento fonte usado na resposta da busca semântica"""
    codigo: str = Field(..., description="Código da habilidade/competência")
    tipo: str = Field(..., description="Tipo do documento (habilidade/competencia)")
    relevancia: float = Field(..., ge=0, le=1, description="Score de relevância (0-1)")
    titulo: Optional[str] = Field(None, description="Título do documento")


class BuscaSemanticaResponse(BaseModel):
    """Response da busca semântica"""
    resposta: str = Field(..., description="Resposta gerada pela IA")
    fontes: List[DocumentoFonte] = Field(..., description="Documentos fontes utilizados")
    documentos_consultados: int = Field(..., description="Total de documentos consultados")
    tempo_processamento: Optional[float] = Field(None, description="Tempo de processamento em segundos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "resposta": "Para o 5º ano do Ensino Fundamental, a habilidade EF05MA03 aborda especificamente o trabalho com frações...",
                "fontes": [
                    {
                        "codigo": "EF05MA03",
                        "tipo": "habilidade",
                        "relevancia": 0.95,
                        "titulo": "Identificar e representar frações"
                    }
                ],
                "documentos_consultados": 3,
                "tempo_processamento": 0.85
            }
        }


class ErrorResponse(BaseModel):
    """Modelo padrão para respostas de erro"""
    detail: str = Field(..., description="Descrição do erro")
    error_code: Optional[str] = Field(None, description="Código interno do erro")
    timestamp: Optional[str] = Field(None, description="Timestamp do erro")


class PaginatedResponse(BaseModel):
    """Resposta paginada genérica"""
    items: List[Any] = Field(..., description="Items da página atual")
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
                "pages": 5
            }
        }
