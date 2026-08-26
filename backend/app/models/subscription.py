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
    # Under Stripe these are filled from the webhook's payment-method summary;
    # no card number ever reaches this process.
    card_last4: Mapped[str | None] = mapped_column(String(4))
    card_name: Mapped[str | None] = mapped_column(String(160))
    card_brand: Mapped[str | None] = mapped_column(String(40))
    billing_country: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Stripe ----------------------------------------------------------
    # Unique so a webhook can find the row by either id, and so a bug cannot
    # attach one Stripe subscription to two members.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(80), unique=True, index=True
    )
    stripe_price_id: Mapped[str | None] = mapped_column(String(80))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
