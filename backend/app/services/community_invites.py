"""Community invitations — the outward half of section 13's membership flows.

Three ways into a community already existed, and this adds the fourth the
`members` router's docstring reserved:

    join            the member joins outright, when the policy allows it
    join-request    the member asks, an admin approves
    add-member      an admin adds an existing user, effective immediately
    invite          an admin offers, and the invitee decides        <- here

An invitation is not an add-member with a delay. Adding is unilateral and
immediate; inviting is an offer, and the invitee's acceptance is what creates
the membership. That difference is why the checks are split across two moments:

  * **at invite time** — the actor's permission and rank, and whether the person
    is invitable at all (not already a member, not banned);
  * **at accept time** — the community's capacity and the owner's moderator
    budget, because both can change between the offer and the answer, and the
    plan that matters is the *owner's*, which may have been downgraded since.

Doing the capacity check only at invite time would let an admin queue fifty
invitations against a plan that seats ten. Doing it only at accept time would
let them invite someone who is already banned. Both are needed.

Entitlement before permission, as everywhere else in this module: the community
owner's plan decides whether the community can hold another member, and the
actor's role in the community decides whether they may do the inviting.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.models import (
    ACTIVE_MEMBER_STATUSES, AuditAction, Community, CommunityInvite, CommunityMember,
    CommunityRole, InviteStatus, MembershipStatus, NotificationKind, User,
)
from app.services import audit, notifications
from app.services import communities as communities_service
from app.services import community_permissions as perms
from app.services.community_permissions import Permission

#: How long an invitation stays open when the caller does not say. Long enough
#: to survive a holiday, short enough that a stale roster does not accumulate.
DEFAULT_TTL_DAYS = 14

#: Ceiling on what a caller may ask for, so an invite cannot be made immortal.
MAX_TTL_DAYS = 90

#: How to say "you are not senior enough to invite here" for each setting.
#: `viewer` is absent because it would gate nothing.
INVITE_REFUSAL: dict[CommunityRole, str] = {
    CommunityRole.member: "Viewers cannot invite people to this community.",
    CommunityRole.moderator: "Only moderators and above can invite here.",
    CommunityRole.admin: "Only admins can invite people to this community.",
    CommunityRole.owner: "Only the owner can invite people to this community.",
}


def _require_may_invite(community: Community, actor: CommunityMember) -> None:
    """Whether this member clears the community's `invite_min_role`.

    Deliberately not `perms.require(MEMBER_INVITE)`: that asks a question about
    the *role*, and the answer here belongs to the *community*. MEMBER_INVITE
    stays in the admin permission set so `/my-access` still describes the
    default, but this is what the write path enforces.
    """
    if perms.meets_rank(actor.role, community.invite_min_role):
        return
    raise errors.forbidden(
        errors.Code.PERMISSION_DENIED,
        INVITE_REFUSAL.get(
            community.invite_min_role, "You cannot invite people to this community."
        ),
        permission=Permission.MEMBER_INVITE,
        role=actor.role.value,
        invite_min_role=community.invite_min_role.value,
    )


def _new_token() -> str:
    """43 URL-safe characters. Fits `token`'s 64, and is the thing an emailed
    invitee presents instead of an invite id they have no way to learn."""
    return secrets.token_urlsafe(32)


def _expiry(days: int | None, now: datetime) -> datetime:
    span = DEFAULT_TTL_DAYS if days is None else max(1, min(days, MAX_TTL_DAYS))
    return now + timedelta(days=span)


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------

async def get_invite(db: AsyncSession, invite_id: uuid.UUID) -> CommunityInvite:
    invite = await db.get(CommunityInvite, invite_id)
    if invite is None:
        raise errors.not_found(
            errors.Code.INVITE_NOT_FOUND, "That invitation does not exist."
        )
    return invite


async def get_by_token(db: AsyncSession, token: str) -> CommunityInvite:
    invite = await db.scalar(
        select(CommunityInvite).where(CommunityInvite.token == token)
    )
    if invite is None:
        raise errors.not_found(
            errors.Code.INVITE_NOT_FOUND, "That invitation link is not valid."
        )
    return invite


async def _pending_for(
    db: AsyncSession, community_id: uuid.UUID, *,
    user_id: uuid.UUID | None, email: str | None,
) -> CommunityInvite | None:
    """The live invitation already held by this person, if any."""
    clauses = []
    if user_id is not None:
        clauses.append(CommunityInvite.invited_user_id == user_id)
    if email is not None:
        clauses.append(func.lower(CommunityInvite.email) == email.lower())
    if not clauses:
        return None
    return await db.scalar(
        select(CommunityInvite).where(
            CommunityInvite.community_id == community_id,
            CommunityInvite.status == InviteStatus.pending,
            or_(*clauses),
        )
    )


def _lapse(invite: CommunityInvite, now: datetime) -> bool:
    """Stamp an expired invitation. True when it had in fact lapsed.

    Expiry is a timestamp comparison, not a scheduled job, so `status` only
    catches up when something reads the row. Every path that cares calls this
    first, which keeps "expired" a single definition rather than one per caller.
    """
    if invite.status is InviteStatus.pending and invite.has_expired(now):
        invite.status = InviteStatus.expired
        return True
    return False


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------

async def _resolve_invitee(
    db: AsyncSession, *, user_id: uuid.UUID | None, email: str | None,
) -> tuple[User | None, str | None]:
    """Turn the request's addressee into (user, email-if-no-account).

    An email that belongs to an existing account resolves to that account, so
    the invitation lands in their notifications rather than sitting in a table
    waiting for a signup that already happened.
    """
    if user_id is not None:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            raise errors.not_found(
                errors.Code.MEMBER_NOT_FOUND, "That user does not exist."
            )
        return user, None

    normalised = (email or "").strip().lower()
    if not normalised:
        raise errors.unprocessable(
            errors.Code.VALIDATION_FAILED,
            "Give either a user_id or an email to invite.",
        )
    user = await db.scalar(select(User).where(func.lower(User.email) == normalised))
    if user is not None and user.is_active:
        return user, None
    return None, normalised


async def invite_member(
    db: AsyncSession,
    community: Community,
    actor: CommunityMember,
    *,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    role: CommunityRole = CommunityRole.member,
    message: str | None = None,
    expires_in_days: int | None = None,
) -> CommunityInvite:
    """Offer membership. The invitee's acceptance is what creates it.

    Who may invite is the community's own setting, not a fixed rank. Default is
    `admin`, which is the historical behaviour; a community that sets
    `invite_min_role` to `member` is one its own members grow — anyone inside
    can bring someone in, while joining still requires an invitation. Read with
    `meets_rank` rather than `outranks`, so an admin still clears an
    admin-only setting.
    """
    _require_may_invite(community, actor)
    communities_service.require_active(community)
    now = datetime.now(UTC)

    # An invitation can no more mint an owner than add-member can: ownership
    # moves through transfer_ownership and nowhere else.
    if role is CommunityRole.owner:
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "Ownership is transferred, not offered in an invitation.",
        )
    if not perms.may_grant(actor.role, role):
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "You cannot offer a role that carries authority you do not outrank.",
            role=role.value, actor_role=actor.role.value,
        )

    target, target_email = await _resolve_invitee(db, user_id=user_id, email=email)

    if target is not None:
        if target.id == actor.user_id:
            raise errors.conflict(
                errors.Code.CONFLICT, "You are already in this community."
            )
        existing_membership = await communities_service.membership_of(
            db, community.id, target.id
        )
        # A banned person is not invitable — lifting the ban is the way back.
        communities_service._reject_if_banned(existing_membership, now)
        if (
            existing_membership is not None
            and existing_membership.status in ACTIVE_MEMBER_STATUSES
        ):
            raise errors.conflict(
                errors.Code.MEMBER_ALREADY_EXISTS,
                "That person is already a member of this community.",
            )

    live = await _pending_for(
        db, community.id, user_id=target.id if target else None, email=target_email
    )
    if live is not None and not _lapse(live, now):
        raise errors.conflict(
            errors.Code.INVITE_ALREADY_EXISTS,
            "That person already has a pending invitation to this community.",
            invite_id=str(live.id),
            expires_at=live.expires_at.isoformat() if live.expires_at else None,
        )

    invite = CommunityInvite(
        community_id=community.id,
        invited_user_id=target.id if target else None,
        email=target_email,
        invited_by_id=actor.user_id,
        role=role,
        status=InviteStatus.pending,
        token=_new_token(),
        message=message,
        expires_at=_expiry(expires_in_days, now),
    )
    db.add(invite)
    # Flush before the audit and notification rows are staged: `invite.id` is a
    # client-side default applied at INSERT, so both would otherwise record None.
    await db.flush()

    audit.record(
        db, AuditAction.INVITE_SENT, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="invite", entity_id=invite.id,
        target_user_id=target.id if target else None, email=target_email, role=role,
    )
    if target is not None:
        notifications.notify(
            db, user_id=target.id, actor_id=actor.user_id,
            kind=NotificationKind.community_invite,
            title=f"You were invited to {community.name}",
            body=message or f"As {role.value}.",
            link=f"/communities?invite={invite.token}",
            invite_id=str(invite.id),
        )
    try:
        await db.commit()
    except IntegrityError:
        # The partial unique index caught a concurrent duplicate invitation.
        await db.rollback()
        raise errors.conflict(
            errors.Code.INVITE_ALREADY_EXISTS,
            "That person already has a pending invitation to this community.",
        ) from None
    await db.refresh(invite)
    return invite


async def resend_invite(
    db: AsyncSession, community: Community, actor: CommunityMember, invite_id: uuid.UUID,
    *, expires_in_days: int | None = None,
) -> CommunityInvite:
    """Extend a pending invitation and issue it a fresh token.

    The old token stops working, which is the point: resending after a
    forwarded email is how an invitation is taken back from the wrong inbox.
    """
    perms.require(actor.role, Permission.MEMBER_INVITE)
    communities_service.require_active(community)
    now = datetime.now(UTC)

    invite = await get_invite(db, invite_id)
    _require_belongs(invite, community)
    _lapse(invite, now)
    if invite.status not in (InviteStatus.pending, InviteStatus.expired):
        raise errors.conflict(
            errors.Code.INVITE_NOT_PENDING,
            f"That invitation was already {invite.status.value}.",
            status=invite.status.value,
        )

    invite.status = InviteStatus.pending
    invite.token = _new_token()
    invite.expires_at = _expiry(expires_in_days, now)
    invite.responded_at = None

    audit.record(
        db, AuditAction.INVITE_RESENT, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="invite", entity_id=invite.id,
    )
    if invite.invited_user_id is not None:
        notifications.notify(
            db, user_id=invite.invited_user_id, actor_id=actor.user_id,
            kind=NotificationKind.community_invite,
            title=f"Your invitation to {community.name} was resent",
            link=f"/communities?invite={invite.token}",
            invite_id=str(invite.id),
        )
    await db.commit()
    await db.refresh(invite)
    return invite


# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------

def _require_belongs(invite: CommunityInvite, community: Community) -> None:
    """Guard against an invite id from one community being used against another."""
    if invite.community_id != community.id:
        raise errors.not_found(
            errors.Code.INVITE_NOT_FOUND, "That invitation does not exist."
        )


async def list_invites(
    db: AsyncSession, community: Community, actor: CommunityMember,
    *, status: InviteStatus | None = None, limit: int = 50, offset: int = 0,
) -> tuple[list[CommunityInvite], int]:
    """The community's own invitation roster. Needs the invite permission —
    who was approached, and by whom, is management information."""
    perms.require(actor.role, Permission.MEMBER_INVITE)

    where = [CommunityInvite.community_id == community.id]
    if status is not None:
        where.append(CommunityInvite.status == status)

    total = await db.scalar(
        select(func.count(CommunityInvite.id)).where(*where)
    ) or 0
    rows = (await db.scalars(
        select(CommunityInvite)
        .where(*where)
        .order_by(CommunityInvite.created_at.desc())
        .limit(limit).offset(offset)
    )).all()

    now = datetime.now(UTC)
    lapsed = [row for row in rows if _lapse(row, now)]
    if lapsed:
        await db.commit()
    return list(rows), total


async def invites_for_user(db: AsyncSession, user: User) -> list[CommunityInvite]:
    """Everything currently open and addressed to this member.

    Matches on the account *and* on the email, so an invitation sent before they
    signed up is waiting for them the moment they do.
    """
    rows = (await db.scalars(
        select(CommunityInvite)
        .where(
            CommunityInvite.status == InviteStatus.pending,
            or_(
                CommunityInvite.invited_user_id == user.id,
                func.lower(CommunityInvite.email) == (user.email or "").lower(),
            ),
        )
        .order_by(CommunityInvite.created_at.desc())
    )).all()

    now = datetime.now(UTC)
    live = [row for row in rows if not _lapse(row, now)]
    if len(live) != len(rows):
        await db.commit()
    return live


# --------------------------------------------------------------------------
# Answering
# --------------------------------------------------------------------------

def _require_addressee(invite: CommunityInvite, user: User) -> None:
    """Only the person an invitation names may answer it.

    The token is a secret, but it is not on its own an authorisation: a
    forwarded link must not let a third party take the seat.
    """
    if invite.invited_user_id is not None and invite.invited_user_id == user.id:
        return
    if (
        invite.email is not None
        and (user.email or "").lower() == invite.email.lower()
    ):
        return
    raise errors.forbidden(
        errors.Code.INVITE_NOT_YOURS, "That invitation was not addressed to you."
    )


async def _require_actionable(
    db: AsyncSession, invite: CommunityInvite, now: datetime
) -> None:
    if _lapse(invite, now):
        await db.commit()
        raise errors.unprocessable(
            errors.Code.INVITE_EXPIRED, "That invitation has expired.",
            expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        )
    if invite.status is not InviteStatus.pending:
        raise errors.conflict(
            errors.Code.INVITE_NOT_PENDING,
            f"That invitation was already {invite.status.value}.",
            status=invite.status.value,
        )


async def accept_invite(
    db: AsyncSession, invite: CommunityInvite, user: User
) -> CommunityMember:
    """Take up the offer. This is the moment the membership exists.

    The capacity and moderator checks live here rather than at invite time
    because they are questions about the community *now* — its owner may have
    downgraded, and other invitations may have been accepted first.
    """
    now = datetime.now(UTC)
    _require_addressee(invite, user)
    await _require_actionable(db, invite, now)

    community = await db.get(Community, invite.community_id)
    if community is None:
        raise errors.not_found(
            errors.Code.COMMUNITY_NOT_FOUND, "That community no longer exists."
        )
    communities_service.require_active(community)

    existing = await communities_service.membership_of(db, community.id, user.id)
    communities_service._reject_if_banned(existing, now)
    if existing is not None and existing.status in ACTIVE_MEMBER_STATUSES:
        # Already in by another route. Close the invitation rather than fail —
        # the invitee's intent is satisfied either way.
        invite.status = InviteStatus.accepted
        invite.responded_at = now
        await db.commit()
        return existing

    await communities_service._check_member_capacity(db, community)
    if invite.role is CommunityRole.moderator:
        await communities_service._check_moderator_budget(db, community)

    membership = existing or CommunityMember(
        community_id=community.id, user_id=user.id
    )
    membership.status = MembershipStatus.joined
    membership.joined_at = now
    membership.banned_until = None
    membership.apply_role(invite.role)
    if existing is None:
        db.add(membership)
    await communities_service.bump_members(db, community.id, +1)

    invite.status = InviteStatus.accepted
    invite.responded_at = now
    # An invitation addressed to an email is bound to the account that accepted
    # it, so the history says who actually took the seat.
    if invite.invited_user_id is None:
        invite.invited_user_id = user.id

    audit.record(
        db, AuditAction.INVITE_ACCEPTED, actor_user_id=user.id,
        community_id=community.id, entity_type="invite", entity_id=invite.id,
        role=invite.role,
    )
    if invite.invited_by_id is not None:
        notifications.notify(
            db, user_id=invite.invited_by_id, actor_id=user.id,
            kind=NotificationKind.community_invite_accepted,
            title=f"{user.name} joined {community.name}",
            body="They accepted your invitation.",
            link=f"/communities?open={community.slug}",
        )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise errors.conflict(
            errors.Code.MEMBER_ALREADY_EXISTS, "You are already a member."
        ) from None
    await db.refresh(membership)
    return membership


async def decline_invite(
    db: AsyncSession, invite: CommunityInvite, user: User
) -> CommunityInvite:
    """Turn the offer down. Kept as a row, so it is not re-sent blindly."""
    now = datetime.now(UTC)
    _require_addressee(invite, user)
    await _require_actionable(db, invite, now)

    invite.status = InviteStatus.declined
    invite.responded_at = now

    audit.record(
        db, AuditAction.INVITE_DECLINED, actor_user_id=user.id,
        community_id=invite.community_id, entity_type="invite", entity_id=invite.id,
    )
    if invite.invited_by_id is not None:
        notifications.notify(
            db, user_id=invite.invited_by_id, actor_id=user.id,
            kind=NotificationKind.community_invite_declined,
            title=f"{user.name} declined your invitation",
        )
    await db.commit()
    await db.refresh(invite)
    return invite


async def revoke_invite(
    db: AsyncSession, community: Community, actor: CommunityMember, invite_id: uuid.UUID
) -> CommunityInvite:
    """Withdraw an invitation that has not been answered."""
    perms.require(actor.role, Permission.MEMBER_INVITE)
    now = datetime.now(UTC)

    invite = await get_invite(db, invite_id)
    _require_belongs(invite, community)
    _lapse(invite, now)
    if invite.status is not InviteStatus.pending:
        raise errors.conflict(
            errors.Code.INVITE_NOT_PENDING,
            f"That invitation was already {invite.status.value}.",
            status=invite.status.value,
        )

    invite.status = InviteStatus.revoked
    invite.responded_at = now
    audit.record(
        db, AuditAction.INVITE_REVOKED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="invite", entity_id=invite.id,
    )
    await db.commit()
    await db.refresh(invite)
    return invite
