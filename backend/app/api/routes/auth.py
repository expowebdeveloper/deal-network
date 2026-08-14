"""OAuth sign-in, token refresh and the current-session endpoint.

Mounted at `/auth` (not under the /api prefix) so the callback path matches
GOOGLE_REDIRECT_URI in .env verbatim.

Browser flow:
    GET  /auth/google/login          -> 307 to Google
    GET  /auth/google/callback       -> 303 to FRONTEND_URL/auth/callback#access_token=...

Tokens come back in the URL *fragment*, which browsers never send to a server
and which stays out of referrers and access logs.
"""

from __future__ import annotations

import json
import logging
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from sqlalchemy import select

from app.api.deps import BearerCredentials, CurrentUser, DbSession
from app.core.config import settings
from app.core.security import (
    TokenError, TokenType, create_access_token, create_oauth_state, create_refresh_token,
    decode_token, verify_oauth_state,
)
from app.models import User
from app.schemas.auth import (
    AuthSession, LogoutRequest, ProviderInfo, ProvidersResponse, RefreshRequest, TokenPair,
)
from app.schemas.common import Message
from app.schemas.user import UserProfile
from app.services import email as email_service
from app.services import oauth
from app.services import tokens as token_service
from app.services.users import AccountLinkError, resolve_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def _safe_redirect_path(value: str | None) -> str:
    """Only allow same-origin relative paths, so state cannot become an open redirect."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return ""
    return value


def _frontend_redirect(redirect_to: str | None = None, **params) -> RedirectResponse:
    """Hand control back to the SPA, passing data in the fragment.

    303 (not 307): Apple's callback is a POST, and 307 would make the browser
    replay the POST against the SPA, which cannot handle it. 303 forces a GET.
    """
    base = settings.frontend_url.rstrip("/")
    target = _safe_redirect_path(redirect_to)
    if target:
        params["redirect_to"] = target
    return RedirectResponse(
        f"{base}/auth/callback#{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(request: Request) -> ProvidersResponse:
    """Which sign-in buttons the frontend should show."""
    base = str(request.base_url).rstrip("/")
    return ProvidersResponse(
        providers=[
            ProviderInfo(name=name, authorize_url=f"{base}/auth/{name}/login")
            for name in oauth.available_providers()
        ]
    )


@router.get("/{provider}/login")
async def start_login(provider: str, redirect_to: str | None = Query(default=None)):
    """Kick off the OAuth dance."""
    if provider not in {"google", "apple"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown provider")

    try:
        state = create_oauth_state(provider, redirect_to)
        url = oauth.authorize_url(provider, state)
    except oauth.OAuthError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback")
async def google_callback(
    db: DbSession,
    background: BackgroundTasks,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        return _frontend_redirect(error=error)
    if not code or not state:
        return _frontend_redirect(error="missing_code")

    try:
        claims = verify_oauth_state(state, "google")
    except TokenError as exc:
        return _frontend_redirect(error=f"invalid_state: {exc}")

    redirect_to = claims.get("redirect_to")

    try:
        profile = await oauth.google_exchange(code)
    except oauth.OAuthError as exc:
        logger.warning("Google exchange failed: %s", exc)
        return _frontend_redirect(error="oauth_exchange_failed", redirect_to=redirect_to)

    try:
        user, created = await resolve_user(db, profile)
    except AccountLinkError as exc:
        logger.warning("Refused to link Google identity: %s", exc)
        await db.rollback()
        return _frontend_redirect(error="account_link_refused", redirect_to=redirect_to)
    await db.commit()
    await db.refresh(user)

    if not user.is_active:
        return _frontend_redirect(error="account_disabled", redirect_to=redirect_to)

    if created:
        background.add_task(email_service.send_welcome, user.email, user.name)

    tokens = _token_pair(user)
    return _frontend_redirect(
        redirect_to=redirect_to,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        new_user=str(created).lower(),
    )


@router.post("/apple/callback")
async def apple_callback(
    db: DbSession,
    background: BackgroundTasks,
    code: str | None = Form(default=None),
    state: str | None = Form(default=None),
    error: str | None = Form(default=None),
    user: str | None = Form(default=None),
):
    """Apple posts the result back as a form, not a redirect with query params."""
    if error:
        return _frontend_redirect(error=error)
    if not code or not state:
        return _frontend_redirect(error="missing_code")

    try:
        claims = verify_oauth_state(state, "apple")
    except TokenError as exc:
        return _frontend_redirect(error=f"invalid_state: {exc}")

    redirect_to = claims.get("redirect_to")

    user_payload = None
    if user:
        try:
            user_payload = json.loads(user)
        except json.JSONDecodeError:
            user_payload = None

    try:
        profile = await oauth.apple_exchange(code, user_payload)
    except oauth.OAuthError as exc:
        logger.warning("Apple exchange failed: %s", exc)
        return _frontend_redirect(error="oauth_exchange_failed", redirect_to=redirect_to)

    try:
        account, created = await resolve_user(db, profile)
    except AccountLinkError as exc:
        logger.warning("Refused to link Apple identity: %s", exc)
        await db.rollback()
        return _frontend_redirect(error="account_link_refused", redirect_to=redirect_to)
    await db.commit()
    await db.refresh(account)

    if not account.is_active:
        return _frontend_redirect(error="account_disabled", redirect_to=redirect_to)

    if created:
        background.add_task(email_service.send_welcome, account.email, account.name)

    tokens = _token_pair(account)
    return _frontend_redirect(
        redirect_to=redirect_to,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        new_user=str(created).lower(),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    if await token_service.is_revoked(db, claims):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been signed out")

    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token subject is invalid") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is not available")
    return _token_pair(user)


@router.get("/me", response_model=UserProfile)
async def me(current_user: CurrentUser) -> User:
    return current_user


@router.get("/session", response_model=AuthSession)
async def session(current_user: CurrentUser) -> AuthSession:
    """Current user plus a re-issued *access* token.

    Deliberately does not mint a refresh token: that would let a 60-minute
    access token be traded up into a fresh 30-day credential. Refresh tokens
    come only from the OAuth callback or from /auth/refresh.
    """
    return AuthSession(
        access_token=create_access_token(current_user.id, current_user.email),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserProfile.model_validate(current_user),
    )


async def _revoke_presented(db: DbSession, token: str, token_type: TokenType) -> bool:
    """Deny-list a token the caller handed us, if it is still worth revoking.

    A token that is expired, forged or already signed out needs no row: it is
    rejected on its own merits. Returning quietly keeps sign-out idempotent.
    """
    try:
        claims = decode_token(token, token_type)
    except TokenError:
        return False

    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        return False

    # The FK needs a live member; a token for a deleted account is already dead.
    if await db.scalar(select(User.id).where(User.id == user_id)) is None:
        return False

    return await token_service.revoke(db, claims, token_type, user_id)


@router.post("/logout", response_model=Message)
async def logout(
    db: DbSession,
    credentials: BearerCredentials,
    payload: LogoutRequest | None = None,
) -> Message:
    """Sign out: revoke this session's access and refresh tokens.

    Authentication is deliberately *optional*. You can only revoke a token you
    are holding, so accepting whatever the caller presents lets sign-out finish
    even when the access token has already expired — the refresh token in the
    body is the half that would otherwise keep the session alive.

    Repeat calls are fine; the only failure is presenting nothing at all.
    """
    refresh_token = payload.refresh_token if payload else None
    if credentials is None and not refresh_token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials is not None:
        await _revoke_presented(db, credentials.credentials, "access")
    if refresh_token:
        await _revoke_presented(db, refresh_token, "refresh")

    # Rows for tokens that have expired can never match again — drop them here
    # so the denylist stays roughly the size of the live session count.
    await token_service.purge_expired(db)
    await db.commit()
    return Message(detail="Signed out")
