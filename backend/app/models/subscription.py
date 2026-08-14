"""Plan subscriptions. Cards are collected but not charged during early access."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import (
    PlanTier, SubscriptionStatus, TimestampMixin, UUIDMixin,
    plan_tier_enum, subscription_status_enum,
)


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    plan: Mapped[PlanTier] = mapped_column(
        plan_tier_enum, default=PlanTier.early_access, nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        subscription_status_enum,
        default=SubscriptionStatus.active,
        nullable=False,
    )
    # Never store raw card data — this is the last four only, for display.
    card_last4: Mapped[str | None] = mapped_column(String(4))
    card_name: Mapped[str | None] = mapped_column(String(160))
    billing_country: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
