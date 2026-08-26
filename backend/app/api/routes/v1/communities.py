"""Community core — backend_flow.md sections 10, 11 and 12.

Routers are thin by design (section 3): each handler resolves the community,
resolves the caller's membership, and hands both to `services/communities.py`.
Every rule that decides an outcome lives there, so an admin job or a background
task can apply the same rules without going through HTTP.

The layered check from section 22 runs in this order on every protected route:

    authentication -> entitlement -> membership -> role permission -> validation
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession
from app.core import errors
from app.models import (
    ACTIVE_MEMBER_STATUSES, Community, CommunityKind, CommunityMember, CommunityStatus,
    MembershipStatus, User, VisibilityLevel,
)
from app.schemas.common import Message, Page
from app.schemas.communities_v1 import (
    AuditEntryOut, CommunityCreate, CommunityDetail, CommunityOut, CommunityUpdate,
    MyAccessOut, PermissionOut,
)
from app.schemas.user import UserSummary
from app.services import audit as audit_service
from app.services import communities as service
from app.services import community_permissions as perms
from sqlalchemy import func, or_, select

router = APIRouter(prefix="/communities", tags=["communities-v1"])

FACEPILE_SIZE = 3


# --------------------------------------------------------------------------
# Shared shaping
# --------------------------------------------------------------------------

async def _decorate(
    db: DbSession, communities: list[Community], user_id: uuid.UUID
) -> list[CommunityOut]:
    """Attach the caller's own standing plus a small facepile.

    Two queries for the whole page rather than two per row.
    """
    if not communities:
        return []

    ids = [c.id for c in communities]

    mine = {
        row.community_id: row
        for row in (
            await db.scalars(
                select(CommunityMember).where(
                    CommunityMember.user_id == user_id,
                    CommunityMember.community_id.in_(ids),
                )
            )
        ).all()
    }

    faces: dict[uuid.UUID, list[UserSummary]] = {cid: [] for cid in ids}
    rows = (
        await db.execute(
            select(CommunityMember.community_id, User)
            .join(User, User.id == CommunityMember.user_id)
            .where(
                CommunityMember.community_id.in_(ids),
                CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
            )
            .order_by(CommunityMember.created_at)
        )
    ).all()
    for community_id, user in rows:
        bucket = faces[community_id]
        if len(bucket) < FACEPILE_SIZE:
            bucket.append(UserSummary.model_validate(user))

    out: list[CommunityOut] = []
    for community in communities:
        membership = mine.get(community.id)
        active = membership is not None and membership.status in ACTIVE_MEMBER_STATUSES
        out.append(CommunityOut(
            **CommunityOut.model_validate(community).model_dump(
                exclude={"my_role", "my_status", "joined", "pending",
                         "my_permissions", "faces"}
            ),
            my_role=membership.role if active else None,
            my_status=membership.status if membership else None,
            joined=active,
            pending=(
                membership is not None and membership.status is MembershipStatus.pending
            ),
            my_permissions=sorted(perms.permissions_for(membership.role)) if active else [],
            faces=faces.get(community.id, []),
        ))
    return out


async def _detail(db: DbSession, community: Community, user_id: uuid.UUID) -> CommunityDetail:
    decorated = (await _decorate(db, [community], user_id))[0]
    return CommunityDetail(
        **decorated.model_dump(),
        channels=sorted(c.name for c in community.channels),
    )


async def resolve(db: DbSession, community_id: str) -> Community:
    return await service.get_community(db, community_id)


async def _actor(db: DbSession, community: Community, user: User) -> CommunityMember:
    """The caller's membership, or a refusal. Used by every write path."""
    return await service.require_membership(db, community, user.id)


# --------------------------------------------------------------------------
# Create and browse
# --------------------------------------------------------------------------

@router.post("", response_model=CommunityDetail, status_code=status.HTTP_201_CREATED)
async def create_community(
    payload: CommunityCreate, db: DbSession, current_user: CurrentUser
) -> CommunityDetail:
    """Section 10's sequence, in `services.communities.create_community`.

    Refusals are specific: COMMUNITY_LIMIT_REACHED with the ceiling and the plan
    that would raise it, PRIVATE_COMMUNITY_NOT_ALLOWED for a visibility the plan
    does not carry, JOIN_POLICY_NOT_ALLOWED likewise.
    """
    community = await service.create_community(
        db, current_user,
        name=payload.name,
        kind=payload.kind,
        visibility=payload.visibility,
        join_policy=payload.join_policy,
        category=payload.category,
        location=payload.location,
        description=payload.description,
        rules=payload.rules,
        banner=payload.banner,
        logo_url=payload.logo_url,
        cover_url=payload.cover_url,
        channels=payload.channels,
    )
    return await _detail(db, community, current_user.id)


