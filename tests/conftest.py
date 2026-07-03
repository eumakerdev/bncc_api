"""
Test configuration and fixtures
"""

import pytest
import asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


@pytest.fixture
def sample_habilidade():
    """Sample habilidade data for testing."""
    return {
        "codigo": "EF05MA03",
        "descricao": "Identificar e representar frações (menores e maiores que a unidade), associando-as ao resultado de uma divisão ou à ideia de parte de um todo, utilizando a reta numérica como recurso.",
        "etapa": "ensino_fundamental",
        "anos": ["5"],
        "area_conhecimento": "matematica",
        "componente": "matematica",
        "competencias_gerais": [1, 2, 4],
        "competencias_especificas": ["EFMAT01", "EFMAT02"],
        "objetos_conhecimento": ["Números racionais expressos na forma decimal e na forma de fração"]
    }


@pytest.fixture
def sample_competencia_geral():
    """Sample competência geral data for testing."""
    return {
        "numero": 1,
        "titulo": "Conhecimento",
        "descricao": "Valorizar e utilizar os conhecimentos historicamente construídos sobre o mundo físico, social, cultural e digital para entender e explicar a realidade, continuar aprendendo e colaborar para a construção de uma sociedade justa, democrática e inclusiva."
    }


@pytest.fixture
def sample_busca_request():
    """Sample busca semântica request for testing."""
    return {
        "query": "Qual habilidade de matemática do 5º ano aborda frações?",
        "max_resultados": 5,
        "incluir_contexto": True
    }
