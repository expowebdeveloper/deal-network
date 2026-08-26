"""Add-ons — the layer between a plan's base entitlements and the effective limit.

community_role_and_subs.md sections 15 and 16. Two halves:

  * **The catalogue** (`load`) — what exists, what it costs on each plan, and
    what each one does to which entitlement key. Cached like the plan catalogue,
    because it is read on the same hot path.
  * **A member's holdings** (`active_for`) — which add-ons they have bought and
    how many, filtered to the ones that grant anything *right now*.

Two rules shape everything here.

**An add-on can only raise.** `apply_to_limit` never returns a smaller ceiling
than the plan's own, whatever the rows say. A misconfigured effect is then a
no-op instead of a way to take access away from a paying member, and it means
the entitlement flow can fold add-ons in unconditionally without first checking
whether doing so is safe.

**An expired holding grants nothing, with no sweeper.** `active_for` compares
`expires_at` against the clock on every read, so the ceiling drops the moment a
holding lapses even if nothing has run to mark it expired.

There is deliberately **no built-in fallback catalogue**, unlike
`plan_catalogue`. An unseeded database has no add-ons, so a blocked action
reports `addon_available: false` and offers only the upgrade. Inventing a
default catalogue here would let the API offer a purchase that no price exists
for.

One deviation from the B.4 source table, flagged for the PRD owner: it lists
Priority Support & Onboarding as available on Silver *and* Gold, but Gold's
plan already grants `support.priority`. An `enable` effect on a feature the
plan already carries changes nothing, so a Gold row would charge $20/mo for
no change in access. It is seeded Silver-only. If Gold's tick is meant to be
something lesser than the add-on, the fix is to split the key — not to sell
the same one twice.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import AddonEffect, AddonStatus, PlanTier
from app.models.plan import EntitlementKind

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class Effect:
    """What one add-on does to one entitlement key."""

    addon_code: str
    kind: str
    key: str
    effect: AddonEffect
    amount: int

    def step(self, quantity: int) -> int:
        """How much `quantity` units add. Only `increment` scales."""
        if self.effect is AddonEffect.increment:
            return self.amount * max(quantity, 0)
        return self.amount


@dataclass(frozen=True)
class Price:
    plan_code: PlanTier | None
    price_usd: float
    currency: str
    billing_interval: str
    stripe_price_id: str | None


@dataclass(frozen=True)
class AddonRow:
    code: str
    name: str
    description: str
    unit: str
    max_quantity: int | None
    sort_order: int
    effects: tuple[Effect, ...]
    prices: tuple[Price, ...]

    def price_for(self, plan: PlanTier) -> Price | None:
        """The price on `plan`: a plan-specific row first, then the open row."""
        pinned = [p for p in self.prices if p.plan_code is plan]
        if pinned:
            return pinned[0]
        openly = [p for p in self.prices if p.plan_code is None]
        return openly[0] if openly else None

    def touches(self, key: str) -> bool:
        return any(effect.key == key for effect in self.effects)


@dataclass(frozen=True)
class Catalogue:
    addons: dict[str, AddonRow]
    from_database: bool

    def ordered(self) -> list[AddonRow]:
        return sorted(self.addons.values(), key=lambda a: (a.sort_order, a.code))

    def raising(self, key: str) -> list[AddonRow]:
        """Every add-on whose effects touch `key`, cheapest-ordered."""
        return [row for row in self.ordered() if row.touches(key)]

    def purchasable(self, plan: PlanTier, key: str) -> list[AddonRow]:
        """Add-ons that touch `key` *and* have a price on `plan`.

        The distinction matters for the blocked response: an add-on that exists
        but is not sold on this tier must not be offered as the way out.
        """
        return [row for row in self.raising(key) if row.price_for(plan) is not None]


_cache: Catalogue | None = None
_cached_at: float = 0.0


def invalidate() -> None:
    """Drop the snapshot. Call after writing to any add-on table."""
    global _cache, _cached_at
    _cache = None
    _cached_at = 0.0


async def load(db: AsyncSession, *, force: bool = False) -> Catalogue:
    global _cache, _cached_at

    if not force and _cache is not None and (time.monotonic() - _cached_at) < CACHE_TTL_SECONDS:
        return _cache

    catalogue = await _read(db)
    _cache = catalogue
    _cached_at = time.monotonic()
    return catalogue


async def _read(db: AsyncSession) -> Catalogue:
    from app.models import Addon, AddonEntitlementEffect, AddonPrice

    rows = (await db.scalars(select(Addon).where(Addon.is_active.is_(True)))).all()
    if not rows:
        return Catalogue(addons={}, from_database=False)

    effects: dict[str, list[Effect]] = {}
    for row in (await db.scalars(select(AddonEntitlementEffect))).all():
        effects.setdefault(row.addon_code, []).append(Effect(
            addon_code=row.addon_code,
            kind=row.kind,
            key=row.key,
            effect=row.effect,
            amount=row.step,
        ))

    prices: dict[str, list[Price]] = {}
    for row in (await db.scalars(
        select(AddonPrice).where(AddonPrice.is_active.is_(True))
    )).all():
        prices.setdefault(row.addon_code, []).append(Price(
            plan_code=row.plan_code,
            price_usd=float(row.price_usd),
            currency=row.currency,
            billing_interval=row.billing_interval,
            stripe_price_id=row.stripe_price_id or None,
        ))

    return Catalogue(
        addons={
            row.code: AddonRow(
                code=row.code,
                name=row.name,
                description=row.description,
                unit=row.unit,
                max_quantity=row.max_quantity,
                sort_order=row.sort_order,
                effects=tuple(effects.get(row.code, ())),
                prices=tuple(prices.get(row.code, ())),
            )
            for row in rows
        },
        from_database=True,
    )


# --------------------------------------------------------------------------
# A member's holdings
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Holding:
    """One add-on a member holds, with the effects it currently grants."""

    code: str
    name: str
    unit: str
    quantity: int
    expires_at: datetime | None
    effects: tuple[Effect, ...]


@dataclass(frozen=True)
class Grant:
    """One effect applied at a holding's quantity — what the flow folds in."""

    addon_code: str
    effect: AddonEffect
    amount: int
    quantity: int

    @property
    def step(self) -> int:
        return self.amount * self.quantity if self.effect is AddonEffect.increment \
            else self.amount


