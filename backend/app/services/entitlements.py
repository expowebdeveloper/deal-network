"""What each plan actually unlocks.

Two things are described here, and they are the same two things the pricing page
and the landing page show:

1. **Phases** — the platform is built in seven phases (the phase cards on the
   landing page, and `frontend/src/data/phases.js` behind them). A plan reaches
   up to a phase and everything below it:

       Early access ($0)     phase 1
       Member ($25)          phases 1–4
       Professional ($100)   every phase, 1–7

   Access is cumulative and contiguous: reaching phase 4 means phases 1, 2, 3
   and 4 are all open. There is no plan that skips a phase.

2. **Features** — the ticks on the plan cards: contact limits, the pipeline
   board, creating communities, introduction requests, team seats.

The phase names below are the ones in card.txt, which is also what
`frontend/src/data/phases.js` was transcribed from. Keep the three in step.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.models import PlanTier

# --- The build phases, exactly as the landing page lists them --------------

@dataclass(frozen=True)
class Phase:
    n: int
    name: str

    @property
    def label(self) -> str:
        return f"Phase {self.n}"


PHASES: list[Phase] = [
    Phase(1, "Basic Platform"),
    Phase(2, "CRM, Profiles and Networking"),
    Phase(3, "Data Room and Basic Underwriting"),
    Phase(4, "Advanced Underwriting and Analytics"),
    Phase(5, "AI Agent and Regulatory / Cyber"),
    Phase(6, "Stabilisation, Native Planning, Interview, Team"),
    Phase(7, "Native App and New Features"),
]

PHASES_BY_NUMBER = {phase.n: phase for phase in PHASES}
FIRST_PHASE = PHASES[0].n
LAST_PHASE = PHASES[-1].n


# --- What a plan reaches --------------------------------------------------

@dataclass(frozen=True)
class PlanAccess:
    """How far up the roadmap a plan reaches, and which ticks it carries."""

    max_phase: int
    pro: bool
    # None means no limit.
    contact_limit: int | None
    team_seats: int
    features: frozenset[str] = field(default_factory=frozenset)


# Feature keys are the ticks on the plan cards, in card order.
PLAN_ACCESS: dict[PlanTier, PlanAccess] = {
    PlanTier.early_access: PlanAccess(
        max_phase=1,
        pro=False,
        contact_limit=25,
        team_seats=0,
        # No `create_communities` tick. Freemium joins and participates; it does
        # not start communities. `join_communities` is what it does have, and
        # the two are deliberately separate keys so the distinction survives.
        features=frozenset({
            "full_profile", "join_communities", "unlimited_connections",
        }),
    ),
    PlanTier.member: PlanAccess(
        max_phase=4,
        pro=False,
        contact_limit=None,
        team_seats=0,
        features=frozenset({
            "full_profile", "join_communities", "unlimited_connections",
            "unlimited_contacts", "pipeline_board", "create_communities",
            "introduction_requests",
        }),
    ),
    PlanTier.professional: PlanAccess(
        max_phase=LAST_PHASE,
        pro=True,
        contact_limit=None,
        team_seats=5,
        features=frozenset({
            "full_profile", "join_communities", "unlimited_connections",
            "unlimited_contacts", "pipeline_board", "create_communities",
            "introduction_requests", "team_seats", "shared_company_profile",
            "shared_contact_record", "priority_support", "early_access_to_new",
        }),
    ),
}

# Human wording for the 403 a blocked call gets back.
FEATURE_LABELS: dict[str, str] = {
    "unlimited_contacts": "Unlimited contacts",
    "pipeline_board": "The pipeline board",
    "create_communities": "Creating your own communities",
    "introduction_requests": "Introduction requests",
    "team_seats": "Team seats",
    "shared_company_profile": "A shared company profile",
    "shared_contact_record": "Shared contact records",
    "priority_support": "Priority support",
    "early_access_to_new": "Early access to what ships next",
}

# Cheapest first, so "which plan do I need" answers with the cheapest that works.
PLAN_ORDER: list[PlanTier] = [PlanTier.early_access, PlanTier.member, PlanTier.professional]


def access_for(plan: PlanTier) -> PlanAccess:
    return PLAN_ACCESS[plan]


def phase_included(plan: PlanTier, phase: int) -> bool:
    """A phase is open once the plan reaches it — and every phase below it."""
    return phase <= access_for(plan).max_phase


def phases_for(plan: PlanTier) -> list[Phase]:
    return [phase for phase in PHASES if phase_included(plan, phase.n)]


def allows(plan: PlanTier, feature: str) -> bool:
    return feature in access_for(plan).features


def contact_limit(plan: PlanTier) -> int | None:
    return access_for(plan).contact_limit


def plan_needed_for_feature(feature: str) -> PlanTier | None:
    """The cheapest plan carrying a feature, or None if no plan does."""
    for tier in PLAN_ORDER:
        if allows(tier, feature):
            return tier
    return None


def plan_needed_for_phase(phase: int) -> PlanTier | None:
    """The cheapest plan that reaches a phase, or None if it is past all of them."""
    for tier in PLAN_ORDER:
        if phase_included(tier, phase):
            return tier
    return None


def plan_needed_for_limit(key: str, required: int) -> PlanTier | None:
    """The cheapest plan whose ceiling for `key` reaches `required`."""
    for tier in PLAN_ORDER:
        ceiling = plan_limit(tier, key)
        if ceiling is UNLIMITED or ceiling >= required:
            return tier
    return None


# ==========================================================================
# The service — section 6's class, resolving from a user id
# ==========================================================================

async def effective_plan(db: AsyncSession, user_id: uuid.UUID) -> PlanTier:
    """The plan whose entitlements actually apply to this member right now.

    This is section 5.3 in one function. `subscriptions.plan` records what they
    signed up for; it is not the same question as what they are entitled to. A
    Member whose card was declined and whose subscription Stripe has since moved
    to `unpaid` still has `plan = member` on the row, and must be treated as
    early access until it is paid.
    """
    from app.models import ENTITLED_SUBSCRIPTION_STATUSES, Subscription

    subscription = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    if subscription is None:
        return PlanTier.early_access
    if subscription.plan is PlanTier.early_access:
        return PlanTier.early_access
    if subscription.status not in ENTITLED_SUBSCRIPTION_STATUSES:
        return PlanTier.early_access
    return subscription.plan


async def plan_has_feature(db: AsyncSession, plan: PlanTier, feature_key: str) -> bool:
    """Whether a plan carries a dotted entitlement key, per the configured catalogue.

    The matrices above are the *defaults*; `plan_catalogue` serves whatever the
    plan tables say, falling back to them. Everything that decides access goes
    through here rather than reading FEATURE_MATRIX directly, so a limit tuned
    in the database is actually honoured.

    The fallback is **per key, not per plan**, matching how limits already
    behave: a seeded catalogue that has no row at all for a key answers from the
    built-in default for that one key. Without this, adding a feature key in
    code would silently read as "off for every plan" until someone remembered to
    re-run `seed_plans`.

    Deliberately *not* named `allows`: that name belongs to the older
    plan-card vocabulary above ("create_communities", "pipeline_board"), which
    the pre-v1 routes still use through `deps.require_feature`. The two
    vocabularies describe different things and must not be merged — an earlier
    revision of this file shadowed one with the other and broke every pre-v1
    entitlement check.
    """
    from app.services import plan_catalogue

    key = canonical(feature_key)
    catalogue = await plan_catalogue.load(db)
    granted = catalogue.features.get(plan)
    if granted is None:
        return key in FEATURE_MATRIX[plan]
    if key in granted:
        return True
    if key in catalogue.declared_features.get(plan, frozenset()):
        return False  # the database has a row for it and it says off
    return key in FEATURE_MATRIX[plan]


async def limit_of(db: AsyncSession, plan: PlanTier, limit_key: str) -> int | None:
    """A plan's own ceiling for a key, before any add-on. None means unlimited."""
    from app.services import plan_catalogue

    key = canonical(limit_key)
    catalogue = await plan_catalogue.load(db)
    ceilings = catalogue.limits.get(plan) or LIMIT_MATRIX[plan]
    return ceilings.get(key, LIMIT_MATRIX[plan].get(key))


