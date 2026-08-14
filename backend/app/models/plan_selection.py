"""Record of a member choosing a plan.

Every choice is appended, never overwritten, so there is a full history of who
picked what and when. The member's name and email are snapshotted onto the row
so the record still reads correctly if they later change their profile.

`Subscription` holds the *current* state; this table is the audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import PlanTier, TimestampMixin, UUIDMixin, plan_tier_enum


class PlanSelection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plan_selections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Snapshot of who chose, as they were at the time of choosing.
    user_name: Mapped[str] = mapped_column(String(160), nullable=False)
    user_email: Mapped[str] = mapped_column(String(320), nullable=False)
    user_company: Mapped[str | None] = mapped_column(String(160))

    plan: Mapped[PlanTier] = mapped_column(plan_tier_enum, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(80), nullable=False)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    billing_period: Mapped[str] = mapped_column(String(40), default="monthly", nullable=False)

    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Exactly one row per user carries the current choice.
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Where the choice came from — onboarding gate, plans page, an upgrade later.
    source: Mapped[str] = mapped_column(String(40), default="onboarding", nullable=False)

    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
