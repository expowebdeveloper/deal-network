"""Audit trail — backend_flow.md section 21.

`action` is a plain string rather than a Postgres enum on purpose: the list in
section 21 will keep growing as the later modules land, and a new action should
not need a migration to be recordable.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class AuditAction:
    """The section 21 list. Constants, so a typo fails at import."""

    COMMUNITY_CREATED = "COMMUNITY_CREATED"
    COMMUNITY_UPDATED = "COMMUNITY_UPDATED"
    COMMUNITY_PUBLISHED = "COMMUNITY_PUBLISHED"
    COMMUNITY_ARCHIVED = "COMMUNITY_ARCHIVED"
    COMMUNITY_RESTORED = "COMMUNITY_RESTORED"
    COMMUNITY_DELETED = "COMMUNITY_DELETED"
    OWNERSHIP_TRANSFERRED = "OWNERSHIP_TRANSFERRED"

    MEMBER_JOINED = "MEMBER_JOINED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_LEFT = "MEMBER_LEFT"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    MEMBER_BANNED = "MEMBER_BANNED"
    MEMBER_UNBANNED = "MEMBER_UNBANNED"
    MEMBER_MUTED = "MEMBER_MUTED"
    MEMBER_UNMUTED = "MEMBER_UNMUTED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
    JOIN_REQUEST_CREATED = "JOIN_REQUEST_CREATED"
    JOIN_REQUEST_APPROVED = "JOIN_REQUEST_APPROVED"
    JOIN_REQUEST_REJECTED = "JOIN_REQUEST_REJECTED"

    INVITE_SENT = "INVITE_SENT"
    INVITE_ACCEPTED = "INVITE_ACCEPTED"
    INVITE_DECLINED = "INVITE_DECLINED"
    INVITE_REVOKED = "INVITE_REVOKED"
    INVITE_RESENT = "INVITE_RESENT"

    CHANNEL_CREATED = "CHANNEL_CREATED"
    CHANNEL_UPDATED = "CHANNEL_UPDATED"
    CHANNEL_DELETED = "CHANNEL_DELETED"

    POST_DELETED = "POST_DELETED"
    MESSAGE_DELETED = "MESSAGE_DELETED"
    FILE_SHARED = "FILE_SHARED"
    FILE_ACCESS_CHANGED = "FILE_ACCESS_CHANGED"

    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"
    PLAN_CHANGED = "PLAN_CHANGED"
    BILLING_EVENT_PROCESSED = "BILLING_EVENT_PROCESSED"


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
