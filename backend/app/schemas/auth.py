"""Authentication payloads."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.user import UserProfile


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthSession(BaseModel):
    """Session snapshot. No refresh token — see the /auth/session docstring."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Body of POST /auth/logout.

    Optional: the access token comes from the Authorization header, and the
    refresh token is sent here so both halves of the session can be revoked.
    """

    refresh_token: str | None = None


class ProviderInfo(BaseModel):
    name: str
    authorize_url: str


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]
