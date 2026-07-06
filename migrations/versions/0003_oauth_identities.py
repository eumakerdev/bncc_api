"""oauth identities (login social Google/GitHub) + password_hash nullable

Contas só-social não têm senha (``password_hash`` NULL); a identidade do provedor
é vinculada 1:N em ``oauth_identities`` com unicidade (provider, provider_account_id).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Contas criadas via login social não possuem senha.
    with op.batch_alter_table("developer_accounts") as batch_op:
        batch_op.alter_column(
            "password_hash", existing_type=sa.String(length=255), nullable=True
        )

    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["developer_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_provider_account"
        ),
    )
    op.create_index(
        "ix_oauth_identities_account_id", "oauth_identities", ["account_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_identities_account_id", table_name="oauth_identities")
    op.drop_table("oauth_identities")
    with op.batch_alter_table("developer_accounts") as batch_op:
        batch_op.alter_column(
            "password_hash", existing_type=sa.String(length=255), nullable=False
        )
