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
    """The member's *persona* — what they do in a real-estate transaction.

    Deliberately not the same axis as `CommunityRole`. A persona describes the
    person and is set once at onboarding; a community role describes one
    membership and differs per community. The same Developer is `owner` of the
    community they started and `viewer` in someone else's. Nothing in the
    community module reads this enum: creation rights come from the plan, and
    in-community rights come from `CommunityRole`.
    """

    developer = "Developer"
    investor = "Investor"
    broker = "Broker"
    lender = "Lender"


class VisibilityLevel(str, enum.Enum):
    public = "Public"
    members = "Members"
    private = "Private"


class CommunityKind(str, enum.Enum):
    region = "region"
    industry = "industry"


class JoinPolicy(str, enum.Enum):
    """backend_flow.md 9.1 names these ANYONE / REQUEST_APPROVAL / INVITE_ONLY /
    ADMIN_ADDED. The first three already existed under the names below and are
    stored in Postgres under them, so the wording stays and the mapping is:

        open        = ANYONE
        request     = REQUEST_APPROVAL
        invite      = INVITE_ONLY
        admin_added = ADMIN_ADDED
    """

    open = "open"
    request = "request"
    invite = "invite"
    admin_added = "admin_added"


class MembershipStatus(str, enum.Enum):
    """backend_flow.md 9.2 calls the live state ACTIVE; here it is `joined`,
    which is the value already in the database and in the SPA. The rest of the
    spec's states are added under their own names.
    """

    joined = "joined"  # the spec's ACTIVE
    pending = "pending"
    muted = "muted"
    suspended = "suspended"
    banned = "banned"
    removed = "removed"
    left = "left"


#: Statuses that mean "this person is in the community right now". A muted
#: member is still a member — they just cannot post — so muted counts.
ACTIVE_MEMBER_STATUSES = frozenset({MembershipStatus.joined, MembershipStatus.muted})


class CommunityStatus(str, enum.Enum):
    """A community's lifecycle.

    `draft` is where every community starts. It is configurable by the people
    who can manage it and invisible to everyone else — nobody can browse to it,
    join it or be invited to it until it is published. Publishing is a one-way
    move to `active`; taking a live community back down is `archived`, which is
    reversible, and neither destroys anything.
    """

    draft = "draft"
    active = "active"
    archived = "archived"
    deleted = "deleted"


#: Statuses that still count against `community.max_owned`. A draft occupies a
#: slot: it is a community the member is building, and letting drafts be free
#: would make the ceiling meaningless — create a hundred, publish them one at a
#: time. Archived does not count, because archiving is how a downgrade brings a
#: member back under a lower ceiling.
OWNED_COMMUNITY_STATUSES = frozenset({CommunityStatus.draft, CommunityStatus.active})

#: Statuses in which settings, members, roles and channels may still be changed.
#: A draft is configured before it goes live, so it has to be editable; an
#: archived community is deliberately read-only.
EDITABLE_COMMUNITY_STATUSES = frozenset({CommunityStatus.draft, CommunityStatus.active})


class CommunityRole(str, enum.Enum):
    """A member's standing *inside one community*, independent of their persona.

    `viewer` is the read-only floor: admitted to the community and able to read
    it, but unable to post, comment, react or message. It is what an admin
    demotes a disruptive member to instead of removing them, and what a
    community hands out when it wants an audience rather than participants.
    """

    owner = "owner"
    admin = "admin"
    moderator = "moderator"
    member = "member"
    viewer = "viewer"


#: Higher wins. Used for "you cannot act on someone at or above your own rank",
#: which is what stops an admin removing the owner or demoting a peer.
#:
#: The numbers are compared, never stored, so inserting `viewer` beneath
#: `member` renumbers the rest without touching a single row.
ROLE_RANK: dict[CommunityRole, int] = {
    CommunityRole.viewer: 0,
    CommunityRole.member: 1,
    CommunityRole.moderator: 2,
    CommunityRole.admin: 3,
    CommunityRole.owner: 4,
}


