"""User, visibility, mandate and connection schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.base import ConnectionStatus, MemberRole, VisibilityLevel
from app.schemas.common import ORMModel


class UserSummary(ORMModel):
    """Compact shape used in cards, facepiles and author blocks."""

    id: uuid.UUID
    name: str
    initials: str
    avatar_color: str
    role: MemberRole | None = None
    company: str | None = None
    location: str | None = None


class UserProfile(UserSummary):
    email: EmailStr
    title: str | None = None
    focus: str | None = None
    bio: str | None = None
    completed_projects: int = 0
    units_delivered: int = 0
    active_projects: int = 0
    profile_views: int = 0
    onboarded: bool = False
    created_at: datetime

    # Filled by the route: the two gates between signing in and the app, and
    # which plan was chosen. The SPA routes on these.
    terms_accepted: bool = False
    plan_selected: bool = False
    current_plan: str | None = None


class UserUpdate(BaseModel):
    """Edit profile. Only the fields sent are touched.

    Text arrives from a form, so it is trimmed; a field cleared to blank is
    stored as NULL rather than an empty string, which is what "not set" means
    everywhere else. `name` is the exception — it has no blank state.
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: MemberRole | None = None
    title: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    focus: str | None = Field(default=None, max_length=200)
    bio: str | None = None
    completed_projects: int | None = Field(default=None, ge=0)
    units_delivered: int | None = Field(default=None, ge=0)
    active_projects: int | None = Field(default=None, ge=0)
    onboarded: bool | None = None

    @field_validator("title", "company", "location", "focus", "bio")
    @classmethod
    def _blank_to_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("name")
    @classmethod
    def _needs_a_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name cannot be blank")
        return trimmed


class MemberStats(BaseModel):
    connections: int
    communities: int
    completed_projects: int
    profile_views: int


class VisibilityItem(ORMModel):
    field_key: str
    level: VisibilityLevel


class VisibilityUpdate(BaseModel):
    field_key: str = Field(min_length=1, max_length=64)
    level: VisibilityLevel


class MandateOut(ORMModel):
    asset_classes: str | None = None
    markets: str | None = None
    typical_raise: str | None = None
    stage: str | None = None
    visible_to: VisibilityLevel = VisibilityLevel.members


class MandateUpdate(BaseModel):
    asset_classes: str | None = Field(default=None, max_length=255)
    markets: str | None = Field(default=None, max_length=255)
    typical_raise: str | None = Field(default=None, max_length=120)
    stage: str | None = Field(default=None, max_length=120)
    visible_to: VisibilityLevel | None = None

    @field_validator("asset_classes", "markets", "typical_raise", "stage")
    @classmethod
    def _blank_to_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ConnectionCreate(BaseModel):
    addressee_id: uuid.UUID
    note: str | None = Field(default=None, max_length=2000)


class ConnectionOut(ORMModel):
    id: uuid.UUID
    status: ConnectionStatus
    note: str | None = None
    created_at: datetime
    requester: UserSummary
    addressee: UserSummary
