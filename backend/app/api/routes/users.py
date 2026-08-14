"""Profile, field visibility, mandate and the member directory."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import GATES, CurrentUser, DbSession
from app.models import (
    CommunityMember, Connection, ConnectionStatus, FieldVisibility, Mandate, MemberRole,
    MembershipStatus, PlanSelection, User,
)
from app.schemas.common import Message, Page
from app.schemas.user import (
    ConnectionCreate, ConnectionOut, MandateOut, MandateUpdate, MemberStats, UserProfile,
    UserSummary, UserUpdate, VisibilityItem, VisibilityUpdate,
)
from app.services import email as email_service
from app.services import terms as terms_service
from app.services.users import VISIBILITY_LABELS

router = APIRouter(tags=["members"])


# --- Me -------------------------------------------------------------------

async def _profile(db: DbSession, user: User) -> UserProfile:
    """Profile plus the gate state the SPA routes on: terms, then plan."""
    selection = await db.scalar(
        select(PlanSelection).where(
            PlanSelection.user_id == user.id, PlanSelection.is_current.is_(True)
        )
    )
    return UserProfile(
        **UserProfile.model_validate(user).model_dump(
            exclude={"terms_accepted", "plan_selected", "current_plan"}
        ),
        terms_accepted=await terms_service.has_accepted(db, user.id),
        plan_selected=selection is not None,
        current_plan=selection.plan.value if selection else None,
    )


@router.get("/me", response_model=UserProfile)
async def read_me(current_user: CurrentUser, db: DbSession) -> UserProfile:
    return await _profile(db, current_user)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    payload: UserUpdate, current_user: CurrentUser, db: DbSession
) -> UserProfile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return await _profile(db, current_user)


@router.get("/me/stats", response_model=MemberStats)
async def my_stats(current_user: CurrentUser, db: DbSession) -> MemberStats:
    connections = await db.scalar(
        select(func.count(Connection.id)).where(
            Connection.status == ConnectionStatus.accepted,
            or_(
                Connection.requester_id == current_user.id,
                Connection.addressee_id == current_user.id,
            ),
        )
    )
    communities = await db.scalar(
        select(func.count(CommunityMember.id)).where(
            CommunityMember.user_id == current_user.id,
            CommunityMember.status == MembershipStatus.joined,
        )
    )
    return MemberStats(
        connections=connections or 0,
        communities=communities or 0,
        completed_projects=current_user.completed_projects,
        profile_views=current_user.profile_views,
    )


# --- Field visibility -----------------------------------------------------

@router.get("/me/visibility", response_model=list[VisibilityItem])
async def read_visibility(current_user: CurrentUser, db: DbSession):
    rows = (
        await db.scalars(
            select(FieldVisibility)
            .where(FieldVisibility.user_id == current_user.id)
            .order_by(FieldVisibility.created_at)
        )
    ).all()
    return rows


@router.put("/me/visibility", response_model=VisibilityItem)
async def set_visibility(
    payload: VisibilityUpdate, current_user: CurrentUser, db: DbSession
) -> FieldVisibility:
    if payload.field_key not in VISIBILITY_LABELS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown field '{payload.field_key}'. Known fields: "
            f"{', '.join(sorted(VISIBILITY_LABELS))}",
        )

    row = await db.scalar(
        select(FieldVisibility).where(
            FieldVisibility.user_id == current_user.id,
            FieldVisibility.field_key == payload.field_key,
        )
    )
    if row is None:
        row = FieldVisibility(
            user_id=current_user.id, field_key=payload.field_key, level=payload.level
        )
        db.add(row)
    else:
        row.level = payload.level

    await db.commit()
    await db.refresh(row)
    return row


# --- Mandate --------------------------------------------------------------

@router.get("/me/mandate", response_model=MandateOut)
async def read_mandate(current_user: CurrentUser, db: DbSession) -> Mandate:
    mandate = await db.scalar(select(Mandate).where(Mandate.user_id == current_user.id))
    if mandate is None:
        mandate = Mandate(user_id=current_user.id)
        db.add(mandate)
        await db.commit()
        await db.refresh(mandate)
    return mandate


@router.put("/me/mandate", response_model=MandateOut)
async def update_mandate(
    payload: MandateUpdate, current_user: CurrentUser, db: DbSession
) -> Mandate:
    mandate = await db.scalar(select(Mandate).where(Mandate.user_id == current_user.id))
    if mandate is None:
        mandate = Mandate(user_id=current_user.id)
        db.add(mandate)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(mandate, field, value)

    await db.commit()
    await db.refresh(mandate)
    return mandate


# --- Directory ------------------------------------------------------------

@router.get("/members", response_model=Page[UserSummary], dependencies=GATES)
async def list_members(
    db: DbSession,
    current_user: CurrentUser,
    role: MemberRole | None = Query(default=None, description="Filter by member role"),
    q: str | None = Query(default=None, description="Search name, company or location"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[UserSummary]:
    """The member directory. Not restricted by market — anyone can reach anyone."""
    filters = [User.is_active.is_(True), User.id != current_user.id]
    if role is not None:
        filters.append(User.role == role)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(User.name.ilike(pattern), User.company.ilike(pattern), User.location.ilike(pattern))
        )

    total = await db.scalar(select(func.count(User.id)).where(*filters)) or 0
    rows = (
        await db.scalars(
            select(User).where(*filters).order_by(User.name).limit(limit).offset(offset)
        )
    ).all()
    return Page(items=list(rows), total=total, limit=limit, offset=offset)


@router.get("/members/suggested", response_model=list[UserSummary], dependencies=GATES)
async def suggested_members(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=2, ge=1, le=12),
):
    """People you may know — most shared communities first, excluding anyone you
    already have a connection with (pending or accepted).

    Declared before /members/{user_id} so the path parameter does not match it.
    """
    my_communities = (
        select(CommunityMember.community_id)
        .where(
            CommunityMember.user_id == current_user.id,
            CommunityMember.status == MembershipStatus.joined,
        )
        .scalar_subquery()
    )

    related = (
        select(Connection.addressee_id).where(Connection.requester_id == current_user.id)
    ).union(
        select(Connection.requester_id).where(Connection.addressee_id == current_user.id)
    ).subquery()

    shared = func.count(CommunityMember.community_id)
    rows = (
        await db.execute(
            select(User, shared.label("shared"))
            .outerjoin(
                CommunityMember,
                (CommunityMember.user_id == User.id)
                & (CommunityMember.community_id.in_(my_communities))
                & (CommunityMember.status == MembershipStatus.joined),
            )
            .where(
                User.id != current_user.id,
                User.is_active.is_(True),
                User.id.notin_(select(related.c[0])),
            )
            .group_by(User.id)
            .order_by(shared.desc(), User.name)
            .limit(limit)
        )
    ).all()
    return [UserSummary.model_validate(user) for user, _ in rows]


@router.get("/members/{user_id}", response_model=UserProfile, dependencies=GATES)
async def read_member(user_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    if user.id != current_user.id:
        user.profile_views += 1
        await db.commit()
        await db.refresh(user)
    return user


# --- Connections ----------------------------------------------------------

@router.post("/connections", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED, dependencies=GATES)
async def request_connection(
    payload: ConnectionCreate,
    current_user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> Connection:
    if payload.addressee_id == current_user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "You cannot connect to yourself")

    addressee = await db.get(User, payload.addressee_id)
    if addressee is None or not addressee.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    existing = await db.scalar(
        select(Connection).where(
            or_(
                (Connection.requester_id == current_user.id)
                & (Connection.addressee_id == addressee.id),
                (Connection.requester_id == addressee.id)
                & (Connection.addressee_id == current_user.id),
            )
        )
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A connection already exists ({existing.status.value})"
        )

    connection = Connection(
        requester_id=current_user.id, addressee_id=addressee.id, note=payload.note
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    background.add_task(
        email_service.send_connection_request,
        addressee.email, addressee.name, current_user.name, current_user.company, payload.note,
    )
    return connection


@router.get("/connections", response_model=list[ConnectionOut], dependencies=GATES)
async def list_connections(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: ConnectionStatus | None = Query(default=None, alias="status"),
):
    filters = [
        or_(
            Connection.requester_id == current_user.id,
            Connection.addressee_id == current_user.id,
        )
    ]
    if status_filter is not None:
        filters.append(Connection.status == status_filter)

    rows = (
        await db.scalars(
            select(Connection).where(*filters).order_by(Connection.created_at.desc())
        )
    ).all()
    return rows


@router.post("/connections/{connection_id}/accept", response_model=ConnectionOut, dependencies=GATES)
async def accept_connection(
    connection_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> Connection:
    connection = await db.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if connection.addressee_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the recipient can accept")
    if connection.status is not ConnectionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is no longer pending")

    connection.status = ConnectionStatus.accepted
    await db.commit()
    await db.refresh(connection)

    requester = connection.requester
    background.add_task(
        email_service.send_connection_accepted,
        requester.email, requester.name, current_user.name,
    )
    return connection


@router.post("/connections/{connection_id}/decline", response_model=Message, dependencies=GATES)
async def decline_connection(
    connection_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    connection = await db.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if connection.addressee_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the recipient can decline")

    connection.status = ConnectionStatus.declined
    await db.commit()
    return Message(detail="Request declined")