async def active_for(
    db: AsyncSession, user_id: uuid.UUID, *, now: datetime | None = None
) -> list[Holding]:
    """Every add-on this member holds that grants something right now."""
    from app.models import AddonSubscription

    catalogue = await load(db)
    if not catalogue.addons:
        return []

    now = now or datetime.now(UTC)
    rows = (await db.scalars(
        select(AddonSubscription).where(
            AddonSubscription.user_id == user_id,
            AddonSubscription.status == AddonStatus.active,
        )
    )).all()

    live: list[Holding] = []
    for row in rows:
        if not row.is_live(now):
            continue
        addon = catalogue.addons.get(row.addon_code)
        if addon is None:
            # Bought, then withdrawn from the catalogue or deactivated. Not an
            # error: it simply grants nothing until it is active again.
            logger.debug(
                "Add-on %s held by %s is not in the active catalogue", row.addon_code, user_id
            )
            continue
        quantity = row.quantity
        if addon.max_quantity is not None:
            quantity = min(quantity, addon.max_quantity)
        live.append(Holding(
            code=addon.code,
            name=addon.name,
            unit=addon.unit,
            quantity=quantity,
            expires_at=row.expires_at,
            effects=addon.effects,
        ))
    return live


def grants_for_key(holdings: list[Holding], key: str) -> list[Grant]:
    """The grants that bear on one entitlement key."""
    return [
        Grant(
            addon_code=holding.code,
            effect=effect.effect,
            amount=effect.amount,
            quantity=holding.quantity,
        )
        for holding in holdings
        for effect in holding.effects
        if effect.key == key
    ]