async def has_feature(db: AsyncSession, user_id: uuid.UUID, feature_key: str) -> bool:
    """Whether this member has a capability — plan or add-on, either counts."""
    context = await resolve(db, user_id)
    return context.has(feature_key)


async def get_limit(db: AsyncSession, user_id: uuid.UUID, feature_key: str) -> int | None:
    """This member's *effective* ceiling: their plan's, raised by their add-ons."""
    context = await resolve(db, user_id)
    return context.limit(feature_key).effective


async def check_limit(
    db: AsyncSession, user_id: uuid.UUID, feature_key: str, current_value: int
) -> bool:
    """True when one more of `feature_key` would still be within the plan.

    `current_value` is what they have now, so the question asked is
    "current + 1 <= ceiling".
    """
    ceiling = await get_limit(db, user_id, feature_key)
    if ceiling is UNLIMITED:
        return True
    return current_value < ceiling


async def cheapest_plan_with(db: AsyncSession, feature_key: str) -> PlanTier | None:
    """The cheapest configured plan carrying a feature."""
    for tier in PLAN_ORDER:
        if await plan_has_feature(db, tier, feature_key):
            return tier
    return None


async def cheapest_plan_for_limit(
    db: AsyncSession, limit_key: str, required: int
) -> PlanTier | None:
    """The cheapest configured plan whose ceiling for `limit_key` reaches `required`.

    Plans only — an add-on on top of a cheaper plan is offered separately, as
    `addon_options` on the decision, so the two routes out of a block stay
    distinguishable to whoever has to render them.
    """
    for tier in PLAN_ORDER:
        ceiling = await limit_of(db, tier, limit_key)
        if ceiling is UNLIMITED or ceiling >= required:
            return tier
    return None


