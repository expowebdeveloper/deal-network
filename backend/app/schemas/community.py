"""Community schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.base import CommunityKind, JoinPolicy, MembershipStatus
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
    join_policy: JoinPolicy
    member_count: int
    created_at: datetime

    # Filled per-request for the signed-in member.
    joined: bool = False
    pending: bool = False  # requested to join, awaiting an admin
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
    join_policy: JoinPolicy | None = None


class MembershipOut(ORMModel):
    id: uuid.UUID
    status: MembershipStatus
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
