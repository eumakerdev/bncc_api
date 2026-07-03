"""
Smoke de performance dos endpoints determinísticos (T078 / SC-005).

Assere p95 < 300 ms sob carga nominal local. Mede o custo de servir o snapshot
(get-por-código, listagem paginada) com a autenticação sobreposta por fixture.
É um smoke determinístico — não substitui teste de carga em produção.
"""

import statistics
import sys
import time

import pytest

# Limiar da Constituição / SC-005.
P95_BUDGET_SECONDS = 0.300
_ITERATIONS = 40

# Sob instrumentação (coverage/debugger) a latência medida não representa a real
# — o tracing infla o tempo por requisição. Pular a asserção de p95 nesse caso.
_TRACING = sys.gettrace() is not None
_skip_if_traced = pytest.mark.skipif(
    _TRACING, reason="Medição de latência inválida sob coverage/tracing (SC-005)"
)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    k = max(int(round((pct / 100.0) * len(ordered) + 0.5)) - 1, 0)
    return ordered[min(k, len(ordered) - 1)]


def _measure(client, method) -> list[float]:
    # warm-up (carrega snapshot, compila rotas)
    method(client)
    samples = []
    for _ in range(_ITERATIONS):
        start = time.perf_counter()
        resp = method(client)
        samples.append(time.perf_counter() - start)
        assert resp.status_code == 200
    return samples


@_skip_if_traced
@pytest.mark.usefixtures("override_api_key_auth")
def test_p95_list_habilidades_under_budget(client):
    samples = _measure(client, lambda c: c.get("/api/v1/habilidades?size=20"))
    p95 = _percentile(samples, 95)
    assert p95 < P95_BUDGET_SECONDS, (
        f"p95={p95 * 1000:.1f}ms excede o orçamento de {P95_BUDGET_SECONDS * 1000:.0f}ms "
        f"(mediana={statistics.median(samples) * 1000:.1f}ms)"
    )


@_skip_if_traced
@pytest.mark.usefixtures("override_api_key_auth")
def test_p95_versao_dados_under_budget(client):
    samples = _measure(client, lambda c: c.get("/api/v1/sistema/versao-dados"))
    p95 = _percentile(samples, 95)
    assert p95 < P95_BUDGET_SECONDS, f"p95={p95 * 1000:.1f}ms excede o orçamento"