# ==========================================================================
# The access flow — community_role_and_subs.md B.3 and section 7
# ==========================================================================
#
#     User action
#         |
#     Subscription / tier          effective_plan()
#         |
#     Base entitlements            plan_catalogue -> FEATURE_MATRIX / LIMIT_MATRIX
#         |
#     Active add-ons               addons.active_for()
#         |
#     Effective limit              addons.apply_to_limit()
#         |
#     Current usage                usage.current()
#         |
#     Allow, or an upgrade / add-on prompt
#
# Every gated action in the product runs down that column, in that order, in
# `decide()`. Three properties follow from having one implementation:
#
# **Tier is the only input.** The context resolved below holds a plan, a feature
# set, ceilings and add-on holdings. There is no persona in it — `MemberRole`
# (Developer / Investor / Broker / Lender) is not imported by this module and
# cannot be, because nothing here would have anywhere to put it. Two members on
# the same tier with the same add-ons therefore get identical answers to every
# question, whatever they do for a living. `tier_role_entitlement_test.py`
# proves it for all twelve tier/persona pairs rather than trusting the comment.
#
# **Nothing fails silently.** A refusal is a `Decision` with `allowed=False`,
# and every field the client needs to offer a way out is on it: which key,
# what the ceiling was, what usage was, whether an upgrade exists, whether an
# add-on exists, and which ones. `require()` raises it as the section 23 error
# shape. Where usage cannot be measured yet the decision says `enforced=False`
# instead of quietly returning "no".
#
# **Community role is a different axis.** `services/community_permissions.py`
# answers "may this member, in this community, do this" from `CommunityRole`.
# This module answers "does this account's tier include the capability at all".
# Both must pass; neither substitutes for the other.

COUNT = "count"    #: usage + amount must fit under the ceiling
VALUE = "value"    #: the amount itself must fit; usage is irrelevant (file size)


@dataclass(frozen=True)
class Action:
    """One gated thing a member can try to do.

    An action names at most one feature key and at most one limit key. Both are
    checked, feature first, because "your plan does not include this at all" is
    a different prompt from "your plan includes three of these and you have
    three".
    """

    name: str
    domain: str
    feature: str | None = None
    limit: str | None = None
    #: Error code for a feature refusal and for a ceiling refusal. They differ
    #: because the spec gives each ceiling its own code
    #: (COMMUNITY_LIMIT_REACHED, CHANNEL_LIMIT_REACHED, …).
    feature_code: str = errors.Code.ENTITLEMENT_REQUIRED
    limit_code: str = errors.Code.ENTITLEMENT_REQUIRED
    #: Sentence shown when the ceiling is what refused.
    limit_message: str = ""
    unit: str = ""
    mode: str = COUNT
    #: Extra keyword arguments the usage counter needs, e.g. ("community_id",).
    scope: tuple[str, ...] = ()

    def feature_message(self) -> str:
        return f"{label_for(self.feature)} is not included in your plan."


def _action(name: str, domain: str, **kwargs) -> Action:
    return Action(name=name, domain=domain, **kwargs)


