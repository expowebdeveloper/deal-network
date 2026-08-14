"""The terms document and whether a member has accepted it.

The text lives here rather than in the frontend so that what a member agreed to
is whatever the server served them, and so the version an acceptance is recorded
against is authoritative.

Bump TERMS_VERSION whenever the wording changes: acceptance is matched on it, so
every member is asked again on their next visit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TermsAcceptance, User

TERMS_VERSION = "2026-08-13"

TERMS_SECTIONS: list[dict[str, str]] = [
    {
        "heading": "What we store.",
        "body": (
            "Your profile, company details, community activity, contacts and anything "
            "you upload are stored on our servers."
        ),
    },
    {
        "heading": "How long we keep it.",
        "body": (
            "Information you add is retained for as long as your account exists, and for "
            "a defined period after you close it. It is not deleted automatically."
        ),
    },
    {
        "heading": "What we do not do.",
        "body": (
            "We do not verify, audit or endorse any information a member publishes about "
            "a property, a project or a deal. Anything you rely on, you check yourself."
        ),
    },
    {
        "heading": "Who can see your information.",
        "body": (
            "You control this field by field from your profile. Some operational staff "
            "can access stored data to run and support the service."
        ),
    },
]


async def latest_acceptance(
    db: AsyncSession, user_id: uuid.UUID, version: str = TERMS_VERSION
) -> TermsAcceptance | None:
    """The member's most recent acceptance of a version, or None."""
    return await db.scalar(
        select(TermsAcceptance)
        .where(TermsAcceptance.user_id == user_id, TermsAcceptance.version == version)
        .order_by(TermsAcceptance.accepted_at.desc())
    )


async def has_accepted(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Whether the member is past the terms gate for the version now in force."""
    found = await db.scalar(
        select(TermsAcceptance.id).where(
            TermsAcceptance.user_id == user_id,
            TermsAcceptance.version == TERMS_VERSION,
        )
    )
    return found is not None


def build_acceptance(user: User, marketing_opt_in: bool) -> TermsAcceptance:
    """A row for a member who has just ticked both required boxes."""
    return TermsAcceptance(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        version=TERMS_VERSION,
        accepted_terms=True,
        accepted_unverified=True,
        marketing_opt_in=marketing_opt_in,
        accepted_at=datetime.now(UTC),
    )
