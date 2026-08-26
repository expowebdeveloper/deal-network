"""Current usage, per entitlement key.

This is one step of the entitlement flow in community_role_and_subs.md section
7 — the step between *effective limit* and *allow or reject*:

    Subscription -> Plan -> Base entitlements -> Add-ons -> Effective limit
                                                                 |
                                                          >> current usage <<
                                                                 |
                                                     allow, or upgrade prompt

It lives in its own module for one reason: counting usage means reading the
feature tables (communities, contacts, media), and `services/entitlements.py` is
imported *by* those features. Keeping the counters here, behind a registry keyed
on the entitlement key, means entitlements never imports a feature module at
module scope, and a new gated domain registers a counter instead of editing the
entitlement service.

A counter returns `int` when usage is measurable and `None` when it is not —
"this domain has no table yet". `None` is not zero: the caller must not read it
as "plenty of room left". `entitlements.decide` treats an unmeasurable usage
against a non-zero ceiling as allowed-but-unenforced and says so in the
decision, and against a *zero* ceiling as blocked, because a ceiling of zero
needs no count to be certain about.
"""

from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: A counter takes the session, the account owner, and whatever scope the key
#: needs (`community_id` for a per-community ceiling), and answers in the unit
#: the limit is expressed in — communities, contacts, bytes, dollars.
Counter = Callable[..., Awaitable[int | None]]

_counters: dict[str, Counter] = {}


def counts(*keys: str):
    """Register a counter for one or more entitlement keys."""

    def register(fn: Counter) -> Counter:
        for key in keys:
            _counters[key] = fn
        return fn

    return register


def has_counter(key: str) -> bool:
    return key in _counters


def registered_keys() -> list[str]:
    return sorted(_counters)


async def current(
    db: AsyncSession, user_id: uuid.UUID, key: str, **scope
) -> int | None:
    """Usage for `key`, or None when this deployment cannot measure it yet."""
    counter = _counters.get(key)
    if counter is None:
        return None
    return await counter(db, user_id, **scope)


# --------------------------------------------------------------------------
# Community
# --------------------------------------------------------------------------
# Every counter imports its models inside the function. `services.communities`
# imports `services.entitlements`, which reaches this module, so a module-level
# import here would close the loop.

@counts("community.max_owned")
async def _owned_communities(db: AsyncSession, user_id: uuid.UUID, **_) -> int:
    from app.services.communities import owned_count

    return await owned_count(db, user_id)


@counts("community.max_members")
async def _community_members(
    db: AsyncSession, user_id: uuid.UUID, *, community_id: uuid.UUID | None = None, **_
) -> int | None:
    """Members of one community. The ceiling belongs to its owner, not the joiner."""
    if community_id is None:
        return None
    from app.models import ACTIVE_MEMBER_STATUSES, CommunityMember

    return await db.scalar(
        select(func.count(CommunityMember.id)).where(
            CommunityMember.community_id == community_id,
            CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
        )
    ) or 0


@counts("community.max_channels")
async def _community_channels(
    db: AsyncSession, user_id: uuid.UUID, *, community_id: uuid.UUID | None = None, **_
) -> int | None:
    if community_id is None:
        return None
    from app.models import CommunityChannel

    return await db.scalar(
        select(func.count(CommunityChannel.id)).where(
            CommunityChannel.community_id == community_id
        )
    ) or 0


@counts("community.max_moderators")
async def _community_moderators(
    db: AsyncSession, user_id: uuid.UUID, *, community_id: uuid.UUID | None = None, **_
) -> int | None:
    if community_id is None:
        return None
    from app.models import ACTIVE_MEMBER_STATUSES, CommunityMember, CommunityRole

    return await db.scalar(
        select(func.count(CommunityMember.id)).where(
            CommunityMember.community_id == community_id,
            CommunityMember.role == CommunityRole.moderator,
            CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
        )
    ) or 0


# --------------------------------------------------------------------------
# CRM
# --------------------------------------------------------------------------

@counts("contacts.max")
async def _contacts(db: AsyncSession, user_id: uuid.UUID, **_) -> int:
    from app.models import Contact

    return await db.scalar(
        select(func.count(Contact.id)).where(Contact.owner_id == user_id)
    ) or 0


# --------------------------------------------------------------------------
# Data room
# --------------------------------------------------------------------------

@counts("files.max_storage_bytes")
async def _storage_used(db: AsyncSession, user_id: uuid.UUID, **_) -> int:
    from app.services.files import storage_used

    return await storage_used(db, user_id)
