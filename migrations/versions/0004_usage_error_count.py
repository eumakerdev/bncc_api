"""usage_records: coluna error_count (chamadas com desfecho de erro por dia)

Aditivo: ``count`` segue sendo o total de chamadas autorizadas do dia e
``error_count`` passa a registrar o subconjunto que terminou em erro (>= 400).
Taxa de sucesso do painel = (count - error_count) / count. Não altera a
UniqueConstraint existente (por isso não exige batch mode para recriá-la).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage_records",
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Remove o server_default depois do backfill: o default de aplicação (0) passa
    # a valer para novas linhas, mantendo o schema alinhado ao ORM.
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.alter_column("error_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.drop_column("error_count")
