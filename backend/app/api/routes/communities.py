"""Communities: browse, create, join, leave, moderate.

Admin rights come from `CommunityMember.is_admin` (the creator is seeded as one).
Every write path checks membership or admin before touching a row.
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core import errors
from app.models import (
    Community, CommunityChannel, CommunityKind, CommunityMember, JoinPolicy,
    MembershipStatus, NotificationKind, Post, User, VisibilityLevel,
)
from app.schemas.common import Message, Page
from app.schemas.community import (
    ChannelCreate, ChannelOut, CommunityCreate, CommunityDetail, CommunityOut,
    CommunityUpdate, JoinResult, MembershipOut,
)
from app.schemas.user import UserSummary
from app.services import communities as community_service
from app.services import notifications

router = APIRouter(prefix="/communities", tags=["communities"])

FACEPILE_SIZE = 3
DEFAULT_CHANNELS = ["# general"]


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or uuid.uuid4().hex[:12]


async def _unique_slug(db: DbSession, name: str, exclude_id: uuid.UUID | None = None) -> str:
    """Append -2, -3 … rather than rejecting a duplicate display name."""
    base = _slugify(name)
    candidate, suffix = base, 1
    while True:
        statement = select(Community.id).where(Community.slug == candidate)
        if exclude_id is not None:
            statement = statement.where(Community.id != exclude_id)
        if await db.scalar(statement) is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def _get_community(db: DbSession, slug: str) -> Community:
    community = await db.scalar(select(Community).where(Community.slug == slug))
    if community is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Community not found")
    return community


async def _membership(
    db: DbSession, community_id: uuid.UUID, user_id: uuid.UUID
) -> CommunityMember | None:
    return await db.scalar(
        select(CommunityMember).where(
            CommunityMember.community_id == community_id,
            CommunityMember.user_id == user_id,
        )
    )


async def _require_admin(db: DbSession, community: Community, user: User) -> CommunityMember:
    membership = await _membership(db, community.id, user.id)
    if membership is None or not membership.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only a community admin can do that"
        )
    return membership


async def _bump_members(db: DbSession, community_id: uuid.UUID, delta: int) -> None:
    """Adjust member_count in the database, never through a Python round trip.

    `count = count + 1` computed in Python loses one of two concurrent joins under
    READ COMMITTED; computing it in SQL does not. greatest(...) keeps it >= 0.
    """
    new_value = Community.member_count + delta
    if delta < 0:
        new_value = func.greatest(new_value, 0)
    await db.execute(
        update(Community).where(Community.id == community_id).values(member_count=new_value)
    )


async def _decorate(
    db: DbSession, communities: list[Community], user_id: uuid.UUID
) -> list[CommunityOut]:
    """Attach `joined`, the caller's own role, and a small facepile.

    Two queries for the whole page rather than two per row.
    """
    if not communities:
        return []

    ids = [c.id for c in communities]

    mine = (
        await db.execute(
            select(
                CommunityMember.community_id,
                CommunityMember.status,
                CommunityMember.role,
            ).where(
                CommunityMember.user_id == user_id,
                CommunityMember.community_id.in_(ids),
            )
        )
    ).all()
    joined_ids = {cid for cid, st, _ in mine if st is MembershipStatus.joined}
    pending_ids = {cid for cid, st, _ in mine if st is MembershipStatus.pending}
    # Only a joined member has a role worth reporting — a pending request does
    # not make someone a member, whatever the row happens to say.
    my_roles = {cid: role for cid, st, role in mine if st is MembershipStatus.joined}

    faces: dict[uuid.UUID, list[UserSummary]] = {cid: [] for cid in ids}
    rows = (
        await db.execute(
            select(CommunityMember.community_id, User)
            .join(User, User.id == CommunityMember.user_id)
            .where(
                CommunityMember.community_id.in_(ids),
                CommunityMember.status == MembershipStatus.joined,
            )
            .order_by(CommunityMember.created_at)
        )
    ).all()
    for community_id, user in rows:
        bucket = faces[community_id]
        if len(bucket) < FACEPILE_SIZE:
            bucket.append(UserSummary.model_validate(user))

    return [
        CommunityOut(
            **CommunityOut.model_validate(c).model_dump(
                exclude={"joined", "pending", "my_role", "faces"}
            ),
            joined=c.id in joined_ids,
            pending=c.id in pending_ids,
            my_role=my_roles.get(c.id),
            faces=faces.get(c.id, []),
        )
        for c in communities
    ]


async def _detail(db: DbSession, community: Community, user_id: uuid.UUID) -> CommunityDetail:
    decorated = (await _decorate(db, [community], user_id))[0]
    return CommunityDetail(
        **decorated.model_dump(), channels=[c.name for c in community.channels]
    )


# --------------------------------------------------------------------------
# Browse and create
# --------------------------------------------------------------------------

@router.get("", response_model=Page[CommunityOut])
async def list_communities(
    db: DbSession,
    current_user: CurrentUser,
    kind: CommunityKind | None = Query(default=None, description="region or industry"),
    joined: bool | None = Query(default=None, description="Only communities you belong to"),
    q: str | None = Query(default=None, description="Search name and description"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[CommunityOut]:
    filters = []
    if kind is not None:
        filters.append(Community.kind == kind)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(Community.name.ilike(pattern), Community.description.ilike(pattern))
        )
    if joined:
        member_filter = (
            select(CommunityMember.community_id)
            .where(
                CommunityMember.user_id == current_user.id,
                CommunityMember.status == MembershipStatus.joined,
            )
            .scalar_subquery()
        )
        filters.append(Community.id.in_(member_filter))

    # Start from what this member is actually allowed to see, not from every
    # row in the table. This used to be a bare `select(Community)`, which listed
    # archived communities, private ones the caller had no part in, and — once
    # communities gained a draft stage — other people's unpublished drafts.
    # `visible_communities_query` is the same base the /api/v1 browse uses, so
    # both surfaces answer with one rule instead of two that can drift.
    visible = await community_service.visible_communities_query(current_user.id)
    statement = visible
    count_statement = select(func.count()).select_from(visible.subquery())
    if filters:
        statement = statement.where(*filters)
        count_statement = select(func.count()).select_from(
            visible.where(*filters).subquery()
        )

    total = await db.scalar(count_statement) or 0
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


#: DomainError codes -> the short `detail` string this API has always used.
#: The SPA switches on these, so they are part of the contract.
_LEGACY_DETAIL: dict[str, str] = {
    errors.Code.ENTITLEMENT_REQUIRED: "upgrade_required",
    errors.Code.PRIVATE_COMMUNITY_NOT_ALLOWED: "upgrade_required",
    errors.Code.JOIN_POLICY_NOT_ALLOWED: "upgrade_required",
    errors.Code.COMMUNITY_LIMIT_REACHED: "community_limit_reached",
}


def _as_legacy(exc: errors.DomainError) -> HTTPException:
    """Re-shape a DomainError for the pre-v1 contract.

    These routes answer `{"detail": "..."}` with the reason in headers; /api/v1
    answers the structured section 23 body. Translating here keeps one set of
    rules without changing what existing clients receive.
    """
    details = exc.details or {}
    headers = {"X-Required-Plan": str(details.get("upgrade_plan") or "")}
    if details.get("limit") is not None:
        headers["X-Community-Limit"] = str(details["limit"])
    return HTTPException(
        exc.status_code,
        detail=_LEGACY_DETAIL.get(exc.code, exc.message),
        headers=headers,
    )


@router.post(
    "", response_model=CommunityDetail, status_code=status.HTTP_201_CREATED,
)
async def create_community(
    payload: CommunityCreate, current_user: CurrentUser, db: DbSession
) -> CommunityDetail:
    """Create a community, under the same rules as POST /api/v1/communities.

    This used to carry `require_feature("create_communities")` and build the row
    inline, which left two problems. The plan rules disagreed with /api/v1 — the
    free tier is allowed one community by backend_flow.md 11, but this route
    refused outright — and because the SPA calls *this* endpoint, that was the
    rule members actually met. It also never set `owner_id`, so a community made
    through the UI had no owner: nobody could administer it in the v1 endpoints
    and it counted against nobody's plan limit.

    Delegating fixes both. The service is where the sequence lives (entitlement,
    then the per-plan ceiling under a lock, then visibility and join policy),
    and it sets ownership and the owner's role properly.

    Visibility is fixed to public because this payload has no field for it;
    private communities are created through /api/v1/communities.
    """
    try:
        community = await community_service.create_community(
            db, current_user,
            name=payload.name,
            kind=payload.kind,
            visibility=VisibilityLevel.public,
            join_policy=payload.join_policy,
            location=payload.location,
            description=payload.description,
            banner=payload.banner,
            channels=payload.channels or list(DEFAULT_CHANNELS),
        )
    except errors.DomainError as exc:
        raise _as_legacy(exc) from exc

    return await _detail(db, community, current_user.id)


@router.post("/{slug}/publish", response_model=CommunityDetail)
async def publish_community(
    slug: str, current_user: CurrentUser, db: DbSession
) -> CommunityDetail:
    """Take a draft live — the same rule as POST /api/v1/communities/{id}/publish.

    Declared before /{slug} so the slug route does not swallow the path, and
    kept on this prefix because the SPA creates communities here: without it a
    community made in the UI would be stranded as a draft.
    """
    community = await community_service.get_community(db, slug)
    try:
        actor = await community_service.require_membership(db, community, current_user.id)
        community = await community_service.publish_community(db, community, actor)
    except errors.DomainError as exc:
        raise _as_legacy(exc) from exc
    return await _detail(db, community, current_user.id)


@router.get("/suggested", response_model=list[CommunityOut])
async def suggested_communities(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=3, ge=1, le=12),
):
    """Communities to join — the biggest ones you are not in and have not asked to join.

    Declared before /{slug} so the slug route does not swallow "suggested".
    """
    mine = (
        select(CommunityMember.community_id)
        .where(CommunityMember.user_id == current_user.id)
        .scalar_subquery()
    )
    rows = (
        await db.scalars(
            select(Community)
            .where(
                Community.id.notin_(mine),
                Community.join_policy != JoinPolicy.invite,
            )
            .order_by(Community.member_count.desc(), Community.name)
            .limit(limit)
        )
    ).all()
    return await _decorate(db, list(rows), current_user.id)


@router.get("/{slug}", response_model=CommunityDetail)
async def read_community(slug: str, db: DbSession, current_user: CurrentUser) -> CommunityDetail:
    community = await _get_community(db, slug)
    return await _detail(db, community, current_user.id)


@router.patch("/{slug}", response_model=CommunityDetail)
async def update_community(
    slug: str, payload: CommunityUpdate, current_user: CurrentUser, db: DbSession
) -> CommunityDetail:
    """Edit a community, under the same rules as PATCH /api/v1/communities/{id}.

    This used to set the fields inline, which left two problems. It never
    validated `visibility` or `join_policy` against the plan, so a tier that
    could not *create* a private community could still PATCH one into being —
    the create route delegates and is checked, this one was not. And its
    nullable list was `description` alone, so clearing a logo or a description's
    neighbours came back as a 422 for no reason.

    Delegating fixes both, and picks up the audit row and the draft-editable
    rule for free.
    """
    community = await _get_community(db, slug)
    actor = await _require_admin(db, community, current_user)

    changes = payload.model_dump(exclude_unset=True)
    try:
        community = await community_service.update_community(db, community, actor, changes)
    except errors.DomainError as exc:
        raise _as_legacy(exc) from exc
    return await _detail(db, community, current_user.id)


@router.delete("/{slug}", response_model=Message)
async def delete_community(slug: str, current_user: CurrentUser, db: DbSession) -> Message:
    community = await _get_community(db, slug)
    await _require_admin(db, community, current_user)

    # The FK is ON DELETE SET NULL, so leaving these behind would publish a
    # members-only discussion into everyone's global feed. Delete them with it.
    await db.execute(delete(Post).where(Post.community_id == community.id))
    await db.delete(community)
    await db.commit()
    return Message(detail="Community deleted")


# --------------------------------------------------------------------------
# Membership
# --------------------------------------------------------------------------

@router.get("/{slug}/members", response_model=Page[MembershipOut])
async def list_members(
    slug: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[MembershipOut]:
    community = await _get_community(db, slug)

    # The full roster is members-only; non-members still see the facepile on the card.
    membership = await _membership(db, community.id, current_user.id)
    if membership is None or membership.status is not MembershipStatus.joined:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Join the community to see its members"
        )

    filters = [
        CommunityMember.community_id == community.id,
        CommunityMember.status == MembershipStatus.joined,
    ]
    total = await db.scalar(select(func.count(CommunityMember.id)).where(*filters)) or 0
    rows = (
        await db.scalars(
            select(CommunityMember)
            .where(*filters)
            .order_by(CommunityMember.created_at)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return Page(items=list(rows), total=total, limit=limit, offset=offset)


@router.post("/{slug}/join", response_model=JoinResult, status_code=status.HTTP_201_CREATED)
async def join_community(slug: str, current_user: CurrentUser, db: DbSession) -> JoinResult:
    """Open communities join immediately; request-to-join ones go to pending."""
    community = await _get_community(db, slug)
    if community.join_policy is JoinPolicy.invite:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This community is invite only")

    existing = await _membership(db, community.id, current_user.id)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Your request is already pending"
            if existing.status is MembershipStatus.pending
            else "You are already a member",
        )

    membership = CommunityMember(
        community_id=community.id,
        user_id=current_user.id,
        status=(
            MembershipStatus.pending
            if community.join_policy is JoinPolicy.request
            else MembershipStatus.joined
        ),
    )
    db.add(membership)
    if membership.status is MembershipStatus.joined:
        await _bump_members(db, community.id, +1)

    joining = membership.status is MembershipStatus.joined
    await community_service._notify_admins(
        db, community, actor=current_user,
        kind=(NotificationKind.community_member_added if joining
              else NotificationKind.community_join_request),
        title=(f"{current_user.name} joined {community.name}" if joining
               else f"{current_user.name} asked to join {community.name}"),
        body=None if joining else "Approve or decline from community settings.",
    )

    try:
        await db.commit()
    except IntegrityError:
        # Two joins raced; uq_community_user caught the loser.
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You are already a member") from None
    await db.refresh(community)
    return JoinResult(
        status=membership.status, community=(await _decorate(db, [community], current_user.id))[0]
    )


@router.delete("/{slug}/leave", response_model=Message)
async def leave_community(slug: str, current_user: CurrentUser, db: DbSession) -> Message:
    community = await _get_community(db, slug)

    membership = await _membership(db, community.id, current_user.id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not a member")

    if membership.is_admin:
        others = await db.scalar(
            select(func.count(CommunityMember.id)).where(
                CommunityMember.community_id == community.id,
                CommunityMember.is_admin.is_(True),
                CommunityMember.user_id != current_user.id,
            )
        )
        if not others:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "You are the only admin — promote someone else or delete the community",
            )

    was_joined = membership.status is MembershipStatus.joined
    await db.delete(membership)
    if was_joined:
        await _bump_members(db, community.id, -1)

    await db.commit()
    return Message(detail="Left the community")


# --------------------------------------------------------------------------
# Moderation (request-to-join communities)
# --------------------------------------------------------------------------

@router.get("/{slug}/requests", response_model=list[MembershipOut])
async def list_join_requests(slug: str, current_user: CurrentUser, db: DbSession):
    community = await _get_community(db, slug)
    await _require_admin(db, community, current_user)

    rows = (
        await db.scalars(
            select(CommunityMember)
            .where(
                CommunityMember.community_id == community.id,
                CommunityMember.status == MembershipStatus.pending,
            )
            .order_by(CommunityMember.created_at)
        )
    ).all()
    return rows


@router.post("/{slug}/requests/{user_id}/approve", response_model=MembershipOut)
async def approve_request(
    slug: str, user_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> CommunityMember:
    community = await _get_community(db, slug)
    await _require_admin(db, community, current_user)

    membership = await _membership(db, community.id, user_id)
    if membership is None or membership.status is not MembershipStatus.pending:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending request for that member")

    membership.status = MembershipStatus.joined
    await _bump_members(db, community.id, +1)
    notifications.notify(
        db, user_id=user_id, actor_id=current_user.id,
        kind=NotificationKind.community_join_approved,
        title=f"Your request to join {community.name} was approved",
        body=f"Welcome to {community.name}!",
        link=f"/communities?open={community.slug}",
    )
    await db.commit()
    await db.refresh(membership)
    return membership


@router.post("/{slug}/requests/{user_id}/decline", response_model=Message)
async def decline_request(
    slug: str, user_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    community = await _get_community(db, slug)
    await _require_admin(db, community, current_user)

    membership = await _membership(db, community.id, user_id)
    if membership is None or membership.status is not MembershipStatus.pending:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending request for that member")

    await db.delete(membership)
    await db.commit()
    return Message(detail="Request declined")


# --------------------------------------------------------------------------
# Channels
# --------------------------------------------------------------------------

@router.get("/{slug}/channels", response_model=list[ChannelOut])
async def list_channels(slug: str, db: DbSession, current_user: CurrentUser):
    community = await _get_community(db, slug)
    return sorted(community.channels, key=lambda c: c.name)


@router.post(
    "/{slug}/channels", response_model=ChannelOut, status_code=status.HTTP_201_CREATED
)
async def add_channel(
    slug: str, payload: ChannelCreate, current_user: CurrentUser, db: DbSession
) -> CommunityChannel:
    community = await _get_community(db, slug)
    await _require_admin(db, community, current_user)

    name = payload.name.strip()
    if any(c.name.lower() == name.lower() for c in community.channels):
        raise HTTPException(status.HTTP_409_CONFLICT, "That channel already exists")

    channel = CommunityChannel(community_id=community.id, name=name)
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.delete("/{slug}/channels/{channel_id}", response_model=Message)
async def delete_channel(
    slug: str, channel_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    community = await _get_community(db, slug)
    await _require_admin(db, community, current_user)

    channel = await db.get(CommunityChannel, channel_id)
    if channel is None or channel.community_id != community.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel not found")

    await db.delete(channel)
    await db.commit()
    return Message(detail="Channel deleted")
