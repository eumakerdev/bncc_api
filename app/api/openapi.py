"""
Construção do contrato OpenAPI — enriquecido e versionado (Princípio I).

O mesmo contrato que o FastAPI gera a partir do código vira, aqui, uma referência
de nível profissional: ``info.description`` em markdown, ``tags`` ordenadas e com
descrição, ``servers`` para o "Try it" — **sem** manutenção manual de endpoints
(que divergiria do código).

Este módulo centraliza três responsabilidades:

* :func:`build_public_openapi` — o schema enriquecido de ``/api/v1`` (o que
  ``app.openapi()`` devolve; mantém a saída atual, para não mexer no snapshot de
  contrato nem no ``/api/v1/openapi.json``).
* :func:`openapi_for_version` — o schema vivo de *qualquer* versão registrada,
  filtrado ao seu prefixo — a base de ``/docs/{slug}`` e do seletor de versão.
* :func:`release_manifest` / :func:`frozen_openapi` — leitura dos snapshots por
  release congelados por ``scripts/freeze_openapi.py`` em ``docs/openapi/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api import versions as vreg
from app.core.config import settings

# Raiz do repositório: app/api/openapi.py -> parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_OPENAPI_DIR = _REPO_ROOT / "docs" / "openapi"
"""Diretório versionado dos snapshots de OpenAPI por release (``{slug}/{release}.json``)."""


# --------------------------------------------------------------------------- #
# Conteúdo editorial do contrato (markdown/tags) — reutilizado por todas as    #
# versões enquanto o texto valer para elas.                                    #
# --------------------------------------------------------------------------- #
PUBLIC_DESCRIPTION = """
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
uma nova versão de caminho (`/api/v2`), nunca dentro da versão atual. A
documentação de cada versão fica em **[/docs/v1](/docs/v1)** (e o histórico de
releases é navegável pelo seletor de versão da referência).

> Guia de início rápido, exemplos e receitas: **[/guia](/guia)**.
""".strip()

PUBLIC_TAGS: list[dict[str, str]] = [
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


def public_servers() -> list[dict[str, str]]:
    """Servidores para o 'Try it' e exemplos, derivados do ambiente configurado."""
    from urllib.parse import urlsplit

    parts = urlsplit(settings.EMAIL_VERIFICATION_BASE_URL)
    servers: list[dict[str, str]] = []
    if parts.scheme and parts.netloc:
        origin = f"{parts.scheme}://{parts.netloc}"
        label = "Produção" if settings.is_production else "Ambiente atual"
        servers.append({"url": origin, "description": label})
    if not any(s["url"].startswith("http://localhost") for s in servers):
        servers.append({"url": "http://localhost:8000", "description": "Desenvolvimento local"})
    return servers


def _decorate_info(schema: dict[str, Any]) -> None:
    """Aplica contato/licença/logo ao ``info`` do schema (comum a todas as versões)."""
    info = schema.setdefault("info", {})
    info["contact"] = {
        "name": "BNCC API",
        "url": "https://github.com/eumakerdev/bncc_api",
    }
    info["license"] = {
        "name": "MIT",
        "url": "https://github.com/eumakerdev/bncc_api/blob/main/LICENSE",
    }
    info["x-logo"] = {"url": "/static/logo.svg", "altText": "BNCC API"}


_HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})

_VALIDATION_REF = "#/components/schemas/ValidationErrorResponse"
_VALIDATION_DESCRIPTION = "Requisição inválida — parâmetros ou corpo rejeitados na validação."


def _align_validation_responses(schema: dict[str, Any]) -> None:
    """Documenta o ``400`` que a API realmente devolve na validação (Princípio I).

    O FastAPI injeta automaticamente um ``422`` em toda operação com parâmetros ou
    corpo, mas ``app/core/errors.py::validation_exception_handler`` converte **toda**
    ``RequestValidationError`` em ``400``. O ``422`` documentado era inalcançável — um
    cliente gerado a partir do schema caía no ramo genérico de erro. Alinhamos a
    documentação ao comportamento (e não o contrário: mudar o handler para 422
    quebraria quem já trata 400, vedado pelo Princípio I dentro da v1).

    ``HTTPValidationError``/``ValidationError`` continuam em ``components.schemas``
    mesmo ficando órfãos: eram alcançáveis pelo contrato publicado e removê-los seria
    lido como quebra por ``tests/contract/test_openapi_contract.py``.
    """
    for operations in schema.get("paths", {}).values():
        if not isinstance(operations, dict):
            continue
        for method, operation in operations.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict) or "422" not in responses:
                continue
            responses.pop("422")
            # Um 400 já declarado no roteador (ex.: código de habilidade malformado)
            # mantém sua descrição; só o schema é ampliado para o de validação.
            existing = responses.get("400")
            description = (
                existing.get("description", _VALIDATION_DESCRIPTION)
                if isinstance(existing, dict)
                else _VALIDATION_DESCRIPTION
            )
            responses["400"] = {
                "description": description,
                "content": {"application/json": {"schema": {"$ref": _VALIDATION_REF}}},
            }


def _postprocess(schema: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Enriquecimento comum a toda versão: ``info``, recorte de superfície e erros."""
    _decorate_info(schema)
    # Mantém no contrato apenas a superfície pública da versão (fora dela ficam as
    # rotas SSR do portal/landing: são páginas HTML, não contrato de terceiros).
    schema["paths"] = {p: v for p, v in schema.get("paths", {}).items() if p.startswith(prefix)}
    _align_validation_responses(schema)
    return schema


