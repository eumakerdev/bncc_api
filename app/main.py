"""
BNCC API - Main FastAPI application
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.services.vector_store import VectorStoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Initialize services on startup and cleanup on shutdown.
    """
    logger.info("Starting BNCC API...")
    
    # Initialize vector store service
    try:
        vector_service = VectorStoreService()
        await vector_service.initialize()
        app.state.vector_service = vector_service
        logger.info("Vector store service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize vector store service: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down BNCC API...")
    if hasattr(app.state, 'vector_service'):
        await app.state.vector_service.cleanup()


# Create FastAPI application
app = FastAPI(
    title="BNCC API",
    description="""
    **API RESTful inteligente para a Base Nacional Comum Curricular (BNCC) do Brasil**
    
    Esta API oferece:
    
    - 📚 **Dados Estruturados**: Acesso completo às habilidades e competências da BNCC
    - 🔍 **Busca Semântica**: Pesquise usando linguagem natural
    - 🤖 **IA Integrada**: Conversas inteligentes sobre o currículo
    - 🚀 **Alta Performance**: Resposta rápida e escalável
    - 📖 **Bem Documentada**: Documentação interativa completa
    
    ## Como usar
    
    1. **Explorar habilidades**: Use `/api/v1/habilidades/` para buscar por código ou filtros
    2. **Buscar competências**: Acesse `/api/v1/competencias/` para competências gerais e específicas
    3. **Busca inteligente**: Use `/api/v1/busca-semantica` para perguntas em linguagem natural
    
    ## Suporte
    
    - 📧 GitHub Issues para reportar bugs
    - 📝 Documentação completa no repositório
    - 🔗 Exemplos de uso em curl, Python, JavaScript
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to documentation"""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
