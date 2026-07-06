"""onboarding profiles (perfil de uso pós-login do portal)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=True),
        sa.Column("org_context", sa.String(length=40), nullable=True),
        sa.Column("use_case", sa.String(length=40), nullable=True),
        sa.Column("etapas", sa.String(length=255), nullable=True),
        sa.Column("project_stage", sa.String(length=40), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["developer_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_onboarding_profiles_account_id",
        "onboarding_profiles",
        ["account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_profiles_account_id", table_name="onboarding_profiles")
    op.drop_table("onboarding_profiles")
