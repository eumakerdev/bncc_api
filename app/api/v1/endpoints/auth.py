"""
Endpoints de autenticação do portal (T045) — montados em ``/api/v1/auth``.

Sessão via JWT (Bearer no header **ou** cookie ``session`` httponly). Estes
endpoints **não** usam API key. Mensagens de erro são anti-enumeração.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Response, status

from app.core.config import settings
from app.core.deps import (
    CurrentAccount,
    ForgotRateLimited,
    LoginRateLimited,
    SessionDep,
    SignupRateLimited,
    VerifyRateLimited,
)
from app.models.bncc import ErrorResponse
from app.models.platform import (
    AccountMe,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services import account_service

router = APIRouter()

# Atrás do Firebase Hosting só o cookie `__session` sobrevive de volta ao backend
# (os demais são descartados no caminho ao Cloud Run) — por isso a sessão usa esse
# nome reservado.
_SESSION_COOKIE = "__session"
# Valor fictício apenas para os exemplos do OpenAPI (não é um segredo real).
_EXAMPLE_PW = "SenhaForte123"  # pragma: allowlist secret


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conta de desenvolvedor",
    response_description="Conta criada (ainda não verificada); e-mail de verificação disparado.",
    description=(
        "Cria uma conta de desenvolvedor do portal e dispara um e-mail de "
        "verificação de uso único. A conta permanece `email_verified=false` até "
        "a confirmação (necessária para gerar API keys — FR-007). Não usa API "
        "key, apenas e-mail/senha."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Payload inválido (e-mail malformado ou senha fora da política).",
        },
        409: {
            "model": ErrorResponse,
            "description": "Não foi possível concluir o cadastro (e-mail já em uso).",
        },
        429: {"model": ErrorResponse, "description": "Muitas tentativas de cadastro deste IP."},
    },
)
async def signup(
    payload: Annotated[
        SignupRequest,
        Body(
            openapi_examples={
                "padrao": {
                    "summary": "Cadastro padrão",
                    "value": {"email": "dev@example.com", "password": _EXAMPLE_PW},
                },
            },
        ),
    ],
    session: SessionDep,
    _rate_limit: SignupRateLimited,
) -> SignupResponse:
    account, _token = await account_service.signup(session, payload.email, payload.password)
    return SignupResponse(
        account_id=account.id,
        email=account.email,
        email_verified=account.email_verified,
    )


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Confirmar e-mail via token de verificação",
    response_description="Confirmação de que o e-mail da conta foi verificado.",
    description=(
        "Consome o token de verificação de uso único enviado por e-mail no "
        "cadastro e marca a conta como verificada. Necessário antes de gerar "
        "API keys (FR-007)."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Token de verificação inválido."},
        410: {
            "model": ErrorResponse,
            "description": "Token de verificação expirado ou já utilizado.",
        },
        429: {"model": ErrorResponse, "description": "Muitas tentativas deste IP."},
    },
)
async def verify_email(
    payload: Annotated[
        VerifyEmailRequest,
        Body(
            openapi_examples={
                "padrao": {
                    "summary": "Token recebido por e-mail",
                    "value": {"token": "a1b2c3d4e5f6"},  # pragma: allowlist secret
                },
            },
        ),
    ],
    session: SessionDep,
    _rate_limit: VerifyRateLimited,
) -> VerifyEmailResponse:
    account = await account_service.verify_email(session, payload.token)
    return VerifyEmailResponse(email_verified=account.email_verified)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Autenticar e iniciar sessão do portal",
    response_description="Token de sessão (JWT); também é definido como cookie httponly.",
    description=(
        "Autentica com e-mail/senha e retorna um JWT de sessão do portal "
        "(também definido como cookie httponly `session`). Falha de credencial "
        "ou e-mail não verificado retornam a mesma mensagem (anti-enumeração — "
        "Princípio V / FR-023)."
    ),
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Credenciais inválidas ou e-mail não verificado.",
        },
        429: {"model": ErrorResponse, "description": "Muitas tentativas de login deste IP."},
    },
)
async def login(
    payload: Annotated[
        LoginRequest,
        Body(
            openapi_examples={
                "padrao": {
                    "summary": "Login padrão",
                    "value": {"email": "dev@example.com", "password": _EXAMPLE_PW},
                },
            },
        ),
    ],
    session: SessionDep,
    response: Response,
    _rate_limit: LoginRateLimited,
) -> LoginResponse:
    token = await account_service.login(session, payload.email, payload.password)
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return LoginResponse(
        access_token=token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post(
    "/logout",
    summary="Encerrar a sessão do portal",
    response_description="Confirmação de logout; o cookie de sessão é removido.",
    description="Remove o cookie de sessão httponly. Idempotente — sempre retorna 200.",
)
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(_SESSION_COOKIE)
    return {"logged_out": True}


@router.get(
    "/me",
    response_model=AccountMe,
    summary="Dados da conta autenticada",
    response_description="Dados básicos da conta do desenvolvedor autenticado.",
    description=(
        "Retorna os dados da conta associada à sessão do portal atual "
        "(header `Authorization: Bearer <jwt>` ou cookie `session`)."
    ),
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Sessão ausente, inválida ou expirada.",
        },
    },
)
async def me(account: CurrentAccount) -> AccountMe:
    return AccountMe(
        account_id=account.id,
        email=account.email,
        email_verified=account.email_verified,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Trocar a senha da conta autenticada",
    response_description="Confirmação de que a senha foi alterada.",
    description=(
        "Troca a senha da conta associada à sessão atual, exigindo a senha atual. "
        "A nova senha deve seguir a política (mín. 10 caracteres, com letras e "
        "números). Contas criadas apenas por login social não possuem senha atual — "
        "use o fluxo de redefinição para definir uma."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Senha atual incorreta ou nova senha inválida.",
        },
        401: {"model": ErrorResponse, "description": "Sessão ausente, inválida ou expirada."},
    },
)
async def change_password(
    payload: Annotated[
        ChangePasswordRequest,
        Body(
            openapi_examples={
                "padrao": {
                    "summary": "Troca de senha",
                    "value": {
                        "current_password": _EXAMPLE_PW,  # pragma: allowlist secret
                        "new_password": "NovaSenha456",  # pragma: allowlist secret
                    },
                },
            },
        ),
    ],
    account: CurrentAccount,
    session: SessionDep,
) -> MessageResponse:
    await account_service.change_password(
        session, account, payload.current_password, payload.new_password
    )
    return MessageResponse(detail="Senha alterada com sucesso.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Solicitar redefinição de senha",
    response_description="Resposta neutra: sempre a mesma, exista ou não a conta.",
    description=(
        "Dispara um e-mail com um link de redefinição de senha de uso único, quando "
        "existe uma conta para o e-mail informado. Para preservar a privacidade "
        "(anti-enumeração — Princípio V), a resposta é idêntica exista ou não a conta."
    ),
    responses={
        429: {"model": ErrorResponse, "description": "Muitas solicitações deste IP."},
    },
)
async def forgot_password(
    payload: Annotated[
        ForgotPasswordRequest,
        Body(
            openapi_examples={
                "padrao": {"summary": "Pedido de reset", "value": {"email": "dev@example.com"}},
            },
        ),
    ],
    session: SessionDep,
    _rate_limit: ForgotRateLimited,
) -> MessageResponse:
    await account_service.request_password_reset(session, payload.email)
    return MessageResponse(
        detail="Se houver uma conta para este e-mail, enviamos um link de redefinição."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Redefinir a senha com o token do e-mail",
    response_description="Confirmação de que a senha foi redefinida.",
    description=(
        "Consome o token de uso único enviado por e-mail e grava a nova senha "
        "(seguindo a política). Possuir o link comprova controle do e-mail, então a "
        "conta é marcada como verificada."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Token inválido ou nova senha fora da política.",
        },
        410: {"model": ErrorResponse, "description": "Token expirado ou já utilizado."},
    },
)
async def reset_password(
    payload: Annotated[
        ResetPasswordRequest,
        Body(
            openapi_examples={
                "padrao": {
                    "summary": "Redefinição",
                    "value": {
                        "token": "token-recebido-por-email",
                        "new_password": "NovaSenha456",  # pragma: allowlist secret
                    },
                },
            },
        ),
    ],
    session: SessionDep,
) -> MessageResponse:
    await account_service.reset_password(session, payload.token, payload.new_password)
    return MessageResponse(detail="Senha redefinida com sucesso. Faça login para continuar.")
