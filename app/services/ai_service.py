"""
AI Service for LLM integration and chat functionality
"""

import logging
import time
from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.models.bncc import BuscaSemanticaRequest, BuscaSemanticaResponse, DocumentoFonte
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered chat and semantic search responses"""
    
    def __init__(self, vector_service: VectorStoreService):
        self.vector_service = vector_service
        self.llm_client = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize LLM client based on configuration"""
        try:
            if settings.OPENAI_API_KEY:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.llm_provider = "openai"
                logger.info("Initialized OpenAI client")
            elif settings.GOOGLE_API_KEY:
                import google.generativeai as genai
                genai.configure(api_key=settings.GOOGLE_API_KEY)
                self.llm_client = genai.GenerativeModel('gemini-pro')
                self.llm_provider = "google"
                logger.info("Initialized Google AI client")
            else:
                logger.warning("No LLM API key configured, using mock responses")
                self.llm_provider = "mock"
                
        except ImportError as e:
            logger.warning(f"LLM library not available: {e}, using mock responses")
            self.llm_provider = "mock"
        except Exception as e:
            logger.error(f"Error initializing LLM client: {e}")
            self.llm_provider = "mock"
    
    async def busca_semantica(self, request: BuscaSemanticaRequest) -> BuscaSemanticaResponse:
        """
        Perform semantic search with AI-generated response
        
        Args:
            request: BuscaSemanticaRequest with query and parameters
            
        Returns:
            BuscaSemanticaResponse with AI-generated answer and sources
        """
        start_time = time.time()
        
        try:
            # Step 1: Perform vector search
            fontes = await self.vector_service.search_semantic(
                query=request.query,
                max_results=request.max_resultados,
                similarity_threshold=settings.SIMILARITY_THRESHOLD
            )
            
            if not fontes:
                return BuscaSemanticaResponse(
                    resposta="Desculpe, não encontrei informações relevantes na BNCC para sua consulta. "
                             "Tente reformular sua pergunta ou usar termos mais específicos.",
                    fontes=[],
                    documentos_consultados=0,
                    tempo_processamento=time.time() - start_time
                )
            
            # Step 2: Get detailed context for top results
            contexto_documentos = []
            for fonte in fontes[:5]:  # Limit context to top 5 results
                documento = await self.vector_service.get_document_by_codigo(fonte.codigo)
                if documento:
                    contexto_documentos.append(documento)
            
            # Step 3: Generate AI response
            resposta = await self._generate_response(request.query, contexto_documentos)
            
            processing_time = time.time() - start_time
            
            return BuscaSemanticaResponse(
                resposta=resposta,
                fontes=fontes,
                documentos_consultados=len(contexto_documentos),
                tempo_processamento=round(processing_time, 2)
            )
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return BuscaSemanticaResponse(
                resposta="Ocorreu um erro interno durante a busca. Tente novamente em alguns momentos.",
                fontes=[],
                documentos_consultados=0,
                tempo_processamento=time.time() - start_time
            )
    
    async def _generate_response(self, query: str, documentos: List[Dict[str, Any]]) -> str:
        """
        Generate AI response based on query and retrieved documents
        
        Args:
            query: User's query
            documentos: Retrieved documents for context
            
        Returns:
            AI-generated response string
        """
        try:
            # Build context from documents
            contexto = self._build_context(documentos)
            
            # Create prompt
            prompt = self._create_prompt(query, contexto)
            
            # Generate response based on provider
            if self.llm_provider == "openai":
                return await self._generate_openai_response(prompt)
            elif self.llm_provider == "google":
                return await self._generate_google_response(prompt)
            else:
                return await self._generate_mock_response(query, documentos)
                
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return self._get_fallback_response(documentos)
    
    def _build_context(self, documentos: List[Dict[str, Any]]) -> str:
        """Build context string from documents"""
        contexto_parts = []
        
        for doc in documentos:
            if doc.get('codigo') and doc.get('descricao'):
                doc_text = f"**{doc['codigo']}**: {doc['descricao']}"
                
                # Add additional context based on document type
                if 'etapa' in doc:
                    doc_text += f" (Etapa: {doc['etapa'].replace('_', ' ').title()})"
                
                if 'anos' in doc and doc['anos']:
                    anos_str = ', '.join(doc['anos'])
                    doc_text += f" (Anos: {anos_str})"
                
                if 'componente' in doc:
                    doc_text += f" (Componente: {doc['componente'].replace('_', ' ').title()})"
                
                if 'objetos_conhecimento' in doc and doc['objetos_conhecimento']:
                    obj_conhecimento = ', '.join(doc['objetos_conhecimento'])
                    doc_text += f" (Objetos de conhecimento: {obj_conhecimento})"
                
                contexto_parts.append(doc_text)
        
        return '\n\n'.join(contexto_parts)
    
    def _create_prompt(self, query: str, contexto: str) -> str:
        """Create prompt for LLM"""
        return f"""Você é um assistente especializado na Base Nacional Comum Curricular (BNCC) do Brasil. 
Sua função é responder perguntas sobre habilidades e competências da BNCC de forma clara, precisa e educativa.

PERGUNTA DO USUÁRIO: {query}

CONTEXTO DA BNCC (documentos relevantes encontrados):
{contexto}

INSTRUÇÕES:
1. Responda à pergunta usando APENAS as informações fornecidas no contexto acima
2. Seja específico e mencione os códigos das habilidades/competências relevantes
3. Se a pergunta se refere a um ano/etapa específica, destaque essa informação
4. Organize a resposta de forma clara e educativa
5. Se houver múltiplas habilidades relevantes, liste-as organizadamente
6. Não invente informações que não estão no contexto fornecido
7. Use linguagem acessível para educadores e desenvolvedores

RESPOSTA:"""
    
    async def _generate_openai_response(self, prompt: str) -> str:
        """Generate response using OpenAI"""
        try:
            response = self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado na BNCC."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error with OpenAI API: {e}")
            raise
    
    async def _generate_google_response(self, prompt: str) -> str:
        """Generate response using Google AI"""
        try:
            response = self.llm_client.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': settings.MAX_TOKENS,
                    'temperature': settings.TEMPERATURE,
                }
            )
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error with Google AI API: {e}")
            raise
    
    async def _generate_mock_response(self, query: str, documentos: List[Dict[str, Any]]) -> str:
        """Generate mock response when no LLM is available"""
        if not documentos:
            return "Não foram encontrados documentos relevantes para sua consulta na BNCC."
        
        # Create a simple structured response
        response_parts = [
            f"Encontrei {len(documentos)} documento(s) relevante(s) na BNCC para sua consulta:",
            ""
        ]
        
        for i, doc in enumerate(documentos[:3], 1):  # Limit to top 3
            codigo = doc.get('codigo', 'N/A')
            descricao = doc.get('descricao', '')[:200] + "..." if len(doc.get('descricao', '')) > 200 else doc.get('descricao', '')
            
            response_parts.append(f"{i}. **{codigo}**: {descricao}")
            
            if 'etapa' in doc and 'anos' in doc:
                etapa = doc['etapa'].replace('_', ' ').title()
                anos = ', '.join(doc['anos']) if doc['anos'] else 'N/A'
                response_parts.append(f"   - Etapa: {etapa}, Anos: {anos}")
            
            response_parts.append("")
        
        response_parts.append("💡 **Nota**: Esta é uma resposta automática baseada na similaridade semântica. "
                            "Para respostas mais elaboradas, configure uma API de LLM (OpenAI ou Google AI).")
        
        return '\n'.join(response_parts)
    
    def _get_fallback_response(self, documentos: List[Dict[str, Any]]) -> str:
        """Get fallback response when AI generation fails"""
        if not documentos:
            return "Não foram encontrados documentos relevantes na BNCC para sua consulta."
        
        codigos = [doc.get('codigo', 'N/A') for doc in documentos[:3]]
        return (f"Encontrei informações relevantes na BNCC relacionadas aos códigos: {', '.join(codigos)}. "
                f"Consulte estes documentos para mais detalhes. "
                f"(Ocorreu um erro na geração de resposta detalhada)")


# Service factory
async def create_ai_service(vector_service: VectorStoreService) -> AIService:
    """Create AI service instance"""
    return AIService(vector_service)