#: Every gated action in the product, in one table.
#:
#: A new gated feature adds a row here and calls `require(db, user_id, name)`.
#: It does not write its own plan comparison, and it cannot: the tier is
#: resolved inside `decide`, which no caller can pass a value for.
ACTIONS: dict[str, Action] = {
    # --- Community (sections 8-12) ---------------------------------------
    "community.create": _action(
        "community.create", "community",
        feature=Feature.COMMUNITY_CREATE,
        limit=Limit.COMMUNITY_MAX_OWNED,
        limit_code=errors.Code.COMMUNITY_LIMIT_REACHED,
        limit_message="You have reached your community limit for the current plan.",
        unit="community",
    ),
    "community.join": _action(
        "community.join", "community",
        feature=Feature.COMMUNITY_JOIN,
        limit=Limit.COMMUNITY_MAX_MEMBERS,
        limit_code=errors.Code.COMMUNITY_MEMBER_LIMIT_REACHED,
        limit_message="This community has reached the member limit for its owner's plan.",
        unit="member",
        scope=("community_id",),
    ),
    "community.channel.create": _action(
        "community.channel.create", "community",
        feature=Feature.COMMUNITY_CHANNELS,
        limit=Limit.COMMUNITY_MAX_CHANNELS,
        limit_code=errors.Code.CHANNEL_LIMIT_REACHED,
        limit_message="That is more channels than your plan allows in one community.",
        unit="channel",
        scope=("community_id",),
    ),
    "community.moderator.promote": _action(
        "community.moderator.promote", "community",
        limit=Limit.COMMUNITY_MAX_MODERATORS,
        limit_code=errors.Code.ENTITLEMENT_REQUIRED,
        limit_message="This community has as many moderators as the owner's plan allows.",
        unit="moderator",
        scope=("community_id",),
    ),
    "community.analytics.view": _action(
        "community.analytics.view", "community", feature=Feature.COMMUNITY_ANALYTICS,
    ),

    # --- CRM (section 13) -------------------------------------------------
    "crm.contact.create": _action(
        "crm.contact.create", "crm",
        limit=Limit.CONTACTS_MAX,
        limit_code=errors.Code.CONTACT_LIMIT_REACHED,
        limit_message="You have reached the contact limit for your plan.",
        unit="contact",
    ),
    "crm.pipeline.view": _action("crm.pipeline.view", "crm", feature=Feature.CRM_PIPELINE),
    "crm.introduction.request": _action(
        "crm.introduction.request", "crm", feature=Feature.CRM_INTRODUCTIONS,
    ),
    "crm.team.permissions": _action(
        "crm.team.permissions", "crm", feature=Feature.CRM_PERMISSIONS_ADVANCED,
    ),
    "team.seat.add": _action(
        "team.seat.add", "team",
        feature=Feature.TEAM_SEATS,
        limit=Limit.TEAM_MAX_SEATS,
        limit_code=errors.Code.TEAM_SEAT_LIMIT_REACHED,
        limit_message="Your plan includes no further team seats.",
        unit="seat",
    ),

    # --- Data room (section 14) ------------------------------------------
    "dataroom.file.upload": _action(
        "dataroom.file.upload", "dataroom",
        feature=Feature.FILES_UPLOAD,
        limit=Limit.FILES_MAX_STORAGE_BYTES,
        limit_code=errors.Code.STORAGE_QUOTA_EXCEEDED,
        limit_message="That upload would take you past your plan's storage allowance.",
        unit="bytes",
    ),
    "dataroom.file.size": _action(
        "dataroom.file.size", "dataroom",
        limit=Limit.FILES_MAX_FILE_SIZE_BYTES,
        limit_code=errors.Code.FILE_SIZE_LIMIT_EXCEEDED,
        limit_message="That file is larger than your plan allows.",
        unit="bytes",
        mode=VALUE,
    ),
    "dataroom.share_link.create": _action(
        "dataroom.share_link.create", "dataroom", feature=Feature.DATAROOM_SHARE_LINKS,
    ),
    "dataroom.external_invite.send": _action(
        "dataroom.external_invite.send", "dataroom",
        feature=Feature.DATAROOM_SHARE_LINKS,
        limit=Limit.DATAROOM_EXTERNAL_INVITES_MONTHLY,
        limit_code=errors.Code.DATAROOM_INVITE_LIMIT_REACHED,
        limit_message="You have used this month's external data room invitations.",
        unit="invitation",
    ),
    "dataroom.access_control.per_file": _action(
        "dataroom.access_control.per_file", "dataroom",
        feature=Feature.DATAROOM_PER_FILE_ACCESS,
    ),

    # --- Underwriting (section 15) ---------------------------------------
    "underwriting.deal.create": _action(
        "underwriting.deal.create", "underwriting",
        feature=Feature.UNDERWRITING,
        limit=Limit.UNDERWRITING_DEALS_MONTHLY,
        limit_code=errors.Code.UNDERWRITING_LIMIT_REACHED,
        limit_message="You have used this month's underwriting runs.",
        unit="deal",
    ),
    "underwriting.sensitivity.run": _action(
        "underwriting.sensitivity.run", "underwriting",
        feature=Feature.UNDERWRITING_SENSITIVITY,
    ),

    # --- Analytics (section 16) ------------------------------------------
    "analytics.benchmarks.view": _action(
        "analytics.benchmarks.view", "analytics", feature=Feature.ANALYTICS_OWN_VS_MARKET,
    ),
    "analytics.dashboard.view": _action(
        "analytics.dashboard.view", "analytics", feature=Feature.ANALYTICS_FULL_DASHBOARD,
    ),
    "analytics.area_aggregates.view": _action(
        "analytics.area_aggregates.view", "analytics",
        feature=Feature.ANALYTICS_AREA_AGGREGATES,
    ),
    "analytics.private_views.view": _action(
        "analytics.private_views.view", "analytics", feature=Feature.ANALYTICS_PRIVATE_VIEWS,
    ),
    "analytics.export": _action(
        "analytics.export", "analytics", feature=Feature.ANALYTICS_EXPORT,
    ),

    # --- AI (section 17) --------------------------------------------------
    "ai.agent.use": _action("ai.agent.use", "ai", feature=Feature.AI_AGENT),
    "ai.provider.connect": _action(
        "ai.provider.connect", "ai", feature=Feature.AI_BYO_PROVIDER,
    ),
    "ai.spend": _action(
        "ai.spend", "ai",
        limit=Limit.AI_SPEND_CAP_USD,
        limit_code=errors.Code.AI_SPEND_CAP_REACHED,
        limit_message="This month's AI spend cap for your plan has been reached.",
        unit="usd",
    ),
    "ai.recommendations.view": _action(
        "ai.recommendations.view", "ai", feature=Feature.AI_PERSONALISED_RECS,
    ),
    "ai.audit_log.read": _action(
        "ai.audit_log.read", "ai", feature=Feature.AI_AUDIT_LOG,
    ),

    # --- Support ----------------------------------------------------------
    "support.priority.use": _action(
        "support.priority.use", "support", feature=Feature.SUPPORT_PRIORITY,
    ),
}


