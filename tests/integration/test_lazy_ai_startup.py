"""
Regressao de CUSTO: a camada de IA NAO pode ser carregada no startup.

Carregar torch/SentenceTransformer no lifespan custava ~70s de cold start e
~1,2 GiB residentes, o que obrigava `min-instances=1` no Cloud Run — 72% da
fatura mensal para servir ~100 requisicoes/dia. Depois da correcao o modelo sobe
apenas na primeira busca semantica (`vector_store.get_vector_service`).

Isso e frouxo de perceber quando regride: nada quebra, o servico so volta a ficar
lento para subir e caro para manter. Por isso o teste principal roda em um
**subprocesso limpo** — dentro da suite, qualquer outro teste pode ja ter
importado torch e mascarar a regressao.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest
from app.services import vector_store


@pytest.fixture(autouse=True)
def singleton_limpo():
    """
    Zera o singleton da IA antes de cada teste e restaura depois.

    Estes testes afirmam "nada carregou o modelo", o que so e observavel a partir
    de um estado limpo — outro teste da suite (busca semantica) pode ter carregado
    antes. A restauracao no teardown evita que a proxima suite pague os ~15s de
    recarga do modelo.
    """
    anterior = vector_store.peek_vector_service()
    vector_store.reset_vector_service()
    try:
        yield
    finally:
        vector_store.reset_vector_service()
        vector_store._vector_service = anterior


def test_startup_nao_importa_stack_de_ml():
    """Importar e subir a app nao pode puxar torch/sentence-transformers/chromadb."""
    script = textwrap.dedent("""
        import json, sys
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app):           # executa o lifespan completo
            pass

        print(json.dumps([m for m in ("torch", "sentence_transformers", "chromadb")
                          if m in sys.modules]))
        """)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"subprocesso falhou:\n{proc.stderr}"

    carregados = __import__("json").loads(proc.stdout.strip().splitlines()[-1])
    assert carregados == [], (
        "O startup carregou a stack de ML: "
        f"{carregados}. Isso restaura ~70s de cold start e forca min-instances=1 "
        "no Cloud Run (~R$300/mes). A IA deve subir sob demanda em "
        "vector_store.get_vector_service()."
    )


def test_lifespan_nao_instancia_o_vector_service():
    """Rodar o lifespan inteiro nao pode criar/instanciar o servico de IA."""
    from app.main import app
    from fastapi.testclient import TestClient

    # Client proprio (e nao a fixture `client`): o lifespan precisa rodar DEPOIS
    # do reset feito pela fixture acima, senao o teste nao prova nada.
    with TestClient(app):
        assert vector_store.peek_vector_service() is None
    assert vector_store.peek_vector_service() is None


def test_readiness_nao_dispara_a_carga_do_modelo(client):
    """
    O readiness reporta o estado da IA sem carrega-la.

    Sem isso, um health check periodico manteria o modelo residente de graca —
    exatamente o custo que a carga preguicosa elimina.
    """
    from app.services.vector_store import peek_vector_service

    resp = client.get("/api/v1/sistema/readiness")
    assert resp.status_code == 200, resp.text

    # O contrato so admite estes dois valores (Principio I).
    assert resp.json()["components"]["ai"] in {"available", "unavailable"}
    assert peek_vector_service() is None, "readiness carregou o modelo"


def test_endpoints_deterministicos_nao_carregam_a_ia(client, override_api_key_auth):
    """O nucleo deterministico nao paga nada pela camada de IA (Principio VII)."""
    from app.services.vector_store import peek_vector_service

    for path in ("/api/v1/sistema/health", "/api/v1/sistema/versao-dados"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path}: {resp.text}"

    assert peek_vector_service() is None


def test_get_vector_service_e_idempotente():
    """Chamadas concorrentes carregam o modelo UMA vez (nao N x 1,2 GiB)."""
    import asyncio

    from app.services import vector_store

    vector_store.reset_vector_service()
    chamadas = {"n": 0}

    async def fake_initialize(self):
        chamadas["n"] += 1
        await asyncio.sleep(0.01)  # janela para a corrida acontecer
        self.available = True

    original = vector_store.VectorStoreService.initialize
    vector_store.VectorStoreService.initialize = fake_initialize
    try:

        async def exercitar():
            servicos = await asyncio.gather(*(vector_store.get_vector_service() for _ in range(8)))
            # Todas as chamadas devolvem exatamente a MESMA instancia.
            assert all(s is servicos[0] for s in servicos)

        asyncio.run(exercitar())
    finally:
        vector_store.VectorStoreService.initialize = original
        vector_store.reset_vector_service()

    assert chamadas["n"] == 1, f"o modelo foi carregado {chamadas['n']}x, deveria ser 1x"
