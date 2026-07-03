"""
Utilitários de segurança (Princípio V).

- Hash de senha com Argon2 (passlib).
- Emissão/validação de JWT para a sessão do portal.
- Geração de API key + hash SHA-256 + prefixo não sensível para lookup/exibição.

Nunca loga nem retorna segredos em claro.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

_JWT_ALGORITHM = "HS256"

# Prefixo público das API keys (não sensível). Ex.: bncc_live_ab12cd34...
API_KEY_ENV_PREFIX = "bncc_live_"
_API_KEY_PUBLIC_PREFIX_LEN = len(API_KEY_ENV_PREFIX) + 8


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Retorna o hash Argon2 da senha."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica a senha contra o hash Argon2 (constante em tempo)."""
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# JWT de sessão do portal
# --------------------------------------------------------------------------- #
def create_access_token(subject: str, expires_minutes: int | None = None, **claims: Any) -> str:
    """Cria um JWT assinado com SECRET_KEY para a sessão do portal."""
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodifica/valida o JWT. Retorna o payload ou None se inválido/expirado."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# --------------------------------------------------------------------------- #
# API keys
# --------------------------------------------------------------------------- #
def generate_api_key() -> tuple[str, str, str]:
    """
    Gera uma nova API key.

    Retorna (full_key, prefix, key_hash):
    - full_key: segredo completo, exibido UMA única vez ao dev.
    - prefix: parte não sensível, indexável/exibível.
    - key_hash: SHA-256 do full_key, o único valor persistido para comparação.
    """
    secret = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_ENV_PREFIX}{secret}"
    prefix = full_key[:_API_KEY_PUBLIC_PREFIX_LEN]
    key_hash = hash_api_key(full_key)
    return full_key, prefix, key_hash


def hash_api_key(full_key: str) -> str:
    """SHA-256 hex da key completa (determinístico, para lookup por hash)."""
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def api_key_prefix(full_key: str) -> str:
    """Extrai o prefixo público de uma key completa."""
    return full_key[:_API_KEY_PUBLIC_PREFIX_LEN]


def generate_verification_token() -> tuple[str, str]:
    """Gera token de verificação de e-mail de uso único. Retorna (token, token_hash)."""
    token = secrets.token_urlsafe(32)
    return token, hash_verification_token(token)


def hash_verification_token(token: str) -> str:
    """SHA-256 hex do token de verificação (só o hash é persistido)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