def build_public_openapi(app: FastAPI) -> dict[str, Any]:
    """OpenAPI enriquecido e restrito ao contrato público ``/api/v1``.

    Mantida byte-a-byte equivalente à versão anterior (que vivia em ``app/main.py``)
    para não perturbar o snapshot de contrato nem ``/api/v1/openapi.json``. Remove
    do schema as rotas SSR do portal (``/portal/*``): são páginas HTML, não parte do
    contrato consumido por terceiros.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=PUBLIC_DESCRIPTION,
        routes=app.routes,
        tags=PUBLIC_TAGS,
        servers=public_servers(),
    )
    _postprocess(schema, "/api/v1")

    app.openapi_schema = schema
    return schema


def openapi_for_version(app: FastAPI, slug: str) -> dict[str, Any]:
    """OpenAPI **vivo** de uma versão registrada, filtrado ao seu prefixo.

    Para a versão mais recente (hoje ``v1``) reaproveita :func:`build_public_openapi`
    — saída idêntica ao que já é servido. Para versões não-mais-recentes (quando
    existirem), constrói genericamente a partir das rotas cujo caminho começa no
    prefixo da versão, com ``servers`` apontando para esse prefixo.
    """
    version = vreg.get_version(slug)
    if version is None:
        raise KeyError(slug)

    if slug == vreg.LATEST_SLUG:
        return build_public_openapi(app)

    schema = get_openapi(
        title=version.title,
        version=version.release,
        description=PUBLIC_DESCRIPTION,
        routes=app.routes,
        tags=PUBLIC_TAGS,
        servers=[{"url": version.prefix, "description": version.title}],
    )
    return _postprocess(schema, version.prefix)


# --------------------------------------------------------------------------- #
# Snapshots por release (eixo histórico) — congelados em docs/openapi/.        #
# scripts/freeze_openapi.py escreve {slug}/{release}.json + {slug}/index.json. #
# --------------------------------------------------------------------------- #
def _version_dir(slug: str) -> Path:
    return DOCS_OPENAPI_DIR / slug


def release_manifest(slug: str) -> list[str]:
    """Releases arquivadas de uma versão (mais nova primeiro), ou ``[]`` se nenhuma.

    Lê ``docs/openapi/{slug}/index.json``. Tolerante a ausência/corrupção: nunca
    levanta — a UI simplesmente não oferece histórico quando não há arquivo.
    """
    index = _version_dir(slug) / "index.json"
    if not index.is_file():
        return []
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    releases = data.get("releases", []) if isinstance(data, dict) else []
    return [str(r) for r in releases] if isinstance(releases, list) else []


def frozen_openapi(slug: str, release: str) -> dict[str, Any] | None:
    """O OpenAPI congelado de ``{slug}@{release}``, ou ``None`` se inexistente.

    ``release`` é validado contra o manifesto para evitar path traversal — só
    releases explicitamente arquivadas são servidas.
    """
    if release not in release_manifest(slug):
        return None
    path = _version_dir(slug) / f"{release}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
