"""
Serviço de e-mail (T040).

Dois backends (settings.EMAIL_BACKEND):
- ``console`` (dev/testes): registra o link de verificação via ``logging`` — nunca
  usa rede. O link é ``EMAIL_VERIFICATION_BASE_URL?token=<token>``.
- ``smtp`` (produção): envia via ``aiosmtplib`` (async), com TLS opcional.

Nunca loga a senha; o token só aparece no backend de console (dev), por design.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("bncc.email")


def _link_with_token(base: str, token: str) -> str:
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}token={token}"


def _verification_link(token: str) -> str:
    return _link_with_token(settings.EMAIL_VERIFICATION_BASE_URL, token)


def _reset_link(token: str) -> str:
    return _link_with_token(settings.PASSWORD_RESET_BASE_URL, token)


async def send_verification_email(email: str, token: str) -> None:
    """Envia (ou registra, em console) o e-mail de verificação de conta."""
    link = _verification_link(token)
    backend = settings.EMAIL_BACKEND.strip().lower()

    if backend == "smtp":
        await _send_smtp(email, link)
        return

    # Backend de console (padrão dev/testes): apenas registra o link.
    logger.info("Verificação de e-mail para %s: %s", email, link)


async def send_password_reset_email(email: str, token: str) -> None:
    """Envia (ou registra, em console) o e-mail de redefinição de senha."""
    link = _reset_link(token)
    backend = settings.EMAIL_BACKEND.strip().lower()

    if backend == "smtp":
        await _send_smtp(
            email,
            link,
            subject="Redefinição de senha — BNCC API",
            body=(
                "Recebemos um pedido para redefinir a senha da sua conta na BNCC API.\n\n"
                "Crie uma nova senha pelo link abaixo (expira em breve):\n\n"
                f"{link}\n\n"
                "Se você não solicitou, ignore esta mensagem — sua senha continua a mesma."
            ),
        )
        return

    logger.info("Redefinição de senha para %s: %s", email, link)


async def _send_smtp(
    email: str,
    link: str,
    subject: str = "Confirme seu e-mail — BNCC API",
    body: str | None = None,
) -> None:
    """Envia um e-mail transacional por SMTP assíncrono (produção)."""
    from email.message import EmailMessage

    import aiosmtplib

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = email
    message["Subject"] = subject
    message.set_content(
        body
        if body is not None
        else (
            "Bem-vindo(a) à BNCC API.\n\n"
            "Confirme seu e-mail para liberar a geração de API keys:\n\n"
            f"{link}\n\n"
            "Se você não solicitou este cadastro, ignore esta mensagem."
        )
    )

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        start_tls=settings.SMTP_USE_TLS,
        # EHLO exige ASCII; o hostname da máquina pode ter acento (ex.: Windows
        # local) e quebraria com UnicodeEncodeError. Fixamos um valor ASCII.
        local_hostname="localhost",
    )
