"""
Endpoints de autenticação do portal (T045) — montados em ``/api/v1/auth``.

Sessão via JWT (Bearer no header **ou** cookie ``session`` httponly). Estes
endpoints **não** usam API key. Mensagens de erro são anti-enumeração.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.deps import CurrentAccount, SessionDep
from app.models.platform import (
    AccountMe,
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services import account_service

router = APIRouter()

_SESSION_COOKIE = "session"


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, session: SessionDep) -> SignupResponse:
    account, _token = await account_service.signup(session, payload.email, payload.password)
    return SignupResponse(
        account_id=account.id,
        email=account.email,
        email_verified=account.email_verified,
    )


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(payload: VerifyEmailRequest, session: SessionDep) -> VerifyEmailResponse:
    account = await account_service.verify_email(session, payload.token)
    return VerifyEmailResponse(email_verified=account.email_verified)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: SessionDep, response: Response) -> LoginResponse:
    token = await account_service.login(session, payload.email, payload.password)
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return LoginResponse(
        access_token=token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(_SESSION_COOKIE)
    return {"logged_out": True}


@router.get("/me", response_model=AccountMe)
async def me(account: CurrentAccount) -> AccountMe:
    return AccountMe(
        account_id=account.id,
        email=account.email,
        email_verified=account.email_verified,
    )