def action_for(name: str) -> Action:
    action = ACTIONS.get(name)
    if action is None:
        # A typo in an action name must not read as "allowed". Failing at the
        # call is the only safe answer, and it fails the same way on every tier.
        raise KeyError(f"Unknown entitlement action: {name!r}")
    return action


def actions_in(domain: str) -> list[Action]:
    return [a for a in ACTIONS.values() if a.domain == domain]


# --------------------------------------------------------------------------
# The resolved context — steps 1 to 4 of the flow, once per request
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Ceiling:
    """One effective limit, and where it came from."""

    key: str
    base: int | None
    effective: int | None
    addon_grant: int
    sources: tuple[str, ...] = ()

    @property
    def unlimited(self) -> bool:
        return self.effective is UNLIMITED


@dataclass(frozen=True)
class Context:
    """Everything the flow needs about one account, resolved once.

    Note what is *not* here: no persona, no community role, no user row. The
    only identity in it is the plan. That is the whole of "tier is the only
    factor" — not a rule applied by convention, but a shape that has nowhere to
    put anything else.
    """

    user_id: uuid.UUID
    plan: PlanTier
    plan_features: frozenset[str]
    addon_features: frozenset[str]
    base_limits: dict[str, int | None]
    holdings: tuple = ()

    @property
    def features(self) -> frozenset[str]:
        return self.plan_features | self.addon_features

    def has(self, feature_key: str) -> bool:
        return canonical(feature_key) in self.features

    def limit(self, limit_key: str) -> Ceiling:
        """The effective ceiling: the plan's, raised by any add-on."""
        from app.services import addons as addon_service

        key = canonical(limit_key)
        base = self.base_limits.get(key, LIMIT_MATRIX[self.plan].get(key))
        grants = addon_service.grants_for_key(list(self.holdings), key)
        effective = addon_service.apply_to_limit(base, grants)
        grant_total = 0
        if base is not None and effective is not None:
            grant_total = effective - base
        return Ceiling(
            key=key,
            base=base,
            effective=effective,
            addon_grant=grant_total,
            sources=tuple(sorted({g.addon_code for g in grants})),
        )


async def resolve(db: AsyncSession, user_id: uuid.UUID) -> Context:
    """Steps 1-4: subscription -> tier -> base entitlements -> active add-ons.

    One call, so a request that checks several keys pays for one plan lookup and
    one add-on lookup rather than one of each per key.
    """
    from app.services import addons as addon_service, plan_catalogue

    plan = await effective_plan(db, user_id)
    catalogue = await plan_catalogue.load(db)
    holdings = await addon_service.active_for(db, user_id)

    declared = catalogue.declared_features.get(plan, frozenset())
    configured = catalogue.features.get(plan)
    if configured is None:
        plan_features = FEATURE_MATRIX[plan]
    else:
        # Per-key fallback, exactly as `plan_has_feature` does it: a key the
        # database has never heard of answers from the built-in default.
        plan_features = frozenset(configured) | frozenset(
            key for key in FEATURE_MATRIX[plan] if key not in declared
        )

    return Context(
        user_id=user_id,
        plan=plan,
        plan_features=plan_features,
        addon_features=addon_service.granted_features(holdings),
        base_limits=dict(catalogue.limits.get(plan) or LIMIT_MATRIX[plan]),
        holdings=tuple(holdings),
    )


