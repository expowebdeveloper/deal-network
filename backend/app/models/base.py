"""Shared column mixins and the enums used across models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MemberRole(str, enum.Enum):
    developer = "Developer"
    investor = "Investor"
    broker = "Broker"
    lender = "Lender"
    service_provider = "Service provider"


class VisibilityLevel(str, enum.Enum):
    public = "Public"
    members = "Members"
    private = "Private"


class CommunityKind(str, enum.Enum):
    region = "region"
    industry = "industry"


class JoinPolicy(str, enum.Enum):
    open = "open"
    request = "request"
    invite = "invite"


class MembershipStatus(str, enum.Enum):
    joined = "joined"
    pending = "pending"


class ConnectionStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class ContactStage(str, enum.Enum):
    new_lead = "New lead"
    contacted = "Contacted"
    in_discussion = "In discussion"
    committed = "Committed"
    closed = "Closed"


class IntroStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class PlanTier(str, enum.Enum):
    early_access = "early_access"
    member = "member"
    professional = "professional"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    past_due = "past_due"


class OAuthProvider(str, enum.Enum):
    google = "google"
    apple = "apple"


class MediaKind(str, enum.Enum):
    image = "image"
    document = "document"


# One shared type instance per Postgres enum. Reusing the same object across
# tables means CREATE TYPE is emitted once instead of once per column.
member_role_enum = SAEnum(MemberRole, name="member_role")
visibility_level_enum = SAEnum(VisibilityLevel, name="visibility_level")
community_kind_enum = SAEnum(CommunityKind, name="community_kind")
join_policy_enum = SAEnum(JoinPolicy, name="join_policy")
membership_status_enum = SAEnum(MembershipStatus, name="membership_status")
connection_status_enum = SAEnum(ConnectionStatus, name="connection_status")
contact_stage_enum = SAEnum(ContactStage, name="contact_stage")
intro_status_enum = SAEnum(IntroStatus, name="intro_status")
plan_tier_enum = SAEnum(PlanTier, name="plan_tier")
subscription_status_enum = SAEnum(SubscriptionStatus, name="subscription_status")
oauth_provider_enum = SAEnum(OAuthProvider, name="oauth_provider")
media_kind_enum = SAEnum(MediaKind, name="media_kind")
