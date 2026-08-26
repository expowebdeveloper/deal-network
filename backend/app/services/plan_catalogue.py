"""Loading the plan catalogue out of the database, with a cache.

`services/entitlements.py` is on the hot path — an entitlement is checked on
almost every write in the product — so it cannot issue two queries per check.
This module loads the whole catalogue once into an immutable snapshot and hands
that out until something invalidates it.

Two rules govern the fallback:

  * **An unseeded database must still behave correctly.** If `plans` is empty,
    the snapshot is built from the built-in defaults in `entitlements.py`. The
    application boots and enforces the right limits before `seed_plans` has ever
    run — it just cannot be reconfigured without a deploy.
  * **A partially seeded plan falls back per key, not per plan.** A plan row
    with no entry for `community.max_owned` uses the default for that one key
    rather than reporting "no limit", which would be a way to bypass a ceiling
    by deleting a row.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlanTier
from app.models.plan import EntitlementKind, Plan, PlanEntitlement

logger = logging.getLogger(__name__)

#: How long a snapshot is trusted. Short enough that a change made directly in
#: the database shows up on its own; `invalidate()` is the immediate path.
#: Matters mainly with several worker processes, where one process's
#: `invalidate()` cannot reach the others.
CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class PlanRow:
    code: PlanTier
    name: str
    description: str
    price: str
    currency: str
    interval: str | None
    billed_note: str
    featured: bool
    max_phase: int
    stripe_price_id: str | None


@dataclass(frozen=True)
class Catalogue:
    """An immutable read of the plan tables."""

    plans: dict[PlanTier, PlanRow]
    #: Feature keys the plan *grants* — a row that exists and is enabled.
    features: dict[PlanTier, frozenset[str]]
    #: Feature keys the plan has a row for at all, enabled or not. The
    #: difference from `features` is what makes a per-key fallback possible:
    #: a key with a row that says off is off, and a key with no row falls back
    #: to the built-in default rather than reading as off. Without this, adding
    #: a feature key in code would switch it off for every plan on any database
    #: that has been seeded, until someone re-ran seed_plans.
    declared_features: dict[PlanTier, frozenset[str]]
    limits: dict[PlanTier, dict[str, int | None]]
    #: False when this was built from the built-in defaults rather than the
    #: database — surfaced on /health so an unseeded deployment is visible.
    from_database: bool

    def ordered(self) -> list[PlanRow]:
        from app.services.entitlements import PLAN_ORDER

        return [self.plans[code] for code in PLAN_ORDER if code in self.plans]


_cache: Catalogue | None = None
_cached_at: float = 0.0


def invalidate() -> None:
    """Drop the snapshot. Call after writing to the plan tables."""
    global _cache, _cached_at
    _cache = None
    _cached_at = 0.0


def _defaults() -> Catalogue:
    """The built-in catalogue from entitlements.py, as a snapshot."""
    from app.services import entitlements as ent

    plans = {}
    for code in ent.PLAN_ORDER:
        name, description, featured = DEFAULT_COPY[code]
        paid = code is not PlanTier.early_access
        plans[code] = PlanRow(
            code=code,
            name=name,
            description=description,
            price=DEFAULT_PRICES[code],
            currency="usd",
            interval="month" if paid else None,
            billed_note=DEFAULT_BILLED[code],
            featured=featured,
            max_phase=ent.access_for(code).max_phase,
            stripe_price_id=None,
        )
    every_key = frozenset(
        key for tier in ent.PLAN_ORDER for key in ent.FEATURE_MATRIX[tier]
    )
    return Catalogue(
        plans=plans,
        features={code: ent.FEATURE_MATRIX[code] for code in ent.PLAN_ORDER},
        declared_features={code: every_key for code in ent.PLAN_ORDER},
        limits={code: dict(ent.LIMIT_MATRIX[code]) for code in ent.PLAN_ORDER},
        from_database=False,
    )


DEFAULT_PRICES: dict[PlanTier, str] = {
    PlanTier.early_access: "0",
    PlanTier.member: "25",
    PlanTier.professional: "100",
}

#: Display names are the product's vocabulary; the enum codes beside them are
#: what Stripe, the API and the SPA key on and do not change. The pairing is
#: fixed by price: Freemium $0, Silver $25, Gold $100.
DEFAULT_COPY: dict[PlanTier, tuple[str, str, bool]] = {
    PlanTier.early_access: (
        "Freemium",
        "For everyone on the network while we grow the first few hundred members.",
        False,
    ),
    PlanTier.member: (
        "Silver",
        "For individual developers, brokers and investors running their own relationships.",
        True,
    ),
    PlanTier.professional: (
        "Gold",
        "For firms running a team, with several people working the same relationships.",
        False,
    ),
}

DEFAULT_BILLED: dict[PlanTier, str] = {
    PlanTier.early_access: "No card required",
    PlanTier.member: "Billed monthly · cancel anytime",
    PlanTier.professional: "Billed monthly · includes 5 seats",
}


async def load(db: AsyncSession, *, force: bool = False) -> Catalogue:
    """The catalogue, from cache when it is fresh."""
    global _cache, _cached_at

    if not force and _cache is not None and (time.monotonic() - _cached_at) < CACHE_TTL_SECONDS:
        return _cache

    catalogue = await _read(db)
    _cache = catalogue
    _cached_at = time.monotonic()
    return catalogue


async def _read(db: AsyncSession) -> Catalogue:
    from app.services import entitlements as ent

    rows = (await db.scalars(select(Plan).where(Plan.is_active.is_(True)))).all()
    if not rows:
        logger.debug("Plan tables are empty — using built-in entitlement defaults")
        return _defaults()

    entitlements = (await db.scalars(select(PlanEntitlement))).all()
    by_plan: dict[PlanTier, list[PlanEntitlement]] = {}
    for row in entitlements:
        by_plan.setdefault(row.plan_code, []).append(row)

    plans: dict[PlanTier, PlanRow] = {}
    features: dict[PlanTier, frozenset[str]] = {}
    declared: dict[PlanTier, frozenset[str]] = {}
    limits: dict[PlanTier, dict[str, int | None]] = {}

    for plan in rows:
        plans[plan.code] = PlanRow(
            code=plan.code,
            name=plan.name,
            description=plan.description,
            price=f"{plan.price_usd:.0f}" if plan.price_usd == int(plan.price_usd)
            else f"{plan.price_usd}",
            currency=plan.currency,
            interval=plan.interval,
            billed_note=plan.billed_note,
            featured=plan.featured,
            max_phase=plan.max_phase,
            stripe_price_id=plan.stripe_price_id or None,
        )

        rows_for_plan = by_plan.get(plan.code, [])
        features[plan.code] = frozenset({
            row.key for row in rows_for_plan
            if row.kind == EntitlementKind.FEATURE and row.enabled
        })
        declared[plan.code] = frozenset({
            row.key for row in rows_for_plan if row.kind == EntitlementKind.FEATURE
        })

        # Start from the defaults so a missing row cannot read as "no ceiling".
        ceilings: dict[str, int | None] = dict(ent.LIMIT_MATRIX.get(plan.code, {}))
        for row in by_plan.get(plan.code, []):
            if row.kind == EntitlementKind.LIMIT:
                ceilings[row.key] = row.value
        limits[plan.code] = ceilings

    # A tier missing from the table entirely still has to resolve — otherwise a
    # deleted row would 500 every request from a member on that plan.
    for code in ent.PLAN_ORDER:
        if code not in plans:
            logger.warning("Plan %s is missing from the plans table — using defaults", code)
            fallback = _defaults()
            plans.setdefault(code, fallback.plans[code])
            features.setdefault(code, fallback.features[code])
            declared.setdefault(code, fallback.declared_features[code])
            limits.setdefault(code, fallback.limits[code])

    return Catalogue(
        plans=plans, features=features, declared_features=declared,
        limits=limits, from_database=True,
    )


async def seed_plans(db: AsyncSession, *, overwrite: bool = False) -> dict[str, int]:
    """Write the built-in catalogue into the plan tables.

    Idempotent. By default it only fills in what is missing, so a deployment
    that has tuned a limit in the database keeps its value; `overwrite=True`
    resets everything to the built-in defaults.
    """
    from app.services import entitlements as ent

    defaults = _defaults()
    created_plans = updated_plans = created_rows = updated_rows = 0

    for code in ent.PLAN_ORDER:
        row = defaults.plans[code]
        plan = await db.scalar(select(Plan).where(Plan.code == code))
        is_new = plan is None
        if is_new:
            plan = Plan(code=code)
            db.add(plan)
            created_plans += 1
        elif overwrite:
            updated_plans += 1

        # Only write the plan's own fields when it is new, or when the caller
        # asked to reset. Otherwise a tuned price or description survives.
        if is_new or overwrite:
            plan.name = row.name
            plan.description = row.description
            plan.price_usd = float(row.price)
            plan.currency = row.currency
            plan.interval = row.interval
            plan.billed_note = row.billed_note
            plan.featured = row.featured
            plan.max_phase = row.max_phase
            plan.sort_order = ent.PLAN_ORDER.index(code)
            plan.is_active = True

        # Every key any plan knows about gets a row, so a feature that is *off*
        # for a tier is recorded as off rather than merely absent.
        every_feature = sorted({k for tier in ent.PLAN_ORDER for k in ent.FEATURE_MATRIX[tier]})
        every_limit = sorted({k for tier in ent.PLAN_ORDER for k in ent.LIMIT_MATRIX[tier]})

        existing = {
            e.key: e for e in (await db.scalars(
                select(PlanEntitlement).where(PlanEntitlement.plan_code == code)
            )).all()
        }

        for key in every_feature:
            enabled = key in ent.FEATURE_MATRIX[code]
            entry = existing.get(key)
            if entry is None:
                db.add(PlanEntitlement(
                    plan_code=code, kind=EntitlementKind.FEATURE, key=key, enabled=enabled
                ))
                created_rows += 1
            elif overwrite:
                entry.kind = EntitlementKind.FEATURE
                entry.enabled = enabled
                updated_rows += 1

        for key in every_limit:
            ceiling = ent.LIMIT_MATRIX[code].get(key)
            entry = existing.get(key)
            if entry is None:
                db.add(PlanEntitlement(
                    plan_code=code, kind=EntitlementKind.LIMIT, key=key,
                    limit_value=None if ceiling is None else ceiling,
                    is_unlimited=ceiling is None,
                ))
                created_rows += 1
            elif overwrite:
                entry.kind = EntitlementKind.LIMIT
                entry.limit_value = None if ceiling is None else ceiling
                entry.is_unlimited = ceiling is None
                updated_rows += 1

    await db.commit()
    invalidate()
    return {
        "plans_created": created_plans,
        "plans_updated": updated_plans,
        "entitlements_created": created_rows,
        "entitlements_updated": updated_rows,
    }