# --------------------------------------------------------------------------
# The decision — step 9, and everything the client needs to act on it
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    """The answer to one gated action, allowed or not.

    Section 7's blocked response, plus the fields that make it useful for the
    allowed case too (an "3 of 4 used" line needs the same numbers). `body()` is
    the JSON shape; `raise_for_status()` turns a refusal into the section 23
    error. There is no third outcome — no None, no silent False.
    """

    allowed: bool
    entitlement_key: str
    message: str
    #: FEATURE when the key is a yes/no capability, LIMIT when it is a ceiling.
    #: Decides one thing beyond documentation: a feature refusal also reports
    #: its key as `feature` in `body()`, which is the name the SPA and the
    #: pre-v1 tests have always read.
    kind: str = "feature"
    action: str | None = None
    domain: str | None = None
    reason: str | None = None
    current_usage: int | None = None
    limit: int | None = None
    base_limit: int | None = None
    addon_grant: int = 0
    requested: int = 0
    unit: str = ""
    current_plan: str = ""
    upgrade_plan: str | None = None
    upgrade_available: bool = False
    addon_available: bool = False
    addon_options: tuple[dict, ...] = ()
    #: False when the ceiling could not be compared against real usage because
    #: this deployment has no counter for the key yet. The action is allowed,
    #: and this flag is how a caller knows the allowance was not verified.
    enforced: bool = True

    @property
    def blocked(self) -> bool:
        return not self.allowed

    @property
    def remaining(self) -> int | None:
        """How many more are allowed, or None for unlimited/unknown."""
        if self.limit is None or self.current_usage is None:
            return None
        return max(self.limit - self.current_usage, 0)

    def body(self) -> dict:
        """Section 7's response shape.

        `current` and `current_usage` are the same number under two names:
        `current` is what the community and file modules have always sent and
        what the SPA reads, `current_usage` is the spec's spelling. Both are
        here so neither has to change.
        """
        payload = {
            "allowed": self.allowed,
            "reason": self.reason,
            # The same key under the name each reader expects: `feature` is what
            # the SPA switches on for a capability refusal, `entitlement_key` is
            # the spec's spelling and is always present.
            "feature": self.entitlement_key if self.kind == "feature" else None,
            "action": self.action,
            "domain": self.domain,
            "entitlement_key": self.entitlement_key,
            "current_usage": self.current_usage,
            "current": self.current_usage,
            "limit": self.limit,
            "base_limit": self.base_limit,
            "addon_grant": self.addon_grant,
            "requested": self.requested or None,
            "unit": self.unit or None,
            "current_plan": self.current_plan,
            "upgrade_plan": self.upgrade_plan,
            "upgrade_available": self.upgrade_available,
            "addon_available": self.addon_available,
            "addon_options": list(self.addon_options),
            "enforced": self.enforced,
        }
        return {k: v for k, v in payload.items() if v is not None or k in _ALWAYS}

    def raise_for_status(self) -> None:
        """Raise the section 23 error when blocked. A no-op when allowed."""
        if self.allowed:
            return
        details = self.body()
        details.pop("allowed", None)
        details.pop("reason", None)
        raise errors.forbidden(self.reason, self.message, **details)


#: Keys that stay in `body()` even when null, because their absence would read
#: as a different answer: "no ceiling" is not "unlimited", and a blocked
#: decision with no `upgrade_plan` means there is no plan that would help.
_ALWAYS = frozenset({
    "allowed", "reason", "limit", "current_usage", "current", "upgrade_plan",
    "upgrade_available", "addon_available",
})


async def _addon_options(
    db: AsyncSession, plan: PlanTier, key: str
) -> tuple[dict, ...]:
    """The add-ons that would lift `key` on this plan, priced."""
    from app.services import addons as addon_service

    catalogue = await addon_service.load(db)
    options = []
    for row in catalogue.purchasable(plan, canonical(key)):
        price = row.price_for(plan)
        step = next(
            (e.amount for e in row.effects if e.key == canonical(key)), None
        )
        options.append({
            "code": row.code,
            "name": row.name,
            "unit": row.unit,
            "step": step,
            "price_usd": price.price_usd if price else None,
            "currency": price.currency if price else None,
            "interval": price.billing_interval if price else None,
        })
    return tuple(options)


async def decide_feature(
    db: AsyncSession,
    user_id: uuid.UUID,
    feature_key: str,
    *,
    code: str = errors.Code.ENTITLEMENT_REQUIRED,
    message: str | None = None,
    context: Context | None = None,
    action: Action | None = None,
) -> Decision:
    """Is this capability in the plan (or bought as an add-on)?"""
    context = context or await resolve(db, user_id)
    key = canonical(feature_key)

    if context.has(key):
        return Decision(
            allowed=True,
            entitlement_key=key,
            message="",
            action=action.name if action else None,
            domain=action.domain if action else None,
            current_plan=context.plan.value,
        )

    needed = await cheapest_plan_with(db, key)
    options = await _addon_options(db, context.plan, key)
    return Decision(
        allowed=False,
        entitlement_key=key,
        kind="feature",
        reason=code,
        message=message or f"{label_for(key)} is not included in your plan.",
        action=action.name if action else None,
        domain=action.domain if action else None,
        current_plan=context.plan.value,
        upgrade_plan=needed.value if needed else None,
        upgrade_available=needed is not None,
        addon_available=bool(options),
        addon_options=options,
    )


