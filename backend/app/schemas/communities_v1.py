"""Community and membership schemas for /api/v1 — backend_flow.md 9, 12, 13.

Separate from `schemas/community.py`, which serves the pre-v1 routes the SPA
still calls. The two describe the same tables at different levels of detail;
keeping them apart means adding a field here cannot change what the running
frontend receives.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.base import (
    CommunityKind, CommunityRole, CommunityStatus, InviteStatus, JoinPolicy, MembershipStatus,
    VisibilityLevel,
)
from app.schemas.common import ORMModel
from app.schemas.user import UserSummary


class CommunityOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: CommunityKind
    category: str | None = None
    location: str
    description: str | None = None
    rules: str | None = None
    banner: str
    initials: str
    logo_url: str | None = None
    cover_url: str | None = None
    visibility: VisibilityLevel
    join_policy: JoinPolicy
    post_min_role: CommunityRole = CommunityRole.member
    invite_min_role: CommunityRole = CommunityRole.admin
    status: CommunityStatus
    member_count: int
    owner_id: uuid.UUID | None = None
    created_at: datetime
    published_at: datetime | None = None
    archived_at: datetime | None = None

    # Filled per request for the member asking.
    my_role: CommunityRole | None = None
    my_status: MembershipStatus | None = None
    joined: bool = False
    pending: bool = False
    my_permissions: list[str] = Field(default_factory=list)
    faces: list[UserSummary] = Field(default_factory=list)


class CommunityDetail(CommunityOut):
    channels: list[str] = Field(default_factory=list)


class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    kind: CommunityKind = CommunityKind.industry
    category: str | None = Field(default=None, max_length=160)
    location: str = Field(default="Global", max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    rules: str | None = Field(default=None, max_length=8000)
    banner: str = Field(default="b1", pattern=r"^b[1-6]$")
    logo_url: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=500)
    # Defaults are the only combination every plan may use, so a request that
    # omits both never trips an entitlement check.
    visibility: VisibilityLevel = VisibilityLevel.public
    join_policy: JoinPolicy = JoinPolicy.open
    channels: list[str] | None = Field(default=None, max_length=50)


class CommunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    rules: str | None = Field(default=None, max_length=8000)
    banner: str | None = Field(default=None, pattern=r"^b[1-6]$")
    logo_url: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=500)
    visibility: VisibilityLevel | None = None
    join_policy: JoinPolicy | None = None
    post_min_role: CommunityRole | None = None
    invite_min_role: CommunityRole | None = None

    @model_validator(mode="after")
    def _sane_min_roles(self) -> CommunityUpdate:
        """A gate nobody can clear, or one everybody clears, is a mistake.

        `viewer` as a floor gates nothing — viewers cannot post or invite in the
        first place — and `owner` as a floor for inviting would leave a
        community whose admins cannot bring anyone in.
        """
        for field in ("post_min_role", "invite_min_role"):
            value = getattr(self, field)
            if value is CommunityRole.viewer:
                raise ValueError(f"{field} cannot be viewer — it would gate nothing.")
        return self


class MemberOut(ORMModel):
    id: uuid.UUID
    community_id: uuid.UUID
    user_id: uuid.UUID
    role: CommunityRole
    status: MembershipStatus
    joined_at: datetime | None = None
    muted_until: datetime | None = None
    banned_until: datetime | None = None
    created_at: datetime
    user: UserSummary


class MemberAdd(BaseModel):
    """Section 13's direct-add body. OWNER is rejected by the service."""

    user_id: uuid.UUID
    role: CommunityRole = CommunityRole.member


class RoleUpdate(BaseModel):
    role: CommunityRole


class BanRequest(BaseModel):
    # Omit for a permanent ban.
    days: int | None = Field(default=None, ge=1, le=3650)
    reason: str | None = Field(default=None, max_length=500)


class MuteRequest(BaseModel):
    minutes: int = Field(default=60, ge=1, le=60 * 24 * 30)


class JoinResult(BaseModel):
    status: MembershipStatus
    role: CommunityRole
    community: CommunityOut


# --------------------------------------------------------------------------
# Invitations
# --------------------------------------------------------------------------

class InviteCreate(BaseModel):
    """Address an invitation to an account or to an email, and offer a role.

    Exactly one of `user_id` / `email` is required; the service resolves an
    email that already has an account to that account. OWNER is rejected there,
    not here, so the refusal carries the same error shape as every other
    role rule.
    """

    user_id: uuid.UUID | None = None
    email: EmailStr | None = None
    role: CommunityRole = CommunityRole.member
    message: str | None = Field(default=None, max_length=1000)
    expires_in_days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def _exactly_one_addressee(self) -> InviteCreate:
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Give exactly one of user_id or email.")
        return self


class InviteResend(BaseModel):
    expires_in_days: int | None = Field(default=None, ge=1, le=90)


class InviteOut(ORMModel):
    id: uuid.UUID
    community_id: uuid.UUID
    invited_user_id: uuid.UUID | None = None
    email: str | None = None
    invited_by_id: uuid.UUID | None = None
    role: CommunityRole
    status: InviteStatus
    message: str | None = None
    expires_at: datetime | None = None
    responded_at: datetime | None = None
    created_at: datetime

    invited_user: UserSummary | None = None
    invited_by: UserSummary | None = None


class InviteWithToken(InviteOut):
    """What the sender gets back. The token is the link they pass on, so it is
    returned to whoever created the invitation and to nobody else — the roster
    listing uses `InviteOut`, which has no token field."""

    token: str


class InviteAccept(BaseModel):
    """Accept by link. Members answering from their own invitation list use the
    id-addressed endpoint instead and send no body."""

    token: str = Field(min_length=16, max_length=64)


class PermissionOut(BaseModel):
    key: str
    label: str


class MyAccessOut(BaseModel):
    """What the caller may do here — for greying out controls, not for security."""

    role: CommunityRole | None = None
    status: MembershipStatus | None = None
    permissions: list[PermissionOut]


class AuditEntryOut(ORMModel):
    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    meta: dict
    created_at: datetime
