"""Request dependencies: the database session and the signed-in user."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import TokenError, decode_token
from app.models import User
from app.services import tokens as token_service

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
# The raw `Authorization: Bearer …` header, for routes that need the token
# itself rather than just the member behind it (sign-out revokes it).
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_user(db: DbSession, credentials: BearerCredentials) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token subject is invalid"
        ) from exc

    # A signed-out token stays cryptographically valid until it expires, so the
    # denylist is what actually ends the session.
    if await token_service.is_revoked(db, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been signed out",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not available"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(db: DbSession, credentials: BearerCredentials) -> User | None:
    """For endpoints that show more detail to signed-in members but allow anonymous."""
    if credentials is None:
        return None
    try:
        return await get_current_user(db, credentials)
    except HTTPException:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def require_terms_accepted(db: DbSession, current_user: CurrentUser) -> User:
    """Block everything past sign-in until the member has agreed to the terms.

    Runs before `require_plan_selected` wherever both apply, so a member who has
    done neither is told about the first step rather than the second. `detail` is
    a stable code the SPA switches on.
    """
    from app.services import terms as terms_service  # imported here to avoid a cycle

    if not await terms_service.has_accepted(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="terms_not_accepted",
        )
    return current_user


TermsGated = Annotated[User, Depends(require_terms_accepted)]


async def require_plan_selected(db: DbSession, current_user: CurrentUser) -> User:
    """Block the app until the member has chosen a plan.

    Enforced server-side as well as in the router, so the gate cannot be skipped
    by calling the API directly. `detail` is a stable code the SPA switches on.
    """
    from app.models import PlanSelection  # imported here to avoid a cycle

    chosen = await db.scalar(
        select(PlanSelection.id).where(
            PlanSelection.user_id == current_user.id,
            PlanSelection.is_current.is_(True),
        )
    )
    if chosen is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="plan_not_selected",
        )
    return current_user


PlanGated = Annotated[User, Depends(require_plan_selected)]

# Both gates, in the order a member meets them. Use this on any route that is
# part of the product proper, so no endpoint can pick up one gate and miss the
# other — `api/router.py` applies it to whole routers, and routes that live in
# an ungated router (the member directory, in routes/users.py) apply it here.
GATES = [Depends(require_terms_accepted), Depends(require_plan_selected)]


async def _plan_of(db: DbSession, user_id) -> "PlanTier":  # noqa: F821
    from app.models import PlanTier, Subscription  # imported here to avoid a cycle

    subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    return subscription.plan if subscription else PlanTier.early_access


def require_phase(phase: int):
    """Dependency factory: refuse the call unless the plan reaches a build phase.

    The counterpart to `require_feature` below, for whole phases rather than
    individual ticks: put it on the routes a phase introduces and the tier rules
    (free → phase 1, Member → 1–4, Professional → all of them) are enforced in
    one place instead of being re-derived per route.
    """
    async def dependency(db: DbSession, current_user: CurrentUser) -> User:
        from app.services import entitlements as entitlement_service

        plan = await _plan_of(db, current_user.id)
        if not entitlement_service.phase_included(plan, phase):
            needed = entitlement_service.plan_needed_for_phase(phase)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="upgrade_required",
                headers={
                    "X-Required-Plan": needed.value if needed else "",
                    "X-Required-Phase": str(phase),
                },
            )
        return current_user

    return dependency


def require_feature(feature: str):
    """Dependency factory: refuse the call unless the member's plan carries a tick.

    Returns `403 {"detail": "upgrade_required"}` — a stable code, like the two
    gates above — with the plan that would unlock it in the `X-Required-Plan`
    header, so a client can say *which* plan to upgrade to without parsing prose.
    """
    async def dependency(db: DbSession, current_user: CurrentUser) -> User:
        from app.services import entitlements as entitlement_service

        plan = await _plan_of(db, current_user.id)
        if not entitlement_service.allows(plan, feature):
            needed = entitlement_service.plan_needed_for_feature(feature)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="upgrade_required",
                headers={
                    "X-Required-Plan": needed.value if needed else "",
                    "X-Required-Feature": feature,
                },
            )
        return current_user

    return dependency
