"""Community invitations — the fourth membership route in section 13.

Two audiences, and the split in URL shape follows it:

    /communities/{id}/invites…   the community's side — send, list, resend, revoke
    /invites…                    the invitee's side — what am I offered, accept, decline

Keeping the invitee's endpoints off the community prefix is deliberate. Someone
answering an invitation is not yet a member, so they cannot satisfy the
membership checks every `/communities/{id}/…` write path applies — and an
invitation to a *private* community must be answerable without first being able
to read it.

The routers are thin, as everywhere in v1: they resolve the community and the
caller's membership, then hand over to `services/community_invites.py`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import InviteStatus
from app.schemas.common import Page
from app.schemas.communities_v1 import (
    InviteAccept, InviteCreate, InviteOut, InviteResend, InviteWithToken, MemberOut,
)
from app.services import community_invites as service

from .communities import _actor, resolve

# --------------------------------------------------------------------------
# The community's side
# --------------------------------------------------------------------------

router = APIRouter(prefix="/communities", tags=["invites-v1"])


@router.post(
    "/{community_id}/invites",
    response_model=InviteWithToken,
    status_code=status.HTTP_201_CREATED,
)
async def send_invite(
    community_id: str, payload: InviteCreate, db: DbSession, current_user: CurrentUser
) -> InviteWithToken:
    """Offer membership to an account or an email address.

    Needs MEMBER_INVITE (admin and above) and a role the caller outranks. The
    membership is not created here — acceptance does that, and the community's
    capacity is re-checked at that point.

    The response carries the token, because the caller is the one who passes the
    link on. The roster listing does not.
    """
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    invite = await service.invite_member(
        db, community, actor,
        user_id=payload.user_id,
        email=payload.email,
        role=payload.role,
        message=payload.message,
        expires_in_days=payload.expires_in_days,
    )
    return InviteWithToken.model_validate(invite)


@router.get("/{community_id}/invites", response_model=Page[InviteOut])
async def list_invites(
    community_id: str, db: DbSession, current_user: CurrentUser,
    invite_status: InviteStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[InviteOut]:
    """Who has been invited, by whom, and what became of it."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    rows, total = await service.list_invites(
        db, community, actor, status=invite_status, limit=limit, offset=offset
    )
    return Page[InviteOut](
        items=[InviteOut.model_validate(row) for row in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post("/{community_id}/invites/{invite_id}/resend", response_model=InviteWithToken)
async def resend_invite(
    community_id: str, invite_id: uuid.UUID, payload: InviteResend,
    db: DbSession, current_user: CurrentUser,
) -> InviteWithToken:
    """Re-open and re-token an invitation. The previous link stops working."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    invite = await service.resend_invite(
        db, community, actor, invite_id, expires_in_days=payload.expires_in_days
    )
    return InviteWithToken.model_validate(invite)


@router.delete("/{community_id}/invites/{invite_id}", response_model=InviteOut)
async def revoke_invite(
    community_id: str, invite_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> InviteOut:
    """Withdraw an unanswered invitation. The row survives as history."""
    community = await resolve(db, community_id)
    actor = await _actor(db, community, current_user)
    invite = await service.revoke_invite(db, community, actor, invite_id)
    return InviteOut.model_validate(invite)


# --------------------------------------------------------------------------
# The invitee's side
# --------------------------------------------------------------------------

me_router = APIRouter(prefix="/invites", tags=["invites-v1"])


@me_router.get("", response_model=list[InviteOut])
async def my_invites(db: DbSession, current_user: CurrentUser) -> list[InviteOut]:
    """Every open invitation addressed to me.

    Matched on the account and on the email, so an invitation sent before
    signup is waiting once the account exists.
    """
    rows = await service.invites_for_user(db, current_user)
    return [InviteOut.model_validate(row) for row in rows]


@me_router.post("/accept", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def accept_by_token(
    payload: InviteAccept, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    """Accept from a link. The token identifies the invitation; the signed-in
    account still has to be the one it was addressed to."""
    invite = await service.get_by_token(db, payload.token)
    membership = await service.accept_invite(db, invite, current_user)
    return MemberOut.model_validate(membership)


@me_router.post(
    "/{invite_id}/accept", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
async def accept_invite(
    invite_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> MemberOut:
    """Accept one of my own invitations, by id. This is what creates the
    membership, at the role the invitation offered."""
    invite = await service.get_invite(db, invite_id)
    membership = await service.accept_invite(db, invite, current_user)
    return MemberOut.model_validate(membership)


@me_router.post("/{invite_id}/decline", response_model=InviteOut)
async def decline_invite(
    invite_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> InviteOut:
    invite = await service.get_invite(db, invite_id)
    invite = await service.decline_invite(db, invite, current_user)
    return InviteOut.model_validate(invite)
