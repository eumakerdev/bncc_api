"""
Servidor de estáticos com Cache-Control explícito.

O `StaticFiles` do Starlette envia ETag/Last-Modified mas nenhum Cache-Control,
então a CDN do Firebase Hosting não reaproveita os assets. O TTL é curto de
propósito: os arquivos não têm fingerprint no nome (um CSS defasado pós-deploy
se auto-cura em 1h) e a purga da CDN exige redeploy do hosting.
"""

from __future__ import annotations

from typing import Any

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class CachedStaticFiles(StaticFiles):
    """`StaticFiles` que adiciona `Cache-Control` a toda resposta de arquivo."""

    def __init__(self, *args: Any, cache_control: str = "public, max-age=3600", **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.cache_control = cache_control

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers.setdefault("Cache-Control", self.cache_control)
        return response
