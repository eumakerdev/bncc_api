"""
Endpoints for semantic search functionality
"""

from fastapi import APIRouter, HTTPException, status, Depends
import logging

from app.models.bncc import BuscaSemanticaRequest, BuscaSemanticaResponse
from app.services.vector_store import VectorStoreService
from app.services.ai_service import create_ai_service
from app.core.deps import get_vector_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=BuscaSemanticaResponse,
    summary="Busca semântica inteligente",
    description="""
    Realiza uma busca semântica inteligente na BNCC usando processamento de linguagem natural.
    
    **Como funciona:**
    1. 🔍 Sua pergunta é convertida em um vetor semântico
    2. 📊 O sistema busca por similaridade nas habilidades e competências
    3. 🤖 Uma IA analisa os resultados e gera uma resposta contextualizada
    4. 📚 Você recebe a resposta com as fontes utilizadas
    
    **Exemplos de perguntas:**
    - "Quais habilidades de matemática do 5º ano abordam frações?"
    - "Competências de língua portuguesa sobre leitura no ensino fundamental"
    - "Habilidades de ciências sobre meio ambiente para anos iniciais"
    - "O que a BNCC diz sobre educação digital?"
    
    **Dicas para melhores resultados:**
    - Seja específico sobre o ano/etapa
    - Mencione o componente curricular se souber
    - Use termos educacionais conhecidos
    - Faça perguntas diretas e claras
    
    **Limitações:**
    - Máximo de 500 caracteres por pergunta
    - Resposta baseada apenas no conteúdo da BNCC
    - Resultados limitados a 20 documentos por busca
    """
)
async def busca_semantica(
    request: BuscaSemanticaRequest,
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Perform semantic search with AI-generated response"""
    
    try:
        # Create AI service
        ai_service = await create_ai_service(vector_service)
        
        # Perform semantic search
        response = await ai_service.busca_semantica(request)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno durante a busca semântica. Tente novamente."
        )


@router.get(
    "/stats",
    summary="Estatísticas da busca semântica",
    description="""
    Retorna estatísticas sobre o sistema de busca semântica.
    
    **Informações incluídas:**
    - Total de documentos indexados
    - Modelo de embedding utilizado
    - Distribuição por tipo de documento
    - Status do sistema
    """
)
async def get_search_stats(
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Get semantic search system statistics"""
    
    try:
        stats = await vector_service.get_collection_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting search stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas do sistema"
        )


@router.post(
    "/test",
    summary="Testar busca vetorial (modo debug)",
    description="""
    Endpoint para testes e debug da busca vetorial.
    
    **Apenas para desenvolvimento e debug.**
    
    Retorna resultados brutos da busca vetorial sem processamento de IA,
    mostrando scores de similaridade e metadados dos documentos encontrados.
    """
)
async def test_vector_search(
    request: BuscaSemanticaRequest,
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Test vector search functionality (debug mode)"""
    
    try:
        # Perform raw vector search
        fontes = await vector_service.search_semantic(
            query=request.query,
            max_results=request.max_resultados
        )
        
        # Return raw results for debugging
        return {
            "query": request.query,
            "total_results": len(fontes),
            "results": [
                {
                    "codigo": fonte.codigo,
                    "tipo": fonte.tipo,
                    "relevancia": fonte.relevancia,
                    "titulo": fonte.titulo
                }
                for fonte in fontes
            ],
            "embedding_model": vector_service.embedding_model.get_sentence_embedding_dimension() if hasattr(vector_service.embedding_model, 'get_sentence_embedding_dimension') else "unknown",
            "collection_size": vector_service.collection.count() if vector_service.collection else 0
        }
        
    except Exception as e:
        logger.error(f"Error in vector search test: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no teste de busca vetorial: {str(e)}"
        )
