"""Subscription state, and the rules that move it.

backend_flow.md section 32: *Stripe is the billing source for paid subscription
state.* This module is where that is honoured. Nothing outside a webhook may set
a subscription to a paid tier — POST /billing/checkout-session only opens the
Checkout page, and the plan becomes real when Stripe says it did.

The one exception is Early Access, which is free and therefore has no Stripe
side at all; selecting it activates immediately (section 7.3).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.config import settings
from app.models import (
    AuditAction, BillingEvent, PlanSelection, PlanTier, SignupIntent, Subscription,
    SubscriptionStatus, User,
)
from app.services import audit
from app.services import stripe_client

logger = logging.getLogger(__name__)

#: Display prices, in whole dollars. The authoritative amount lives on the
#: Stripe Price; these are for the catalogue and the plan_selections audit row.
PLAN_PRICES: dict[PlanTier, str] = {
    PlanTier.early_access: "0",
    PlanTier.member: "25",
    PlanTier.professional: "100",
}

#: Human names for the tiers, used in plan-selection history rows and in the
#: prose of billing errors. Kept in step with `plan_catalogue.DEFAULT_COPY` and
#: with `plans.name` — three places, one vocabulary. The enum codes beside them
#: are what Stripe and the API key on and do not change.
PLAN_NAMES: dict[PlanTier, str] = {
    PlanTier.early_access: "Freemium",
    PlanTier.member: "Silver",
    PlanTier.professional: "Gold",
}

PAID_PLANS = (PlanTier.member, PlanTier.professional)

#: Cheapest first. Comparing indexes is how a downgrade is told from an upgrade.
PLAN_ORDER: list[PlanTier] = [PlanTier.early_access, PlanTier.member, PlanTier.professional]

#: Stripe's subscription statuses -> ours. Anything unrecognised is treated as
#: `incomplete`, which is *not* an entitled status — an unknown state must fail
#: closed rather than hand out a plan.
STRIPE_STATUS: dict[str, SubscriptionStatus] = {
    "active": SubscriptionStatus.active,
    "trialing": SubscriptionStatus.trialing,
    "past_due": SubscriptionStatus.past_due,
    "canceled": SubscriptionStatus.cancelled,
    "unpaid": SubscriptionStatus.unpaid,
    "incomplete": SubscriptionStatus.incomplete,
    "incomplete_expired": SubscriptionStatus.incomplete_expired,
    "paused": SubscriptionStatus.unpaid,
}

#: The events section 8 asks the webhook to handle.
HANDLED_EVENTS = frozenset({
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
})


# --------------------------------------------------------------------------
# Signup intents — backend_flow.md 7.1
# --------------------------------------------------------------------------

async def create_signup_intent(
    db: AsyncSession, plan: PlanTier, email: str | None = None
) -> SignupIntent:
    """Hold a plan choice made before the account exists.

    Section 7.1: *Do not rely only on a plan=member query parameter.* The id
    returned here is what signup carries, so the tier cannot be swapped by
    editing a URL.
    """
    intent = SignupIntent(
        plan=plan,
        email=(email or "").strip().lower() or None,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.signup_intent_ttl_minutes),
    )
    db.add(intent)
    await db.commit()
    await db.refresh(intent)
    return intent


async def read_signup_intent(db: AsyncSession, intent_id: uuid.UUID) -> SignupIntent:
    """Fetch a spendable intent, or refuse. Changes nothing."""
    intent = await db.get(SignupIntent, intent_id)
    if intent is None or not intent.is_spendable(datetime.now(UTC)):
        raise errors.unprocessable(
            errors.Code.SIGNUP_INTENT_INVALID,
            "That plan selection has expired or was already used. Choose a plan again.",
        )
    return intent


async def consume_signup_intent(
    db: AsyncSession, intent_id: uuid.UUID, user: User
) -> PlanTier:
    """Spend an intent for a freshly created account, returning its plan.

    Marking it consumed is a commit, so it must be the *last* step of whatever
    it authorises — see `activate_signup_intent`, which opens Stripe Checkout
    before spending the intent rather than after. An intent burned by a step
    that then failed would leave the member with no plan and no way to retry.
    """
    intent = await read_signup_intent(db, intent_id)
    intent.consumed_at = datetime.now(UTC)
    intent.user_id = user.id
    await db.commit()
    return intent.plan


async def purge_expired_intents(db: AsyncSession) -> int:
    """Housekeeping for section 26's 'cleanup of expired signup intents'."""
    result = await db.execute(
        update(SignupIntent)
        .where(
            SignupIntent.expires_at < datetime.now(UTC),
            SignupIntent.consumed_at.is_(None),
        )
        .values(consumed_at=datetime.now(UTC))
    )
    await db.commit()
    return result.rowcount or 0


