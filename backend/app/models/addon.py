"""Add-ons: the paid increments that sit on top of a plan's entitlements.

community_role_and_subs.md section 18 asks for three tables, and there is a
fourth here because the first three describe the *catalogue* and none of them
records a purchase:

    addons                      what can be bought        ("Extra community")
    addon_prices                what it costs, per plan   ($9/mo on Silver)
    addon_entitlement_effects   what it does              (+1 community.max_owned)
    addon_subscriptions         who has bought it         (this member, ×2)

Splitting the effect from the price is the point of the design. Billing changes
a row in `addon_prices`; capability changes a row in
`addon_entitlement_effects`; neither touches the other, and no feature module
learns that add-ons exist at all — they resolve through
`services/entitlements.effective_limit`, which folds the effects into the plan
ceiling before anyone compares it against usage.

The keys an effect names are the same dotted keys `plan_entitlements` uses, so
an add-on can only ever raise something a plan already describes. An effect
naming a key no plan has is inert rather than dangerous.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import (
    AddonEffect, AddonStatus, PlanTier, TimestampMixin, UUIDMixin,
    addon_effect_enum, addon_status_enum, plan_tier_enum,
)


class Addon(UUIDMixin, TimestampMixin, Base):
    """One purchasable increment, identified by a stable code."""

    __tablename__ = "addons"

    # `code` rather than the surrogate id is what prices, effects and purchases
    # reference, so the catalogue reads like the product does: "extra_community"
    # instead of a UUID nobody can recognise in a log line.
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # What one unit is: "community", "seat", "10 GB", "10 deals".
    unit: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    # The most anyone may hold. None means no cap beyond what they will pay for.
    max_quantity: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AddonPrice(UUIDMixin, TimestampMixin, Base):
    """What an add-on costs, optionally per plan.

    `plan_code` is nullable on purpose: NULL means "on any plan". A row with a
    plan pinned wins over the open row for that plan, which is how an add-on can
    be cheaper on Gold than on Silver, or offered on Gold only.
    """

    __tablename__ = "addon_prices"
    __table_args__ = (
        UniqueConstraint("addon_code", "plan_code", "billing_interval", name="uq_addon_price"),
    )

    addon_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("addons.code", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_code: Mapped[PlanTier | None] = mapped_column(plan_tier_enum)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), default="month", nullable=False)
    stripe_price_id: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AddonEntitlementEffect(UUIDMixin, TimestampMixin, Base):
    """What one add-on does to one entitlement key.

    One row per key, so an add-on that raises two ceilings at once (a bundle) is
    two rows rather than a special case.
    """

    __tablename__ = "addon_entitlement_effects"
    __table_args__ = (
        UniqueConstraint("addon_code", "key", name="uq_addon_effect_key"),
    )

    addon_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("addons.code", ondelete="CASCADE"), index=True, nullable=False
    )
    # "feature" or "limit" — models.plan.EntitlementKind, the same vocabulary
    # `plan_entitlements.kind` uses.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    effect: Mapped[AddonEffect] = mapped_column(
        addon_effect_enum, default=AddonEffect.increment, nullable=False
    )
    # How much, for `increment` and `set_to`. Ignored by `unlimited`/`enable`.
    amount: Mapped[int | None] = mapped_column(Numeric(20, 0))

    @property
    def step(self) -> int:
        return int(self.amount) if self.amount is not None else 0


class AddonSubscription(UUIDMixin, TimestampMixin, Base):
    """A member's holding of one add-on.

    Quantity rather than a row per unit: "three extra communities" is one row
    with `quantity = 3`, which is also how Stripe models a subscription item, so
    the webhook has one row to keep in step.
    """

    __tablename__ = "addon_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "addon_code", name="uq_addon_subscription_owner"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    addon_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("addons.code", ondelete="CASCADE"), index=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[AddonStatus] = mapped_column(
        addon_status_enum, default=AddonStatus.active, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # None means "until cancelled". A date in the past stops granting anything
    # the moment it passes, with no sweeper job needed — `active_for` compares
    # against the clock on every read.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stripe_subscription_item_id: Mapped[str | None] = mapped_column(
        String(80), unique=True, index=True
    )

    def is_live(self, now: datetime) -> bool:
        """Whether this holding grants anything right now."""
        if self.status is not AddonStatus.active:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return self.quantity > 0
