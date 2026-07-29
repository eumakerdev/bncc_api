"""
Canonicalização da `Location` dos redirects (Princípio V).

Regressão da auditoria de produção de 2026-07-29 (achado 4): qualquer redirect
gerado pelo app devolvia um `Location` absoluto montado com o `Host` **interno**
do Cloud Run::

    GET /api/v1/habilidades/  ->  307
    Location: https://bncc-api-esjlky3g3a-rj.a.run.app/api/v1/habilidades

Dois efeitos: divulga a identidade interna do serviço (§V veda vazar "detalhes de
infraestrutura") e faz um SDK com `follow_redirects` migrar para fora da CDN sem
perceber, anulando o cache que o modelo de custo pressupõe.
"""

from __future__ import annotations

import pytest
from app.core.config import settings
from app.main import _canonical_location

INTERNAL_HOST = "bncc-api-esjlky3g3a-rj.a.run.app"
PUBLIC = "https://bncc.api.br"


@pytest.fixture
def site_url(monkeypatch):
    monkeypatch.setattr(settings, "SITE_URL", PUBLIC)
    return PUBLIC


def test_trailing_slash_redirect_uses_public_host(client, site_url) -> None:
    """O redirect de barra final do Starlette sai com o host público, não o interno."""
    response = client.get(
        "/api/v1/habilidades/",
        headers={"Host": INTERNAL_HOST},
        follow_redirects=False,
    )
    assert response.status_code in (301, 302, 307, 308)
    assert response.headers["location"] == f"{PUBLIC}/api/v1/habilidades"
    assert INTERNAL_HOST not in response.headers["location"]


def test_relative_location_is_left_alone(client, site_url) -> None:
    """`Location` relativa já é imune ao host — reescrevê-la só quebraria o portal."""
    response = client.get("/portal/dashboard", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith("/portal/")


def test_no_site_url_leaves_redirects_untouched(client, monkeypatch) -> None:
    """Em dev (`SITE_URL` vazio) não há host canônico — o middleware não age."""
    monkeypatch.setattr(settings, "SITE_URL", "")
    response = client.get(
        "/api/v1/habilidades/",
        headers={"Host": INTERNAL_HOST},
        follow_redirects=False,
    )
    assert INTERNAL_HOST in response.headers["location"]


# --------------------------------------------------------------------------- #
# A regra em si — o guard de host externo é o que protege o fluxo OAuth.       #
# --------------------------------------------------------------------------- #
def test_external_redirect_is_never_rewritten(site_url) -> None:
    """A autorização OAuth aponta para o Google/GitHub e NÃO pode ser canonicalizada."""
    external = "https://accounts.google.com/o/oauth2/v2/auth?client_id=x&state=y"
    assert _canonical_location(external, INTERNAL_HOST) is None


def test_already_canonical_location_is_not_touched(site_url) -> None:
    assert _canonical_location(f"{PUBLIC}/portal", "bncc.api.br") is None


def test_query_and_fragment_are_preserved(site_url) -> None:
    rewritten = _canonical_location(
        f"https://{INTERNAL_HOST}/docs/v1?release=1.3.0#tag", INTERNAL_HOST
    )
    assert rewritten == f"{PUBLIC}/docs/v1?release=1.3.0#tag"
