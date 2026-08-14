"""Plans and subscriptions.

Nothing is charged during early access. A card is captured for later billing and
only the last four digits are ever stored — wire a real PSP (Stripe) in before
going live.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession
from app.models import Contact, PlanSelection, PlanTier, Subscription, SubscriptionStatus
from app.schemas.common import Message
from app.schemas.crm import (
    PlanFeature, PlanOut, PlanSelect, PlanSelectionOut, PublicPlanOut, SubscribeRequest,
    SubscriptionOut,
)
from app.schemas.entitlements import Entitlements, ModuleAccess
from app.services import email as email_service
from app.services import entitlements as entitlement_service

router = APIRouter(prefix="/plans", tags=["plans"])

# The price list is the one thing here a visitor may read before signing in — the
# public pricing page runs on it. Everything else on `router` is behind the terms
# gate; see api/router.py, which includes this one without it.
public_router = APIRouter(prefix="/plans", tags=["plans"])

PLAN_PRICES: dict[PlanTier, str] = {
    PlanTier.early_access: "0",
    PlanTier.member: "25",
    PlanTier.professional: "100",
}

PLAN_CATALOGUE: list[dict] = [
    {
        "id": PlanTier.early_access,
        "name": "Early access",
        "tagline": "For everyone on the network while we grow the first few hundred members.",
        "price": "$0",
        "per": None,
        "billed": "No card required",
        "featured": False,
        "features": [
            "Full profile",
            "Join any community",
            "Unlimited connections",
            "Up to 25 contacts",
        ],
    },
    {
        "id": PlanTier.member,
        "name": "Member",
        "tagline": "For individual developers, brokers and investors running their own relationships.",
        "price": "$25",
        "per": "/month",
        "billed": "Billed monthly · cancel anytime",
        "featured": True,
        "features": [
            "Everything in early access",
            "Unlimited contacts",
            "Pipeline board",
            "Create your own communities",
            "Introduction requests",
            ("Team seats", False),
        ],
    },
    {
        "id": PlanTier.professional,
        "name": "Professional",
        "tagline": "For firms running a team, with several people working the same relationships.",
        "price": "$100",
        "per": "/month",
        "billed": "Billed monthly · includes 5 seats",
        "featured": False,
        "features": [
            "Everything in Member",
            "5 team seats included",
            "Shared company profile",
            "Shared contact record",
            "Priority support",
            "Early access to what ships next",
        ],
    },
]


async def _subscription_for(db: DbSession, user_id) -> Subscription:
    subscription = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    if subscription is None:
        subscription = Subscription(user_id=user_id, plan=PlanTier.early_access)
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
    return subscription


def _plan_out(plan: dict, *, is_current: bool = False) -> PlanOut:
    return PlanOut(
        **{k: v for k, v in plan.items() if k != "features"},
        features=[
            PlanFeature(label=f[0], included=f[1])
            if isinstance(f, tuple)
            else PlanFeature(label=f)
            for f in plan["features"]
        ],
        is_current=is_current,
    )


@public_router.get("/catalogue", response_model=list[PublicPlanOut])
async def read_catalogue() -> list[PublicPlanOut]:
    """The price list, without signing in — what the public pricing page shows.

    Same catalogue as GET /plans; only "which one is yours" needs an account, so
    nothing here is marked current.
    """
    rows = []
    for plan in PLAN_CATALOGUE:
        access = entitlement_service.access_for(plan["id"])
        rows.append(PublicPlanOut(
            **_plan_out(plan).model_dump(),
            max_phase=access.max_phase,
            pro=access.pro,
        ))
    return rows


@router.get("", response_model=list[PlanOut])
async def list_plans(db: DbSession, current_user: CurrentUser) -> list[PlanOut]:
    current = await _subscription_for(db, current_user.id)
    return [_plan_out(plan, is_current=plan["id"] == current.plan) for plan in PLAN_CATALOGUE]


def _plan_name(plan: PlanTier) -> str:
    return next(p["name"] for p in PLAN_CATALOGUE if p["id"] == plan)


def _modules_for(plan: PlanTier) -> list[ModuleAccess]:
    """Every module, flagged with whether this plan reaches it."""
    rows = []
    for module in entitlement_service.MODULES:
        included = entitlement_service.module_included(plan, module)
        rows.append(ModuleAccess(
            id=module.id,
            title=module.title,
            phase_from=module.phase_from,
            phase_to=module.phase_to,
            phase_label=module.phase_label,
            pro=module.pro,
            included=included,
            unlocked_by=None if included
            else entitlement_service.plan_needed_for_module(module.id),
        ))
    return rows


def _entitlements(plan: PlanTier, contacts_used: int | None = None) -> Entitlements:
    access = entitlement_service.access_for(plan)
    every_feature = sorted(
        {feature for tier in entitlement_service.PLAN_ORDER
         for feature in entitlement_service.access_for(tier).features}
    )
    return Entitlements(
        plan=plan,
        plan_name=_plan_name(plan),
        max_phase=access.max_phase,
        pro=access.pro,
        contact_limit=access.contact_limit,
        contacts_used=contacts_used,
        team_seats=access.team_seats,
        features={name: name in access.features for name in every_feature},
        modules=_modules_for(plan),
    )


@router.get("/entitlements", response_model=Entitlements)
async def read_entitlements(db: DbSession, current_user: CurrentUser) -> Entitlements:
    """What the member's own plan unlocks, and how much of their limit is used.

    Declared before /{anything} would be, and kept on /plans because it only
    ever answers "what does my plan give me".
    """
    subscription = await _subscription_for(db, current_user.id)
    used = await db.scalar(
        select(func.count(Contact.id)).where(Contact.owner_id == current_user.id)
    )
    return _entitlements(subscription.plan, contacts_used=used or 0)


@router.get("/{plan}/entitlements", response_model=Entitlements)
async def read_plan_entitlements(plan: PlanTier) -> Entitlements:
    """What a given plan unlocks — for the pricing page, before choosing."""
    return _entitlements(plan)


@router.post("/select", response_model=PlanSelectionOut, status_code=status.HTTP_201_CREATED)
async def select_plan(
    payload: PlanSelect, current_user: CurrentUser, db: DbSession
) -> PlanSelection:
    """Choose a plan. This is what unlocks the rest of the app.

    Appends a row to `plan_selections` (who, which plan, how much, when) and
    points the member's subscription at it. No payment is taken — the card step
    lives in POST /plans/subscribe and will move to Stripe.
    """
    catalogue = next((p for p in PLAN_CATALOGUE if p["id"] == payload.plan), None)
    if catalogue is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown plan")

    # Only one row may be current; the rest stay as history.
    await db.execute(
        update(PlanSelection)
        .where(PlanSelection.user_id == current_user.id, PlanSelection.is_current.is_(True))
        .values(is_current=False)
    )

    had_previous = await db.scalar(
        select(func.count(PlanSelection.id)).where(PlanSelection.user_id == current_user.id)
    )

    now = datetime.now(UTC)
    selection = PlanSelection(
        user_id=current_user.id,
        user_name=current_user.name,
        user_email=current_user.email,
        user_company=current_user.company,
        plan=payload.plan,
        plan_name=catalogue["name"],
        price_usd=float(PLAN_PRICES[payload.plan]),
        billing_period="none" if payload.plan is PlanTier.early_access else "monthly",
        selected_at=now,
        is_current=True,
        source="onboarding" if not had_previous else "change",
    )
    db.add(selection)

    subscription = await _subscription_for(db, current_user.id)
    subscription.plan = payload.plan
    subscription.status = SubscriptionStatus.active
    if subscription.started_at is None:
        subscription.started_at = now

    await db.commit()
    await db.refresh(selection)
    return selection


@router.get("/selection", response_model=PlanSelectionOut | None)
async def read_selection(current_user: CurrentUser, db: DbSession) -> PlanSelection | None:
    """The member's current choice, or null if they have not chosen yet."""
    return await db.scalar(
        select(PlanSelection).where(
            PlanSelection.user_id == current_user.id,
            PlanSelection.is_current.is_(True),
        )
    )


