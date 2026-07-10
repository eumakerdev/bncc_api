"""
Schemas Pydantic da plataforma (contas, keys, uso) — request/response.

Política de senha (FR-007): >= 10 caracteres, com ao menos letras e números.
Segredos (hash de senha/key/token) nunca aparecem em nenhum schema de saída.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_MIN_LEN = 10


def _validate_password_policy(value: str) -> str:
    if len(value) < _PASSWORD_MIN_LEN:
        raise ValueError(f"Senha deve ter ao menos {_PASSWORD_MIN_LEN} caracteres")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Senha deve conter letras e números")
    return value


# --------------------------------------------------------------------------- #
# Auth / contas
# --------------------------------------------------------------------------- #
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., description="Mínimo 10 caracteres, com letras e números")

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_policy(v)


class SignupResponse(BaseModel):
    account_id: str
    email: EmailStr
    email_verified: bool = False


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=8)


class VerifyEmailResponse(BaseModel):
    email_verified: bool = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class AccountMe(BaseModel):
    account_id: str
    email: EmailStr
    email_verified: bool


# --------------------------------------------------------------------------- #
# Gestão de senha (troca logada + "esqueci a senha")
# --------------------------------------------------------------------------- #
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Senha atual da conta")
    new_password: str = Field(
        ..., description="Nova senha: mín. 10 caracteres, com letras e números"
    )

    @field_validator("new_password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_policy(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=8)
    new_password: str = Field(
        ..., description="Nova senha: mín. 10 caracteres, com letras e números"
    )

    @field_validator("new_password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_policy(v)


class MessageResponse(BaseModel):
    """Resposta neutra e genérica (usada em fluxos anti-enumeração)."""

    detail: str


# --------------------------------------------------------------------------- #
# API keys
# --------------------------------------------------------------------------- #
class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class ApiKeyCreatedResponse(BaseModel):
    """Segredo `key` exibido UMA única vez, na criação."""

    id: str
    name: str
    prefix: str
    key: str = Field(..., description="Segredo completo — exibido apenas nesta resposta")


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    status: str
    created_at: datetime
    last_used_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Uso
# --------------------------------------------------------------------------- #
class BucketUsage(BaseModel):
    used_this_minute: int = 0
    limit_per_minute: int
    used_today: int | None = None
    limit_per_day: int | None = None


class KeyUsageResponse(BaseModel):
    api_key_id: str
    deterministic: BucketUsage
    ai: BucketUsage


class AccountUsageResponse(BaseModel):
    account_id: str
    total_keys: int
    deterministic_used_today: int
    ai_used_today: int


class UsageDailyPoint(BaseModel):
    """Um ponto da série diária do painel (um dia do calendário UTC)."""

    date: date
    total: int = Field(..., description="Chamadas autorizadas no dia (qualquer desfecho)")
    successful: int = Field(..., description="Chamadas com desfecho de sucesso (< 400)")
    failed: int = Field(..., description="Chamadas com desfecho de erro (>= 400)")


class AccountAnalyticsResponse(BaseModel):
    """BI de uso da conta: série diária + KPIs agregados da janela (30 dias)."""

    account_id: str
    window_days: int
    series: list[UsageDailyPoint]
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float | None = Field(
        None, description="successful/total na janela; nulo quando não houve tráfego"
    )
    total_requests_prev: int = Field(..., description="Total da janela anterior (para o delta)")
    total_requests_delta_pct: float | None = Field(
        None, description="Variação % vs. janela anterior; nulo quando a anterior foi zero"
    )
    ai_requests: int = Field(..., description="Chamadas de IA na janela")
    deterministic_requests: int = Field(..., description="Chamadas determinísticas na janela")
    active_keys: int
    new_keys_last_7d: int = Field(..., description="Keys ativas criadas nos últimos 7 dias")
