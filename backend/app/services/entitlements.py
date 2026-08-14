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

from dataclasses import dataclass, field

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
        features=frozenset({"full_profile", "join_communities", "unlimited_connections"}),
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
