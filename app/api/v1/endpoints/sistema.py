"""
System endpoints for monitoring and administration
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
import logging

from app.core.config import settings
from app.services.bncc_service import get_bncc_service, BNCCDataService
from app.services.vector_store import VectorStoreService
from app.core.deps import get_vector_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/info",
    summary="Informações do sistema",
    description="""
    Retorna informações gerais sobre a API BNCC.
    
    **Informações incluídas:**
    - Versão da API
    - Ambiente de execução
    - Configurações principais
    - Status dos serviços
    """
)
async def get_system_info():
    """Get system information"""
    
    return {
        "name": "BNCC API",
        "version": "1.0.0",
        "description": "API RESTful inteligente para a Base Nacional Comum Curricular",
        "environment": settings.ENVIRONMENT,
        "features": [
            "Busca de habilidades e competências",
            "Filtros avançados",
            "Busca semântica com IA",
            "Documentação interativa",
            "Suporte ao protocolo MCP"
        ],
        "endpoints": {
            "documentation": "/docs",
            "redoc": "/redoc",
            "openapi": "/api/v1/openapi.json"
        }
    }


@router.get(
    "/stats",
    summary="Estatísticas dos dados",
    description="""
    Retorna estatísticas completas sobre os dados da BNCC carregados no sistema.
    
    **Estatísticas incluídas:**
    - Total de habilidades por etapa
    - Distribuição por área de conhecimento
    - Distribuição por componente curricular
    - Total de competências gerais e específicas
    """
)
async def get_data_stats(
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Get BNCC data statistics"""
    
    stats = await bncc_service.get_statistics()
    return stats


@router.get(
    "/health",
    summary="Health check detalhado",
    description="""
    Verifica o status de saúde de todos os componentes do sistema.
    
    **Componentes verificados:**
    - Serviço de dados BNCC
    - Banco de dados vetorial (ChromaDB)
    - Modelo de embeddings
    - Configurações principais
    """
)
async def detailed_health_check(
    bncc_service: BNCCDataService = Depends(get_bncc_service),
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Detailed health check of all system components"""
    
    health_status = {
        "status": "healthy",
        "timestamp": "",
        "components": {}
    }
    
    try:
        # Check BNCC data service
        bncc_stats = await bncc_service.get_statistics()
        health_status["components"]["bncc_data"] = {
            "status": "healthy" if bncc_stats.get("total_habilidades", 0) > 0 else "warning",
            "total_habilidades": bncc_stats.get("total_habilidades", 0),
            "total_competencias": bncc_stats.get("total_competencias_gerais", 0) + bncc_stats.get("total_competencias_especificas", 0)
        }
        
        # Check vector store
        vector_stats = await vector_service.get_collection_stats()
        health_status["components"]["vector_store"] = {
            "status": vector_stats.get("status", "unknown"),
            "total_documents": vector_stats.get("total_documents", 0),
            "embedding_model": vector_stats.get("embedding_model", "unknown")
        }
        
        # Check configuration
        health_status["components"]["configuration"] = {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "data_path_exists": settings.BNCC_DATA_PATH != "",
            "vector_store_configured": settings.CHROMADB_PATH != ""
        }
        
        # Overall status
        component_statuses = [comp.get("status") for comp in health_status["components"].values()]
        if "error" in component_statuses:
            health_status["status"] = "error"
        elif "warning" in component_statuses:
            health_status["status"] = "warning"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "error",
            "error": str(e),
            "components": {}
        }


@router.get(
    "/validate",
    summary="Validar integridade dos dados",
    description="""
    Executa uma validação completa da integridade dos dados da BNCC.
    
    **Validações realizadas:**
    - Estrutura dos dados JSON
    - Validação de modelos Pydantic
    - Verificação de códigos únicos
    - Consistência de referências
    - Campos obrigatórios
    
    **⚠️ Atenção:** Esta operação pode demorar alguns segundos para completar.
    """
)
async def validate_data_integrity(
    bncc_service: BNCCDataService = Depends(get_bncc_service)
):
    """Validate BNCC data integrity"""
    
    try:
        validation_report = await bncc_service.validate_data_integrity()
        return validation_report
        
    except Exception as e:
        logger.error(f"Error validating data integrity: {e}")
        return {
            "valid": False,
            "errors": [f"Validation process failed: {str(e)}"],
            "warnings": [],
            "summary": {}
        }


@router.get(
    "/config",
    summary="Configuração da aplicação",
    description="""
    Retorna as configurações não sensíveis da aplicação.
    
    **⚠️ Nota de segurança:** Chaves de API e informações sensíveis são omitidas.
    """
)
async def get_app_config():
    """Get application configuration (non-sensitive data only)"""
    
    return {
        "api": {
            "host": settings.API_HOST,
            "port": settings.API_PORT,
            "environment": settings.ENVIRONMENT
        },
        "data": {
            "bncc_data_path": settings.BNCC_DATA_PATH,
            "chromadb_path": settings.CHROMADB_PATH
        },
        "ai": {
            "embedding_model": settings.EMBEDDING_MODEL,
            "llm_model": settings.LLM_MODEL,
            "max_tokens": settings.MAX_TOKENS,
            "temperature": settings.TEMPERATURE,
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "google_ai_configured": bool(settings.GOOGLE_API_KEY)
        },
        "search": {
            "similarity_threshold": settings.SIMILARITY_THRESHOLD,
            "max_search_results": settings.MAX_SEARCH_RESULTS
        },
        "rate_limiting": {
            "requests_per_minute": settings.RATE_LIMIT_REQUESTS,
            "window_seconds": settings.RATE_LIMIT_WINDOW
        }
    }
