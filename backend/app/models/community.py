"""Communities, their membership rows and channels."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import (
    CommunityKind, JoinPolicy, MembershipStatus, TimestampMixin, UUIDMixin,
    community_kind_enum, join_policy_enum, membership_status_enum,
)


class Community(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communities"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    kind: Mapped[CommunityKind] = mapped_column(
        community_kind_enum, nullable=False
    )
    location: Mapped[str] = mapped_column(String(160), default="Global", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    banner: Mapped[str] = mapped_column(String(4), default="b1", nullable=False)
    initials: Mapped[str] = mapped_column(String(4), default="", nullable=False)
    join_policy: Mapped[JoinPolicy] = mapped_column(
        join_policy_enum, default=JoinPolicy.open, nullable=False
    )
    member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    memberships: Mapped[list[CommunityMember]] = relationship(
        back_populates="community", cascade="all, delete-orphan"
    )
    channels: Mapped[list[CommunityChannel]] = relationship(
        back_populates="community", cascade="all, delete-orphan", lazy="selectin"
    )


class CommunityMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "community_members"
    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_community_user"),
    )

    community_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[MembershipStatus] = mapped_column(
        membership_status_enum,
        default=MembershipStatus.joined,
        nullable=False,
    )
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    community: Mapped[Community] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821


class CommunityChannel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "community_channels"
    __table_args__ = (UniqueConstraint("community_id", "name", name="uq_channel_name"),)

    community_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    community: Mapped[Community] = relationship(back_populates="channels")
