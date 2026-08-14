"""Contact, introduction request and plan schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.base import ContactStage, IntroStatus, MemberRole, PlanTier, SubscriptionStatus
from app.schemas.common import ORMModel
from app.schemas.user import UserSummary


# --- Contacts -------------------------------------------------------------

class ContactOut(ORMModel):
    id: uuid.UUID
    name: str
    company: str | None = None
    role: MemberRole | None = None
    market: str | None = None
    market_short: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    stage: ContactStage
    source: str | None = None
    notes: str | None = None
    initials: str
    avatar_color: str
    last_touch_at: datetime | None = None
    created_at: datetime
    person: UserSummary | None = None


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    company: str | None = Field(default=None, max_length=160)
    role: MemberRole | None = None
    market: str | None = Field(default=None, max_length=160)
    market_short: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    stage: ContactStage = ContactStage.new_lead
    source: str | None = Field(default=None, max_length=160)
    notes: str | None = None
    person_id: uuid.UUID | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    company: str | None = Field(default=None, max_length=160)
    role: MemberRole | None = None
    market: str | None = Field(default=None, max_length=160)
    market_short: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    stage: ContactStage | None = None
    source: str | None = Field(default=None, max_length=160)
    notes: str | None = None


class StageUpdate(BaseModel):
    stage: ContactStage


class PipelineColumn(BaseModel):
    stage: ContactStage
    count: int
    contacts: list[ContactOut]


class Pipeline(BaseModel):
    columns: list[PipelineColumn]


# --- Investors ------------------------------------------------------------

class IntroCommunity(ORMModel):
    id: uuid.UUID
    name: str


class IntroductionOut(ORMModel):
    id: uuid.UUID
    status: IntroStatus
    message: str | None = None
    created_at: datetime
    responded_at: datetime | None = None
    from_user: UserSummary
    to_user: UserSummary
    via_community: IntroCommunity | None = None


class IntroductionCreate(BaseModel):
    to_user_id: uuid.UUID
    via_community_id: uuid.UUID | None = None
    message: str | None = Field(default=None, max_length=2000)


class IntroductionRespond(BaseModel):
    accept: bool


class InvestorTiles(BaseModel):
    investors_following: int
    introduction_requests: int
    awaiting_reply: int
    profile_views: int
    shared_communities: int


# --- Plans ----------------------------------------------------------------

class PlanFeature(BaseModel):
    label: str
    included: bool = True


class PlanOut(BaseModel):
    id: PlanTier
    name: str
    tagline: str
    price: str
    per: str | None = None
    billed: str
    featured: bool = False
    features: list[PlanFeature]
    is_current: bool = False


class PublicPlanOut(PlanOut):
    """The price list as an anonymous visitor sees it.

    Carries how far up the roadmap the tier reaches so the public pricing page
    does not have to hold its own copy of the entitlement rules.
    """

    max_phase: int
    pro: bool = False


class PlanSelect(BaseModel):
    """Choosing a plan during onboarding. No card — Stripe comes later."""

    plan: PlanTier


class PlanSelectionOut(ORMModel):
    id: uuid.UUID
    plan: PlanTier
    plan_name: str
    price_usd: float
    billing_period: str
    selected_at: datetime
    is_current: bool
    source: str
    user_name: str
    user_email: str
    user_company: str | None = None


class SubscribeRequest(BaseModel):
    plan: PlanTier
    card_number: str = Field(min_length=12, max_length=24)
    card_name: str = Field(min_length=1, max_length=160)
    expiry: str = Field(pattern=r"^\s*\d{2}\s*/\s*\d{2,4}\s*$")
    cvc: str = Field(pattern=r"^\d{3,4}$")
    billing_country: str = Field(min_length=2, max_length=80)


class SubscriptionOut(ORMModel):
    plan: PlanTier
    status: SubscriptionStatus
    card_last4: str | None = None
    card_name: str | None = None
    billing_country: str | None = None
    started_at: datetime | None = None
