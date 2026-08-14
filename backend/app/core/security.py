"""JWT issuing/verification and the signed OAuth state token."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh", "oauth_state"]


class TokenError(Exception):
    """Raised when a token is missing, expired, malformed or of the wrong type."""


def _encode(payload: dict[str, Any], expires: timedelta, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    body = {
        **payload,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(body, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("Token is invalid") from exc

    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token")
    return payload


def create_access_token(user_id: uuid.UUID | str, email: str) -> str:
    return _encode(
        {"sub": str(user_id), "email": email},
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(user_id: uuid.UUID | str) -> str:
    return _encode(
        {"sub": str(user_id)},
        timedelta(days=settings.refresh_token_expire_days),
        "refresh",
    )


def create_oauth_state(provider: str, redirect_to: str | None = None) -> str:
    """Short-lived signed state, checked on the OAuth callback to stop CSRF."""
    return _encode(
        {"provider": provider, "redirect_to": redirect_to},
        timedelta(minutes=10),
        "oauth_state",
    )


def verify_oauth_state(state: str, provider: str) -> dict[str, Any]:
    payload = decode_token(state, "oauth_state")
    if payload.get("provider") != provider:
        raise TokenError("OAuth state does not match the provider")
    return payload