def apply_to_limit(base: int | None, grants: list[Grant]) -> int | None:
    """Fold add-on grants into a plan ceiling. None means unlimited.

    Never returns less than `base`: an add-on raises or does nothing.
    """
    if base is None:  # already unlimited — nothing to raise
        return None
    if not grants:
        return base

    effective = base
    for grant in grants:
        if grant.effect is AddonEffect.unlimited:
            return None
        if grant.effect is AddonEffect.increment:
            effective += max(grant.step, 0)
        elif grant.effect is AddonEffect.set_to:
            effective = max(effective, grant.amount)
        # `enable` is a feature effect; it does not move a ceiling.
    return max(effective, base)


def granted_features(holdings: list[Holding]) -> frozenset[str]:
    """Feature keys an add-on switches on. Add-ons never switch one off."""
    return frozenset({
        effect.key
        for holding in holdings
        for effect in holding.effects
        if effect.kind == EntitlementKind.FEATURE and effect.effect is AddonEffect.enable
    })


# --------------------------------------------------------------------------
# Purchases
# --------------------------------------------------------------------------

async def grant(
    db: AsyncSession,
    user_id: uuid.UUID,
    addon_code: str,
    *,
    quantity: int = 1,
    expires_at: datetime | None = None,
    stripe_subscription_item_id: str | None = None,
    commit: bool = True,
):
    """Record a purchase, or raise the quantity of one already held.

    Called by the billing layer once payment is confirmed — never straight from
    a request handler, because holding an add-on is what raises a ceiling.
    """
    from app.models import AddonSubscription

    existing = await db.scalar(
        select(AddonSubscription).where(
            AddonSubscription.user_id == user_id,
            AddonSubscription.addon_code == addon_code,
        )
    )
    now = datetime.now(UTC)
    if existing is None:
        existing = AddonSubscription(
            user_id=user_id,
            addon_code=addon_code,
            quantity=quantity,
            status=AddonStatus.active,
            started_at=now,
            expires_at=expires_at,
            stripe_subscription_item_id=stripe_subscription_item_id,
        )
        db.add(existing)
    else:
        # A re-purchase of a lapsed holding starts again at `quantity` rather
        # than adding to a number the member is no longer paying for.
        was_live = existing.is_live(now)
        existing.quantity = existing.quantity + quantity if was_live else quantity
        existing.status = AddonStatus.active
        existing.started_at = existing.started_at or now
        existing.expires_at = expires_at
        existing.cancelled_at = None
        if stripe_subscription_item_id:
            existing.stripe_subscription_item_id = stripe_subscription_item_id

    if commit:
        await db.commit()
        await db.refresh(existing)
    return existing


async def revoke(
    db: AsyncSession, user_id: uuid.UUID, addon_code: str, *, commit: bool = True
) -> None:
    """Stop a holding granting anything, keeping the row as history."""
    from app.models import AddonSubscription

    existing = await db.scalar(
        select(AddonSubscription).where(
            AddonSubscription.user_id == user_id,
            AddonSubscription.addon_code == addon_code,
        )
    )
    if existing is None:
        return
    existing.status = AddonStatus.cancelled
    existing.cancelled_at = datetime.now(UTC)
    if commit:
        await db.commit()


# --------------------------------------------------------------------------
# The seed template
# --------------------------------------------------------------------------
# This is a *seed*, not a fallback: nothing reads it at request time. `load`
# answers from the tables only, so an unconfigured deployment offers no add-ons
# rather than offering one that cannot be bought.
#
# The prices are the proposed figures from community_role_and_subs.md, which
# section 25.3 marks as unconfirmed. They are here so the flow is exercisable
# end to end; confirm them before charging anyone.

_MB = 1024 * 1024
_GB = 1024 * _MB

