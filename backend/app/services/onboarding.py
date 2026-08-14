"""Profile setup: the choices offered, and applying the answers to the profile.

The option lists live here rather than in the frontend so both steps offer the
same things the API will accept, and so adding a market or an asset class is a
one-line change on one side.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mandate, MemberOnboarding, MemberRole, User

# Step 1 of 2 is the role picker, step 2 the company details. Bump this if more
# steps arrive — the wizard renders its progress from what the API reports.
TOTAL_STEPS = 2

ROLE_OPTIONS: list[dict] = [
    {
        "id": MemberRole.developer,
        "title": "Developer / Sponsor",
        "description": "I build or convert property and raise capital for it",
    },
    {
        "id": MemberRole.investor,
        "title": "Investor / LP",
        "description": "I put capital into other people's projects",
    },
    {
        "id": MemberRole.broker,
        "title": "Broker / Agent",
        "description": "I introduce buyers, sellers and tenants",
    },
    {
        "id": MemberRole.lender,
        "title": "Lender",
        "description": "I provide construction or acquisition finance",
    },
    {
        "id": MemberRole.service_provider,
        "title": "Service provider",
        "description": "Architecture, legal, PM, valuation and similar",
    },
]

MARKET_OPTIONS = ["Mohali, IN", "Bangalore, IN", "New York, US", "Bay Area, US"]
TEAM_SIZE_OPTIONS = ["Just me", "2–10", "11–50", "50+"]
ASSET_CLASS_OPTIONS = [
    "Residential", "Mixed-use", "Medical", "Industrial", "Retail", "Hospitality",
]


async def get_or_create(db: AsyncSession, user_id: uuid.UUID) -> MemberOnboarding:
    """The member's setup row, created empty on first look."""
    row = await db.scalar(
        select(MemberOnboarding).where(MemberOnboarding.user_id == user_id)
    )
    if row is None:
        row = MemberOnboarding(user_id=user_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def current_step(row: MemberOnboarding) -> int:
    """Which step to show: 1 until a role is picked, 2 after that."""
    return 1 if row.role is None else 2


def split_asset_classes(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


async def apply_to_profile(db: AsyncSession, user: User, row: MemberOnboarding) -> None:
    """Copy the answers onto the profile the rest of the app reads.

    Blank answers are left alone rather than blanking a field the member may
    have filled in elsewhere.
    """
    if row.role is not None:
        user.role = row.role
    if row.company:
        user.company = row.company
    if row.primary_market:
        user.location = row.primary_market
    if row.asset_classes:
        user.focus = row.asset_classes
    if row.short_description:
        user.bio = row.short_description
    user.onboarded = True

    mandate = await db.scalar(select(Mandate).where(Mandate.user_id == user.id))
    if mandate is None:
        mandate = Mandate(user_id=user.id)
        db.add(mandate)
    if row.asset_classes:
        mandate.asset_classes = row.asset_classes
    if row.primary_market:
        mandate.markets = row.primary_market


def stamp_completed(row: MemberOnboarding) -> None:
    row.completed_at = datetime.now(UTC)
