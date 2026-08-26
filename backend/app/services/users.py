"""Provisioning a member from an OAuth profile, and the defaults they start with."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FieldVisibility, Mandate, OAuthIdentity, PlanTier, Subscription, User, VisibilityLevel,
)
from app.services.oauth import OAuthProfile, derive_initials, pick_avatar_color

#: Which profile fields each visibility key controls.
#:
#: The keys are the eight rows on the Field visibility panel; the values are the
#: attributes of `User` that must disappear when a viewer is not allowed to see
#: them. `lenders` and `investors` are absent on purpose — they describe a rule
#: ("never shown to other members") rather than a stored field.
VISIBILITY_FIELDS: dict[str, tuple[str, ...]] = {
    "company": ("company",),
    "markets": ("location",),
    "completed": ("completed_projects", "units_delivered"),
    "active": ("active_projects",),
    "contact": ("email",),
}

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


# --------------------------------------------------------------------------
# Applying field visibility to an outbound profile
# --------------------------------------------------------------------------

async def visible_profile(
    db: AsyncSession, user: User, viewer_id: uuid.UUID | None
) -> dict:
    """One member's profile as another member is allowed to see it.

    The Field visibility panel lets a member mark each part of their profile
    Public, Members or Private. Until now those choices were recorded and never
    enforced: `GET /api/members/{id}` returned the whole row, so an email set to
    Private was served to anyone who asked. This is what closes that.

    Returns a plain dict rather than mutating `user`. That matters — the caller
    holds a live ORM object and commits in the same request (it increments
    `profile_views`), so blanking attributes on it would write the blanks to the
    database and destroy the member's real data.

    Levels:
      Public   — anyone, signed in or not
      Members  — any signed-in member
      Private  — the owner alone

    Public and Members behave identically here because every route on this API
    requires a session. The distinction becomes real when a signed-out public
    profile page exists; the check is written properly now so that page does not
    have to reopen this question.
    """
    data = {
        column.key: getattr(user, column.key)
        for column in sa_inspect(User).mapper.column_attrs
    }
    if viewer_id == user.id:
        return data  # your own profile is never filtered

    rows = (await db.scalars(
        select(FieldVisibility).where(FieldVisibility.user_id == user.id)
    )).all()
    levels = {row.field_key: row.level for row in rows}

    is_signed_in = viewer_id is not None
    for key, attributes in VISIBILITY_FIELDS.items():
        level = levels.get(key, DEFAULT_VISIBILITY.get(key, VisibilityLevel.members))
        if level is VisibilityLevel.public:
            continue
        if level is VisibilityLevel.members and is_signed_in:
            continue
        # Private, or Members-level being read by nobody in particular.
        for attribute in attributes:
            data[attribute] = None if not isinstance(data.get(attribute), int) else 0
    return data
