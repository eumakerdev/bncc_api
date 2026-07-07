"""
Superfícies de documentação (US3) — agora **versionadas** por contrato.

Duas páginas complementares, ambas alimentadas pelo **mesmo contrato OpenAPI**
(gerado no código, nunca escrito à mão que possa divergir — Princípio I):

- ``/guia``  — hub de conteúdo (início rápido, autenticação, paginação, erros,
  limites, busca semântica, versionamento) no design system compartilhado.
- ``/docs``  — referência interativa (Scalar) da versão **mais recente**
  (``versions.LATEST_SLUG``). Back-compat: continua servindo o Scalar apontado
  para ``/api/v1/openapi.json``.
- ``/docs/{slug}`` — referência interativa de uma versão específica; ``404`` se a
  versão for desconhecida. Um seletor no topo alterna entre versões vivas e, via
  parâmetro ``?release=X.Y.Z``, entre **releases históricas congeladas** dessa
  versão (o ``data-url`` do Scalar passa a apontar para o snapshot congelado).

O bundle do Scalar é **self-hosted** em ``/static/vendor/`` (sem CDN — Princípio V).
ReDoc continua disponível em ``/redoc`` como fallback leve (ver ``app/main.py``).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from app.api import versions as vreg
from app.api.openapi import release_manifest
from app.web.router import templates

router = APIRouter()


def _version_options() -> list[dict[str, object]]:
    """Lista de versões (com releases congeladas) para o seletor do topo.

    Cada item traz os metadados exibíveis (``slug``/``title``/``release``/
    ``status``), as URLs (``openapi_url``/``docs_url``) e a lista de releases
    históricas arquivadas (``releases``, mais nova primeiro; ``[]`` se nenhuma —
    outro agente gera esses snapshots em paralelo)."""
    options: list[dict[str, object]] = []
    for version in vreg.list_versions():
        options.append(
            {
                "slug": version.slug,
                "title": version.title,
                "release": version.release,
                "status": version.status,
                "openapi_url": version.openapi_url,
                "docs_url": version.docs_url,
                "releases": release_manifest(version.slug),
            }
        )
    return options


def _reference_context(slug: str, release: str | None) -> dict[str, object]:
    """Monta o contexto do template da referência para uma versão/release.

    Quando ``release`` é uma release **arquivada** da versão, o ``data_url`` aponta
    para o snapshot congelado (``/api/{slug}/releases/{release}/openapi.json``) e
    ``active_release`` marca o modo histórico; caso contrário usa o OpenAPI vivo da
    versão (``openapi_url``) — parâmetro inválido/ausente degrada para o vivo."""
    version = vreg.get_version(slug)
    if version is None:  # pragma: no cover - chamadores já validam o slug
        raise HTTPException(status_code=404, detail="Versão de API desconhecida.")

    archived = release_manifest(slug)
    active_release = release if release and release in archived else None
    if active_release is not None:
        data_url = f"{version.prefix}/releases/{active_release}/openapi.json"
    else:
        data_url = version.openapi_url

    return {
        "current": {
            "slug": version.slug,
            "title": version.title,
            "release": version.release,
            "status": version.status,
            "openapi_url": version.openapi_url,
            "docs_url": version.docs_url,
        },
        "versions": _version_options(),
        "active_release": active_release,
        "data_url": data_url,
    }


@router.get("/guia", response_class=HTMLResponse, include_in_schema=False)
async def guia(request: Request) -> Response:
    """Hub de documentação: início rápido, autenticação, limites e versionamento."""
    return templates.TemplateResponse(request, "docs.html")


@router.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def api_reference(request: Request, release: str | None = None) -> Response:
    """Referência interativa (Scalar) da versão mais recente — self-hosted."""
    context = _reference_context(vreg.LATEST_SLUG, release)
    return templates.TemplateResponse(request, "reference.html", context)


@router.get("/docs/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def api_reference_versioned(
    request: Request, slug: str, release: str | None = None
) -> Response:
    """Referência interativa de uma versão específica; ``404`` se desconhecida.

    Com ``?release=X.Y.Z`` válida, mostra a release histórica congelada dessa
    versão; parâmetro ausente/inválido cai para o OpenAPI vivo da versão."""
    if not vreg.is_known_version(slug):
        raise HTTPException(status_code=404, detail="Versão de API desconhecida.")
    context = _reference_context(slug, release)
    return templates.TemplateResponse(request, "reference.html", context)
