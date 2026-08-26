"""The only module that talks to Stripe.

Two things it exists to guarantee:

  * **Nothing else imports `stripe`.** The SDK is optional at runtime — the app
    must boot and serve every non-billing route on a machine with no Stripe
    account — so the import happens inside `_api()` and a missing package or a
    missing key surfaces as a 503 BILLING_NOT_CONFIGURED, not an ImportError at
    startup.
  * **The SDK's blocking HTTP never runs on the event loop.** `stripe` is
    synchronous; every call here goes through `run_in_threadpool`.

No card details pass through this process. The browser sends them straight to
Stripe from the Checkout page, and what comes back is a token plus the last four
digits.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core import errors
from app.core.config import settings

logger = logging.getLogger(__name__)

# The Stripe API version this code was written against. Pinning it means a
# server-side upgrade at Stripe cannot silently change the shape of a webhook.
API_VERSION = "2024-06-20"


def is_configured() -> bool:
    return settings.stripe_enabled


def _api():
    """Import and configure the SDK, or refuse the call."""
    if not settings.stripe_enabled:
        raise errors.unavailable(
            errors.Code.BILLING_NOT_CONFIGURED,
            "Billing is not configured on this server. Set STRIPE_SECRET_KEY in "
            "backend/.env to enable it.",
        )
    try:
        import stripe
    except ModuleNotFoundError as exc:  # pragma: no cover - deployment slip
        raise errors.unavailable(
            errors.Code.BILLING_NOT_CONFIGURED,
            "The stripe package is not installed. Run: pip install -r requirements.txt",
        ) from exc

    stripe.api_key = settings.stripe_secret_key
    stripe.api_version = API_VERSION
    if settings.stripe_api_base:
        # stripe-mock only. Refused outright in production: a redirected api_base
        # means payments are being confirmed by something that is not Stripe.
        if settings.is_production:
            raise errors.unavailable(
                errors.Code.BILLING_NOT_CONFIGURED,
                "STRIPE_API_BASE is set in production. Unset it — billing must talk "
                "to Stripe itself.",
            )
        stripe.api_base = settings.stripe_api_base
    return stripe


async def _call(fn, *args, **kwargs):
    """Run one SDK call off the event loop, mapping its errors to ours."""
    stripe = _api()
    try:
        return await run_in_threadpool(lambda: fn(stripe)(*args, **kwargs))
    except stripe.error.StripeError as exc:
        # `user_message` is the only part Stripe intends an end user to read;
        # everything else can leak account internals into an API response.
        message = getattr(exc, "user_message", None) or "The payment provider rejected that."
        logger.error("Stripe call failed: %s", exc)
        raise errors.DomainError(
            errors.Code.BILLING_ERROR, message, status_code=502
        ) from exc


# --- Customers ------------------------------------------------------------

async def create_customer(*, email: str, name: str | None, user_id: str) -> dict:
    return await _call(
        lambda s: s.Customer.create,
        email=email,
        name=name or None,
        # Lets a Stripe-side human find the member, and lets a webhook that only
        # carries a customer id recover the account without a database lookup.
        metadata={"user_id": user_id},
    )


async def retrieve_customer(customer_id: str) -> dict:
    return await _call(lambda s: s.Customer.retrieve, customer_id)


# --- Checkout and portal --------------------------------------------------

async def create_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    user_id: str,
    plan: str,
    trial_days: int | None = None,
) -> dict:
    subscription_data: dict[str, Any] = {"metadata": {"user_id": user_id, "plan": plan}}
    if trial_days:
        subscription_data["trial_period_days"] = trial_days

    return await _call(
        lambda s: s.checkout.Session.create,
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        # Echoed back on checkout.session.completed, so the webhook knows who
        # and what without trusting anything the browser sent.
        client_reference_id=user_id,
        metadata={"user_id": user_id, "plan": plan},
        subscription_data=subscription_data,
        allow_promotion_codes=True,
    )


async def retrieve_checkout_session(session_id: str) -> dict:
    """Read back a Checkout Session, with its subscription expanded.

    Used on the success redirect. Stripe's webhook and the browser's return trip
    race each other, and the browser often wins — so the return page asks Stripe
    directly rather than trusting that the webhook has already been applied.
    """
    return await _call(
        lambda s: s.checkout.Session.retrieve,
        session_id,
        expand=["subscription", "subscription.default_payment_method", "customer"],
    )


async def create_portal_session(*, customer_id: str, return_url: str) -> dict:
    """Stripe's hosted billing portal — card updates, invoices, cancellation.

    Using it is why there is no card form, no invoice list UI and no PCI scope
    on our side.
    """
    return await _call(
        lambda s: s.billing_portal.Session.create,
        customer=customer_id,
        return_url=return_url,
    )


# --- Subscriptions --------------------------------------------------------

async def retrieve_subscription(subscription_id: str) -> dict:
    return await _call(
        lambda s: s.Subscription.retrieve,
        subscription_id,
        expand=["default_payment_method"],
    )


async def update_subscription_price(*, subscription_id: str, price_id: str) -> dict:
    """Move an existing subscription onto a different Price, with proration.

    The current item has to be named explicitly — passing only the new price
    would add a second line rather than replacing the first.
    """
    current = await retrieve_subscription(subscription_id)
    items = current.get("items", {}).get("data", [])
    if not items:
        raise errors.DomainError(
            errors.Code.BILLING_ERROR,
            "That subscription has no billable items.",
            status_code=502,
        )
    return await _call(
        lambda s: s.Subscription.modify,
        subscription_id,
        items=[{"id": items[0]["id"], "price": price_id}],
        proration_behavior="create_prorations",
        cancel_at_period_end=False,
    )


async def cancel_subscription(*, subscription_id: str, immediately: bool = False) -> dict:
    """Cancel at period end by default — they paid for the rest of the month."""
    if immediately:
        return await _call(lambda s: s.Subscription.cancel, subscription_id)
    return await _call(
        lambda s: s.Subscription.modify, subscription_id, cancel_at_period_end=True
    )


async def reactivate_subscription(subscription_id: str) -> dict:
    """Undo a cancel-at-period-end, while the period is still running."""
    return await _call(
        lambda s: s.Subscription.modify, subscription_id, cancel_at_period_end=False
    )


# --- Invoices -------------------------------------------------------------

async def list_invoices(*, customer_id: str, limit: int = 24) -> list[dict]:
    result = await _call(lambda s: s.Invoice.list, customer=customer_id, limit=limit)
    return list(result.get("data", []))


# --- Webhooks -------------------------------------------------------------

def construct_event(payload: bytes, signature: str | None) -> dict:
    """Verify the signature and return the event.

    Synchronous because it is pure local crypto — no HTTP. An unverified body is
    refused outright: this endpoint is public, and trusting it would let anyone
    grant themselves a Professional plan with one POST.
    """
    if not settings.stripe_webhook_secret:
        raise errors.unavailable(
            errors.Code.BILLING_NOT_CONFIGURED,
            "STRIPE_WEBHOOK_SECRET is not set, so webhook signatures cannot be verified.",
        )
    if not signature:
        raise errors.DomainError(
            errors.Code.WEBHOOK_SIGNATURE_INVALID,
            "Missing Stripe-Signature header.",
            status_code=400,
        )

    stripe = _api()
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except ValueError as exc:
        raise errors.DomainError(
            errors.Code.WEBHOOK_SIGNATURE_INVALID, "Malformed webhook body.", status_code=400
        ) from exc
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Rejected a webhook with a bad signature")
        raise errors.DomainError(
            errors.Code.WEBHOOK_SIGNATURE_INVALID,
            "Webhook signature verification failed.",
            status_code=400,
        ) from exc
    return event
