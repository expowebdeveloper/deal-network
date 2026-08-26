"""Importing this module registers every mapper on Base.metadata."""

from app.models.addon import (
    Addon, AddonEntitlementEffect, AddonPrice, AddonSubscription,
)
from app.models.audit import AuditAction, AuditLog
from app.models.base import (
    ACTIVE_MEMBER_STATUSES, EDITABLE_COMMUNITY_STATUSES, ENTITLED_SUBSCRIPTION_STATUSES,
    OWNED_COMMUNITY_STATUSES, ROLE_RANK, AddonEffect, AddonStatus, CommunityKind,
    CommunityRole, CommunityStatus, ConnectionStatus, ContactStage, IntroStatus, InviteStatus,
    JoinPolicy, MediaKind, MemberRole, MembershipStatus, OAuthProvider, PlanTier,
    SubscriptionStatus, VisibilityLevel,
)
from app.models.billing import BillingEvent, SignupIntent
from app.models.community import (
    Community, CommunityChannel, CommunityInvite, CommunityMember,
)
from app.models.crm import Contact, IntroductionRequest, InvestorFollow
from app.models.media import MediaAsset, PostAttachment
from app.models.notification import (
    Notification, NotificationKind, PresenterNote, PresenterSection,
)
from app.models.onboarding import MemberOnboarding
from app.models.plan import EntitlementKind, Plan, PlanEntitlement
from app.models.plan_selection import PlanSelection
from app.models.post import Post, PostComment, PostLike
from app.models.subscription import Subscription
from app.models.terms import TermsAcceptance
from app.models.token import RevokedToken
from app.models.user import Connection, FieldVisibility, Mandate, OAuthIdentity, User

__all__ = [
    "ACTIVE_MEMBER_STATUSES", "EDITABLE_COMMUNITY_STATUSES",
    "ENTITLED_SUBSCRIPTION_STATUSES", "OWNED_COMMUNITY_STATUSES", "ROLE_RANK",
    "Addon", "AddonEffect", "AddonEntitlementEffect", "AddonPrice", "AddonStatus",
    "AddonSubscription",
    "AuditAction", "AuditLog", "BillingEvent", "Community", "CommunityChannel",
    "CommunityInvite", "CommunityKind", "CommunityMember", "CommunityRole",
    "CommunityStatus", "Connection",
    "ConnectionStatus", "Contact", "ContactStage", "EntitlementKind", "FieldVisibility",
    "IntroStatus", "IntroductionRequest", "InvestorFollow", "InviteStatus", "JoinPolicy",
    "Mandate",
    "MediaAsset", "MediaKind", "MemberOnboarding", "MemberRole",
    "MembershipStatus", "Notification", "NotificationKind", "OAuthIdentity", "OAuthProvider",
    "Plan", "PlanEntitlement", "PresenterNote", "PresenterSection",
    "PlanSelection", "PlanTier",
    "Post", "PostComment", "PostLike", "RevokedToken", "SignupIntent", "Subscription",
    "SubscriptionStatus", "TermsAcceptance", "User", "VisibilityLevel",
]