@router.get("/selections", response_model=list[PlanSelectionOut])
async def read_selection_history(current_user: CurrentUser, db: DbSession):
    """Full history, newest first."""
    rows = (
        await db.scalars(
            select(PlanSelection)
            .where(PlanSelection.user_id == current_user.id)
            .order_by(PlanSelection.selected_at.desc())
        )
    ).all()
    return rows


@router.get("/subscription", response_model=SubscriptionOut)
async def read_subscription(db: DbSession, current_user: CurrentUser) -> Subscription:
    return await _subscription_for(db, current_user.id)


@router.post("/subscribe", response_model=SubscriptionOut)
async def subscribe(
    payload: SubscribeRequest,
    current_user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> Subscription:
    if payload.plan is PlanTier.early_access:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Early access does not need a subscription"
        )

    digits = re.sub(r"\D", "", payload.card_number)
    if not 12 <= len(digits) <= 19:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Card number looks wrong")

    subscription = await _subscription_for(db, current_user.id)
    subscription.plan = payload.plan
    subscription.status = SubscriptionStatus.active
    subscription.card_last4 = digits[-4:]  # never store the full number
    subscription.card_name = payload.card_name
    subscription.billing_country = payload.billing_country
    subscription.started_at = datetime.now(UTC)
    subscription.cancelled_at = None

    await db.commit()
    await db.refresh(subscription)

    plan_name = next(p["name"] for p in PLAN_CATALOGUE if p["id"] == payload.plan)
    background.add_task(
        email_service.send_subscription_confirmation,
        current_user.email, current_user.name, plan_name, PLAN_PRICES[payload.plan],
    )
    return subscription


@router.post("/cancel", response_model=Message)
async def cancel(db: DbSession, current_user: CurrentUser) -> Message:
    """Cancelling drops you back to early access.

    There is no billing period to run out during early access, so leaving the
    tier set to `member` with status `cancelled` would make the Plans screen
    keep showing Member as the current plan.
    """
    subscription = await _subscription_for(db, current_user.id)
    if subscription.plan is PlanTier.early_access:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is nothing to cancel")

    subscription.plan = PlanTier.early_access
    subscription.status = SubscriptionStatus.active
    subscription.cancelled_at = datetime.now(UTC)
    subscription.card_last4 = None
    subscription.card_name = None
    await db.commit()
    return Message(detail="Subscription cancelled — you are back on early access")
