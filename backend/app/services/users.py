"""Provisioning a member from an OAuth profile, and the defaults they start with."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FieldVisibility, Mandate, OAuthIdentity, PlanTier, Subscription, User, VisibilityLevel,
)
from app.services.oauth import OAuthProfile, derive_initials, pick_avatar_color

# Mirrors the field-visibility rows on the profile screen.
DEFAULT_VISIBILITY: dict[str, VisibilityLevel] = {
    "company": VisibilityLevel.public,
    "markets": VisibilityLevel.public,
    "completed": VisibilityLevel.public,
    "raise": VisibilityLevel.members,
    "active": VisibilityLevel.members,
    "contact": VisibilityLevel.private,
    "lenders": VisibilityLevel.private,
    "investors": VisibilityLevel.private,
}

VISIBILITY_LABELS: dict[str, str] = {
    "company": "Company name",
    "markets": "Markets",
    "completed": "Completed projects",
    "raise": "Typical raise size",
    "active": "Current projects in progress",
    "contact": "Email and phone",
    "lenders": "Lenders and loan terms",
    "investors": "Investor names",
}


class AccountLinkError(Exception):
    """Raised when a provider identity may not be attached to an existing account."""


async def _new_user(db: AsyncSession, profile: OAuthProfile) -> User:
    user = User(
        email=profile.email,
        name=profile.name or profile.email.split("@")[0],
        initials=derive_initials(profile.name, profile.email),
        avatar_color=pick_avatar_color(profile.subject),
        avatar_url=profile.picture,
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()

    for field_key, level in DEFAULT_VISIBILITY.items():
        db.add(FieldVisibility(user_id=user.id, field_key=field_key, level=level))
    db.add(Mandate(user_id=user.id))
    db.add(Subscription(user_id=user.id, plan=PlanTier.early_access))
    return user


async def resolve_user(db: AsyncSession, profile: OAuthProfile) -> tuple[User, bool]:
    """Find or create the member behind an OAuth profile.

    Returns (user, created).

    Linking rule: a *verified* email may attach a second provider to an existing
    account. An unverified one may not — otherwise anyone who can make a provider
    assert `victim@example.com` could adopt the victim's account and sign in as
    them. Providers that do not assert verification are rejected upstream in
    services/oauth.py, so this is belt and braces.
    """
    identity = await db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == profile.provider,
            OAuthIdentity.subject == profile.subject,
        )
    )
    if identity is not None:
        user = await db.get(User, identity.user_id)
        if user is not None:
            user.last_login_at = datetime.now(UTC)
            await db.flush()
            return user, False

    existing = await db.scalar(select(User).where(User.email == profile.email))
    if existing is not None and not profile.email_verified:
        raise AccountLinkError(
            f"{profile.provider.value} did not verify {profile.email}, "
            "so it cannot be linked to the existing account"
        )

    created = False
    if existing is None:
        try:
            # A concurrent first login for the same address would violate the
            # unique email constraint; fall back to the row the winner created.
            async with db.begin_nested():
                user = await _new_user(db, profile)
            created = True
        except IntegrityError:
            user = await db.scalar(select(User).where(User.email == profile.email))
            if user is None:
                raise
            user.last_login_at = datetime.now(UTC)
    else:
        user = existing
        user.last_login_at = datetime.now(UTC)

    try:
        async with db.begin_nested():
            db.add(
                OAuthIdentity(
                    user_id=user.id,
                    provider=profile.provider,
                    subject=profile.subject,
                    email=profile.email,
                )
            )
    except IntegrityError:
        # Another request linked the same identity first — harmless.
        pass

    await db.flush()
    return user, created
