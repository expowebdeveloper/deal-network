"""Community membership — backend_flow.md section 13.

Four ways in, and they are deliberately distinct:

    POST /join            the member joins, when the policy allows it
    POST /join-requests   the member asks, and waits for approval
    POST /members         an owner/admin adds an existing user directly
    POST /invites         an invitation, accepted later  (not in this pass)

and two ways out, which are not the same thing:

    remove — the membership ends; they may rejoin
    ban    — the membership ends and they may not rejoin until it is lifted

Removal never touches the person's Deal Network account (section 13).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core import errors
from app.models import (
    ACTIVE_MEMBER_STATUSES, CommunityMember, CommunityRole, JoinPolicy, MembershipStatus, User,
)
from app.schemas.common import Message, Page
from app.schemas.communities_v1 import (
    BanRequest, CommunityOut, JoinResult, MemberAdd, MemberOut, MuteRequest, RoleUpdate,
)
from app.services import communities as service
from app.services import community_permissions as perms
from app.services.community_permissions import Permission

from .communities import _actor, _decorate, resolve

router = APIRouter(prefix="/communities", tags=["members-v1"])


async def _as_join_result(db: DbSession, community, membership, user_id) -> JoinResult:
    await db.refresh(community)
    card = (await _decorate(db, [community], user_id))[0]
    return JoinResult(status=membership.status, role=membership.role, community=card)


# --------------------------------------------------------------------------
# Joining
# --------------------------------------------------------------------------

@router.post(
    "/{community_id}/join", response_model=JoinResult, status_code=status.HTTP_201_CREATED
)
async def join_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> JoinResult:
    """Join outright on an open community; queue for approval on a gated one."""
    community = await resolve(db, community_id)
    await service.require_view(db, community, current_user.id)
    membership = await service.join_community(db, community, current_user)
    return await _as_join_result(db, community, membership, current_user.id)


@router.post(
    "/{community_id}/join-requests",
    response_model=JoinResult,
    status_code=status.HTTP_201_CREATED,
)
async def request_to_join(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> JoinResult:
    """Ask to join a request-approval community.

    Distinct from /join in the spec, but the same underlying transition — so
    this refuses on an open community rather than quietly creating a request
    nobody will ever look at.
    """
    community = await resolve(db, community_id)
    await service.require_view(db, community, current_user.id)
    if community.join_policy is not JoinPolicy.request:
        raise errors.unprocessable(
            errors.Code.JOIN_POLICY_NOT_ALLOWED,
            "This community does not use join requests. Use /join instead."
            if community.join_policy is JoinPolicy.open
            else "This community is invite only.",
            join_policy=community.join_policy.value,
        )
    membership = await service.join_community(db, community, current_user)
    return await _as_join_result(db, community, membership, current_user.id)


@router.get("/{community_id}/join-requests", response_model=list[MemberOut])
async def list_join_requests(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> list[MemberOut]:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    rows = await service.list_join_requests(db, community, actor)
    return [MemberOut.model_validate(row) for row in rows]


@router.post("/{community_id}/join-requests/{request_id}/approve", response_model=MemberOut)
async def approve_join_request(
    community_id: str, request_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    """`request_id` may be the membership row's id or the applicant's user id."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    membership = await service.approve_join_request(db, community, actor, request_id)
    return MemberOut.model_validate(membership)


