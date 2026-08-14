"""Importing this module registers every mapper on Base.metadata."""

from app.models.base import (
    CommunityKind, ConnectionStatus, ContactStage, IntroStatus, JoinPolicy, MediaKind,
    MemberRole, MembershipStatus, OAuthProvider, PlanTier, SubscriptionStatus, VisibilityLevel,
)
from app.models.community import Community, CommunityChannel, CommunityMember
from app.models.crm import Contact, IntroductionRequest, InvestorFollow
from app.models.media import MediaAsset, PostAttachment
from app.models.onboarding import MemberOnboarding
from app.models.plan_selection import PlanSelection
from app.models.post import Post, PostComment, PostLike
from app.models.subscription import Subscription
from app.models.terms import TermsAcceptance
from app.models.token import RevokedToken
from app.models.user import Connection, FieldVisibility, Mandate, OAuthIdentity, User

__all__ = [
    "Community", "CommunityChannel", "CommunityKind", "CommunityMember", "Connection",
    "ConnectionStatus", "Contact", "ContactStage", "FieldVisibility", "IntroStatus",
    "IntroductionRequest", "InvestorFollow", "JoinPolicy", "Mandate", "MediaAsset",
    "MediaKind", "MemberOnboarding", "MemberRole",
    "MembershipStatus", "OAuthIdentity", "OAuthProvider", "PlanTier", "Post", "PostComment",
    "PostLike", "RevokedToken", "Subscription", "SubscriptionStatus", "TermsAcceptance",
    "User", "VisibilityLevel",
]
