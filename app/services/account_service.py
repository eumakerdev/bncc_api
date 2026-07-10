"""
Serviço de contas de desenvolvedor (T041).

Cadastro com senha Argon2, verificação de e-mail por token de uso único e login
com JWT de sessão. Todas as mensagens de falha de credencial/existência são
**anti-enumeração** (idênticas), conforme Princípio V / FR-023.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_verification_token,
    hash_password,
    hash_verification_token,
    verify_password,
)
from app.db.tables import DeveloperAccount, EmailVerificationToken, PasswordResetToken
from app.services import email_service

# Mensagens neutras (não revelam se o e-mail existe / qual credencial falhou).
_SIGNUP_CONFLICT = "Não foi possível concluir o cadastro."
_LOGIN_FAILED = "Credenciais inválidas ou e-mail não verificado."
_TOKEN_INVALID = "Token de verificação inválido."
_TOKEN_EXPIRED = "Token de verificação expirado ou já utilizado."
_CURRENT_PASSWORD_INVALID = "Senha atual incorreta."  # pragma: allowlist secret
_RESET_TOKEN_INVALID = "Link de redefinição inválido."
_RESET_TOKEN_EXPIRED = "Link de redefinição expirado ou já utilizado."

# Hash Argon2 fixo (senha nunca usada por conta real) para gastar o mesmo tempo
# de verificação quando a conta não existe — sem isto, `verify_password` só
# roda para e-mails cadastrados, o que vaza timing e permite enumerar contas.
_DUMMY_PASSWORD_HASH = hash_password("nao-e-uma-senha-real-so-para-timing-000")


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    """Normaliza datetimes lidos do banco (SQLite pode devolver naive) para UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def signup(session: AsyncSession, email: str, password: str) -> tuple[DeveloperAccount, str]:
    """
    Cria uma conta não verificada e dispara o e-mail de verificação.

    Retorna ``(account, plaintext_token)`` — o token em claro é devolvido para que
    o portal/testes o utilizem no backend de console (dev). Nunca é persistido em
    claro (apenas o hash).
    """
    normalized = _normalize_email(email)

    existing = await session.execute(
        select(DeveloperAccount).where(DeveloperAccount.email == normalized)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_SIGNUP_CONFLICT)

    account = DeveloperAccount(
        email=normalized,
        password_hash=hash_password(password),
        email_verified=False,
    )
    session.add(account)

    token, token_hash = generate_verification_token()
    verification = EmailVerificationToken(
        account=account,
        token_hash=token_hash,
        expires_at=_now() + timedelta(minutes=settings.EMAIL_TOKEN_EXPIRE_MINUTES),
    )
    session.add(verification)

    try:
        await session.flush()
    except IntegrityError:
        # Corrida rara em cadastro concorrente com o mesmo e-mail.
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_SIGNUP_CONFLICT) from None

    await session.commit()
    await session.refresh(account)

    await email_service.send_verification_email(account.email, token)
    return account, token


async def verify_email(session: AsyncSession, token: str) -> DeveloperAccount:
    """Consome o token de uso único e marca a conta como verificada."""
    token_hash = hash_verification_token(token)
    result = await session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_TOKEN_INVALID)
    if record.used_at is not None or _as_aware(record.expires_at) <= _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=_TOKEN_EXPIRED)

    account = await session.get(DeveloperAccount, record.account_id)
    if account is None:  # integridade referencial — não deveria ocorrer
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_TOKEN_INVALID)

    record.used_at = _now()
    account.email_verified = True
    await session.commit()
    await session.refresh(account)
    return account


async def login(
    session: AsyncSession,
    email: str,
    password: str,
    expires_minutes: int | None = None,
) -> str:
    """
    Autentica e retorna um JWT de sessão do portal.

    Falha (credencial inválida **ou** e-mail não verificado) → 401 com mensagem
    idêntica (anti-enumeração). O hash de senha é sempre verificado, mesmo quando
    a conta não existe, para não vazar timing.

    ``expires_minutes`` permite ao portal SSR emitir uma sessão longa (login
    persistente); quando ``None`` usa o padrão ``ACCESS_TOKEN_EXPIRE_MINUTES``,
    que a API REST (``/api/v1/auth/login``) anuncia no contrato.
    """
    normalized = _normalize_email(email)
    result = await session.execute(
        select(DeveloperAccount).where(DeveloperAccount.email == normalized)
    )
    account = result.scalar_one_or_none()

    # Conta só-social (password_hash=None) não pode logar por senha: usa o hash
    # dummy para gastar o mesmo tempo e falhar com a mensagem neutra padrão.
    hash_to_check = (
        account.password_hash
        if account is not None and account.password_hash
        else _DUMMY_PASSWORD_HASH
    )
    password_ok = verify_password(password, hash_to_check)
    if account is None or not password_ok or not account.email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_LOGIN_FAILED)

    return create_access_token(
        subject=account.id,
        email=account.email,
        expires_minutes=expires_minutes,
    )


# --------------------------------------------------------------------------- #
# Gestão de senha
# --------------------------------------------------------------------------- #
async def change_password(
    session: AsyncSession,
    account: DeveloperAccount,
    current_password: str,
    new_password: str,
) -> None:
    """Troca a senha de uma conta autenticada, exigindo a senha atual.

    Contas só-social (``password_hash`` NULL) não têm senha atual válida: a
    verificação falha e devem usar o fluxo de redefinição para **definir** uma.
    """
    hash_to_check = account.password_hash or _DUMMY_PASSWORD_HASH
    if not verify_password(current_password, hash_to_check) or not account.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_CURRENT_PASSWORD_INVALID
        )
    account.password_hash = hash_password(new_password)
    await session.commit()


async def request_password_reset(session: AsyncSession, email: str) -> str | None:
    """Emite (e envia) um token de redefinição de senha de uso único.

    **Anti-enumeração:** para e-mail inexistente não cria registro nem envia nada,
    e o chamador sempre responde de forma idêntica. Retorna o token em claro apenas
    quando emitido (para o backend de console em dev/testes); nunca é persistido em
    claro. Funciona também para contas só-social — permite *definir* uma senha.
    """
    normalized = _normalize_email(email)
    result = await session.execute(
        select(DeveloperAccount).where(DeveloperAccount.email == normalized)
    )
    account = result.scalar_one_or_none()
    if account is None:
        return None

    token, token_hash = generate_verification_token()
    reset = PasswordResetToken(
        account_id=account.id,
        token_hash=token_hash,
        expires_at=_now() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    session.add(reset)
    await session.commit()

    await email_service.send_password_reset_email(account.email, token)
    return token


async def reset_password(session: AsyncSession, token: str, new_password: str) -> DeveloperAccount:
    """Consome o token de redefinição e grava a nova senha.

    Possuir o link prova controle da caixa de e-mail, então a conta é marcada como
    verificada (mesma semântica da verificação de e-mail)."""
    token_hash = hash_verification_token(token)
    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_RESET_TOKEN_INVALID)
    if record.used_at is not None or _as_aware(record.expires_at) <= _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=_RESET_TOKEN_EXPIRED)

    account = await session.get(DeveloperAccount, record.account_id)
    if account is None:  # integridade referencial — não deveria ocorrer
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_RESET_TOKEN_INVALID)

    record.used_at = _now()
    account.password_hash = hash_password(new_password)
    account.email_verified = True
    await session.commit()
    await session.refresh(account)
    return account