@router.post("/{community_id}/join-requests/{request_id}/reject", response_model=Message)
async def reject_join_request(
    community_id: str, request_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> Message:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    await service.reject_join_request(db, community, actor, request_id)
    return Message(detail="Join request rejected")


# --------------------------------------------------------------------------
# The roster
# --------------------------------------------------------------------------

@router.get("/{community_id}/members", response_model=Page[MemberOut])
async def list_members(
    community_id: str,
    db: DbSession,
    current_user: CurrentUser,
    role: CommunityRole | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[MemberOut]:
    """The full roster is members-only; the facepile on the card is not."""
    community = await resolve(db, community_id)
    await service.require_membership(db, community, current_user.id)

    filters = [
        CommunityMember.community_id == community.id,
        CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
    ]
    if role is not None:
        filters.append(CommunityMember.role == role)

    total = await db.scalar(select(func.count(CommunityMember.id)).where(*filters)) or 0
    rows = (
        await db.scalars(
            select(CommunityMember)
            .where(*filters)
            .order_by(CommunityMember.role, CommunityMember.created_at)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return Page(
        items=[MemberOut.model_validate(row) for row in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get("/{community_id}/members/{user_id}", response_model=MemberOut)
async def read_member(
    community_id: str, user_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    community = await resolve(db, community_id)
    await service.require_membership(db, community, current_user.id)
    membership = await service.membership_of(db, community.id, user_id)
    if membership is None or membership.status not in ACTIVE_MEMBER_STATUSES:
        raise errors.not_found(
            errors.Code.MEMBER_NOT_FOUND, "That person is not a member of this community."
        )
    return MemberOut.model_validate(membership)


@router.post(
    "/{community_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
async def add_member(
    community_id: str, payload: MemberAdd, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    """Add an existing Deal Network user directly — section 13's add-member flow.

    Not the same as an invitation: the membership becomes active immediately, so
    it needs the Add Members permission and cannot grant OWNER.
    """
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)

    target = await db.get(User, payload.user_id)
    if target is None or not target.is_active:
        raise errors.not_found(errors.Code.MEMBER_NOT_FOUND, "That user does not exist.")

    membership = await service.add_member(db, community, actor, target, payload.role)
    return MemberOut.model_validate(membership)


# --------------------------------------------------------------------------
# Member administration
# --------------------------------------------------------------------------

@router.post("/{community_id}/members/{user_id}/remove", response_model=Message)
async def remove_member(
    community_id: str, user_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> Message:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    await service.remove_member(db, community, actor, user_id)
    return Message(detail="Member removed from the community")


@router.post("/{community_id}/members/{user_id}/ban", response_model=MemberOut)
async def ban_member(
    community_id: str, user_id: uuid.UUID, payload: BanRequest,
    db: DbSession, current_user: CurrentUser,
) -> MemberOut:
    """Ban, optionally for a number of days. Omit `days` for a permanent ban."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    membership = await service.ban_member(
        db, community, actor, user_id, days=payload.days, reason=payload.reason
    )
    return MemberOut.model_validate(membership)


@router.post("/{community_id}/members/{user_id}/unban", response_model=MemberOut)
async def unban_member(
    community_id: str, user_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    """Lift a ban. They are not re-admitted — they may now rejoin like anyone."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    membership = await service.unban_member(db, community, actor, user_id)
    return MemberOut.model_validate(membership)


@router.post("/{community_id}/members/{user_id}/mute", response_model=MemberOut)
async def mute_member(
    community_id: str, user_id: uuid.UUID, payload: MuteRequest,
    db: DbSession, current_user: CurrentUser,
) -> MemberOut:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    membership = await service.mute_member(
        db, community, actor, user_id, minutes=payload.minutes
    )
    return MemberOut.model_validate(membership)


@router.post("/{community_id}/members/{user_id}/unmute", response_model=MemberOut)
async def unmute_member(
    community_id: str, user_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    membership = await service.unmute_member(db, community, actor, user_id)
    return MemberOut.model_validate(membership)


@router.patch("/{community_id}/members/{user_id}/role", response_model=MemberOut)
async def change_member_role(
    community_id: str, user_id: uuid.UUID, payload: RoleUpdate,
    db: DbSession, current_user: CurrentUser,
) -> MemberOut:
    """Change a member's role. Setting `owner` transfers ownership.

    A community has exactly one owner (section 4), so a transfer demotes the
    outgoing owner to admin in the same transaction.
    """
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    membership = await service.change_role(db, community, actor, user_id, payload.role)
    return MemberOut.model_validate(membership)
