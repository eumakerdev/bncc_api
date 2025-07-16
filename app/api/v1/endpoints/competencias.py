"""
Endpoints for competencias (competencies) from BNCC
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends

from app.models.bncc import (
    CompetenciaGeral, CompetenciaEspecifica,
    EtapaEnsino, AreaConhecimento, ComponenteCurricular
)
from app.services.bncc_service import get_bncc_service, BNCCDataService

router = APIRouter()


@router.get(
    "/gerais",
    response_model=List[CompetenciaGeral],
    summary="Listar competências gerais",
    description="""
    Retorna todas as 10 competências gerais da BNCC.
    
    As competências gerais são fundamentais para o desenvolvimento integral 
    do estudante e devem ser trabalhadas em todas as etapas da Educação Básica.
    
    **Competências Gerais da BNCC:**
    1. Conhecimento
    2. Pensamento científico, crítico e criativo
    3. Repertório cultural
    4. Comunicação
    5. Cultura digital
    6. Trabalho e projeto de vida
    7. Argumentação
    8. Autoconhecimento e autocuidado
    9. Empatia e cooperação
    10. Responsabilidade e cidadania
    """
)
async def get_competencias_gerais(
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get all general competencies"""
    
    competencias = await bncc_service.get_competencias_gerais()
    
    return competencias


@router.get(
    "/gerais/{numero}",
    response_model=CompetenciaGeral,
    summary="Buscar competência geral por número",
    description="""
    Retorna uma competência geral específica pelo seu número (1-10).
    
    **Exemplos:**
    - `/competencias/gerais/1` - Competência sobre Conhecimento
    - `/competencias/gerais/4` - Competência sobre Comunicação
    - `/competencias/gerais/10` - Competência sobre Responsabilidade e cidadania
    """
)
async def get_competencia_geral_by_numero(
    numero: int = Query(..., ge=1, le=10, description="Número da competência geral (1-10)"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get a specific general competency by its number"""
    
    competencia = await bncc_service.get_competencia_geral_by_numero(numero)
    
    if not competencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Competência geral número {numero} não encontrada"
        )
    
    return competencia


@router.get(
    "/especificas",
    response_model=List[CompetenciaEspecifica],
    summary="Listar competências específicas",
    description="""
    Retorna competências específicas com filtros opcionais.
    
    As competências específicas são definidas para cada área de conhecimento 
    e componente curricular, detalhando aspectos específicos do desenvolvimento.
    
    **Filtros disponíveis:**
    - **area**: Área de conhecimento
    - **componente**: Componente curricular
    - **etapa**: Etapa de ensino
    
    **Exemplos de uso:**
    - `/competencias/especificas?area=matematica`
    - `/competencias/especificas?componente=lingua_portuguesa&etapa=ensino_fundamental`
    """
)
async def get_competencias_especificas(
    area: Optional[AreaConhecimento] = Query(None, description="Área de conhecimento"),
    componente: Optional[ComponenteCurricular] = Query(None, description="Componente curricular"),
    etapa: Optional[EtapaEnsino] = Query(None, description="Etapa de ensino"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get specific competencies with optional filters"""
    
    competencias = await bncc_service.get_competencias_especificas(
        area=area,
        componente=componente,
        etapa=etapa
    )
    
    return competencias


@router.get(
    "/especificas/{codigo}",
    response_model=CompetenciaEspecifica,
    summary="Buscar competência específica por código",
    description="""
    Retorna uma competência específica pelo seu código único.
    
    **Exemplos de códigos válidos:**
    - EFMAT01 (Competência específica de Matemática - Ensino Fundamental)
    - EFLP01 (Competência específica de Língua Portuguesa - Ensino Fundamental)
    - EMMAT01 (Competência específica de Matemática - Ensino Médio)
    """
)
async def get_competencia_especifica_by_codigo(
    codigo: str,
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get a specific competency by its codigo"""
    
    competencia = await bncc_service.get_competencia_especifica_by_codigo(codigo)
    
    if not competencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Competência específica com código '{codigo}' não encontrada"
        )
    
    return competencia


@router.get(
    "/areas/{area_conhecimento}",
    response_model=List[CompetenciaEspecifica],
    summary="Buscar competências por área de conhecimento",
    description="""
    Retorna todas as competências específicas de uma área de conhecimento.
    
    **Áreas disponíveis:**
    - linguagens
    - matematica
    - ciencias_natureza
    - ciencias_humanas
    - ensino_religioso
    """
)
async def get_competencias_by_area(
    area_conhecimento: AreaConhecimento,
    etapa: Optional[EtapaEnsino] = Query(None, description="Filtrar por etapa"),
    componente: Optional[ComponenteCurricular] = Query(None, description="Filtrar por componente"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get competencies by knowledge area"""
    
    competencias = await bncc_service.get_competencias_especificas(
        area=area_conhecimento,
        etapa=etapa,
        componente=componente
    )
    
    return competencias


@router.get(
    "/componentes/{componente}",
    response_model=List[CompetenciaEspecifica],
    summary="Buscar competências por componente curricular",
    description="""
    Retorna todas as competências específicas de um componente curricular.
    
    **Componentes disponíveis:**
    - lingua_portuguesa
    - matematica
    - ciencias
    - geografia
    - historia
    - arte
    - educacao_fisica
    - lingua_inglesa
    - ensino_religioso
    """
)
async def get_competencias_by_componente(
    componente: ComponenteCurricular,
    etapa: Optional[EtapaEnsino] = Query(None, description="Filtrar por etapa"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get competencies by curricular component"""
    
    competencias = await bncc_service.get_competencias_especificas(
        componente=componente,
        etapa=etapa
    )
    
    return competencias


@router.get(
    "/etapas/{etapa}",
    response_model=List[CompetenciaEspecifica],
    summary="Buscar competências por etapa de ensino",
    description="""
    Retorna todas as competências específicas de uma etapa de ensino.
    
    **Etapas disponíveis:**
    - educacao_infantil
    - ensino_fundamental
    - ensino_medio
    """
)
async def get_competencias_by_etapa(
    etapa: EtapaEnsino,
    area: Optional[AreaConhecimento] = Query(None, description="Filtrar por área"),
    componente: Optional[ComponenteCurricular] = Query(None, description="Filtrar por componente"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get competencies by education stage"""
    
    competencias = await bncc_service.get_competencias_especificas(
        etapa=etapa,
        area=area,
        componente=componente
    )
    
    return competencias
