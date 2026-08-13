"""
Inicialização do schema (dev/testes).

Em produção, as migrações Alembic são a fonte da verdade. Este módulo vive fora
de ``app.db.base`` para quebrar o ciclo de importação base ↔ tables: ``tables``
importa ``Base`` no nível do módulo, e a criação de tabelas precisa conhecer os
dois — então quem faz a ponte é este módulo, não ``base``.
"""

from __future__ import annotations

from app.db import tables  # noqa: F401  (registra as tabelas no metadata)
from app.db.base import Base, engine


async def init_models() -> None:
    """
    Cria as tabelas a partir dos metadados (dev/testes).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
