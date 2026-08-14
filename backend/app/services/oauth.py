"""OAuth providers.

Each provider turns an authorization code into a normalised `OAuthProfile`.
A provider is only usable when its credentials are present in .env — see
`available_providers()`, which the frontend uses to decide which buttons to show.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import settings
from app.models.base import OAuthProvider

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

HTTP_TIMEOUT = 15.0


class OAuthError(Exception):
    """Raised when a provider rejects the exchange or returns something unusable."""


@dataclass(slots=True)
class OAuthProfile:
    provider: OAuthProvider
    subject: str
    email: str
    # True only when the provider explicitly asserts the address is verified.
    # Account linking depends on this — see services/users.py.
    email_verified: bool
    name: str | None = None
    picture: str | None = None


def _is_verified(value: object) -> bool:
    """Providers send this as a bool or as the string 'true'."""
    return value is True or (isinstance(value, str) and value.lower() == "true")


def _json(response: httpx.Response, provider: str) -> dict:
    """Decode a provider response, turning malformed bodies into OAuthError."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise OAuthError(f"{provider} returned a malformed response") from exc
    if not isinstance(payload, dict):
        raise OAuthError(f"{provider} returned an unexpected response")
    return payload


# --------------------------------------------------------------------------
# Google
# --------------------------------------------------------------------------

def google_authorize_url(state: str) -> str:
    if not settings.google_enabled:
        raise OAuthError("Google sign-in is not configured")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def google_exchange(code: str) -> OAuthProfile:
    if not settings.google_enabled:
        raise OAuthError("Google sign-in is not configured")

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if token_response.status_code != 200:
                raise OAuthError(f"Google rejected the code: {token_response.text}")

            access_token = _json(token_response, "Google").get("access_token")
            if not access_token:
                raise OAuthError("Google did not return an access token")

            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_response.status_code != 200:
                raise OAuthError("Could not read the Google profile")
    except httpx.RequestError as exc:
        raise OAuthError(f"Could not reach Google: {exc}") from exc

    info = _json(userinfo_response, "Google")
    email = info.get("email")
    if not email:
        raise OAuthError("Google account has no email address")

    # Absent must mean "not verified" — defaulting to True would let an
    # unverified address be trusted for account linking.
    verified = _is_verified(info.get("email_verified"))
    if not verified:
        raise OAuthError("Google email address is not verified")

    return OAuthProfile(
        provider=OAuthProvider.google,
        subject=info["sub"],
        email=email.lower(),
        email_verified=verified,
        name=info.get("name"),
        picture=info.get("picture"),
    )


# --------------------------------------------------------------------------
# Apple
# --------------------------------------------------------------------------

def _apple_client_secret() -> str:
    """Apple wants a short-lived ES256 JWT in place of a static client secret."""
    now = int(time.time())
    private_key = settings.apple_private_key.replace("\\n", "\n")
    return jwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": now,
            "exp": now + 3600,
            "aud": APPLE_ISSUER,
            "sub": settings.apple_client_id,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


def apple_authorize_url(state: str) -> str:
    if not settings.apple_enabled:
        raise OAuthError("Apple sign-in is not configured")

    params = {
        "client_id": settings.apple_client_id,
        "redirect_uri": settings.apple_redirect_uri,
        "response_type": "code",
        "scope": "name email",
        "state": state,
        # Apple only returns name/email in a form POST.
        "response_mode": "form_post",
    }
    return f"{APPLE_AUTH_URL}?{urlencode(params)}"


async def apple_exchange(code: str, user_payload: dict | None = None) -> OAuthProfile:
    """Exchange the code and verify the returned identity token against Apple's JWKS.

    Apple sends the display name exactly once, on first authorisation, in a
    separate `user` form field — pass it through as `user_payload`.
    """
    if not settings.apple_enabled:
        raise OAuthError("Apple sign-in is not configured")

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            token_response = await client.post(
                APPLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.apple_client_id,
                    "client_secret": _apple_client_secret(),
                    "redirect_uri": settings.apple_redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_response.status_code != 200:
                raise OAuthError(f"Apple rejected the code: {token_response.text}")

            identity_token = _json(token_response, "Apple").get("id_token")
            if not identity_token:
                raise OAuthError("Apple did not return an identity token")

            keys_response = await client.get(APPLE_KEYS_URL)
            if keys_response.status_code != 200:
                raise OAuthError("Could not fetch Apple's signing keys")
    except httpx.RequestError as exc:
        raise OAuthError(f"Could not reach Apple: {exc}") from exc

    try:
        kid = jwt.get_unverified_header(identity_token).get("kid")
    except jwt.PyJWTError as exc:
        raise OAuthError("Apple identity token is malformed") from exc

    key_data = next(
        (k for k in _json(keys_response, "Apple").get("keys", []) if k.get("kid") == kid), None
    )
    if key_data is None:
        raise OAuthError("Apple identity token was signed with an unknown key")

    try:
        claims = jwt.decode(
            identity_token,
            jwt.PyJWK(key_data).key,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer=APPLE_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise OAuthError(f"Apple identity token failed verification: {exc}") from exc

    email = claims.get("email")
    if not email:
        raise OAuthError("Apple account did not share an email address")

    # Apple sends this as the string "true"/"false". Without this check an
    # unverified Apple address could be used to claim someone else's account.
    verified = _is_verified(claims.get("email_verified"))
    if not verified:
        raise OAuthError("Apple email address is not verified")

    name = None
    if user_payload:
        parts = user_payload.get("name") or {}
        name = " ".join(
            filter(None, [parts.get("firstName"), parts.get("lastName")])
        ).strip() or None

    return OAuthProfile(
        provider=OAuthProvider.apple,
        subject=claims["sub"],
        email=email.lower(),
        email_verified=verified,
        name=name,
    )


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def available_providers() -> list[str]:
    providers = []
    if settings.google_enabled:
        providers.append("google")
    if settings.apple_enabled:
        providers.append("apple")
    return providers


def authorize_url(provider: str, state: str) -> str:
    if provider == "google":
        return google_authorize_url(state)
    if provider == "apple":
        return apple_authorize_url(state)
    raise OAuthError(f"Unknown provider '{provider}'")


def derive_initials(name: str | None, email: str) -> str:
    """'Vikram Sethi' -> 'VS'. Falls back to the email's first two letters."""
    if name:
        parts = [p for p in name.replace("-", " ").split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        if parts:
            return parts[0][:2].upper()
    return email[:2].upper()


def pick_avatar_color(subject: str) -> str:
    """Stable a1–a6 gradient choice so an avatar keeps its colour between logins."""
    index = uuid.uuid5(uuid.NAMESPACE_OID, subject).int % 6
    return f"a{index + 1}"