async def decide_limit(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit_key: str,
    *,
    current_usage: int | None,
    amount: int = 1,
    mode: str = COUNT,
    code: str = errors.Code.ENTITLEMENT_REQUIRED,
    message: str | None = None,
    unit: str = "",
    context: Context | None = None,
    action: Action | None = None,
) -> Decision:
    """Steps 5-9: effective limit, current usage, allow or prompt.

    `current_usage` of None means "this deployment cannot measure it yet". That
    is answered honestly rather than as zero: a non-zero ceiling allows the
    action with `enforced=False`, and a ceiling of *zero* still refuses, because
    no count is needed to be sure about zero.
    """
    context = context or await resolve(db, user_id)
    key = canonical(limit_key)
    ceiling = context.limit(key)

    def verdict(allowed: bool, *, enforced: bool = True, **extra) -> Decision:
        return Decision(
            allowed=allowed,
            entitlement_key=key,
            kind="limit",
            reason=None if allowed else code,
            message="" if allowed else (message or f"{label_for(key)} is at your plan's limit."),
            action=action.name if action else None,
            domain=action.domain if action else None,
            current_usage=current_usage,
            limit=ceiling.effective,
            base_limit=ceiling.base,
            addon_grant=ceiling.addon_grant,
            requested=amount,
            unit=unit or (action.unit if action else ""),
            current_plan=context.plan.value,
            enforced=enforced,
            **extra,
        )

    if ceiling.effective is UNLIMITED:
        return verdict(True)

    if mode == VALUE:
        # A size, not a count: the value itself must fit, and `value == ceiling`
        # is allowed.
        if amount <= ceiling.effective:
            return verdict(True)
        required = amount
    else:
        if amount <= 0:
            return verdict(True)  # adding nothing is always within a ceiling
        if ceiling.effective > 0 and current_usage is None:
            # Unmeasurable usage against a real ceiling. Allowed, and flagged,
            # so this shows up as an unenforced allowance rather than as a
            # silent pass or a silent block.
            #
            # Two quite different situations, logged differently. A key with no
            # counter at all is a gap in this deployment and worth a warning. A
            # key that *has* a counter but was asked without the scope it needs
            # is the /actions preview asking "in general", which is expected and
            # only worth a debug line — warning on it would bury the first case.
            from app.services import usage as usage_service

            if usage_service.has_counter(key):
                logger.debug(
                    "%s asked without the scope %s needs — unenforced against %s",
                    action.name if action else "action", key, ceiling.effective,
                )
            else:
                logger.warning(
                    "No usage counter for %s — allowing %s unenforced against a ceiling of %s",
                    key, action.name if action else "action", ceiling.effective,
                )
            return verdict(True, enforced=False)
        used = current_usage or 0
        if used + amount <= ceiling.effective:
            return verdict(True)
        required = used + amount

    needed = await cheapest_plan_for_limit(db, key, required)
    options = await _addon_options(db, context.plan, key)
    return verdict(
        False,
        upgrade_plan=needed.value if needed else None,
        upgrade_available=needed is not None,
        addon_available=bool(options),
        addon_options=options,
    )


async def decide(
    db: AsyncSession,
    user_id: uuid.UUID,
    action: str | Action,
    *,
    usage: int | None = None,
    amount: int = 1,
    context: Context | None = None,
    **scope,
) -> Decision:
    """Run the whole flow for one named action. Never raises for a refusal.

    `usage` overrides the registered counter, for callers that have already
    counted (under a lock, say, which is the only way a create-then-count race
    can be closed). Everything else comes from the registry, so a caller cannot
    accidentally supply a tier, a persona or a ceiling of its own.
    """
    from app.services import usage as usage_service

    spec = action_for(action) if isinstance(action, str) else action
    context = context or await resolve(db, user_id)

    if spec.feature is not None:
        verdict = await decide_feature(
            db, user_id, spec.feature,
            code=spec.feature_code, context=context, action=spec,
        )
        if verdict.blocked:
            return verdict

    if spec.limit is None:
        return Decision(
            allowed=True,
            entitlement_key=spec.feature or spec.name,
            message="",
            action=spec.name,
            domain=spec.domain,
            current_plan=context.plan.value,
        )

    measured = usage
    if measured is None and spec.mode == COUNT:
        measured = await usage_service.current(
            db, user_id, canonical(spec.limit),
            **{name: scope.get(name) for name in spec.scope},
        )

    return await decide_limit(
        db, user_id, spec.limit,
        current_usage=measured,
        amount=amount,
        mode=spec.mode,
        code=spec.limit_code,
        message=spec.limit_message or None,
        unit=spec.unit,
        context=context,
        action=spec,
    )


async def require(
    db: AsyncSession,
    user_id: uuid.UUID,
    action: str | Action,
    *,
    usage: int | None = None,
    amount: int = 1,
    context: Context | None = None,
    **scope,
) -> Decision:
    """`decide`, raising the section 23 error when the answer is no.

    This is what a route or service calls. The returned decision is the allowed
    one, so a caller that wants to say "2 of 3 used" can read it.
    """
    verdict = await decide(
        db, user_id, action, usage=usage, amount=amount, context=context, **scope
    )
    verdict.raise_for_status()
    return verdict