#: The B.4 catalogue. code -> (name, unit, max_quantity, description,
#:                             [(kind, key, effect, amount)],
#:                             [(plan, price_usd)])
#:
#: **Every price row names a plan.** `addon_prices.plan_code` is nullable, and a
#: NULL row means "on any plan at one price" — but nothing here uses it, on
#: purpose. A single flat row is the shape B.4 argues against: it makes "what
#: does this cost on Gold?" un-answerable from the table, and it is the row you
#: would have to split anyway the first time the two tiers need different money.
#: Two explicit rows cost nothing and make the per-plan price directly
#: editable, A/B-testable and auditable.
#:
#: **Plan scoping is the absence of a row, never a condition.** Extra
#: Underwriting Runs has no Gold row because Gold's runs are already unlimited;
#: the Moderator Seat has no Silver row because moderator seats are a Gold
#: capability. Neither fact appears in any `if plan is …` anywhere — the flow
#: offers what `addon_prices` prices for the member's tier and nothing else,
#: so retiring an add-on from a tier is a DELETE and launching a tier is an
#: INSERT.
#:
#: Freemium is deliberately absent from every row. An add-on raises a plan's
#: ceiling; the free tier's answer to a ceiling is to subscribe.
DEFAULT_ADDONS: dict[str, tuple] = {
    "extra_community": (
        "Extra Community", "per community", 5,
        "One more community you can own, on top of what your plan includes.",
        [(EntitlementKind.LIMIT, "community.max_owned", AddonEffect.increment, 1)],
        [(PlanTier.member, 15.0), (PlanTier.professional, 15.0)],
    ),
    "extra_members_100": (
        "Extra Members", "per 100 members", 20,
        "Room for 100 more members in each community you own.",
        [(EntitlementKind.LIMIT, "community.max_members", AddonEffect.increment, 100)],
        [(PlanTier.member, 10.0), (PlanTier.professional, 10.0)],
    ),
    "dataroom_storage_25gb": (
        "Extra Data Room Storage", "per 25 GB", 20,
        "Twenty-five more gigabytes of data room storage.",
        [(EntitlementKind.LIMIT, "files.max_storage_bytes", AddonEffect.increment, 25 * _GB)],
        [(PlanTier.member, 5.0), (PlanTier.professional, 5.0)],
    ),
    "ai_spend_25": (
        "Extra AI Spend Cap", "per $25", 20,
        "Twenty-five dollars more of AI spend each month.",
        [(EntitlementKind.LIMIT, "ai.spend_cap.usd", AddonEffect.increment, 25)],
        [(PlanTier.member, 10.0), (PlanTier.professional, 10.0)],
    ),
    # Silver only: Gold's underwriting runs are already unlimited, and
    # `apply_to_limit` leaves an unlimited ceiling unlimited — so a Gold row
    # would sell something that provably cannot change anything.
    "underwriting_runs_10": (
        "Extra Underwriting Runs", "per 10 runs", 10,
        "Ten more underwriting runs each month.",
        [(
            EntitlementKind.LIMIT,
            "underwriting.deals.max_per_month", AddonEffect.increment, 10,
        )],
        [(PlanTier.member, 10.0)],
    ),
    # Gold only: moderator seats are a Gold capability, so Silver's route past
    # the ceiling is the upgrade, not a seat.
    "moderator_seat": (
        "Additional Moderator Seat", "per seat", 10,
        "Promote one more member to moderator in a community you own.",
        [(EntitlementKind.LIMIT, "community.max_moderators", AddonEffect.increment, 1)],
        [(PlanTier.professional, 5.0)],
    ),
    # Silver only, and this one differs from the source table — see the note in
    # the module docstring. Gold's plan already carries `support.priority`, and
    # an `enable` effect on a feature the plan grants is a no-op, so a Gold row
    # would take $20/mo for nothing. One row restores it if that is wrong.
    "priority_support": (
        "Priority Support & Onboarding", "per account", 1,
        "Priority support and a guided onboarding session.",
        [(EntitlementKind.FEATURE, "support.priority", AddonEffect.enable, 0)],
        [(PlanTier.member, 20.0)],
    ),
}

#: Codes that were in an earlier catalogue and are not sold any more.
#:
#: Deactivated rather than deleted: `addon_subscriptions` references
#: `addons.code`, so dropping the row would take a member's purchase history
#: with it. An inactive add-on falls out of `load()`, so it stops being offered
#: and stops granting immediately, and the record of who bought it survives.
RETIRED_ADDONS: frozenset[str] = frozenset({
    "storage_10gb",          # replaced by dataroom_storage_25gb
    "underwriting_deals_10",  # replaced by underwriting_runs_10
    "contacts_500",          # never in the B.4 catalogue
    "dataroom_invites_10",   # never in the B.4 catalogue
    "team_seat",             # never in the B.4 catalogue
})


