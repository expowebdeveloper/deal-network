"""Notification and presenter-note shapes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.notification import NotificationKind, PresenterSection
from app.schemas.common import ORMModel
from app.schemas.user import UserSummary


class NotificationOut(ORMModel):
    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str | None = None
    #: Relative SPA path, or null when there is nowhere to go.
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime
    actor: UserSummary | None = None


class NotificationFeed(BaseModel):
    items: list[NotificationOut]
    unread: int


class PresenterNoteOut(ORMModel):
    id: uuid.UUID
    section: PresenterSection
    position: int
    heading: str
    detail: str | None = None
    extra: str | None = None


class PresenterNoteCreate(BaseModel):
    section: PresenterSection
    heading: str = Field(min_length=1, max_length=4000)
    detail: str | None = Field(default=None, max_length=4000)
    extra: str | None = Field(default=None, max_length=4000)
    position: int | None = Field(default=None, ge=0, le=9999)


class PresenterNoteUpdate(BaseModel):
    heading: str | None = Field(default=None, min_length=1, max_length=4000)
    detail: str | None = Field(default=None, max_length=4000)
    extra: str | None = Field(default=None, max_length=4000)
    position: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None


class PresenterBoard(BaseModel):
    """Everything the drawer renders, grouped the way it is displayed.

    `can_edit` is what the UI switches on. It is a convenience, not the
    boundary — every write re-checks `is_staff` server-side.
    """

    decisions: list[PresenterNoteOut]
    changes: list[PresenterNoteOut]
    references: list[PresenterNoteOut]
    standing: list[PresenterNoteOut]
    can_edit: bool = False
