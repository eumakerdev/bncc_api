"""cost_records (transparência pública de custos de infraestrutura)

Custo mensal por serviço (Cloud SQL, Cloud Run, IA, outros), líquido de créditos,
em BRL. Grão ``(period_month, service)`` com unicidade para upsert idempotente pelo
ingestor de billing. Alimenta a seção "Transparência de custos" da landing.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cost_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("period_month", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "service",
            sa.Enum("banco", "servidor", "ia", "outros", name="costservice"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("period_month", "service", name="uq_cost_period_service"),
    )
    op.create_index(
        "ix_cost_records_period_month",
        "cost_records",
        ["period_month"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cost_records_period_month", table_name="cost_records")
    op.drop_table("cost_records")
