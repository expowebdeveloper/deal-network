"""Community schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.base import (
    CommunityKind, CommunityRole, CommunityStatus, JoinPolicy, MembershipStatus,
    VisibilityLevel,
)
from app.schemas.common import ORMModel
from app.schemas.user import UserSummary


class CommunityOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: CommunityKind
    location: str
    description: str | None = None
    banner: str
    initials: str
    # A community's own picture. Null means fall back to the initials bubble,
    # which is what every community starts with.
    logo_url: str | None = None
    join_policy: JoinPolicy
    # The lowest role allowed to post. `member` means everyone.
    post_min_role: CommunityRole = CommunityRole.member
    # The lowest role allowed to invite. `admin` is the default; `member` turns
    # a community into one its own members grow.
    invite_min_role: CommunityRole = CommunityRole.admin
    visibility: VisibilityLevel = VisibilityLevel.public
    # `draft` until it is published. The SPA needs this to know whether to show
    # the Publish control or the live view.
    status: CommunityStatus = CommunityStatus.active
    member_count: int
    created_at: datetime
    published_at: datetime | None = None

    # Filled per-request for the signed-in member.
    joined: bool = False
    pending: bool = False  # requested to join, awaiting an admin
    # The caller's own role here, so the SPA knows whether to offer the role
    # controls at all. None when they are not a member.
    my_role: CommunityRole | None = None
    faces: list[UserSummary] = Field(default_factory=list)


class CommunityDetail(CommunityOut):
    channels: list[str] = Field(default_factory=list)


class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    kind: CommunityKind
    location: str = Field(default="Global", max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    banner: str = Field(default="b1", pattern=r"^b[1-6]$")
    join_policy: JoinPolicy = JoinPolicy.open
    channels: list[str] = Field(default_factory=lambda: ["# general"])


class CommunityUpdate(BaseModel):
    """Admin edits. Every field optional — only what is sent is changed."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    banner: str | None = Field(default=None, pattern=r"^b[1-6]$")
    # Send the path the media upload returned. Explicit null clears it and the
    # community goes back to its initials.
    logo_url: str | None = Field(default=None, max_length=500)
    join_policy: JoinPolicy | None = None
    post_min_role: CommunityRole | None = None
    invite_min_role: CommunityRole | None = None
    visibility: VisibilityLevel | None = None


class MembershipOut(ORMModel):
    id: uuid.UUID
    status: MembershipStatus
    # `role` is the real thing; `is_admin` is the pre-v1 boolean kept in step by
    # CommunityMember.apply_role, and still read by older clients.
    role: CommunityRole
    is_admin: bool
    created_at: datetime
    user: UserSummary


class ChannelOut(ORMModel):
    id: uuid.UUID
    name: str


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class JoinResult(BaseModel):
    """What happened when you asked to join — joined outright, or awaiting approval."""

    status: MembershipStatus
    community: CommunityOut
