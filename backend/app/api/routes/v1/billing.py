"""Billing endpoints — backend_flow.md section 8.

Three access levels, and the split matters:

  * `public_router`  — the price list and the pre-signup plan choice. No account
                       exists yet at this point in the flow (section 7.1).
  * `router`         — everything about *your* subscription. Signed in.
  * `webhook_router` — Stripe only. No bearer token; the Stripe signature is the
                       authentication, and an unsigned request is refused.

Paid state is never set here. POST /checkout-session opens Stripe's page and
returns a URL; the plan becomes real when the webhook says Stripe took the
money (section 32).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core import errors
from app.core.config import settings
from app.models import PlanTier
from app.schemas.billing import (
    ActivateSignupRequest, ActivationOut, BillingPlanOut, ChangePlanRequest,
    CheckoutConfirmOut, CheckoutSessionCreate, CheckoutSessionOut, ConfirmCheckoutRequest,
    EntitlementsOut, InvoiceOut, OverLimitOut, PortalSessionOut, SignupIntentCreate,
    SignupIntentOut, SubscriptionOut, WebhookAck,
)
from app.services import billing as billing_service
from app.services import entitlements as ent
from app.services import plan_catalogue
from app.services import stripe_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])
public_router = APIRouter(prefix="/billing", tags=["billing"])
webhook_router = APIRouter(prefix="/billing", tags=["billing"])

async def _plan_row(db: DbSession, plan: PlanTier) -> BillingPlanOut:
    """One row of the price list, read from the configured catalogue."""
    catalogue = await plan_catalogue.load(db)
    row = catalogue.plans[plan]
    paid = plan is not PlanTier.early_access
    return BillingPlanOut(
        code=plan,
        name=row.name,
        price=row.price,
        currency=row.currency,
        interval=row.interval,
        description=row.description,
        featured=row.featured,
        features=await ent.features_of(db, plan),
        limits=await ent.limits_of(db, plan),
        max_phase=row.max_phase,
        # Early access needs no Stripe Price; a paid tier without one cannot be
        # bought, and the pricing page should say so rather than 503 on click.
        purchasable=(not paid) or bool(
            row.stripe_price_id or settings.stripe_price_for(plan.value)
        ),
    )


# --------------------------------------------------------------------------
# Public — the pricing page and the pre-signup choice
# --------------------------------------------------------------------------

@public_router.get("/plans", response_model=list[BillingPlanOut])
async def list_plans(db: DbSession) -> list[BillingPlanOut]:
    """The price list. Readable without an account — it is the pricing page."""
    return [await _plan_row(db, plan) for plan in ent.PLAN_ORDER]


@public_router.get("/plans/{plan_code}", response_model=BillingPlanOut)
async def read_plan(plan_code: PlanTier, db: DbSession) -> BillingPlanOut:
    return await _plan_row(db, plan_code)


@public_router.post(
    "/signup-intent", response_model=SignupIntentOut, status_code=status.HTTP_201_CREATED
)
async def create_signup_intent(payload: SignupIntentCreate, db: DbSession) -> SignupIntentOut:
    """Section 7.1 — hold the chosen plan server-side before the account exists.

    The returned id is what signup carries, so the tier a new account gets is
    the one that was actually clicked and not whatever a query string claims.
    """
    intent = await billing_service.create_signup_intent(db, payload.plan_code, payload.email)
    return SignupIntentOut.model_validate(intent)


# --------------------------------------------------------------------------
# Authenticated — your own subscription
# --------------------------------------------------------------------------

async def _subscription_out(db: DbSession, user) -> SubscriptionOut:
    subscription = await billing_service.subscription_for(db, user.id)
    out = SubscriptionOut.model_validate(subscription)
    out.effective_plan = await ent.effective_plan(db, user.id)
    return out


@router.post("/activate-signup", response_model=ActivationOut)
async def activate_signup(
    payload: ActivateSignupRequest, db: DbSession, current_user: CurrentUser
) -> ActivationOut:
    """Spend the plan chosen before signing up — backend_flow.md section 7.

    Early Access activates here and now (7.3). Member and Professional get a
    Stripe customer and a Checkout URL, and are granted **nothing** until the
    webhook confirms payment (7.4) — so `activated` comes back false with a
    `checkout_url` to send the browser to.
    """
    result = await billing_service.activate_signup_intent(
        db, current_user, payload.signup_intent_id
    )
    return ActivationOut(**result)


@router.get("/subscription", response_model=SubscriptionOut)
async def read_subscription(db: DbSession, current_user: CurrentUser) -> SubscriptionOut:
    return await _subscription_out(db, current_user)


@router.get("/downgrade-preview", response_model=OverLimitOut)
async def downgrade_preview(db: DbSession, current_user: CurrentUser) -> OverLimitOut:
    """What is currently over the member's plan ceiling, changing nothing.

    Lets the Plans screen say "downgrading archives 4 communities" before the
    member commits, rather than surprising them afterwards.
    """
    return OverLimitOut(**await billing_service.over_limit_report(db, current_user))


@router.get("/entitlements", response_model=EntitlementsOut)
async def read_entitlements(db: DbSession, current_user: CurrentUser) -> EntitlementsOut:
    """What this member's plan unlocks right now, keyed as in section 6.1."""
    return EntitlementsOut(**await ent.snapshot(db, current_user.id))


