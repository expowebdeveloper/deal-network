"""Tables the Stripe flow needs either side of the checkout.

`SignupIntent` is backend_flow.md 7.1: the visitor picks a plan on the public
pricing page *before* there is an account, and the choice is held server-side so
signup cannot be talked into a different tier with a query parameter.

`BillingEvent` is the webhook's idempotency ledger (section 27). Stripe retries
delivery on any non-2xx and can deliver the same event twice on its own, so
"have I already applied this event id" has to be a uniqueness constraint in the
database rather than a check in application code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import PlanTier, TimestampMixin, UUIDMixin, plan_tier_enum


class SignupIntent(UUIDMixin, TimestampMixin, Base):
    """A plan chosen before signing up, good until it expires or is consumed."""

    __tablename__ = "signup_intents"

    plan: Mapped[PlanTier] = mapped_column(plan_tier_enum, nullable=False)
    # Optional — the pricing page may know the email before the account exists.
    email: Mapped[str | None] = mapped_column(String(320), index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Filled in when the intent is spent, so the choice stays auditable.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    def is_spendable(self, now: datetime) -> bool:
        return self.consumed_at is None and self.expires_at > now


class BillingEvent(UUIDMixin, TimestampMixin, Base):
    """One row per Stripe event id, inserted before the event is applied."""

    __tablename__ = "billing_events"

    # The uniqueness constraint IS the idempotency mechanism — a duplicate
    # delivery loses the insert race and is acknowledged without reapplying.
    stripe_event_id: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # Whole event, so a mis-handled one can be replayed without asking Stripe.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    user: Mapped["User | None"] = relationship(lazy="selectin")  # noqa: F821
