from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from notes_rag.api.errors import ApiError
from notes_rag.config import Settings
from notes_rag.domain.users import Session, User
from notes_rag.services.authentication import (
    AuthenticationFailed,
    AuthenticationService,
    RateLimited,
    UsernameConflict,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    username: str
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(id=user.id, username=user.username, created_at=user.created_at)


def auth_service(request: Request) -> AuthenticationService:
    return request.app.state.auth_service


def settings(request: Request) -> Settings:
    return request.app.state.settings


def session_cookie_name(configuration: Settings) -> str:
    return "__Host-notes_session" if configuration.cookie_secure else "notes_session"


async def current_session(
    request: Request,
    service: Annotated[AuthenticationService, Depends(auth_service)],
    configuration: Annotated[Settings, Depends(settings)],
) -> Session:
    token = request.cookies.get(session_cookie_name(configuration))
    if not token:
        raise ApiError(401, "unauthenticated", "Autenticação necessária.")
    try:
        return await service.authenticate(token)
    except AuthenticationFailed as error:
        raise ApiError(401, "unauthenticated", "Autenticação necessária.") from error


async def mutation_session(
    request: Request,
    session: Annotated[Session, Depends(current_session)],
    service: Annotated[AuthenticationService, Depends(auth_service)],
    configuration: Annotated[Settings, Depends(settings)],
) -> Session:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(configuration.allowed_origin).rstrip("/"):
        raise ApiError(403, "csrf_rejected", "Solicitação de origem inválida.")
    csrf = request.headers.get("x-csrf-token", "")
    if not service.validate_csrf(session, csrf):
        raise ApiError(403, "csrf_rejected", "Token CSRF inválido.")
    return session


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    service: Annotated[AuthenticationService, Depends(auth_service)],
) -> UserResponse:
    try:
        return UserResponse.from_domain(await service.register(payload.username, payload.password))
    except UsernameConflict as error:
        raise ApiError(409, "username_conflict", "Nome de usuário indisponível.") from error


@router.post("/login", status_code=204)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthenticationService, Depends(auth_service)],
    configuration: Annotated[Settings, Depends(settings)],
) -> None:
    client_key = request.client.host if request.client else "unknown"
    try:
        credentials = await service.login(payload.username, payload.password, client_key)
    except RateLimited as error:
        raise ApiError(429, "rate_limited", "Muitas tentativas. Tente novamente depois.") from error
    except AuthenticationFailed as error:
        raise ApiError(401, "authentication_failed", "Credenciais inválidas.") from error
    response.set_cookie(
        session_cookie_name(configuration),
        credentials.token,
        httponly=True,
        secure=configuration.cookie_secure,
        samesite="strict",
        path="/",
        max_age=configuration.session_lifetime_seconds,
    )
    response.set_cookie(
        "notes_csrf",
        credentials.csrf_token,
        httponly=False,
        secure=configuration.cookie_secure,
        samesite="strict",
        path="/",
        max_age=configuration.session_lifetime_seconds,
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: Annotated[Session, Depends(mutation_session)],
    service: Annotated[AuthenticationService, Depends(auth_service)],
    configuration: Annotated[Settings, Depends(settings)],
) -> None:
    await service.logout(session)
    response.delete_cookie(session_cookie_name(configuration), path="/")
    response.delete_cookie("notes_csrf", path="/")


@router.get("/me", response_model=UserResponse)
async def me(
    session: Annotated[Session, Depends(current_session)],
    service: Annotated[AuthenticationService, Depends(auth_service)],
) -> UserResponse:
    try:
        return UserResponse.from_domain(await service.current_user(session))
    except AuthenticationFailed as error:
        raise ApiError(401, "unauthenticated", "Autenticação necessária.") from error
