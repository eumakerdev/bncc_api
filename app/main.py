"""
BNCC API — aplicação FastAPI.

Monta a API REST versionada (/api/v1), as páginas server-rendered (landing +
portal + docs) e a documentação OpenAPI. Registra handlers de erro globais e
faz fail-fast de configuração no startup (a validação ocorre na importação de
`settings`, Princípio V / FR-023).
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.web.router import web_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bncc")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Iniciando BNCC API (env=%s)...", settings.ENVIRONMENT)

    # Banco da plataforma: em dev criamos as tabelas; em prod, Alembic é a verdade.
    try:
        from app.db.base import init_models

        await init_models()
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("Falha ao inicializar o banco da plataforma: %s", e)

    # Camada de IA (opcional; degrada graciosamente — Princípio VII).
    try:
        from app.services.vector_store import VectorStoreService

        vector_service = VectorStoreService()
        await vector_service.initialize()
        app.state.vector_service = vector_service
        logger.info("Vector store inicializado.")
    except Exception as e:
        logger.warning("Camada de IA indisponível no startup (degrada): %s", e)

    yield

    if hasattr(app.state, "vector_service"):
        try:
            await app.state.vector_service.cleanup()
        except Exception:  # pragma: no cover
            pass


app = FastAPI(
    title="BNCC API",
    description=(
        "API pública que expõe toda a Base Nacional Comum Curricular (BNCC) do Brasil: "
        "dados determinísticos das três etapas, acesso self-service por API keys, "
        "documentação automática e busca semântica com IA (não-oficial)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(web_router)

_static_dir = Path(__file__).parent / "web" / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
