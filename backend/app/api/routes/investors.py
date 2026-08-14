"""The investor-facing side: follows, introduction requests and the overview tiles."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_feature
from app.models import (
    Community, CommunityMember, Contact, ContactStage, IntroductionRequest, IntroStatus,
    InvestorFollow, MembershipStatus, User,
)
from app.schemas.common import Message
from app.schemas.crm import (
    IntroductionCreate, IntroductionOut, IntroductionRespond, InvestorTiles,
)
from app.services import email as email_service

router = APIRouter(prefix="/investors", tags=["investors"])


@router.get("/overview", response_model=InvestorTiles)
async def overview(db: DbSession, current_user: CurrentUser) -> InvestorTiles:
    following = await db.scalar(
        select(func.count(InvestorFollow.id)).where(
            InvestorFollow.member_id == current_user.id
        )
    )
    requests = await db.scalar(
        select(func.count(IntroductionRequest.id)).where(
            IntroductionRequest.to_user_id == current_user.id
        )
    )
    awaiting = await db.scalar(
        select(func.count(IntroductionRequest.id)).where(
            IntroductionRequest.to_user_id == current_user.id,
            IntroductionRequest.status == IntroStatus.pending,
        )
    )
    communities = await db.scalar(
        select(func.count(CommunityMember.id)).where(
            CommunityMember.user_id == current_user.id,
            CommunityMember.status == MembershipStatus.joined,
        )
    )
    return InvestorTiles(
        investors_following=following or 0,
        introduction_requests=requests or 0,
        awaiting_reply=awaiting or 0,
        profile_views=current_user.profile_views,
        shared_communities=communities or 0,
    )


@router.get("/introductions", response_model=list[IntroductionOut])
async def list_introductions(
    db: DbSession,
    current_user: CurrentUser,
    direction: str = Query(default="incoming", pattern="^(incoming|outgoing)$"),
    status_filter: IntroStatus | None = Query(default=None, alias="status"),
):
    if direction == "incoming":
        filters = [IntroductionRequest.to_user_id == current_user.id]
    else:
        filters = [IntroductionRequest.from_user_id == current_user.id]
    if status_filter is not None:
        filters.append(IntroductionRequest.status == status_filter)

    rows = (
        await db.scalars(
            select(IntroductionRequest)
            .where(*filters)
            .order_by(IntroductionRequest.created_at.desc())
        )
    ).all()
    return rows


@router.post(
    "/introductions", response_model=IntroductionOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_feature("introduction_requests"))],
)
async def request_introduction(
    payload: IntroductionCreate,
    current_user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> IntroductionRequest:
    if payload.to_user_id == current_user.id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "You cannot request an introduction to yourself"
        )

    target = await db.get(User, payload.to_user_id)
    if target is None or not target.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    community = None
    if payload.via_community_id is not None:
        community = await db.get(Community, payload.via_community_id)
        if community is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Community not found")

    duplicate = await db.scalar(
        select(IntroductionRequest).where(
            IntroductionRequest.from_user_id == current_user.id,
            IntroductionRequest.to_user_id == target.id,
            IntroductionRequest.status == IntroStatus.pending,
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a pending request")

    request = IntroductionRequest(
        from_user_id=current_user.id,
        to_user_id=target.id,
        via_community_id=payload.via_community_id,
        message=payload.message,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    background.add_task(
        email_service.send_introduction_request,
        target.email, target.name, current_user.name, current_user.company,
        community.name if community else None, payload.message,
    )
    return request


@router.post("/introductions/{request_id}/respond", response_model=IntroductionOut)
async def respond_to_introduction(
    request_id: uuid.UUID,
    payload: IntroductionRespond,
    current_user: CurrentUser,
    db: DbSession,
) -> IntroductionRequest:
    """Accepting drops the requester into your contacts as a new lead."""
    request = await db.get(IntroductionRequest, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if request.to_user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the recipient can respond")
    if request.status is not IntroStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is no longer pending")

    request.status = IntroStatus.accepted if payload.accept else IntroStatus.declined
    request.responded_at = datetime.now(UTC)

    if payload.accept:
        requester = request.from_user
        already = await db.scalar(
            select(Contact).where(
                Contact.owner_id == current_user.id, Contact.person_id == requester.id
            )
        )
        if already is None:
            db.add(
                Contact(
                    owner_id=current_user.id,
                    person_id=requester.id,
                    name=requester.name,
                    company=requester.company,
                    role=requester.role,
                    market=requester.location,
                    stage=ContactStage.new_lead,
                    source="Introduction",
                    initials=requester.initials,
                    avatar_color=requester.avatar_color,
                    last_touch_at=datetime.now(UTC),
                )
            )

    await db.commit()
    await db.refresh(request)
    return request


@router.post("/follow/{member_id}", response_model=Message, status_code=status.HTTP_201_CREATED)
async def follow_member(
    member_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    if member_id == current_user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "You cannot follow yourself")

    member = await db.get(User, member_id)
    if member is None or not member.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    existing = await db.scalar(
        select(InvestorFollow).where(
            InvestorFollow.investor_id == current_user.id,
            InvestorFollow.member_id == member_id,
        )
    )
    if existing is not None:
        return Message(detail="Already following")

    db.add(InvestorFollow(investor_id=current_user.id, member_id=member_id))
    await db.commit()
    return Message(detail="Following")


@router.delete("/follow/{member_id}", response_model=Message)
async def unfollow_member(
    member_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    existing = await db.scalar(
        select(InvestorFollow).where(
            InvestorFollow.investor_id == current_user.id,
            InvestorFollow.member_id == member_id,
        )
    )
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not following this member")

    await db.delete(existing)
    await db.commit()
    return Message(detail="Unfollowed")