# --------------------------------------------------------------------------
# The subscription row
# --------------------------------------------------------------------------

async def subscription_for(
    db: AsyncSession, user_id: uuid.UUID, *, commit: bool = True
) -> Subscription:
    """The member's subscription, created on early access if absent.

    `commit=False` is for callers that are inside a transaction they own — the
    webhook, above all. Committing there would end that transaction early and
    break the all-or-nothing guarantee section 27 asks for.
    """
    subscription = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    if subscription is None:
        subscription = Subscription(user_id=user_id, plan=PlanTier.early_access)
        db.add(subscription)
        if not commit:
            await db.flush()
            return subscription
        try:
            await db.commit()
        except IntegrityError:
            # Two first-time requests raced; user_id is unique, so re-read.
            await db.rollback()
            subscription = await db.scalar(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            if subscription is None:
                raise
            return subscription
        await db.refresh(subscription)
    return subscription


def _record_plan_selection(
    db: AsyncSession, user: User, plan: PlanTier, *, source: str
) -> None:
    """Append to the plan_selections history the pre-v1 screens already read."""
    db.add(PlanSelection(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        user_company=user.company,
        plan=plan,
        plan_name=PLAN_NAMES[plan],
        price_usd=float(PLAN_PRICES[plan]),
        billing_period="none" if plan is PlanTier.early_access else "monthly",
        selected_at=datetime.now(UTC),
        is_current=True,
        source=source,
    ))


async def _clear_current_selection(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(PlanSelection)
        .where(PlanSelection.user_id == user_id, PlanSelection.is_current.is_(True))
        .values(is_current=False)
    )


async def activate_free_plan(
    db: AsyncSession, user: User, *, source: str = "signup"
) -> Subscription:
    """Section 7.3 — Early Access activates with no payment step."""
    subscription = await subscription_for(db, user.id)
    subscription.plan = PlanTier.early_access
    subscription.status = SubscriptionStatus.active
    subscription.started_at = subscription.started_at or datetime.now(UTC)
    subscription.cancelled_at = None
    subscription.cancel_at_period_end = False

    await _clear_current_selection(db, user.id)
    _record_plan_selection(db, user, PlanTier.early_access, source=source)
    audit.record(
        db, AuditAction.PLAN_CHANGED, actor_user_id=user.id,
        entity_type="subscription", entity_id=subscription.id, plan="early_access",
    )
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def activate_signup_intent(
    db: AsyncSession, user: User, intent_id: uuid.UUID
) -> dict:
    """Spend a pre-signup plan choice on a newly created account — section 7.

    This is the join between "the visitor picked a tier on the pricing page" and
    "an account now exists". Which of the spec's two branches runs depends on
    the tier, and only on the tier:

        7.3  Early Access -> activate now, no Stripe involved
        7.4  Member / Professional -> create the Stripe customer, open Checkout,
             and grant *nothing*; the webhook does that when payment succeeds

    So a paid signup leaves the member on early access until Stripe confirms.
    That is deliberate — it is the only arrangement in which an abandoned or
    failed checkout cannot leave a paid plan switched on.
    """
    # Validated but *not* yet spent — see below.
    plan = (await read_signup_intent(db, intent_id)).plan

    if plan is PlanTier.early_access:
        subscription = await activate_free_plan(db, user)
        await consume_signup_intent(db, intent_id, user)
        return {
            "plan": plan,
            "status": subscription.status,
            "activated": True,
            "checkout_url": None,
        }

    # Paid: the account starts on early access and stays there until the
    # webhook lands. Recording the *choice* separately keeps the funnel
    # visible — who picked what, whether or not they went on to pay.
    await subscription_for(db, user.id)
    await _clear_current_selection(db, user.id)
    _record_plan_selection(db, user, plan, source="signup_intent")
    await db.commit()

    # Checkout first, then spend the intent. If Stripe is unreachable or
    # unconfigured this raises, the intent stays spendable, and the member can
    # simply try again — rather than losing their plan choice to an outage.
    checkout = await start_checkout(db, user, plan)
    await consume_signup_intent(db, intent_id, user)
    return {
        "plan": plan,
        "status": SubscriptionStatus.incomplete,
        "activated": False,
        "checkout_url": checkout["checkout_url"],
        "session_id": checkout["session_id"],
    }


# --------------------------------------------------------------------------
# Stripe: customer, checkout, portal
# --------------------------------------------------------------------------

async def ensure_customer(db: AsyncSession, user: User) -> str:
    """The member's Stripe customer id, created on first use."""
    subscription = await subscription_for(db, user.id)
    if subscription.stripe_customer_id:
        return subscription.stripe_customer_id

    customer = await stripe_client.create_customer(
        email=user.email, name=user.name, user_id=str(user.id)
    )
    subscription.stripe_customer_id = customer["id"]
    await db.commit()
    return customer["id"]


async def price_for_plan(db: AsyncSession, plan: PlanTier) -> str:
    """The Stripe Price id for a tier.

    The plan row wins over the environment, so a Price can be swapped in the
    database without a redeploy (backend_flow.md 6.2's spirit, applied to
    billing as well as to limits).
    """
    from app.services import plan_catalogue

    catalogue = await plan_catalogue.load(db)
    row = catalogue.plans.get(plan)
    price_id = (row.stripe_price_id if row else None) or settings.stripe_price_for(plan.value)
    if not price_id:
        raise errors.unavailable(
            errors.Code.BILLING_NOT_CONFIGURED,
            f"No Stripe Price is configured for the {PLAN_NAMES[plan]} plan. "
            f"Set STRIPE_PRICE_{plan.value.upper()} in backend/.env.",
        )
    return price_id


async def plan_for_price(db: AsyncSession, price_id: str) -> PlanTier | None:
    """The reverse map, checking the plan rows before the environment."""
    from app.services import plan_catalogue

    catalogue = await plan_catalogue.load(db)
    for code, row in catalogue.plans.items():
        if row.stripe_price_id and row.stripe_price_id == price_id:
            return code
    mapped = settings.stripe_plan_by_price.get(price_id or "")
    return PlanTier(mapped) if mapped else None


async def start_checkout(db: AsyncSession, user: User, plan: PlanTier) -> dict:
    """Open a Checkout Session. This grants nothing — the webhook does that."""
    if plan not in PAID_PLANS:
        raise errors.unprocessable(
            errors.Code.PLAN_UNKNOWN,
            "Early access is free and does not go through checkout.",
        )

    price_id = await price_for_plan(db, plan)
    customer_id = await ensure_customer(db, user)
    session = await stripe_client.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=(
            settings.frontend_link(settings.stripe_success_path)
            + "?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=settings.frontend_link(settings.stripe_cancel_path),
        user_id=str(user.id),
        plan=plan.value,
    )
    return {"checkout_url": session["url"], "session_id": session["id"]}


async def confirm_checkout(db: AsyncSession, user: User, session_id: str) -> dict:
    """Apply a finished Checkout Session on the browser's return trip.

    Stripe redirects the member back to the app the moment payment succeeds, and
    fires the webhook independently. Which arrives first is a race, and the
    redirect usually wins — so this exists to make the success page truthful
    rather than leaving it to poll and hope.

    It is not a shortcut around the webhook. It asks Stripe for the session,
    checks the session really belongs to *this* member, and then applies the
    same `apply_subscription` the webhook would. Both paths writing the same
    state from the same source is what makes running both safe: whichever lands
    second is a no-op, and the webhook remains the authority for everything that
    happens later (renewals, failures, cancellations).

    The ownership check is the security boundary. A session id is not a secret —
    it travels in a URL — so without it any member could paste someone else's
    session id and be granted their plan.
    """
    session = await stripe_client.retrieve_checkout_session(session_id)

    owner = (
        (session.get("metadata") or {}).get("user_id")
        or session.get("client_reference_id")
    )
    customer_id = _id_of(session.get("customer"))
    subscription = await subscription_for(db, user.id)

    belongs = str(user.id) in {str(owner or "")} or (
        customer_id is not None and customer_id == subscription.stripe_customer_id
    )
    if not belongs:
        logger.warning(
            "Member %s tried to confirm checkout session %s, which is not theirs",
            user.id, session_id,
        )
        raise errors.forbidden(
            errors.Code.COMMUNITY_ACCESS_DENIED,
            "That checkout session does not belong to this account.",
        )

    paid = session.get("payment_status") == "paid" or session.get("status") == "complete"
    stripe_sub = session.get("subscription")

    if not paid or not isinstance(stripe_sub, dict):
        # Still processing, or abandoned. Report it rather than guessing — some
        # payment methods settle asynchronously and the webhook will finish the
        # job when they do.
        return {
            "activated": False,
            "payment_status": session.get("payment_status") or "unpaid",
            "plan": subscription.plan,
            "status": subscription.status,
            "effective_plan": await entitlement_plan(db, user.id),
        }

    await apply_subscription(db, subscription, stripe_sub, user=user)
    await db.commit()
    await db.refresh(subscription)

    return {
        "activated": True,
        "payment_status": "paid",
        "plan": subscription.plan,
        "status": subscription.status,
        "effective_plan": await entitlement_plan(db, user.id),
    }


async def entitlement_plan(db: AsyncSession, user_id: uuid.UUID) -> PlanTier:
    from app.services import entitlements as ent

    return await ent.effective_plan(db, user_id)


async def start_portal(db: AsyncSession, user: User) -> dict:
    subscription = await subscription_for(db, user.id)
    if not subscription.stripe_customer_id:
        raise errors.unprocessable(
            errors.Code.SUBSCRIPTION_NOT_ACTIVE,
            "There is no billing account to manage yet.",
        )
    session = await stripe_client.create_portal_session(
        customer_id=subscription.stripe_customer_id,
        return_url=settings.frontend_link(settings.stripe_portal_return_path),
    )
    return {"portal_url": session["url"]}


async def change_plan(db: AsyncSession, user: User, plan: PlanTier) -> Subscription:
    """Move between paid tiers in place, with proration.

    The local row is not edited here. Stripe emits customer.subscription.updated
    for this change, and that webhook is what writes the new tier — one path to
    paid state instead of two that can disagree.
    """
    subscription = await subscription_for(db, user.id)
    if plan is PlanTier.early_access:
        return await cancel(db, user)
    if not subscription.stripe_subscription_id:
        raise errors.unprocessable(
            errors.Code.SUBSCRIPTION_NOT_ACTIVE,
            "There is no active subscription to change. Start one from checkout.",
        )
    if subscription.plan is plan and subscription.status in (
        SubscriptionStatus.active, SubscriptionStatus.trialing
    ):
        raise errors.conflict(
            errors.Code.CONFLICT, f"You are already on {PLAN_NAMES[plan]}."
        )

    await stripe_client.update_subscription_price(
        subscription_id=subscription.stripe_subscription_id,
        price_id=await price_for_plan(db, plan),
    )
    return subscription


async def cancel(db: AsyncSession, user: User) -> Subscription:
    """Cancel at period end. Entitlements last until Stripe says otherwise."""
    subscription = await subscription_for(db, user.id)
    if not subscription.stripe_subscription_id:
        # Nothing at Stripe to cancel — an early-access row, or a paid one that
        # never completed checkout. Drop it locally so the UI is truthful.
        if subscription.plan is PlanTier.early_access:
            raise errors.conflict(
                errors.Code.CONFLICT, "There is nothing to cancel."
            )
        subscription.plan = PlanTier.early_access
        subscription.status = SubscriptionStatus.active
        subscription.cancelled_at = datetime.now(UTC)
        await _clear_current_selection(db, user.id)
        _record_plan_selection(db, user, PlanTier.early_access, source="cancel")
        await db.commit()
        await db.refresh(subscription)
        return subscription

    await stripe_client.cancel_subscription(
        subscription_id=subscription.stripe_subscription_id
    )
    subscription.cancel_at_period_end = True
    audit.record(
        db, AuditAction.SUBSCRIPTION_CHANGED, actor_user_id=user.id,
        entity_type="subscription", entity_id=subscription.id, action_taken="cancel",
    )
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def reactivate(db: AsyncSession, user: User) -> Subscription:
    subscription = await subscription_for(db, user.id)
    if not subscription.stripe_subscription_id or not subscription.cancel_at_period_end:
        raise errors.conflict(
            errors.Code.CONFLICT, "There is no scheduled cancellation to undo."
        )
    await stripe_client.reactivate_subscription(subscription.stripe_subscription_id)
    subscription.cancel_at_period_end = False
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def list_invoices(db: AsyncSession, user: User) -> list[dict]:
    subscription = await subscription_for(db, user.id)
    if not subscription.stripe_customer_id:
        return []
    raw = await stripe_client.list_invoices(customer_id=subscription.stripe_customer_id)
    return [
        {
            "id": invoice.get("id"),
            "number": invoice.get("number"),
            "status": invoice.get("status"),
            "amount_due": invoice.get("amount_due"),
            "amount_paid": invoice.get("amount_paid"),
            "currency": invoice.get("currency"),
            "created": _as_datetime(invoice.get("created")),
            "hosted_invoice_url": invoice.get("hosted_invoice_url"),
            "invoice_pdf": invoice.get("invoice_pdf"),
        }
        for invoice in raw
    ]


# --------------------------------------------------------------------------
# Reading a Stripe subscription onto our row
# --------------------------------------------------------------------------

def _as_datetime(unix: int | None) -> datetime | None:
    return datetime.fromtimestamp(unix, tz=UTC) if unix else None


def _first_item(stripe_sub: dict) -> dict:
    items = (stripe_sub.get("items") or {}).get("data") or []
    return items[0] if items else {}


async def plan_from_subscription(db: AsyncSession, stripe_sub: dict) -> PlanTier | None:
    """Which tier a Stripe subscription represents, by its Price id."""
    item = _first_item(stripe_sub)
    price_id = (item.get("price") or {}).get("id")
    plan = await plan_for_price(db, price_id or "")
    if plan is not None:
        return plan
    # A Price that is live at Stripe but mapped nowhere would otherwise silently
    # downgrade a paying member, so say so loudly and change nothing.
    logger.error(
        "Stripe subscription %s uses price %s, which no plan row or STRIPE_PRICE_* "
        "setting maps. The member's tier cannot be resolved.",
        stripe_sub.get("id"), price_id,
    )
    return None


def _period_end(stripe_sub: dict) -> datetime | None:
    """Recent API versions moved current_period_end onto the item."""
    if stripe_sub.get("current_period_end"):
        return _as_datetime(stripe_sub["current_period_end"])
    return _as_datetime(_first_item(stripe_sub).get("current_period_end"))


async def apply_subscription(
    db: AsyncSession, subscription: Subscription, stripe_sub: dict, *, user: User | None = None
) -> Subscription:
    """Write a Stripe subscription object onto the local row.

    The single place paid state is set. Called only from webhook handling.
    """
    status = STRIPE_STATUS.get(stripe_sub.get("status", ""), SubscriptionStatus.incomplete)
    plan = await plan_from_subscription(db, stripe_sub)
    previous_plan = subscription.plan

    subscription.stripe_subscription_id = stripe_sub.get("id")
    subscription.stripe_price_id = (_first_item(stripe_sub).get("price") or {}).get("id")
    subscription.status = status
    subscription.current_period_end = _period_end(stripe_sub)
    subscription.cancel_at_period_end = bool(stripe_sub.get("cancel_at_period_end"))
    if stripe_sub.get("customer"):
        subscription.stripe_customer_id = _id_of(stripe_sub["customer"])

    if status in (SubscriptionStatus.cancelled, SubscriptionStatus.incomplete_expired):
        # The subscription is over: drop to the free tier so entitlements and
        # the Plans screen both stop showing a paid plan.
        subscription.plan = PlanTier.early_access
        subscription.cancelled_at = _as_datetime(stripe_sub.get("canceled_at")) or datetime.now(UTC)
        subscription.stripe_subscription_id = None
    elif plan is not None:
        subscription.plan = plan
        subscription.started_at = (
            subscription.started_at or _as_datetime(stripe_sub.get("start_date"))
            or datetime.now(UTC)
        )
        subscription.cancelled_at = None

    _apply_card_summary(subscription, stripe_sub)

    if user is not None and subscription.plan is not previous_plan:
        await _clear_current_selection(db, user.id)
        _record_plan_selection(db, user, subscription.plan, source="stripe")
        audit.record(
            db, AuditAction.PLAN_CHANGED, actor_user_id=user.id,
            entity_type="subscription", entity_id=subscription.id,
            plan=subscription.plan, previous_plan=previous_plan, status=status,
        )
        # Section 32: bring resources within the new plan by archiving and
        # locking, never by deleting. Runs on any move down the order, whether
        # that is a deliberate downgrade or a cancellation.
        if PLAN_ORDER.index(subscription.plan) < PLAN_ORDER.index(previous_plan):
            await apply_downgrade(db, user, to_plan=subscription.plan, commit=False)
    return subscription


def _id_of(value) -> str | None:
    """Stripe returns a related object either expanded or as a bare id string."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id")
    return None


def _apply_card_summary(subscription: Subscription, stripe_sub: dict) -> None:
    """Store the last four and brand, if the payment method came expanded.

    This is display data only. The card number itself never reaches this
    process — the browser sends it to Stripe directly from the Checkout page.
    """
    method = stripe_sub.get("default_payment_method")
    if not isinstance(method, dict):
        return
    card = method.get("card") or {}
    if card.get("last4"):
        subscription.card_last4 = card["last4"]
        subscription.card_brand = card.get("brand")
    billing = (method.get("billing_details") or {})
    if billing.get("name"):
        subscription.card_name = billing["name"]
    country = (billing.get("address") or {}).get("country")
    if country:
        subscription.billing_country = country


# --------------------------------------------------------------------------
# Webhook processing — sections 8 and 27
# --------------------------------------------------------------------------

async def _user_for_event(db: AsyncSession, obj: dict) -> tuple[User | None, Subscription | None]:
    """Find the account an event belongs to.

    Three routes, cheapest first: our own metadata, then the customer id we
    stored at checkout, then the customer's metadata at Stripe.

    Runs inside the caller's transaction, so it never commits.
    """
    user_id = (obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id")
    if user_id:
        try:
            user = await db.get(User, uuid.UUID(str(user_id)))
        except ValueError:
            user = None
        if user is not None:
            return user, await subscription_for(db, user.id, commit=False)

    customer_id = _id_of(obj.get("customer"))
    if customer_id:
        subscription = await db.scalar(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        if subscription is not None:
            return await db.get(User, subscription.user_id), subscription

        # Never seen this customer — ask Stripe who it is before giving up. This
        # is a last-resort identity hint, so a failure here means "cannot
        # identify", not "retry": the metadata will not appear later either.
        try:
            customer = await stripe_client.retrieve_customer(customer_id)
        except errors.DomainError as exc:
            logger.warning("Could not look up Stripe customer %s: %s", customer_id, exc)
            return None, None
        meta_id = (customer.get("metadata") or {}).get("user_id")
        if meta_id:
            try:
                user = await db.get(User, uuid.UUID(str(meta_id)))
            except ValueError:
                user = None
            if user is not None:
                return user, await subscription_for(db, user.id, commit=False)

    return None, None


async def process_event(db: AsyncSession, event: dict) -> str:
    """Apply one verified Stripe event, exactly once.

    Section 27: validate, check idempotency, record the event, update the
    subscription and commit — **one transaction**. The ledger insert is flushed
    rather than committed, so the unique index on `stripe_event_id` still
    rejects a concurrent second delivery, while a failure part-way through rolls
    the claim back along with everything else.

    That last part is the whole point. Claiming the event id in its own
    committed transaction would mean a mid-processing failure leaves the claim
    behind: Stripe retries, sees a duplicate, skips — and a payment that was
    taken is never applied. Rolling back together makes the retry a clean first
    attempt.
    """
    event_id = event.get("id") or ""
    event_type = event.get("type") or ""

    ledger = BillingEvent(
        stripe_event_id=event_id,
        event_type=event_type,
        payload=_trimmed(event),
    )
    db.add(ledger)
    try:
        # Flush, not commit: this claims the id within the open transaction.
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info("Stripe event %s already processed — ignoring the redelivery", event_id)
        return "duplicate"

    try:
        if event_type not in HANDLED_EVENTS:
            outcome = "ignored"
        else:
            obj = (event.get("data") or {}).get("object") or {}
            outcome = await _apply_event(db, event_type, obj, ledger)

        ledger.processed_at = datetime.now(UTC)
        if outcome == "applied":
            audit.record(
                db, AuditAction.BILLING_EVENT_PROCESSED, actor_user_id=ledger.user_id,
                entity_type="billing_event", entity_id=ledger.id, event_type=event_type,
            )
        await db.commit()
    except Exception:
        # Undo the claim with the rest, then let it out so the endpoint answers
        # 5xx and Stripe retries into a clean slate.
        await db.rollback()
        logger.exception("Failed to apply Stripe event %s (%s)", event_id, event_type)
        raise
    return outcome


def _trimmed(event: dict) -> dict:
    """Keep the event without the parts that are large and of no later use."""
    return {
        "id": event.get("id"),
        "type": event.get("type"),
        "created": event.get("created"),
        "livemode": event.get("livemode"),
        "data": event.get("data"),
    }


async def _apply_event(
    db: AsyncSession, event_type: str, obj: dict, ledger: BillingEvent
) -> str:
    user, subscription = await _user_for_event(db, obj)
    if user is None or subscription is None:
        # Not ours — another integration on the same account, or a customer
        # deleted here. Acknowledge so Stripe stops retrying.
        ledger.error = "No matching Deal Network account"
        logger.warning("Stripe %s had no matching account", event_type)
        return "unmatched"

    ledger.user_id = user.id

    if event_type == "checkout.session.completed":
        subscription_id = _id_of(obj.get("subscription"))
        if not subscription_id:
            ledger.error = "Checkout session carried no subscription"
            return "ignored"
        stripe_sub = await stripe_client.retrieve_subscription(subscription_id)
        await apply_subscription(db, subscription, stripe_sub, user=user)
        return "applied"

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        if event_type == "customer.subscription.deleted":
            # The object in a delete event already reads `canceled`.
            obj = {**obj, "status": "canceled"}
        await apply_subscription(db, subscription, obj, user=user)
        return "applied"

    if event_type == "invoice.paid":
        # Dunning succeeded. Re-read rather than trusting the invoice, so the
        # tier and period come from the subscription itself.
        subscription_id = _id_of(obj.get("subscription")) or subscription.stripe_subscription_id
        if subscription_id:
            stripe_sub = await stripe_client.retrieve_subscription(subscription_id)
            await apply_subscription(db, subscription, stripe_sub, user=user)
        return "applied"

    if event_type == "invoice.payment_failed":
        # Stripe drives the status itself via customer.subscription.updated;
        # this event exists so the member can be told.
        subscription.status = SubscriptionStatus.past_due
        return "applied"

    return "ignored"


async def owned_community_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """How many communities occupy a slot — see communities.owned_count."""
    from app.services.communities import owned_count

    return await owned_count(db, user_id)


# --------------------------------------------------------------------------
# Downgrades — backend_flow.md section 32
# --------------------------------------------------------------------------
#
#   "Downgrades archive/lock over-limit resources instead of silently deleting
#    data."
#
# Two distinct things can go over on a downgrade, and they are handled
# differently because one is a count and the other is a capability:
#
#   * too many communities  -> archive the excess (reversible, keeps the data)
#   * a visibility or join policy the new plan cannot use -> lock it back to
#     something the plan does allow, rather than archiving a working community
#
# Nothing is ever deleted, and the member keeps everything on re-upgrade: an
# archived community is restored with POST /communities/{id}/restore.

async def apply_downgrade(
    db: AsyncSession, user: User, *, to_plan: PlanTier, commit: bool = True
) -> dict:
    """Bring a member's resources within a plan they have just dropped to.

    Returns a summary of what changed, which the caller can log or email.
    Called from webhook handling, inside that transaction, with commit=False.
    """
    from app.models import Community, CommunityStatus, JoinPolicy, VisibilityLevel
    from app.services import communities as community_service
    from app.services import entitlements as ent
    from app.services.entitlements import Limit

    summary: dict = {"archived": [], "relaxed": [], "plan": to_plan.value}

    # Everything that still exists, archived included. An archived community is
    # dormant, not gone: leaving a private one private would let a later
    # restore reintroduce a setting the plan does not carry.
    everything = (await db.scalars(
        select(Community)
        .where(
            Community.owner_id == user.id,
            Community.status != CommunityStatus.deleted,
        )
        # Oldest first: the ones kept are the ones they have had longest, which
        # is the least surprising rule and is deterministic.
        .order_by(Community.created_at, Community.id)
    )).all()
    owned = [c for c in everything if c.status is CommunityStatus.active]

    # --- Capability: a visibility or policy the new plan cannot use ----------
    for community in everything:
        feature = community_service.VISIBILITY_FEATURE.get(community.visibility)
        if feature and not await ent.plan_has_feature(db, to_plan, feature):
            community.visibility = VisibilityLevel.public
            summary["relaxed"].append({
                "community_id": str(community.id),
                "field": "visibility",
                "to": VisibilityLevel.public.value,
            })
            audit.record(
                db, AuditAction.COMMUNITY_UPDATED, actor_user_id=user.id,
                community_id=community.id, entity_type="community",
                entity_id=community.id, reason="downgrade", field="visibility",
            )

        policy_feature = community_service.JOIN_POLICY_FEATURE.get(community.join_policy)
        if policy_feature and not await ent.plan_has_feature(db, to_plan, policy_feature):
            community.join_policy = JoinPolicy.open
            summary["relaxed"].append({
                "community_id": str(community.id),
                "field": "join_policy",
                "to": JoinPolicy.open.value,
            })
            audit.record(
                db, AuditAction.COMMUNITY_UPDATED, actor_user_id=user.id,
                community_id=community.id, entity_type="community",
                entity_id=community.id, reason="downgrade", field="join_policy",
            )

    # --- Count: more communities than the new plan allows --------------------
    ceiling = await ent.limit_of(db, to_plan, Limit.COMMUNITY_MAX_OWNED)
    if ceiling is not None and len(owned) > ceiling:
        now = datetime.now(UTC)
        # Archive the newest ones; keep the oldest `ceiling`.
        for community in owned[ceiling:]:
            community.status = CommunityStatus.archived
            community.archived_at = now
            summary["archived"].append({
                "community_id": str(community.id), "name": community.name,
            })
            audit.record(
                db, AuditAction.COMMUNITY_ARCHIVED, actor_user_id=user.id,
                community_id=community.id, entity_type="community",
                entity_id=community.id, reason="downgrade", to_plan=to_plan.value,
            )

    if summary["archived"] or summary["relaxed"]:
        logger.info(
            "Downgrade to %s for %s: archived %d, relaxed %d",
            to_plan.value, user.email, len(summary["archived"]), len(summary["relaxed"]),
        )
    if commit:
        await db.commit()
    return summary


async def over_limit_report(db: AsyncSession, user: User) -> dict:
    """What is currently over the member's plan, without changing anything.

    Lets the Plans screen warn "downgrading will archive 4 communities" before
    the member commits to it.
    """
    from app.models import Community, CommunityStatus
    from app.services import entitlements as ent
    from app.services.entitlements import Limit

    plan = await ent.effective_plan(db, user.id)
    ceiling = await ent.limit_of(db, plan, Limit.COMMUNITY_MAX_OWNED)
    active = await db.scalar(
        select(func.count(Community.id)).where(
            Community.owner_id == user.id,
            Community.status == CommunityStatus.active,
        )
    ) or 0
    return {
        "plan": plan.value,
        "communities_active": active,
        "communities_limit": ceiling,
        "communities_over": max(0, active - ceiling) if ceiling is not None else 0,
    }
