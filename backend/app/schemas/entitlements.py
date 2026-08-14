"""What a plan unlocks: the modules it reaches and the features it carries."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.base import PlanTier


class ModuleAccess(BaseModel):
    """One roadmap module, and whether the plan in question reaches it."""

    id: str
    title: str
    phase_from: int
    phase_to: int
    phase_label: str
    pro: bool
    included: bool
    # The cheapest plan that does include it — null when already included.
    unlocked_by: PlanTier | None = None


class Entitlements(BaseModel):
    """Everything the client needs to decide what to offer and what to lock."""

    plan: PlanTier
    plan_name: str
    max_phase: int
    pro: bool
    # None means unlimited.
    contact_limit: int | None = None
    contacts_used: int | None = None
    team_seats: int
    features: dict[str, bool]
    modules: list[ModuleAccess]
