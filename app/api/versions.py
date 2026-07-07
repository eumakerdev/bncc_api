"""
Registro central das versões da API (o eixo de versionamento do contrato).

Cada versão maior vive sob um prefixo de caminho estável (``/api/v1``, ``/api/v2``,
…). A Constituição (§I) proíbe quebra dentro de uma versão publicada; mudanças
incompatíveis nascem numa NOVA versão de caminho. Este módulo é a **fonte única da
verdade** sobre QUAIS versões existem, seu estado no ciclo de vida e a release
(campo ``version`` do app FastAPI) atualmente servida em cada uma.

Hoje só existe ``v1``. Para publicar ``v2`` no futuro:

1. Inclua o novo router com ``prefix="/api/v2"`` (ver ``app/main.py``).
2. Acrescente um ``APIVersion("v2", …)`` em :data:`API_VERSIONS`.

A documentação por versão (``/docs/{slug}``, ``/api/{slug}/openapi.json``), o
seletor de versão do Scalar e o congelamento de snapshots por release passam a
cobrir a nova versão automaticamente — nada mais a fazer aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VersionStatus = Literal["current", "deprecated", "sunset"]


@dataclass(frozen=True)
class APIVersion:
    """Metadados de uma versão maior do contrato público."""

    slug: str
    """Identificador de caminho, ex.: ``"v1"``."""

    release: str
    """Release semântica atualmente servida nesta versão (ex.: ``"1.3.0"``)."""

    status: VersionStatus
    """Estado no ciclo de vida: ``current`` | ``deprecated`` | ``sunset``."""

    title: str
    """Título exibido na referência (Scalar) e no OpenAPI da versão."""

    summary: str
    """Frase curta descrevendo a versão (seletor de versão / manifesto)."""

    @property
    def prefix(self) -> str:
        """Prefixo de caminho estável da versão (ex.: ``/api/v1``)."""
        return f"/api/{self.slug}"

    @property
    def openapi_url(self) -> str:
        """URL do OpenAPI vivo desta versão."""
        return f"{self.prefix}/openapi.json"

    @property
    def docs_url(self) -> str:
        """URL da referência interativa (Scalar) desta versão."""
        return f"/docs/{self.slug}"


# Ordem = mais nova primeiro (a UI e o manifesto preservam esta ordem).
API_VERSIONS: tuple[APIVersion, ...] = (
    APIVersion(
        slug="v1",
        release="1.3.0",
        status="current",
        title="BNCC API v1",
        summary="Primeira versão pública estável do contrato /api/v1.",
    ),
)

LATEST_SLUG: str = API_VERSIONS[0].slug
"""Slug da versão mais recente — o padrão de ``/docs`` e ``/api/.../openapi.json``."""

_BY_SLUG: dict[str, APIVersion] = {v.slug: v for v in API_VERSIONS}


def list_versions() -> tuple[APIVersion, ...]:
    """Todas as versões registradas, da mais nova para a mais antiga."""
    return API_VERSIONS


def get_version(slug: str) -> APIVersion | None:
    """A versão de ``slug``, ou ``None`` se desconhecida."""
    return _BY_SLUG.get(slug)


def is_known_version(slug: str) -> bool:
    """Se ``slug`` corresponde a uma versão registrada."""
    return slug in _BY_SLUG


def latest_version() -> APIVersion:
    """A versão mais recente (nunca vazia enquanto :data:`API_VERSIONS` existir)."""
    return _BY_SLUG[LATEST_SLUG]
