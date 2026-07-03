"""
Configuração e fixtures de teste (infraestrutura compartilhada).

Define um ambiente seguro de teste (SECRET_KEY, DATABASE_URL SQLite isolado),
prepara o banco da plataforma e oferece fixtures para contas verificadas, API
keys e sobreposição da auth (US1 usa override; a auth real chega em US2).
"""

import os
import tempfile
from pathlib import Path

import pytest

# --- Ambiente de teste (definido ANTES de importar a aplicação) ---------------
# DB por PID: garante que execuções paralelas de pytest não colidam no mesmo arquivo.
_TMP_DB = Path(tempfile.gettempdir()) / f"bncc_test_{os.getpid()}.db"
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-000000")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB.as_posix()}"
os.environ.setdefault("EMAIL_BACKEND", "console")

import pytest_asyncio  # noqa: E402
from app.core.security import generate_api_key, hash_password  # noqa: E402
from app.db.base import async_session_factory, engine  # noqa: E402
from app.db.tables import ApiKey, ApiKeyStatus, DeveloperAccount  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _prepare_db():
    """Recria o schema da plataforma a cada teste (isolamento)."""
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Zera os limitadores in-process (globais de módulo) entre testes."""
    from app.core.deps import ai_limiter, deterministic_limiter

    deterministic_limiter.reset()
    ai_limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def verified_account(db_session):
    """Cria uma conta de desenvolvedor com e-mail verificado."""
    account = DeveloperAccount(
        email="dev@example.com",
        password_hash=hash_password("senha-forte-123"),
        email_verified=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def api_key(db_session, verified_account):
    """Cria uma API key ativa e devolve (full_key, ApiKey)."""
    full_key, prefix, key_hash = generate_api_key()
    key = ApiKey(
        account_id=verified_account.id,
        name="test-key",
        prefix=prefix,
        key_hash=key_hash,
        status=ApiKeyStatus.active,
    )
    db_session.add(key)
    await db_session.commit()
    await db_session.refresh(key)
    return full_key, key


@pytest.fixture
def auth_headers(api_key):
    """Header Authorization Bearer com uma API key válida."""
    full_key, _ = api_key
    return {"Authorization": f"Bearer {full_key}"}


@pytest.fixture
def override_api_key_auth():
    """
    Sobrepõe a auth por API key (US1): qualquer requisição é aceita.
    Uso: incluir a fixture; ela limpa o override ao final.
    """
    from app.core.deps import require_api_key

    class _FakeKey:
        id = "test-key-id"
        status = ApiKeyStatus.active

    app.dependency_overrides[require_api_key] = lambda: _FakeKey()
    yield
    app.dependency_overrides.pop(require_api_key, None)


# --- Amostras de dados (compat. com testes existentes) ------------------------
@pytest.fixture
def sample_habilidade():
    return {
        "codigo": "EF05MA03",
        "descricao": "Identificar e representar frações (menores e maiores que a unidade), "
        "associando-as ao resultado de uma divisão ou à ideia de parte de um todo, "
        "utilizando a reta numérica como recurso.",
        "etapa": "ensino_fundamental",
        "anos": ["5"],
        "area_conhecimento": "matematica",
        "componente": "matematica",
        "competencias_gerais": [1, 2, 4],
        "competencias_especificas": ["EFMAT01", "EFMAT02"],
        "objetos_conhecimento": ["Números racionais na forma decimal e fracionária"],
    }


@pytest.fixture
def sample_busca_request():
    return {
        "query": "Qual habilidade de matemática do 5º ano aborda frações?",
        "max_resultados": 5,
        "incluir_contexto": True,
    }
