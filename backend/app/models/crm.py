"""Private CRM records: contacts, the pipeline and introduction requests."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import (
    ContactStage, IntroStatus, MemberRole, TimestampMixin, UUIDMixin,
    contact_stage_enum, intro_status_enum, member_role_enum,
)


class Contact(UUIDMixin, TimestampMixin, Base):
    """A row in one member's own contact book. Never shared with anyone else."""

    __tablename__ = "contacts"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Set when the contact is also a member of the network.
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    company: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[MemberRole | None] = mapped_column(member_role_enum)
    market: Mapped[str | None] = mapped_column(String(160))
    market_short: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))

    stage: Mapped[ContactStage] = mapped_column(
        contact_stage_enum,
        default=ContactStage.new_lead,
        nullable=False,
    )
    source: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    initials: Mapped[str] = mapped_column(String(4), default="", nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(4), default="a1", nullable=False)

    person: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[person_id], lazy="selectin"
    )


class IntroductionRequest(UUIDMixin, TimestampMixin, Base):
    """An investor asking to be introduced to a member."""

    __tablename__ = "introduction_requests"

    from_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    via_community_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="SET NULL")
    )
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IntroStatus] = mapped_column(
        intro_status_enum, default=IntroStatus.pending, nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    from_user: Mapped["User"] = relationship(  # noqa: F821
        foreign_keys=[from_user_id], lazy="selectin"
    )
    to_user: Mapped["User"] = relationship(  # noqa: F821
        foreign_keys=[to_user_id], lazy="selectin"
    )
    via_community: Mapped["Community | None"] = relationship(lazy="selectin")  # noqa: F821


class InvestorFollow(UUIDMixin, TimestampMixin, Base):
    """An investor following a member's investor-facing profile."""

    __tablename__ = "investor_follows"

    investor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    investor: Mapped["User"] = relationship(  # noqa: F821
        foreign_keys=[investor_id], lazy="selectin"
    )
