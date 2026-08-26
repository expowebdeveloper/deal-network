"""The plan catalogue and its entitlements, as data.

backend_flow.md section 6.2: *"The numeric values should live in database
configuration so they can be changed without application code changes."* These
two tables are that configuration. `services/entitlements.py` reads them through
a cached snapshot and falls back to its own built-in defaults when they are
empty, so the application still runs correctly on a database that has not been
seeded yet.

Splitting a plan's *identity* (`plans`) from what it *grants*
(`plan_entitlements`) means a new capability is a row, not a migration.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import PlanTier, TimestampMixin, UUIDMixin, plan_tier_enum


class EntitlementKind:
    """A row is either a yes/no capability or a numeric ceiling."""

    FEATURE = "feature"
    LIMIT = "limit"


class Plan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plans"

    code: Mapped[PlanTier] = mapped_column(
        plan_tier_enum, unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    # None for a free plan; "month" for the paid tiers.
    interval: Mapped[str | None] = mapped_column(String(16))
    billed_note: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # How far up the seven-phase roadmap this tier reaches.
    max_phase: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Overrides STRIPE_PRICE_* from .env when set, so a Price can be swapped
    # without a redeploy. Blank means "use the environment".
    stripe_price_id: Mapped[str | None] = mapped_column(String(80))

    # No `entitlements` relationship on purpose: plan_catalogue reads both
    # tables in one pass each and assembles the snapshot in Python, so a
    # relationship would only add a per-plan query on a hot path.


class PlanEntitlement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_code", "key", name="uq_plan_entitlement_key"),
    )

    # A real foreign key to plans.code (unique, so it can be an FK target), so
    # an entitlement row cannot outlive the plan it belongs to.
    plan_code: Mapped[PlanTier] = mapped_column(
        plan_tier_enum,
        ForeignKey("plans.code", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # "feature" or "limit" — see EntitlementKind.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # A dotted key from backend_flow.md 6.1 / 6.2, e.g. "community.private".
    key: Mapped[str] = mapped_column(String(80), nullable=False)

    # Features use this.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Limits use these two. `is_unlimited` is explicit rather than encoding
    # "unlimited" as NULL, which would be indistinguishable from "unset".
    limit_value: Mapped[int | None] = mapped_column(Numeric(20, 0))
    is_unlimited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @property
    def value(self) -> int | None:
        """The ceiling, with None meaning unlimited."""
        if self.is_unlimited:
            return None
        return int(self.limit_value) if self.limit_value is not None else 0
