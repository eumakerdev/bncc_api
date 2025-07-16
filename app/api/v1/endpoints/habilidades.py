"""
Endpoints for habilidades (skills) from BNCC
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends

from app.models.bncc import (
    Habilidade, HabilidadeFiltros, PaginatedResponse, 
    EtapaEnsino, AreaConhecimento, ComponenteCurricular
)
from app.services.bncc_service import get_bncc_service, BNCCDataService

router = APIRouter()


@router.get(
    "/{codigo_habilidade}",
    response_model=Habilidade,
    summary="Buscar habilidade por código",
    description="""
    Retorna os detalhes completos de uma habilidade específica da BNCC.
    
    **Exemplos de códigos válidos:**
    - EF67EF01 (Educação Física, 6º/7º ano)
    - EF05MA03 (Matemática, 5º ano)
    - EI03EO04 (Educação Infantil)
    
    **Formato do código:**
    - EF: Ensino Fundamental
    - EI: Educação Infantil
    - EM: Ensino Médio
    """
)
async def get_habilidade_by_codigo(
    codigo_habilidade: str,
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get a specific habilidade by its codigo"""
    
    habilidade = await bncc_service.get_habilidade_by_codigo(codigo_habilidade)
    
    if not habilidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habilidade com código '{codigo_habilidade}' não encontrada"
        )
    
    return habilidade


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="Buscar habilidades com filtros",
    description="""
    Busca habilidades da BNCC com filtros opcionais para refinar os resultados.
    
    **Filtros disponíveis:**
    - **etapa**: Etapa de ensino (educacao_infantil, ensino_fundamental, ensino_medio)
    - **ano**: Ano escolar específico (ex: "5", "6", "7")
    - **area_conhecimento**: Área do conhecimento
    - **componente**: Componente curricular específico
    - **competencia_geral**: Número da competência geral (1-10)
    
    **Paginação:**
    - **page**: Página atual (padrão: 1)
    - **size**: Itens por página (padrão: 20, máximo: 100)
    
    **Exemplos de uso:**
    - `/habilidades/?etapa=ensino_fundamental&ano=5&componente=matematica`
    - `/habilidades/?area_conhecimento=linguagens&competencia_geral=4`
    """
)
async def search_habilidades(
    etapa: Optional[EtapaEnsino] = Query(None, description="Etapa de ensino"),
    ano: Optional[str] = Query(None, description="Ano escolar"),
    area_conhecimento: Optional[AreaConhecimento] = Query(None, description="Área de conhecimento"),
    componente: Optional[ComponenteCurricular] = Query(None, description="Componente curricular"),
    competencia_geral: Optional[int] = Query(None, ge=1, le=10, description="Competência geral (1-10)"),
    page: int = Query(1, ge=1, description="Página atual"),
    size: int = Query(20, ge=1, le=100, description="Itens por página"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Search habilidades with filters and pagination"""
    
    # Create filters object
    filtros = HabilidadeFiltros(
        etapa=etapa,
        ano=ano,
        area_conhecimento=area_conhecimento,
        componente=componente,
        competencia_geral=competencia_geral
    )
    
    # Calculate pagination
    skip = (page - 1) * size
    
    # Get results and total count
    habilidades = await bncc_service.search_habilidades(filtros, skip=skip, limit=size)
    total = await bncc_service.count_habilidades(filtros)
    
    # Calculate total pages
    pages = (total + size - 1) // size if total > 0 else 0
    
    return PaginatedResponse(
        items=habilidades,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get(
    "/areas/{area_conhecimento}",
    response_model=List[Habilidade],
    summary="Buscar habilidades por área de conhecimento",
    description="""
    Retorna todas as habilidades de uma área específica de conhecimento.
    
    **Áreas disponíveis:**
    - linguagens
    - matematica
    - ciencias_natureza
    - ciencias_humanas
    - ensino_religioso
    """
)
async def get_habilidades_by_area(
    area_conhecimento: AreaConhecimento,
    etapa: Optional[EtapaEnsino] = Query(None, description="Filtrar por etapa"),
    ano: Optional[str] = Query(None, description="Filtrar por ano"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de resultados"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get habilidades by knowledge area"""
    
    filtros = HabilidadeFiltros(
        area_conhecimento=area_conhecimento,
        etapa=etapa,
        ano=ano
    )
    
    habilidades = await bncc_service.search_habilidades(filtros, limit=limit)
    
    return habilidades


@router.get(
    "/componentes/{componente}",
    response_model=List[Habilidade],
    summary="Buscar habilidades por componente curricular",
    description="""
    Retorna todas as habilidades de um componente curricular específico.
    
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
async def get_habilidades_by_componente(
    componente: ComponenteCurricular,
    etapa: Optional[EtapaEnsino] = Query(None, description="Filtrar por etapa"),
    ano: Optional[str] = Query(None, description="Filtrar por ano"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de resultados"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get habilidades by curricular component"""
    
    filtros = HabilidadeFiltros(
        componente=componente,
        etapa=etapa,
        ano=ano
    )
    
    habilidades = await bncc_service.search_habilidades(filtros, limit=limit)
    
    return habilidades


@router.get(
    "/etapas/{etapa}/anos/{ano}",
    response_model=List[Habilidade],
    summary="Buscar habilidades por etapa e ano",
    description="""
    Retorna todas as habilidades de uma etapa e ano específicos.
    
    **Exemplos:**
    - `/habilidades/etapas/ensino_fundamental/anos/5`
    - `/habilidades/etapas/educacao_infantil/anos/3`
    """
)
async def get_habilidades_by_etapa_ano(
    etapa: EtapaEnsino,
    ano: str,
    area_conhecimento: Optional[AreaConhecimento] = Query(None, description="Filtrar por área"),
    componente: Optional[ComponenteCurricular] = Query(None, description="Filtrar por componente"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de resultados"),
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get habilidades by education stage and year"""
    
    filtros = HabilidadeFiltros(
        etapa=etapa,
        ano=ano,
        area_conhecimento=area_conhecimento,
        componente=componente
    )
    
    habilidades = await bncc_service.search_habilidades(filtros, limit=limit)
    
    return habilidades
