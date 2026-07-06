"""
Serviço de login social (OAuth 2.0) — Google e GitHub.

Princípio II: nenhuma dependência de objetos HTTP do FastAPI (Request/Response)
vive aqui. O fluxo de navegador (redirect/cookies) fica no portal; este módulo só
sabe montar URLs de autorização, trocar ``code`` por ``access_token`` e resolver a
identidade do provedor numa ``DeveloperAccount`` (find-or-create + auto-link).

Princípio V/VII: implementação manual com ``httpx`` (sem dependência nova nem
SessionMiddleware). Só confiamos em e-mail marcado como verificado pelo provedor;
sem e-mail verificado, o login social falha (``OAuthError``), nunca cria conta.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.tables import DeveloperAccount, OAuthIdentity


class OAuthError(Exception):
    """Falha esperada do fluxo OAuth (provedor recusou, e-mail não verificado…).

    Mensagem nunca é exposta ao usuário — o portal a converte num aviso neutro.
    """


@dataclass(frozen=True)
class OAuthUserInfo:
    provider: str
    provider_account_id: str
    email: str
    email_verified: bool
    name: str | None = None


# Metadados dos provedores suportados (endpoints públicos e escopos mínimos).
PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scopes": "openid email profile",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scopes": "read:user user:email",
    },
}


def provider_enabled(provider: str) -> bool:
    """True quando client_id e client_secret do provedor estão configurados."""
    if provider == "google":
        return settings.google_oauth_enabled
    if provider == "github":
        return settings.github_oauth_enabled
    return False


def _credentials(provider: str) -> tuple[str, str]:
    if provider == "google":
        return settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET
    if provider == "github":
        return settings.GITHUB_OAUTH_CLIENT_ID, settings.GITHUB_OAUTH_CLIENT_SECRET
    raise OAuthError(f"Provedor desconhecido: {provider}")


def redirect_uri(provider: str) -> str:
    """URL de callback registrada no provedor (deriva de OAUTH_REDIRECT_BASE_URL)."""
    base = settings.OAUTH_REDIRECT_BASE_URL.rstrip("/")
    return f"{base}/portal/auth/{provider}/callback"


def build_authorize_url(provider: str, state: str) -> str:
    """Monta a URL de autorização do provedor com o ``state`` anti-CSRF."""
    meta = PROVIDERS[provider]
    client_id, _ = _credentials(provider)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider),
        "scope": meta["scopes"],
        "response_type": "code",
        "state": state,
    }
    return f"{meta['authorize_url']}?{urlencode(params)}"


def _as_bool(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


async def exchange_code(provider: str, code: str, client: httpx.AsyncClient) -> str:
    """Troca o ``code`` de autorização por um ``access_token`` do provedor."""
    meta = PROVIDERS[provider]
    client_id, client_secret = _credentials(provider)
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri(provider),
        "grant_type": "authorization_code",
    }
    try:
        response = await client.post(
            meta["token_url"], data=data, headers={"Accept": "application/json"}
        )
        payload = response.json()
    except Exception as exc:  # rede/JSON inválido — falha tratada, sem 500 opaco
        raise OAuthError("Falha ao trocar o código de autorização.") from exc

    token = payload.get("access_token")
    if not token:
        raise OAuthError("Provedor não retornou access_token.")
    return str(token)


async def fetch_identity(
    provider: str, access_token: str, client: httpx.AsyncClient
) -> OAuthUserInfo:
    """Busca o perfil no provedor e normaliza para ``OAuthUserInfo``.

    Exige um e-mail **verificado** pelo provedor; caso contrário levanta
    ``OAuthError`` (não confiamos em e-mail não verificado para vincular contas).
    """
    if provider == "google":
        return await _fetch_google(access_token, client)
    if provider == "github":
        return await _fetch_github(access_token, client)
    raise OAuthError(f"Provedor desconhecido: {provider}")


async def _fetch_google(access_token: str, client: httpx.AsyncClient) -> OAuthUserInfo:
    try:
        response = await client.get(
            PROVIDERS["google"]["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = response.json()
    except Exception as exc:
        raise OAuthError("Falha ao obter o perfil do Google.") from exc

    sub = data.get("sub")
    email = data.get("email")
    verified = _as_bool(data.get("email_verified"))
    if not sub or not email or not verified:
        raise OAuthError("Conta do Google sem e-mail verificado.")
    return OAuthUserInfo(
        provider="google",
        provider_account_id=str(sub),
        email=str(email),
        email_verified=True,
        name=data.get("name"),
    )


async def _fetch_github(access_token: str, client: httpx.AsyncClient) -> OAuthUserInfo:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        profile = (await client.get(PROVIDERS["github"]["userinfo_url"], headers=headers)).json()
        emails = (await client.get(PROVIDERS["github"]["emails_url"], headers=headers)).json()
    except Exception as exc:
        raise OAuthError("Falha ao obter o perfil do GitHub.") from exc

    account_id = profile.get("id")
    if not account_id:
        raise OAuthError("Perfil do GitHub inválido.")

    email = _github_primary_verified_email(emails)
    if not email:
        raise OAuthError("Conta do GitHub sem e-mail primário verificado.")

    return OAuthUserInfo(
        provider="github",
        provider_account_id=str(account_id),
        email=email,
        email_verified=True,
        name=profile.get("name") or profile.get("login"),
    )


def _github_primary_verified_email(emails: object) -> str | None:
    """Escolhe o e-mail primário verificado (fallback: qualquer verificado)."""
    if not isinstance(emails, list):
        return None
    fallback: str | None = None
    for entry in emails:
        if not isinstance(entry, dict) or not entry.get("verified"):
            continue
        address = entry.get("email")
        if not address:
            continue
        if entry.get("primary"):
            return str(address)
        fallback = fallback or str(address)
    return fallback


async def find_or_create_account(session: AsyncSession, info: OAuthUserInfo) -> DeveloperAccount:
    """Resolve a identidade do provedor numa conta (find-or-create + auto-link).

    1. Identidade já vinculada → retorna a conta.
    2. E-mail (verificado) casa com conta existente → vincula a identidade.
    3. Caso contrário → cria conta nova (sem senha, ``email_verified=True``).
    """
    if not info.email_verified:  # invariante defensiva (fetch_identity já garante)
        raise OAuthError("E-mail do provedor não verificado.")

    existing = await _identity_account(session, info)
    if existing is not None:
        return existing

    normalized = info.email.strip().lower()
    result = await session.execute(
        select(DeveloperAccount).where(DeveloperAccount.email == normalized)
    )
    account = result.scalar_one_or_none()

    if account is None:
        account = DeveloperAccount(email=normalized, password_hash=None, email_verified=True)
        session.add(account)
    elif not account.email_verified:
        account.email_verified = True

    session.add(
        OAuthIdentity(
            account=account,
            provider=info.provider,
            provider_account_id=info.provider_account_id,
            email=normalized,
        )
    )

    try:
        await session.flush()
    except IntegrityError:
        # Corrida: outra requisição criou a mesma identidade em paralelo.
        await session.rollback()
        linked = await _identity_account(session, info)
        if linked is not None:
            return linked
        raise OAuthError("Não foi possível vincular a identidade social.") from None

    await session.commit()
    await session.refresh(account)
    return account


async def _identity_account(session: AsyncSession, info: OAuthUserInfo) -> DeveloperAccount | None:
    result = await session.execute(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == info.provider,
            OAuthIdentity.provider_account_id == info.provider_account_id,
        )
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        return None
    return await session.get(DeveloperAccount, identity.account_id)
