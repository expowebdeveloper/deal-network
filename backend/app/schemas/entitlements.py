"""What a plan unlocks: the phases it reaches and the features it carries."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.base import PlanTier


class PhaseAccess(BaseModel):
    """One build phase, and whether the plan in question reaches it."""

    n: int
    name: str
    label: str
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
    phases: list[PhaseAccess]


# --------------------------------------------------------------------------
# The keyed entitlement flow — community_role_and_subs.md B.3
# --------------------------------------------------------------------------
# These mirror `services/entitlements.Decision` and `snapshot()`. They exist so
# the /api/v1 surface is typed and documented rather than returning bare dicts,
# and so the SPA has one shape to switch on whichever action was refused.

class AddonOption(BaseModel):
    """An add-on that would lift the ceiling the caller just hit."""

    code: str
    name: str
    unit: str = ""
    #: How much one unit adds, in the limit's own unit.
    step: int | None = None
    price_usd: float | None = None
    currency: str | None = None
    interval: str | None = None


class DecisionOut(BaseModel):
    """One answer from the entitlement flow, allowed or refused.

    A refusal always carries both ways out, so a cap-hit prompt can reach an
    upgrade or an add-on purchase without another round trip:
    `upgrade_plan` names the cheapest plan that would clear it, and
    `addon_options` lists what could be bought on the current plan instead.
    """

    allowed: bool
    action: str | None = None
    domain: str | None = None
    entitlement_key: str
    reason: str | None = None
    message: str = ""
    current_usage: int | None = None
    limit: int | None = None
    base_limit: int | None = None
    addon_grant: int = 0
    remaining: int | None = None
    unit: str = ""
    current_plan: str
    upgrade_plan: str | None = None
    upgrade_available: bool = False
    addon_available: bool = False
    addon_options: list[AddonOption] = []
    #: False when the ceiling could not be compared against measured usage.
    enforced: bool = True


class DecisionRequest(BaseModel):
    """Ask the flow about an action before attempting it."""

    action: str
    #: How many, or how large — one community, 5 channels, 12 MB.
    amount: int = 1
    #: For per-community ceilings (members, channels, moderators).
    community_id: uuid.UUID | None = None


class AddonHoldingOut(BaseModel):
    code: str
    name: str
    unit: str = ""
    quantity: int
    expires_at: str | None = None


class UsageRowOut(BaseModel):
    label: str
    used: int | None = None
    limit: int | None = None
    base_limit: int | None = None
    addon_grant: int = 0
    remaining: int | None = None


class EntitlementSnapshotOut(BaseModel):
    """What this member's tier and add-ons currently grant.

    `limits` is the effective ceiling and `base_limits` the plan's own, so a
    client can render "4 (3 + 1 add-on)" without a second call.
    """

    plan: PlanTier
    features: dict[str, bool]
    limits: dict[str, int | None]
    base_limits: dict[str, int | None]
    addons: list[AddonHoldingOut] = []


class UsageReportOut(BaseModel):
    plan: PlanTier
    usage: dict[str, UsageRowOut]


class AddonCatalogueRowOut(BaseModel):
    code: str
    name: str
    description: str = ""
    unit: str = ""
    max_quantity: int | None = None
    #: Which entitlement keys it raises, and by how much.
    effects: dict[str, int | None] = {}
    price_usd: float | None = None
    currency: str | None = None
    interval: str | None = None
    #: True when the member already holds it.
    owned: bool = False
    owned_quantity: int = 0