@router.get("", response_model=Page[CommunityOut])
async def list_communities(
    db: DbSession,
    current_user: CurrentUser,
    kind: CommunityKind | None = Query(default=None, description="region or industry"),
    category: str | None = Query(default=None),
    visibility: VisibilityLevel | None = Query(default=None),
    joined: bool | None = Query(default=None, description="Only communities you belong to"),
    owned: bool | None = Query(default=None, description="Only communities you own"),
    q: str | None = Query(default=None, description="Search name and description"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[CommunityOut]:
    """Browse. Private and member-only communities appear only to their members."""
    statement = await service.visible_communities_query(current_user.id)

    filters = []
    if kind is not None:
        filters.append(Community.kind == kind)
    if category:
        filters.append(Community.category.ilike(f"%{category.strip()}%"))
    if visibility is not None:
        filters.append(Community.visibility == visibility)
    if owned:
        filters.append(Community.owner_id == current_user.id)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(Community.name.ilike(pattern), Community.description.ilike(pattern))
        )
    if joined:
        mine = (
            select(CommunityMember.community_id)
            .where(
                CommunityMember.user_id == current_user.id,
                CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
            )
            .scalar_subquery()
        )
        filters.append(Community.id.in_(mine))

    if filters:
        statement = statement.where(*filters)

    total = await db.scalar(
        select(func.count()).select_from(statement.subquery())
    ) or 0
    rows = (
        await db.scalars(
            statement.order_by(Community.member_count.desc(), Community.name)
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return Page(
        items=await _decorate(db, list(rows), current_user.id),
        total=total,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------------
# One community
# --------------------------------------------------------------------------

@router.get("/{community_id}", response_model=CommunityDetail)
async def read_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> CommunityDetail:
    community = await resolve(db, community_id)
    await service.require_view(db, community, current_user.id)
    return await _detail(db, community, current_user.id)


@router.patch("/{community_id}", response_model=CommunityDetail)
async def update_community(
    community_id: str, payload: CommunityUpdate, db: DbSession, current_user: CurrentUser
) -> CommunityDetail:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    await service.update_community(
        db, community, actor, payload.model_dump(exclude_unset=True)
    )
    return await _detail(db, community, current_user.id)


@router.delete("/{community_id}", response_model=Message)
async def delete_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> Message:
    """Soft delete — section 12. Nothing is dropped; the row is marked deleted."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    await service.delete_community(db, community, actor)
    return Message(detail="Community deleted")


@router.post("/{community_id}/publish", response_model=CommunityDetail)
async def publish_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> CommunityDetail:
    """Take a draft live.

    Every community is created as a draft: configurable by the people who can
    manage it, and invisible to everyone else until this is called. Needs
    COMMUNITY_MANAGE, and re-checks the owner's plan — a draft may have sat
    through a downgrade, and publishing is the moment it starts having an
    audience.
    """
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    community = await service.publish_community(db, community, actor)
    return await _detail(db, community, current_user.id)


@router.post("/{community_id}/archive", response_model=CommunityDetail)
async def archive_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> CommunityDetail:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    await service.archive_community(db, community, actor)
    return await _detail(db, community, current_user.id)


@router.post("/{community_id}/restore", response_model=CommunityDetail)
async def restore_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> CommunityDetail:
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    await service.restore_community(db, community, actor)
    return await _detail(db, community, current_user.id)


@router.post("/{community_id}/leave", response_model=Message)
async def leave_community(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> Message:
    community = await resolve(db, community_id)
    await service.leave_community(db, community, current_user)
    return Message(detail="You have left the community")


# --------------------------------------------------------------------------
# Introspection
# --------------------------------------------------------------------------

@router.get("/{community_id}/my-access", response_model=MyAccessOut)
async def read_my_access(
    community_id: str, db: DbSession, current_user: CurrentUser
) -> MyAccessOut:
    """What the caller may do here, in section 15's wording.

    For greying out controls only. Every action re-checks server-side; section
    32: "Frontend feature locks are for UX only."
    """
    community = await resolve(db, community_id)
    await service.require_view(db, community, current_user.id)
    membership = await service.membership_of(db, community.id, current_user.id)
    active = membership is not None and membership.status in ACTIVE_MEMBER_STATUSES
    granted = sorted(perms.permissions_for(membership.role)) if active else []
    return MyAccessOut(
        role=membership.role if active else None,
        status=membership.status if membership else None,
        permissions=[
            PermissionOut(key=key, label=perms.LABELS.get(key, key)) for key in granted
        ],
    )


@router.get("/{community_id}/audit", response_model=list[AuditEntryOut])
async def read_audit_log(
    community_id: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEntryOut]:
    """Section 21's trail for one community. Admins and above."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    perms.require(actor.role, perms.Permission.COMMUNITY_MANAGE)
    rows = await audit_service.for_community(db, community.id, limit=limit, offset=offset)
    return [AuditEntryOut.model_validate(row) for row in rows]