# --------------------------------------------------------------------------
# The older shapes, now thin wrappers
# --------------------------------------------------------------------------
# These three are what the community, file and CRM modules already call. They
# keep their signatures and their error codes, and they now run the same flow as
# `require`, which is how those modules picked up add-on ceilings and the fuller
# blocked payload without a line changing at any call site.

async def require_feature_key(
    db: AsyncSession, user_id: uuid.UUID, feature_key: str
) -> None:
    """Raise the section 23 error unless the plan carries `feature_key`."""
    verdict = await decide_feature(db, user_id, feature_key)
    verdict.raise_for_status()


async def require_within_limit(
    db: AsyncSession, user_id: uuid.UUID, limit_key: str, current_value: int, *,
    code: str, message: str,
) -> None:
    """Raise the section 23 error when one more would breach the plan's ceiling."""
    verdict = await decide_limit(
        db, user_id, limit_key,
        current_usage=current_value, amount=1, mode=COUNT, code=code, message=message,
    )
    verdict.raise_for_status()


async def require_value_within_limit(
    db: AsyncSession, user_id: uuid.UUID, limit_key: str, value: int, *,
    code: str, message: str, unit: str = "",
) -> None:
    """Like `require_within_limit`, but for a size rather than a count.

    The difference is off-by-one: a count asks "may I add one more", a size asks
    "is this value itself within the ceiling". Used for file size and storage,
    where `value` is bytes and `value == ceiling` is allowed.
    """
    verdict = await decide_limit(
        db, user_id, limit_key,
        current_usage=None, amount=value, mode=VALUE, code=code, message=message, unit=unit,
    )
    verdict.raise_for_status()


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

async def every_feature_key(db: AsyncSession) -> list[str]:
    from app.services import plan_catalogue

    catalogue = await plan_catalogue.load(db)
    keys = {k for tier in PLAN_ORDER for k in FEATURE_MATRIX[tier]}
    for granted in catalogue.features.values():
        keys |= set(granted)
    for declared in catalogue.declared_features.values():
        keys |= set(declared)
    return sorted(keys)


async def every_limit_key(db: AsyncSession) -> list[str]:
    from app.services import plan_catalogue

    catalogue = await plan_catalogue.load(db)
    keys = {k for tier in PLAN_ORDER for k in LIMIT_MATRIX[tier]}
    for ceilings in catalogue.limits.values():
        keys |= set(ceilings)
    return sorted(keys)


async def features_of(db: AsyncSession, plan: PlanTier) -> dict[str, bool]:
    return {
        key: await plan_has_feature(db, plan, key)
        for key in await every_feature_key(db)
    }


async def limits_of(db: AsyncSession, plan: PlanTier) -> dict[str, int | None]:
    from app.services import plan_catalogue

    catalogue = await plan_catalogue.load(db)
    ceilings = dict(catalogue.limits.get(plan) or LIMIT_MATRIX[plan])
    # Per-key fallback, so a key the tables have never heard of still reports
    # its built-in ceiling rather than vanishing from the response.
    for key, value in LIMIT_MATRIX[plan].items():
        ceilings.setdefault(key, value)
    return ceilings


async def snapshot(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Everything the SPA needs to grey out what a plan does not include.

    `limits` is the *effective* ceiling — the plan's, raised by whatever add-ons
    the member holds — because that is the number a client should show. The
    plan's own figure is alongside it in `base_limits`, so "3 (+1 add-on)" can
    be rendered without a second call.
    """
    context = await resolve(db, user_id)
    keys = await every_limit_key(db)
    ceilings = {key: context.limit(key) for key in keys}
    return {
        "plan": context.plan.value,
        "features": {
            key: context.has(key) for key in await every_feature_key(db)
        },
        "limits": {key: c.effective for key, c in ceilings.items()},
        "base_limits": {key: c.base for key, c in ceilings.items()},
        "addons": [
            {
                "code": holding.code,
                "name": holding.name,
                "unit": holding.unit,
                "quantity": holding.quantity,
                "expires_at": holding.expires_at.isoformat() if holding.expires_at else None,
            }
            for holding in context.holdings
        ],
    }


async def usage_report(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Effective ceiling, current usage and what is left, per measurable key.

    Section 21's telemetry and the SPA's "3 of 4 used" lines read the same
    numbers the flow decides on, rather than counting again themselves.
    """
    from app.services import usage as usage_service

    context = await resolve(db, user_id)
    rows: dict[str, dict] = {}
    for key in usage_service.registered_keys():
        ceiling = context.limit(key)
        used = await usage_service.current(db, user_id, key)
        rows[key] = {
            "label": label_for(key),
            "used": used,
            "limit": ceiling.effective,
            "base_limit": ceiling.base,
            "addon_grant": ceiling.addon_grant,
            "remaining": (
                None if ceiling.effective is UNLIMITED or used is None
                else max(ceiling.effective - used, 0)
            ),
        }
    return {"plan": context.plan.value, "usage": rows}