async def seed_addons(db: AsyncSession, *, overwrite: bool = False) -> dict[str, int]:
    """Write DEFAULT_ADDONS into the add-on tables. Idempotent.

    Without `overwrite` it only fills in what is missing, so a deployment that
    has re-priced an add-on — in the database, which is the point of the table —
    keeps its figure across a re-run. `--reset` is the way back to these
    defaults.

    Anything in RETIRED_ADDONS is deactivated in the same pass, so a catalogue
    change is one edit here rather than an edit plus a hand-written UPDATE.
    """
    from app.models import Addon, AddonEntitlementEffect, AddonPrice

    created = updated = effects_created = prices_created = retired = 0
    prices_retired = 0

    for order, (code, spec) in enumerate(DEFAULT_ADDONS.items()):
        name, unit, max_quantity, description, effects, prices = spec

        addon = await db.scalar(select(Addon).where(Addon.code == code))
        if addon is None:
            addon = Addon(code=code)
            db.add(addon)
            created += 1
            fresh = True
        else:
            fresh = False
            if overwrite:
                updated += 1

        if fresh or overwrite:
            addon.name = name
            addon.unit = unit
            addon.description = description
            addon.max_quantity = max_quantity
            addon.sort_order = order
            addon.is_active = True

        existing_effects = {
            row.key: row for row in (await db.scalars(
                select(AddonEntitlementEffect).where(
                    AddonEntitlementEffect.addon_code == code
                )
            )).all()
        }
        for kind, key, effect, amount in effects:
            row = existing_effects.get(key)
            if row is None:
                db.add(AddonEntitlementEffect(
                    addon_code=code, kind=kind, key=key, effect=effect, amount=amount,
                ))
                effects_created += 1
            elif overwrite:
                row.kind, row.effect, row.amount = kind, effect, amount

        existing_prices = {
            (row.plan_code, row.billing_interval): row
            for row in (await db.scalars(
                select(AddonPrice).where(AddonPrice.addon_code == code)
            )).all()
        }
        declared = {(plan_code, "month") for plan_code, _ in prices}

        for plan_code, price_usd in prices:
            row = existing_prices.get((plan_code, "month"))
            if row is None:
                db.add(AddonPrice(
                    addon_code=code, plan_code=plan_code, price_usd=price_usd,
                    currency="usd", billing_interval="month", is_active=True,
                ))
                prices_created += 1
            elif overwrite:
                row.price_usd = price_usd
                row.is_active = True

        # A price row this catalogue no longer declares is switched off. Without
        # this the whole plan-scoping story fails quietly: an add-on that used
        # to be sold on every tier keeps a `plan_code = NULL` row, NULL resolves
        # as "any plan", and the tier it was supposedly retired from goes on
        # being offered it. Removing a tier from `prices` has to be what removes
        # it from the catalogue, or the table is not the source of truth.
        #
        # Only under `overwrite`: a deployment that has added a price row of its
        # own — a Platinum tier, a promotional rate — must not have it deleted
        # by a routine re-seed.
        if overwrite:
            for key, row in existing_prices.items():
                if key not in declared and row.is_active:
                    row.is_active = False
                    prices_retired += 1

    for code in sorted(RETIRED_ADDONS):
        addon = await db.scalar(select(Addon).where(Addon.code == code))
        if addon is not None and addon.is_active:
            addon.is_active = False
            retired += 1
        # Its prices go too, so a re-activation has to re-state what it costs
        # rather than silently reviving figures nobody has looked at since.
        for row in (await db.scalars(
            select(AddonPrice).where(AddonPrice.addon_code == code)
        )).all():
            row.is_active = False

    await db.commit()
    invalidate()
    return {
        "addons_created": created,
        "addons_updated": updated,
        "effects_created": effects_created,
        "prices_created": prices_created,
        "prices_retired": prices_retired,
        "addons_retired": retired,
    }
