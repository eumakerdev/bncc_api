"""
Regressão: CVE-2026-48710 ("BadHost") — bypass de auth via Host header malformado.

Em Starlette < 1.0.1, um header `Host` contendo `/`, `?` ou `#` fazia
`request.url.path` divergir do path realmente roteado pelo ASGI (`scope["path"]`),
permitindo que uma decisão de segurança baseada em path fosse enganada. Este
projeto corrige isso via `starlette>=1.0.1` (ver requirements.txt); os testes
abaixo provam que (a) o roteamento real da app não é afetado por esse header em
um endpoint protegido, e (b) o objeto `Request` do Starlette não reconstrói mais
um path envenenado a partir de um Host malicioso.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient as StarletteTestClient

# Host header malicioso: tenta fazer request.url.path "parecer" ser /health,
# enquanto a linha de requisição HTTP real pede outro path.
_MALICIOUS_HOST = "testserver/api/v1/sistema/health?x="


def test_protected_endpoint_ignores_path_smuggled_via_host_header(client):
    """
    `/versao-dados` exige API key (401 sem uma). Um Host header que tenta
    disfarçar o path real como `/health` (público) não deve mudar o roteamento
    nem burlar a autenticação — a rota executada continua sendo a protegida.
    """
    response = client.get(
        "/api/v1/sistema/versao-dados",
        headers={"Host": _MALICIOUS_HOST},
    )
    assert response.status_code == 401


def test_malicious_host_header_is_rejected_before_reaching_the_route():
    """
    Prova em nível de framework: o Starlette corrigido (>=1.0.1) rejeita de
    imediato (400) um Host header com caracteres inválidos (`/`, `?`, `#`) — a
    requisição nem chega a ser roteada, então `request.url.path` nunca fica
    disponível para ser lido envenenado. Antes da correção, esse mesmo header
    seria aceito e faria `request.url.path` divergir do path real roteado.
    """

    async def echo_path(request):
        return PlainTextResponse(request.url.path)

    app = Starlette(
        routes=[Route("/protegido", echo_path)],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["testserver"])],
    )

    with StarletteTestClient(app) as test_client:
        response = test_client.get("/protegido", headers={"Host": _MALICIOUS_HOST})

    assert response.status_code == 400
