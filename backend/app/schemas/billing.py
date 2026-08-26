"""Billing schemas — backend_flow.md section 8.

There is no card field anywhere in this module, and that is the point. Card
details go from the browser to Stripe's hosted Checkout page directly; this API
never receives, validates or stores a card number.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.base import PlanTier, SubscriptionStatus
from app.schemas.common import ORMModel


class PlanFeatureOut(BaseModel):
    key: str
    label: str
    included: bool


class BillingPlanOut(BaseModel):
    """One row of the price list, with what it unlocks."""

    code: PlanTier
    name: str
    price: str
    currency: str = "usd"
    interval: str | None = None
    description: str
    featured: bool = False
    # Section 6: the entitlements are what the client greys out against.
    features: dict[str, bool]
    limits: dict[str, int | None]
    max_phase: int
    # False when this tier has no Stripe Price configured yet, so the pricing
    # page can disable its button rather than opening a checkout that 503s.
    purchasable: bool = True


class SignupIntentCreate(BaseModel):
    plan_code: PlanTier
    email: EmailStr | None = None


class SignupIntentOut(ORMModel):
    signup_intent_id: uuid.UUID = Field(validation_alias="id")
    plan_code: PlanTier = Field(validation_alias="plan")
    expires_at: datetime


class SubscriptionOut(ORMModel):
    plan: PlanTier
    status: SubscriptionStatus
    # The plan whose entitlements actually apply — see entitlements.effective_plan.
    # Differs from `plan` while a payment is failing.
    effective_plan: PlanTier | None = None
    started_at: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    cancelled_at: datetime | None = None
    card_last4: str | None = None
    card_brand: str | None = None
    billing_country: str | None = None
    # Stripe ids are deliberately not exposed to the browser.


class CheckoutSessionCreate(BaseModel):
    plan_code: PlanTier


class CheckoutSessionOut(BaseModel):
    checkout_url: str
    session_id: str


class PortalSessionOut(BaseModel):
    portal_url: str


class ConfirmCheckoutRequest(BaseModel):
    # Stripe puts this in the success URL as ?session_id=cs_…
    session_id: str = Field(min_length=8, max_length=200)


class CheckoutConfirmOut(BaseModel):
    """The answer the success page renders.

    `activated` false with `payment_status` "unpaid" means the payment has not
    settled yet and the webhook will finish it — not that anything went wrong.
    """

    activated: bool
    payment_status: str
    plan: PlanTier
    status: SubscriptionStatus
    effective_plan: PlanTier


class ChangePlanRequest(BaseModel):
    plan_code: PlanTier


class InvoiceOut(BaseModel):
    id: str | None = None
    number: str | None = None
    status: str | None = None
    amount_due: int | None = None
    amount_paid: int | None = None
    currency: str | None = None
    created: datetime | None = None
    hosted_invoice_url: str | None = None
    invoice_pdf: str | None = None


class ActivateSignupRequest(BaseModel):
    signup_intent_id: uuid.UUID


class ActivationOut(BaseModel):
    """What happened when a pre-signup plan choice was spent.

    `activated` is the field that matters: false means the tier is *not* live
    and the browser must complete `checkout_url` first.
    """

    plan: PlanTier
    status: SubscriptionStatus
    activated: bool
    checkout_url: str | None = None
    session_id: str | None = None


class OverLimitOut(BaseModel):
    plan: PlanTier
    communities_active: int
    # None means unlimited.
    communities_limit: int | None = None
    communities_over: int = 0


class EntitlementsOut(BaseModel):
    """What the member's tier grants right now.

    `limits` is the effective ceiling — the plan's, raised by any add-on the
    member holds — and `base_limits` is the plan's own figure, so a client can
    tell the two apart. See `services/entitlements.snapshot`.
    """

    plan: PlanTier
    features: dict[str, bool]
    limits: dict[str, int | None]
    base_limits: dict[str, int | None] = {}
    addons: list[dict] = []


class WebhookAck(BaseModel):
    received: bool = True
    outcome: str