class InviteStatus(str, enum.Enum):
    """An invitation's lifecycle. Only `pending` is actionable.

    `revoked` and `declined` are kept rather than deleted so the audit trail can
    answer "who was invited and what happened" after the fact. `expired` is
    written lazily — an invite past its `expires_at` is treated as expired on
    read, and stamped the next time anything touches it.
    """

    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    revoked = "revoked"
    expired = "expired"


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
    """backend_flow.md 5.2, mapped onto the three values already stored.

    Stripe spells it `canceled`; the column has held `cancelled` since the first
    migration, so services/billing.py translates rather than renaming the value.
    """

    active = "active"
    cancelled = "cancelled"
    past_due = "past_due"
    trialing = "trialing"
    incomplete = "incomplete"
    incomplete_expired = "incomplete_expired"
    unpaid = "unpaid"


#: Statuses under which a paid plan's entitlements apply.
#:
#: `past_due` is deliberately included: Stripe moves a subscription there while
#: it retries a failed payment, and cutting access off on the first retry would
#: lock members out over an expired card. Dunning ends in `unpaid` or
#: `cancelled`, and both of those drop to early access.
ENTITLED_SUBSCRIPTION_STATUSES = frozenset({
    SubscriptionStatus.active,
    SubscriptionStatus.trialing,
    SubscriptionStatus.past_due,
})


class OAuthProvider(str, enum.Enum):
    google = "google"
    apple = "apple"


class MediaKind(str, enum.Enum):
    image = "image"
    video = "video"
    document = "document"


class AddonStatus(str, enum.Enum):
    """An add-on purchase's lifecycle.

    Only `active` grants anything, and even then only while `expires_at` has not
    passed — see `services/addons.active_for`. The other values are kept rather
    than deleted so "why did this member's ceiling drop" is answerable after the
    fact, and so a Stripe webhook has somewhere to record a lapse.
    """

    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    expired = "expired"


class AddonEffect(str, enum.Enum):
    """What an add-on does to one entitlement key.

    `increment` is the common case and the only one that multiplies by quantity:
    two Extra Community add-ons raise the ceiling by two. `set_to` pins a value
    regardless of quantity, `unlimited` removes the ceiling, and `enable` turns
    a boolean feature on. Nothing here can *lower* a ceiling or switch a feature
    off — an add-on is additive by construction, so buying one can never take
    away access the plan already grants.
    """

    increment = "increment"
    set_to = "set_to"
    unlimited = "unlimited"
    enable = "enable"


# One shared type instance per Postgres enum. Reusing the same object across
# tables means CREATE TYPE is emitted once instead of once per column.
member_role_enum = SAEnum(MemberRole, name="member_role")
visibility_level_enum = SAEnum(VisibilityLevel, name="visibility_level")
community_kind_enum = SAEnum(CommunityKind, name="community_kind")
community_status_enum = SAEnum(CommunityStatus, name="community_status")
community_role_enum = SAEnum(CommunityRole, name="community_role")
join_policy_enum = SAEnum(JoinPolicy, name="join_policy")
membership_status_enum = SAEnum(MembershipStatus, name="membership_status")
invite_status_enum = SAEnum(InviteStatus, name="invite_status")
connection_status_enum = SAEnum(ConnectionStatus, name="connection_status")
contact_stage_enum = SAEnum(ContactStage, name="contact_stage")
intro_status_enum = SAEnum(IntroStatus, name="intro_status")
plan_tier_enum = SAEnum(PlanTier, name="plan_tier")
subscription_status_enum = SAEnum(SubscriptionStatus, name="subscription_status")
oauth_provider_enum = SAEnum(OAuthProvider, name="oauth_provider")
media_kind_enum = SAEnum(MediaKind, name="media_kind")
addon_status_enum = SAEnum(AddonStatus, name="addon_status")
addon_effect_enum = SAEnum(AddonEffect, name="addon_effect")
