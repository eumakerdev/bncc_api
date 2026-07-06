"""
BNCC API — aplicação FastAPI.

Monta a API REST versionada (/api/v1), as páginas server-rendered (landing +
portal + docs) e a documentação OpenAPI. Registra handlers de erro globais e
faz fail-fast de configuração no startup (a validação ocorre na importação de
`settings`, Princípio V / FR-023).
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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

    if settings.is_production and settings.EMAIL_BACKEND.strip().lower() == "console":
        logger.warning(
            "EMAIL_BACKEND=console em produção: tokens de verificação de e-mail vão "
            "apenas para os logs, não para a caixa de entrada do usuário — a "
            "verificação de e-mail não prova posse real do e-mail enquanto isso não "
            "for corrigido (SMTP/Brevo pendente)."
        )

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
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)


# Docs interativas com favicon/marca da BNCC API (Swagger UI + ReDoc).
_FAVICON = "/static/logo-icon.svg"


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():  # pragma: no cover - HTML estático do FastAPI
    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(
        openapi_url=str(app.openapi_url),
        title=f"{app.title} — Documentação",
        swagger_favicon_url=_FAVICON,
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():  # pragma: no cover - HTML estático do FastAPI
    from fastapi.openapi.docs import get_redoc_html

    return get_redoc_html(
        openapi_url=str(app.openapi_url),
        title=f"{app.title} — Referência",
        redoc_favicon_url=_FAVICON,
    )


register_error_handlers(app)

# Ordem importa: o Starlette aplica o middleware registrado por último como o mais
# externo. Registramos CORS e TrustedHost primeiro (mais internos) e os headers de
# segurança por último, para que eles cheguem em toda resposta — inclusive as
# rejeitadas por Host inválido ou CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)


class SecurityHeadersMiddleware:
    """Middleware ASGI puro (`@app.middleware("http")`/`BaseHTTPMiddleware` foram
    removidos no Starlette 1.0) que injeta headers de segurança em toda resposta HTTP."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                # HSTS só faz sentido quando a conexão real é HTTPS (produção atrás do LB do
                # Cloud Run).
                if settings.is_production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersMiddleware)


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
