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
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
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
    version="1.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

_FAVICON = "/static/logo-icon.svg"

# --------------------------------------------------------------------------- #
# OpenAPI enriquecido (Princípio I — o contrato é a fonte da verdade da doc).  #
# `info.description` (markdown), `tags` ordenadas com descrição e `servers`    #
# transformam o mesmo contrato numa referência de nível profissional, sem      #
# manutenção manual de endpoints. Ver `app/web/docs.py` (Scalar) e `/guia`.    #
# --------------------------------------------------------------------------- #
_OPENAPI_DESCRIPTION = """
API pública e gratuita que expõe **toda a Base Nacional Comum Curricular (BNCC)**
do Brasil — Educação Infantil, Ensino Fundamental e Ensino Médio, incluindo o
Complemento de Computação — de forma estruturada e navegável.

## Autenticação
Os endpoints de dados exigem uma **API key** enviada no cabeçalho
`Authorization: Bearer SUA_CHAVE`. Crie uma chave gratuita no
[portal self-service](/portal/signup) após verificar seu e-mail. Requisições sem
chave válida recebem `401`.

## Limites de uso
- **Determinística** (habilidades, competências, taxonomia, sistema): `60 req/min`.
- **Busca semântica com IA**: `20 req/min` e teto de `500/dia`.

Acima do limite a API responde `429` com o cabeçalho `Retry-After`. As duas cotas
são independentes.

## Dados oficiais × derivados
Os dados determinísticos preservam fielmente a nomenclatura e a estrutura oficiais
da BNCC. Conteúdos gerados por IA (busca semântica, resumos) são **sempre marcados
como não-oficiais** e nunca substituem a fonte da verdade.

## Versionamento
Todos os endpoints ficam sob `/api/v1`. Mudanças incompatíveis são publicadas em
uma nova versão de caminho (`/api/v2`), nunca dentro da versão atual.

> Guia de início rápido, exemplos e receitas: **[/guia](/guia)**.
""".strip()

_OPENAPI_TAGS = [
    {
        "name": "Habilidades",
        "description": (
            "Habilidades da BNCC por código oficial (EI/EF/EM), com filtros, "
            "paginação e relações navegáveis."
        ),
    },
    {
        "name": "Competências",
        "description": "Competências gerais e específicas por componente e etapa.",
    },
    {
        "name": "Taxonomia",
        "description": "Vocabulário estruturante: etapas, componentes, unidades temáticas e eixos.",
    },
    {
        "name": "Busca Semântica",
        "description": (
            "Busca por significado com IA. **Conteúdo não-oficial** e rastreável "
            "por `fontes`; degrada graciosamente se a camada de IA estiver indisponível."
        ),
    },
    {
        "name": "Autenticação",
        "description": "Cadastro, login e verificação de e-mail para acesso ao portal.",
    },
    {
        "name": "API Keys",
        "description": "Emissão e revogação de chaves de API (mostradas apenas na criação).",
    },
    {"name": "Uso", "description": "Consumo e limites de uso por chave."},
    {"name": "Sistema", "description": "Saúde, versão e metadados operacionais da API."},
]


def _public_servers() -> list[dict[str, str]]:
    """Servidores para o 'Try it' e exemplos, derivados do ambiente configurado."""
    parts = urlsplit(settings.EMAIL_VERIFICATION_BASE_URL)
    servers: list[dict[str, str]] = []
    if parts.scheme and parts.netloc:
        origin = f"{parts.scheme}://{parts.netloc}"
        label = "Produção" if settings.is_production else "Ambiente atual"
        servers.append({"url": origin, "description": label})
    if not any(s["url"].startswith("http://localhost") for s in servers):
        servers.append({"url": "http://localhost:8000", "description": "Desenvolvimento local"})
    return servers


def custom_openapi() -> dict:
    """OpenAPI enriquecido e restrito ao contrato público (`/api/v1`).

    Remove as rotas SSR do portal (`/portal/*`) do schema: elas são páginas HTML,
    não parte do contrato de API consumido por terceiros. O teste de contrato
    (`tests/contract/test_openapi_contract.py`) já ignora `/portal`.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=_OPENAPI_DESCRIPTION,
        routes=app.routes,
        tags=_OPENAPI_TAGS,
        servers=_public_servers(),
    )
    schema["info"]["contact"] = {
        "name": "BNCC API",
        "url": "https://github.com/eumakerdev/bncc_api",
    }
    schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://github.com/eumakerdev/bncc_api/blob/main/LICENSE",
    }
    schema["info"]["x-logo"] = {"url": "/static/logo.svg", "altText": "BNCC API"}

    # Mantém no contrato apenas a superfície pública da API.
    schema["paths"] = {p: v for p, v in schema.get("paths", {}).items() if p.startswith("/api/v1")}

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]


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