@router.post("/checkout-session", response_model=CheckoutSessionOut)
async def create_checkout_session(
    payload: CheckoutSessionCreate, db: DbSession, current_user: CurrentUser
) -> CheckoutSessionOut:
    """Open Stripe Checkout for a paid tier.

    Returns a URL for the browser to visit. Nothing is granted here — see the
    webhook below.
    """
    if payload.plan_code is PlanTier.early_access:
        # Free tier: activate it directly rather than opening a checkout for $0.
        await billing_service.activate_free_plan(db, current_user)
        raise errors.unprocessable(
            errors.Code.PLAN_UNKNOWN,
            "Early access is free — it has been activated, with no checkout needed.",
        )
    result = await billing_service.start_checkout(db, current_user, payload.plan_code)
    return CheckoutSessionOut(**result)


@router.post("/confirm-checkout", response_model=CheckoutConfirmOut)
async def confirm_checkout(
    payload: ConfirmCheckoutRequest, db: DbSession, current_user: CurrentUser
) -> CheckoutConfirmOut:
    """Finish a Checkout Session on the return redirect.

    Stripe sends the browser back to `STRIPE_SUCCESS_PATH?session_id=…` as soon
    as payment clears, and fires the webhook separately. This lets the success
    page report the truth immediately instead of polling: it asks Stripe for the
    session, refuses one that is not this member's, and applies the same state
    the webhook would.

    `activated: false` is a normal answer, not an error — some payment methods
    settle asynchronously, and the webhook completes those.
    """
    result = await billing_service.confirm_checkout(
        db, current_user, payload.session_id
    )
    return CheckoutConfirmOut(**result)


@router.post("/portal-session", response_model=PortalSessionOut)
async def create_portal_session(db: DbSession, current_user: CurrentUser) -> PortalSessionOut:
    """Stripe's hosted billing portal — card changes, invoices, cancellation."""
    return PortalSessionOut(**await billing_service.start_portal(db, current_user))


@router.post("/change-plan", response_model=SubscriptionOut)
async def change_plan(
    payload: ChangePlanRequest, db: DbSession, current_user: CurrentUser
) -> SubscriptionOut:
    """Upgrade or downgrade in place, prorated.

    The response still shows the old tier: Stripe confirms the change through
    customer.subscription.updated moments later, and that webhook is what
    rewrites the local row.
    """
    await billing_service.change_plan(db, current_user, payload.plan_code)
    return await _subscription_out(db, current_user)


@router.post("/cancel", response_model=SubscriptionOut)
async def cancel(db: DbSession, current_user: CurrentUser) -> SubscriptionOut:
    """Cancel at the end of the paid period — access lasts until then."""
    await billing_service.cancel(db, current_user)
    return await _subscription_out(db, current_user)


@router.post("/reactivate", response_model=SubscriptionOut)
async def reactivate(db: DbSession, current_user: CurrentUser) -> SubscriptionOut:
    await billing_service.reactivate(db, current_user)
    return await _subscription_out(db, current_user)


@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices(db: DbSession, current_user: CurrentUser) -> list[InvoiceOut]:
    if not stripe_client.is_configured():
        return []
    rows = await billing_service.list_invoices(db, current_user)
    return [InvoiceOut(**row) for row in rows]


# --------------------------------------------------------------------------
# Stripe webhook — sections 8 and 27
# --------------------------------------------------------------------------

@webhook_router.post("/webhook", response_model=WebhookAck)
async def stripe_webhook(request: Request, db: DbSession) -> WebhookAck:
    """Apply a Stripe event, exactly once.

    The raw body is required — `construct_event` verifies a signature over the
    exact bytes, so re-serialising a parsed dict would fail verification.

    Answering non-2xx makes Stripe retry, so the only failures reported that way
    are ones a retry could fix. A duplicate delivery, an event type we ignore,
    or an event for an account that is not ours all answer 200.
    """
    payload = await request.body()
    event = stripe_client.construct_event(payload, request.headers.get("stripe-signature"))
    outcome = await billing_service.process_event(db, event)
    return WebhookAck(outcome=outcome)
