"""
Tabelas ORM da plataforma (data-model.md §B).

developer_accounts, email_verification_tokens, api_keys, usage_records.
Segredos (password_hash, key_hash, token_hash) nunca são expostos por schema de API.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ApiKeyStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class UsageBucket(str, enum.Enum):
    deterministic = "deterministic"
    ai = "ai"


class DeveloperAccount(Base):
    __tablename__ = "developer_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # Nullable: contas criadas via login social (OAuth) não possuem senha.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    onboarding: Mapped[OnboardingProfile | None] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    oauth_identities: Mapped[list[OAuthIdentity]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class OnboardingProfile(Base):
    """
    Perfil de onboarding do portal (1:1 com a conta).

    Cada coluna de resposta guarda slugs do catálogo fixo de
    ``onboarding_service`` (multi-seleção vem separada por vírgula) — nunca
    texto livre do usuário. ``completed_at`` marca a conclusão do fluxo;
    enquanto nulo, o portal exige o preenchimento antes do dashboard.
    """

    __tablename__ = "onboarding_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), unique=True, index=True
    )
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    org_context: Mapped[str | None] = mapped_column(String(40), nullable=True)
    use_case: Mapped[str | None] = mapped_column(String(40), nullable=True)
    etapas: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    account: Mapped[DeveloperAccount] = relationship(back_populates="onboarding")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped[DeveloperAccount] = relationship(back_populates="verification_tokens")


class OAuthIdentity(Base):
    """Identidade de login social (Google/GitHub) vinculada a uma conta.

    Uma conta pode ter múltiplas identidades (um por provedor). A unicidade
    (provider, provider_account_id) impede vincular o mesmo login social a duas
    contas distintas.
    """

    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped[DeveloperAccount] = relationship(back_populates="oauth_identities")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[ApiKeyStatus] = mapped_column(
        Enum(ApiKeyStatus), default=ApiKeyStatus.active, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[DeveloperAccount] = relationship(back_populates="api_keys")
    usage_records: Mapped[list[UsageRecord]] = relationship(
        back_populates="api_key", cascade="all, delete-orphan"
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("api_key_id", "bucket", "window_start", name="uq_usage_window"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    api_key_id: Mapped[str] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"), index=True
    )
    bucket: Mapped[UsageBucket] = mapped_column(Enum(UsageBucket), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    api_key: Mapped[ApiKey] = relationship(back_populates="usage_records")
