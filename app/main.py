"""
BNCC API — aplicação FastAPI.

Monta a API REST versionada (/api/v1), as páginas server-rendered (landing +
portal + docs) e a documentação OpenAPI. Registra handlers de erro globais e
faz fail-fast de configuração no startup (a validação ocorre na importação de
`settings`, Princípio V / FR-023).
"""

import functools
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.openapi import build_public_openapi
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.web.openapi_archive import router as openapi_archive_router
from app.web.router import web_router
from app.web.staticfiles import CachedStaticFiles

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
    version="1.3.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

_FAVICON = "/static/logo-icon.svg"

# --------------------------------------------------------------------------- #
# OpenAPI enriquecido (Princípio I — o contrato é a fonte da verdade da doc).  #
# A construção do schema vive em `app/api/openapi.py`, reutilizada pela        #
# documentação por versão (`/docs/{slug}`, `/api/{slug}/openapi.json`) e pelo  #
# congelamento de snapshots por release. `app.openapi()` mantém a saída do     #
# contrato v1 intacta (o snapshot de contrato não muda).                       #
# --------------------------------------------------------------------------- #
app.openapi = functools.partial(build_public_openapi, app)  # type: ignore[method-assign]


# --------------------------------------------------------------------------- #
# Referência interativa (Scalar) — servida por `app/web/docs.py` em `/docs`.   #
# ReDoc é mantido como fallback leve gerado pelo próprio FastAPI.              #
# --------------------------------------------------------------------------- #
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

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)


# Content-Security-Policy (Princípio V — defesa em profundidade). Deliberadamente
# permissiva o bastante para não quebrar a referência Scalar (/docs), que é um
# bundle de terceiros com scripts/estilos inline e `eval`, nem as páginas SSR
# (landing/portal) que usam scripts/estilos inline. Ainda assim bloqueia a classe
# de ataque mais comum: injeção de `<script src=host-externo>` e clickjacking.
# Recursos externos referenciados nas páginas são apenas navegação (`<a href>`),
# nunca `src` — por isso `default-src 'self'` é seguro aqui.
_CSP_POLICY = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        "connect-src 'self'",
        "worker-src 'self' blob:",
    ]
)


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
                # CSP: por padrão em Report-Only (não bloqueia — só reporta), para
                # rollout sem risco de quebrar Scalar/SSR. `CSP_ENFORCE=true` passa
                # ao modo bloqueante depois de validado em navegador (ver config).
                csp_header = (
                    "Content-Security-Policy"
                    if settings.CSP_ENFORCE
                    else "Content-Security-Policy-Report-Only"
                )
                headers[csp_header] = _CSP_POLICY
                # HSTS só faz sentido quando a conexão real é HTTPS (produção atrás do LB do
                # Cloud Run).
                if settings.is_production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersMiddleware)


class UsageOutcomeMiddleware:
    """Registra o desfecho (sucesso/erro) das chamadas de API autenticadas por key.

    As dependências de rate limit já contabilizam o **total** por dia e marcam em
    ``request.state`` (via ``scope["state"]``) a key/bucket da requisição. Aqui, após
    a resposta, se o status for de erro (>= 400) incrementamos ``error_count`` da
    mesma linha diária — habilitando a taxa de sucesso do painel sem alterar o
    caminho quente das requisições bem-sucedidas. Nunca quebra a resposta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_code = {"code": 200}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if status_code["code"] < 400:
            return
        state = scope.get("state") or {}
        api_key_id = state.get("usage_api_key_id")
        bucket_name = state.get("usage_bucket")
        if not api_key_id or not bucket_name:
            return
        try:
            from app.db.base import async_session_factory
            from app.db.tables import UsageBucket
            from app.services.usage_service import record_error

            async with async_session_factory() as session:
                await record_error(session, api_key_id, UsageBucket(bucket_name))
        except Exception:  # nunca deixa a contabilização derrubar a resposta
            logger.debug("Falha ao registrar desfecho de erro de uso", exc_info=True)


app.add_middleware(UsageOutcomeMiddleware)


app.include_router(api_router, prefix="/api/v1")
# Infra de documentação versionada (/api/versions, /api/{slug}/openapi.json,
# /api/{slug}/releases/{release}/openapi.json). `/api/v1/openapi.json` continua
# sendo servido pela rota nativa do FastAPI (registrada antes deste include).
app.include_router(openapi_archive_router)
app.include_router(web_router)

_static_dir = Path(__file__).parent / "web" / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", CachedStaticFiles(directory=str(_static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
