"""
Camada de dados relacional (SQLAlchemy 2.0 async).

Dev: SQLite via aiosqlite. Prod: trocar DATABASE_URL para postgresql+asyncpg://...
sem mudar o código de domínio (Princípio II).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa de todas as tabelas ORM da plataforma."""


def _create_engine() -> AsyncEngine:
    connect_args: dict = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(
        settings.DATABASE_URL, echo=False, future=True, connect_args=connect_args
    )


engine: AsyncEngine = _create_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provider de sessão de banco (usado via DI em app/core/deps.py)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_models() -> None:
    """
    Cria as tabelas a partir dos metadados (dev/testes).
    Em produção, as migrações Alembic são a fonte da verdade.
    """
    # Importa as tabelas para registrá-las no metadata.
    from app.db import tables  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
