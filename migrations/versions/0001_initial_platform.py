"""initial platform schema (contas/keys/uso/tokens)

Revision ID: 0001
Revises:
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "developer_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_developer_accounts_email", "developer_accounts", ["email"], unique=True)

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["developer_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_email_verification_tokens_account_id",
        "email_verification_tokens",
        ["account_id"],
    )
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "revoked", name="apikeystatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["developer_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_api_keys_account_id", "api_keys", ["account_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("api_key_id", sa.String(length=36), nullable=False),
        sa.Column("bucket", sa.Enum("deterministic", "ai", name="usagebucket"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("api_key_id", "bucket", "window_start", name="uq_usage_window"),
    )
    op.create_index("ix_usage_records_api_key_id", "usage_records", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("api_keys")
    op.drop_table("email_verification_tokens")
    op.drop_index("ix_developer_accounts_email", table_name="developer_accounts")
    op.drop_table("developer_accounts")
