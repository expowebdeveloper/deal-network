"""What each plan actually unlocks.

Two things are described here, and they are the same two things the pricing page
and the landing page show:

1. **Modules** — the platform is built in phases (see the landing page roadmap),
   and a plan reaches up to a phase. Free stops at phase 1, Member at phase 3,
   Professional reaches everything including the Pro-only module.

2. **Features** — the ticks on the plan cards: contact limits, the pipeline
   board, creating communities, introduction requests, team seats.

A module unlocks only when its *whole* phase range is within the plan's reach, so
"Analytics · Phase 3–4" belongs to Professional rather than Member — it is not
finished until phase 4, and Professional is the tier that advertises "early
access to what ships next". Change `_reaches` if a module should instead unlock
as soon as its first phase is in range.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import PlanTier

# --- The modules, exactly as the landing page lists them ------------------

@dataclass(frozen=True)
class Module:
    id: str
    title: str
    phase_from: int
    phase_to: int
    pro: bool = False

    @property
    def phase_label(self) -> str:
        if self.phase_from == self.phase_to:
            return f"Phase {self.phase_from}"
        return f"Phase {self.phase_from}–{self.phase_to}"


MODULES: list[Module] = [
    Module("forum", "Online Forum & Networking Hub", 1, 1),
    Module("news", "Niche News & Market Analysis", 2, 2),
    Module("crm", "CRM & Deal Pipeline", 2, 2),
    Module("dataroom", "Integrated Data & Deal Room", 2, 3),
    Module("lp", "Smarter LP & Capital Sourcing", 2, 2),
    Module("analytics", "Analytics", 3, 4),
    Module("ai", "AI Underwriting", 4, 4, pro=True),
]

MODULES_BY_ID = {module.id: module for module in MODULES}


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
        features=frozenset({"full_profile", "join_communities", "unlimited_connections"}),
    ),
    PlanTier.member: PlanAccess(
        max_phase=3,
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
        max_phase=max(module.phase_to for module in MODULES),
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


def _reaches(access: PlanAccess, module: Module) -> bool:
    """A module counts as included once the plan reaches its final phase."""
    return module.phase_to <= access.max_phase and (access.pro or not module.pro)


def module_included(plan: PlanTier, module: Module) -> bool:
    return _reaches(access_for(plan), module)


def modules_for(plan: PlanTier) -> list[Module]:
    return [module for module in MODULES if module_included(plan, module)]


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


def plan_needed_for_module(module_id: str) -> PlanTier | None:
    module = MODULES_BY_ID.get(module_id)
    if module is None:
        return None
    for tier in PLAN_ORDER:
        if module_included(tier, module):
            return tier
    return None
