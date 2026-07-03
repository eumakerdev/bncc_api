"""
Schemas Pydantic da plataforma (contas, keys, uso) — request/response.

Política de senha (FR-007): >= 10 caracteres, com ao menos letras e números.
Segredos (hash de senha/key/token) nunca aparecem em nenhum schema de saída.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

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
    last_used_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Uso
# --------------------------------------------------------------------------- #
class BucketUsage(BaseModel):
    used_this_minute: int = 0
    limit_per_minute: int
    used_today: Optional[int] = None
    limit_per_day: Optional[int] = None


class KeyUsageResponse(BaseModel):
    api_key_id: str
    deterministic: BucketUsage
    ai: BucketUsage


class AccountUsageResponse(BaseModel):
    account_id: str
    total_keys: int
    deterministic_used_today: int
    ai_used_today: int
