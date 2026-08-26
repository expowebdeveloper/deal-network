"""The entitlement surface: what my tier grants, and may I do this.

community_role_and_subs.md section 17 asks for an `entitlements/` group, and
section 16 asks that a cap-hit prompt reach an upgrade or an add-on purchase in
two clicks or fewer. That second requirement is why `POST /check` exists: the
SPA can ask before it acts, get the same decision the write path would have
made, and render the prompt without provoking an error first.

Nothing here grants anything. Holding an add-on raises a ceiling, so it is
created by the billing layer once a payment is confirmed — never by a request
from the member who would benefit. There is deliberately no `POST /addons`.

Read-only, and cheap: every endpoint resolves the flow's context once
(`entitlements.resolve`) and answers from it.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core import errors
from app.schemas.entitlements import (
    AddonCatalogueRowOut, DecisionOut, DecisionRequest, EntitlementSnapshotOut,
    UsageReportOut,
)
from app.services import addons as addon_service
from app.services import entitlements as ent

router = APIRouter(prefix="/entitlements", tags=["entitlements"])


def _decision_out(decision: ent.Decision) -> DecisionOut:
    return DecisionOut(
        allowed=decision.allowed,
        action=decision.action,
        domain=decision.domain,
        entitlement_key=decision.entitlement_key,
        reason=decision.reason,
        message=decision.message,
        current_usage=decision.current_usage,
        limit=decision.limit,
        base_limit=decision.base_limit,
        addon_grant=decision.addon_grant,
        remaining=decision.remaining,
        unit=decision.unit,
        current_plan=decision.current_plan,
        upgrade_plan=decision.upgrade_plan,
        upgrade_available=decision.upgrade_available,
        addon_available=decision.addon_available,
        addon_options=list(decision.addon_options),
        enforced=decision.enforced,
    )


@router.get("", response_model=EntitlementSnapshotOut)
async def read_snapshot(db: DbSession, current_user: CurrentUser) -> EntitlementSnapshotOut:
    """Every feature and ceiling that applies to me right now.

    The ceilings are effective — the plan's, raised by whatever add-ons I hold.
    """
    return EntitlementSnapshotOut(**await ent.snapshot(db, current_user.id))


@router.get("/usage", response_model=UsageReportOut)
async def read_usage(db: DbSession, current_user: CurrentUser) -> UsageReportOut:
    """Ceiling, usage and what is left, for every key this deployment counts.

    Keys with no counter are absent rather than reported as zero — see
    `services/usage.py`.
    """
    return UsageReportOut(**await ent.usage_report(db, current_user.id))


@router.get("/actions", response_model=dict[str, DecisionOut])
async def read_actions(db: DbSession, current_user: CurrentUser) -> dict[str, DecisionOut]:
    """Every gated action, decided for me — one call, so the UI can grey out.

    Per-community ceilings appear here without a community in hand, so their
    usage is unmeasurable and they come back `enforced: false`. Ask about a
    specific community with `POST /check`.
    """
    context = await ent.resolve(db, current_user.id)
    return {
        name: _decision_out(
            await ent.decide(db, current_user.id, action, context=context)
        )
        for name, action in ent.ACTIONS.items()
    }


@router.post("/check", response_model=DecisionOut)
async def check_action(
    payload: DecisionRequest, db: DbSession, current_user: CurrentUser
) -> DecisionOut:
    """Would this action be allowed? The same decision the write path makes.

    Answers 200 either way: this is a question, not an attempt, so a refusal is
    a result rather than an error. Attempting the action itself is what returns
    403 with the same payload in `details`.
    """
    try:
        action = ent.action_for(payload.action)
    except KeyError as exc:
        raise errors.unprocessable(
            errors.Code.VALIDATION_FAILED,
            f"Unknown entitlement action: {payload.action!r}",
            known_actions=sorted(ent.ACTIONS),
        ) from exc

    decision = await ent.decide(
        db, current_user.id, action,
        amount=payload.amount,
        community_id=payload.community_id,
    )
    return _decision_out(decision)


@router.get("/addons", response_model=list[AddonCatalogueRowOut])
async def read_addons(
    db: DbSession, current_user: CurrentUser
) -> list[AddonCatalogueRowOut]:
    """The add-ons purchasable on my plan, and which I already hold.

    An add-on with no price on this tier is left out: offering something that
    cannot be bought is the same bug as blocking without saying why.
    """
    context = await ent.resolve(db, current_user.id)
    catalogue = await addon_service.load(db)
    held = {holding.code: holding.quantity for holding in context.holdings}

    rows: list[AddonCatalogueRowOut] = []
    for addon in catalogue.ordered():
        price = addon.price_for(context.plan)
        if price is None:
            continue
        rows.append(AddonCatalogueRowOut(
            code=addon.code,
            name=addon.name,
            description=addon.description,
            unit=addon.unit,
            max_quantity=addon.max_quantity,
            effects={effect.key: effect.amount for effect in addon.effects},
            price_usd=price.price_usd,
            currency=price.currency,
            interval=price.billing_interval,
            owned=addon.code in held,
            owned_quantity=held.get(addon.code, 0),
        ))
    return rows
