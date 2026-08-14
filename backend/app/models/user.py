"""Members, their OAuth identities, per-field visibility and investor mandate."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import (
    ConnectionStatus, MemberRole, OAuthProvider, TimestampMixin, UUIDMixin, VisibilityLevel,
    connection_status_enum, member_role_enum, oauth_provider_enum, visibility_level_enum,
)


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    initials: Mapped[str] = mapped_column(String(4), default="", nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(4), default="a1", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    role: Mapped[MemberRole | None] = mapped_column(member_role_enum)
    title: Mapped[str | None] = mapped_column(String(160))
    company: Mapped[str | None] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(160))
    focus: Mapped[str | None] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text)

    completed_projects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    units_delivered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_projects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profile_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    identities: Mapped[list[OAuthIdentity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    visibility: Mapped[list[FieldVisibility]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    mandate: Mapped[Mandate | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class OAuthIdentity(UUIDMixin, TimestampMixin, Base):
    """One row per provider account linked to a user."""

    __tablename__ = "oauth_identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_provider_subject"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[OAuthProvider] = mapped_column(
        oauth_provider_enum, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))

    user: Mapped[User] = relationship(back_populates="identities")


class FieldVisibility(UUIDMixin, TimestampMixin, Base):
    """Public / Members / Private choice for one profile field."""

    __tablename__ = "field_visibility"
    __table_args__ = (UniqueConstraint("user_id", "field_key", name="uq_user_field"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[VisibilityLevel] = mapped_column(
        visibility_level_enum, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="visibility")


class Mandate(UUIDMixin, TimestampMixin, Base):
    """What a member tells investors they are looking for."""

    __tablename__ = "mandates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    asset_classes: Mapped[str | None] = mapped_column(String(255))
    markets: Mapped[str | None] = mapped_column(String(255))
    typical_raise: Mapped[str | None] = mapped_column(String(120))
    stage: Mapped[str | None] = mapped_column(String(120))
    visible_to: Mapped[VisibilityLevel] = mapped_column(
        visibility_level_enum, default=VisibilityLevel.members
    )

    user: Mapped[User] = relationship(back_populates="mandate")


class Connection(UUIDMixin, TimestampMixin, Base):
    """A connection request between two members."""

    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_connection_pair"),
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        connection_status_enum,
        default=ConnectionStatus.pending,
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text)

    requester: Mapped[User] = relationship(foreign_keys=[requester_id], lazy="selectin")
    addressee: Mapped[User] = relationship(foreign_keys=[addressee_id], lazy="selectin")
