"""Profile setup, the step after choosing a plan.

    GET  /api/onboarding           what to show, and what has been answered
    POST /api/onboarding/role      step 1 — what describes you best
    POST /api/onboarding/profile   step 2 — company details, and finish

Each step saves as it is completed, so closing the tab half way through does not
lose the first answer.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models import MemberOnboarding
from app.schemas.onboarding import (
    OnboardingOptions, OnboardingState, ProfileSetup, RoleChoice, RoleOption,
)
from app.services import onboarding as onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _options() -> OnboardingOptions:
    return OnboardingOptions(
        roles=[RoleOption(**option) for option in onboarding_service.ROLE_OPTIONS],
        markets=onboarding_service.MARKET_OPTIONS,
        team_sizes=onboarding_service.TEAM_SIZE_OPTIONS,
        asset_classes=onboarding_service.ASSET_CLASS_OPTIONS,
    )


def _state(row: MemberOnboarding) -> OnboardingState:
    return OnboardingState(
        step=onboarding_service.current_step(row),
        total_steps=onboarding_service.TOTAL_STEPS,
        completed=row.completed_at is not None,
        role=row.role,
        company=row.company,
        primary_market=row.primary_market,
        team_size=row.team_size,
        asset_classes=onboarding_service.split_asset_classes(row.asset_classes),
        short_description=row.short_description,
        completed_at=row.completed_at,
        options=_options(),
    )


@router.get("", response_model=OnboardingState)
async def read_onboarding(current_user: CurrentUser, db: DbSession) -> OnboardingState:
    """The choices on offer, plus anything already answered."""
    return _state(await onboarding_service.get_or_create(db, current_user.id))


@router.post("/role", response_model=OnboardingState)
async def choose_role(
    payload: RoleChoice, current_user: CurrentUser, db: DbSession
) -> OnboardingState:
    """Step 1. The role lands on the profile straight away — it is useful on its
    own for suggestions, even if the member stops before finishing step 2."""
    row = await onboarding_service.get_or_create(db, current_user.id)
    row.role = payload.role
    row.role_chosen_at = datetime.now(UTC)
    current_user.role = payload.role

    await db.commit()
    await db.refresh(row)
    return _state(row)


@router.post("/profile", response_model=OnboardingState)
async def complete_profile(
    payload: ProfileSetup, current_user: CurrentUser, db: DbSession
) -> OnboardingState:
    """Step 2. Saves the company details, copies them onto the profile and marks
    setup finished, which is what closes the wizard for good."""
    row = await onboarding_service.get_or_create(db, current_user.id)
    if row.role is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "role_not_chosen")

    unknown = set(payload.asset_classes) - set(onboarding_service.ASSET_CLASS_OPTIONS)
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown asset class: {', '.join(sorted(unknown))}",
        )
    if payload.primary_market not in onboarding_service.MARKET_OPTIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown market: {payload.primary_market}",
        )
    if payload.team_size not in onboarding_service.TEAM_SIZE_OPTIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown team size: {payload.team_size}",
        )

    row.company = payload.company.strip()
    row.primary_market = payload.primary_market
    row.team_size = payload.team_size
    row.asset_classes = ", ".join(payload.asset_classes) or None
    row.short_description = (payload.short_description or "").strip() or None
    onboarding_service.stamp_completed(row)

    await onboarding_service.apply_to_profile(db, current_user, row)

    await db.commit()
    await db.refresh(row)
    return _state(row)
