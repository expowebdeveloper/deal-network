"""Community and membership rules — backend_flow.md sections 10, 11, 13 and 24.

Everything that decides *whether* something may happen lives here; the routers
in `api/routes/v1/` only unpack the request and hand over. That is section 3's
"keep routers thin", and it is what lets the same rules be reused by a
background job or an admin tool later.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.models import (
    ACTIVE_MEMBER_STATUSES, EDITABLE_COMMUNITY_STATUSES, OWNED_COMMUNITY_STATUSES,
    AuditAction, Community, CommunityChannel, CommunityMember,
    CommunityRole, CommunityStatus, JoinPolicy, MembershipStatus, NotificationKind, PlanTier,
    User, VisibilityLevel,
)
from app.services import audit
from app.services import notifications
from app.services import community_permissions as perms
from app.services import entitlements as ent
from app.services.community_permissions import Permission
from app.services.entitlements import Feature

DEFAULT_CHANNELS = ("# general", "# announcements")

#: Which plan feature each non-default visibility needs (section 11).
VISIBILITY_FEATURE: dict[VisibilityLevel, str | None] = {
    VisibilityLevel.public: None,  # every plan
    VisibilityLevel.private: Feature.COMMUNITY_PRIVATE,
    VisibilityLevel.members: Feature.COMMUNITY_MEMBER_ONLY,
}

#: Likewise for join policies. `open` is available on every plan.
JOIN_POLICY_FEATURE: dict[JoinPolicy, str | None] = {
    JoinPolicy.open: None,
    JoinPolicy.request: Feature.COMMUNITY_JOIN_APPROVAL,
    JoinPolicy.invite: Feature.COMMUNITY_INVITE_ONLY,
    JoinPolicy.admin_added: Feature.COMMUNITY_INVITE_ONLY,
}


# --------------------------------------------------------------------------
# Lookup
# --------------------------------------------------------------------------

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or uuid.uuid4().hex[:12]


async def unique_slug(
    db: AsyncSession, name: str, exclude_id: uuid.UUID | None = None
) -> str:
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


async def get_community(db: AsyncSession, ref: str | uuid.UUID) -> Community:
    """Fetch by id or slug. The spec's URLs use the id; slugs stay supported
    so a link that already exists keeps working."""
    community: Community | None = None
    if isinstance(ref, uuid.UUID):
        community = await db.get(Community, ref)
    else:
        try:
            community = await db.get(Community, uuid.UUID(str(ref)))
        except (ValueError, AttributeError):
            community = await db.scalar(select(Community).where(Community.slug == str(ref)))

    if community is None or community.status is CommunityStatus.deleted:
        raise errors.not_found(
            errors.Code.COMMUNITY_NOT_FOUND, "That community does not exist."
        )
    return community


async def membership_of(
    db: AsyncSession, community_id: uuid.UUID, user_id: uuid.UUID
) -> CommunityMember | None:
    return await db.scalar(
        select(CommunityMember).where(
            CommunityMember.community_id == community_id,
            CommunityMember.user_id == user_id,
        )
    )


async def active_membership(
    db: AsyncSession, community_id: uuid.UUID, user_id: uuid.UUID
) -> CommunityMember | None:
    membership = await membership_of(db, community_id, user_id)
    if membership is None or membership.status not in ACTIVE_MEMBER_STATUSES:
        return None
    return membership


async def require_membership(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> CommunityMember:
    membership = await active_membership(db, community.id, user_id)
    if membership is None:
        raise errors.forbidden(
            errors.Code.MEMBERSHIP_REQUIRED,
            "Join this community to do that.",
            community_id=str(community.id),
        )
    return membership


def require_active(community: Community) -> None:
    """Live and open for business.

    Used by the paths that need an audience — joining, inviting, posting. A
    draft fails here on purpose: it has not been published, so there is nothing
    to join yet.
    """
    if community.status is CommunityStatus.draft:
        raise errors.conflict(
            errors.Code.COMMUNITY_NOT_PUBLISHED,
            "This community is still a draft. Publish it first.",
            status=community.status.value,
        )
    if community.status is not CommunityStatus.active:
        raise errors.conflict(
            errors.Code.COMMUNITY_ARCHIVED,
            "This community is archived. Restore it before making changes.",
            status=community.status.value,
        )


def require_editable(community: Community) -> None:
    """Settings, members, roles and channels may still be changed.

    Wider than `require_active` by exactly one status: a draft is *meant* to be
    edited — that is what the draft stage is for — while an archived community
    stays read-only until it is restored.
    """
    if community.status in EDITABLE_COMMUNITY_STATUSES:
        return
    raise errors.conflict(
        errors.Code.COMMUNITY_ARCHIVED,
        "This community is archived. Restore it before making changes.",
        status=community.status.value,
    )


async def can_view(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> bool:
    """Section 9.1's visibility, as a read check.

    PUBLIC is browsable by any signed-in member. MEMBER_ONLY and PRIVATE both
    require membership; they differ in discoverability, which is applied in the
    list query rather than here.
    """
    # An unpublished community is nobody's business but its own members'. This
    # is checked before visibility, so a *public* draft is still hidden.
    if community.status is CommunityStatus.draft:
        return await active_membership(db, community.id, user_id) is not None
    if community.visibility is VisibilityLevel.public:
        return True
    return await active_membership(db, community.id, user_id) is not None


async def require_view(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> None:
    if not await can_view(db, community, user_id):
        raise errors.forbidden(
            errors.Code.COMMUNITY_ACCESS_DENIED,
            "This community is not visible to you.",
            visibility=community.visibility.value,
        )


# --------------------------------------------------------------------------
# Creation — section 10's fourteen steps, in order
# --------------------------------------------------------------------------

async def _validate_visibility(
    db: AsyncSession, user_id: uuid.UUID, visibility: VisibilityLevel
) -> None:
    feature = VISIBILITY_FEATURE[visibility]
    if feature is None:
        return
    if await ent.has_feature(db, user_id, feature):
        return
    plan = await ent.effective_plan(db, user_id)
    needed = await ent.cheapest_plan_with(db, feature)
    raise errors.forbidden(
        errors.Code.PRIVATE_COMMUNITY_NOT_ALLOWED,
        f"Your plan cannot create {visibility.value.lower()} communities.",
        visibility=visibility.value,
        current_plan=plan.value,
        upgrade_plan=needed.value if needed else None,
    )


async def _validate_join_policy(
    db: AsyncSession, user_id: uuid.UUID, policy: JoinPolicy
) -> None:
    feature = JOIN_POLICY_FEATURE[policy]
    if feature is None:
        return
    if await ent.has_feature(db, user_id, feature):
        return
    plan = await ent.effective_plan(db, user_id)
    needed = await ent.cheapest_plan_with(db, feature)
    raise errors.forbidden(
        errors.Code.JOIN_POLICY_NOT_ALLOWED,
        f"Your plan cannot use the '{policy.value}' join policy.",
        join_policy=policy.value,
        current_plan=plan.value,
        upgrade_plan=needed.value if needed else None,
    )


async def _lock_owner(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialise this member's concurrent creates — section 24.

    Counting owned communities and then inserting is a read-then-write, so two
    simultaneous requests from the same member both see 9 of 10 and both insert.
    A transaction-scoped advisory lock keyed on the user makes the second wait
    for the first to commit, so it counts 10 and is refused.

    Advisory rather than `SELECT … FOR UPDATE` on users: no row is being
    modified, and it does not block unrelated writes to the account.
    """
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"community-create:{user_id}"},
    )


async def owned_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """How many communities occupy a slot against `community.max_owned`.

    **Draft and active.** A draft holds a slot because it is a community the
    member is building; if it did not, the ceiling would mean nothing — create a
    hundred drafts and publish them one at a time.

    **Archived does not.** Archiving is how a downgrade brings a member back
    within a lower ceiling (section 32), so an archived community cannot go on
    holding a slot — otherwise the downgrade would archive three and the member
    would still be over, permanently stuck.

    The trade is that archive-then-create can be repeated. That is the right way
    round: the limit is on how many communities a member runs at once, and an
    archived one is dormant — invisible in browse, read-only, and it has to pass
    this same check to come back.
    """
    return await db.scalar(
        select(func.count(Community.id)).where(
            Community.owner_id == user_id,
            Community.status.in_(OWNED_COMMUNITY_STATUSES),
        )
    ) or 0


async def create_community(
    db: AsyncSession,
    user: User,
    *,
    name: str,
    kind,
    visibility: VisibilityLevel,
    join_policy: JoinPolicy,
    category: str | None = None,
    location: str = "Global",
    description: str | None = None,
    rules: str | None = None,
    banner: str = "b1",
    logo_url: str | None = None,
    cover_url: str | None = None,
    channels: list[str] | None = None,
) -> Community:
    """Section 10, step for step. One transaction (section 27)."""
    # 3/4/5. One pass down the entitlement flow: tier -> base entitlements ->
    # add-ons -> effective ceiling -> usage -> allow or prompt. The count is
    # taken here rather than left to the service's own counter because it has to
    # happen under the lock — two simultaneous requests must not both pass.
    await _lock_owner(db, user.id)
    await ent.require(
        db, user.id, "community.create", usage=await owned_count(db, user.id)
    )

    # 6/7. visibility and join policy against the plan
    await _validate_visibility(db, user.id, visibility)
    await _validate_join_policy(db, user.id, join_policy)

    # 8/9. validate fields and create
    requested = [c.strip() for c in (channels or DEFAULT_CHANNELS) if c.strip()]
    await _check_channel_budget(db, user.id, len(requested) or 1)

    now = datetime.now(UTC)
    community = Community(
        name=name,
        slug=await unique_slug(db, name),
        kind=kind,
        category=category,
        location=location,
        description=description,
        rules=rules,
        banner=banner,
        logo_url=logo_url,
        cover_url=cover_url,
        initials="".join(word[0] for word in name.split()[:2]).upper(),
        visibility=visibility,
        join_policy=join_policy,
        # Every community starts unpublished. It is configurable straight away
        # and invisible to everyone else until `publish_community` is called.
        status=CommunityStatus.draft,
        created_by_id=user.id,
        owner_id=user.id,
        member_count=1,
    )
    db.add(community)
    await db.flush()

    # 10/11. owner membership, with the OWNER role
    membership = CommunityMember(
        community_id=community.id,
        user_id=user.id,
        status=MembershipStatus.joined,
        joined_at=now,
    )
    membership.apply_role(CommunityRole.owner)
    db.add(membership)

    # 12. default channels
    seen: set[str] = set()
    for channel in requested or list(DEFAULT_CHANNELS):
        if channel.lower() not in seen:
            seen.add(channel.lower())
            db.add(CommunityChannel(community_id=community.id, name=channel))

    # 13. audit
    audit.record(
        db, AuditAction.COMMUNITY_CREATED, actor_user_id=user.id,
        community_id=community.id, entity_type="community", entity_id=community.id,
        name=name, visibility=visibility, join_policy=join_policy,
        status=CommunityStatus.draft,
    )

    await db.commit()
    await db.refresh(community)
    return community  # 14.


async def publish_community(
    db: AsyncSession, community: Community, actor: CommunityMember
) -> Community:
    """Take a draft live — the one-way move from `draft` to `active`.

    Only from `draft`: an archived community comes back through `restore`, and
    a live one is already published. `published_at` is stamped once and kept
    through later archive/restore cycles, so it records when the community first
    went live rather than when it was last visible.

    The plan is re-checked here as well as at creation. A draft may have sat
    unpublished across a downgrade, and publishing is the moment it starts
    consuming an audience — so a visibility or join policy the plan no longer
    carries has to be refused now rather than quietly going live.
    """
    perms.require(actor.role, Permission.COMMUNITY_MANAGE)
    if community.status is not CommunityStatus.draft:
        raise errors.conflict(
            errors.Code.CONFLICT,
            "This community is already published."
            if community.status is CommunityStatus.active
            else "Only a draft can be published.",
            status=community.status.value,
        )

    owner_id = community.owner_id or actor.user_id
    await _validate_visibility(db, owner_id, community.visibility)
    await _validate_join_policy(db, owner_id, community.join_policy)

    now = datetime.now(UTC)
    community.status = CommunityStatus.active
    community.published_at = now

    audit.record(
        db, AuditAction.COMMUNITY_PUBLISHED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="community", entity_id=community.id,
        visibility=community.visibility, join_policy=community.join_policy,
    )
    await db.commit()
    await db.refresh(community)
    return community


async def _check_channel_budget(db: AsyncSession, user_id: uuid.UUID, wanted: int) -> None:
    """Whether `wanted` channels fit in one community on this member's plan.

    `usage=0, amount=wanted` rather than `usage=wanted-1, amount=1`: the
    question is whether the whole set fits, which is what makes creating a
    community with five channels on a three-channel plan one refusal instead of
    a partial create.
    """
    await ent.require(db, user_id, "community.channel.create", usage=0, amount=wanted)


# --------------------------------------------------------------------------
# Update, archive, restore, delete
# --------------------------------------------------------------------------

async def update_community(
    db: AsyncSession, community: Community, actor: CommunityMember, changes: dict
) -> Community:
    perms.require(actor.role, Permission.COMMUNITY_MANAGE)
    require_editable(community)

    # Only `description`, `rules`, `category`, `logo_url` and `cover_url` are
    # nullable; an explicit null anywhere else would breach NOT NULL and surface
    # as a 500 rather than a refusal the caller can read.
    nullable = {"description", "rules", "category", "logo_url", "cover_url"}
    nulled = sorted(k for k, v in changes.items() if v is None and k not in nullable)
    if nulled:
        raise errors.unprocessable(
            errors.Code.VALIDATION_FAILED,
            f"These fields cannot be set to null: {', '.join(nulled)}",
            fields=nulled,
        )

    if "visibility" in changes:
        await _validate_visibility(db, actor.user_id, changes["visibility"])
    if "join_policy" in changes:
        await _validate_join_policy(db, actor.user_id, changes["join_policy"])

    new_name = changes.get("name")
    for field, value in changes.items():
        setattr(community, field, value)
    if new_name:
        community.slug = await unique_slug(db, new_name, exclude_id=community.id)
        community.initials = "".join(w[0] for w in new_name.split()[:2]).upper()

    audit.record(
        db, AuditAction.COMMUNITY_UPDATED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="community", entity_id=community.id,
        fields=sorted(changes),
    )
    await db.commit()
    await db.refresh(community)
    return community


async def archive_community(
    db: AsyncSession, community: Community, actor: CommunityMember
) -> Community:
    """Soft delete, per section 12. Nothing is destroyed."""
    perms.require(actor.role, Permission.COMMUNITY_ARCHIVE)
    if community.status is CommunityStatus.archived:
        raise errors.conflict(
            errors.Code.CONFLICT, "This community is already archived."
        )
    community.status = CommunityStatus.archived
    community.archived_at = datetime.now(UTC)
    audit.record(
        db, AuditAction.COMMUNITY_ARCHIVED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="community", entity_id=community.id,
    )
    await db.commit()
    await db.refresh(community)
    return community


async def restore_community(
    db: AsyncSession, community: Community, actor: CommunityMember
) -> Community:
    perms.require(actor.role, Permission.COMMUNITY_ARCHIVE)
    if community.status is not CommunityStatus.archived:
        raise errors.conflict(errors.Code.CONFLICT, "This community is not archived.")

    owner_id = community.owner_id or actor.user_id

    # Restoring reoccupies a slot, so it has to pass the same ceiling a create
    # would — otherwise archive-then-create-then-restore walks past the limit.
    # `owned_count` counts active communities only, which is what makes an
    # archived one free to hold.
    await _lock_owner(db, owner_id)
    restore = await ent.decide(
        db, owner_id, "community.create", usage=await owned_count(db, owner_id)
    )
    if restore.blocked:
        raise errors.forbidden(
            restore.reason,
            "Restoring this community would put you over your plan's limit.",
            **{k: v for k, v in restore.body().items() if k not in ("allowed", "reason")},
        )
    # …and the same capability checks. A community archived on Professional may
    # be member-only; restoring it on Member must not quietly re-enable that.
    await _validate_visibility(db, owner_id, community.visibility)
    await _validate_join_policy(db, owner_id, community.join_policy)

    community.status = CommunityStatus.active
    community.archived_at = None
    audit.record(
        db, AuditAction.COMMUNITY_RESTORED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="community", entity_id=community.id,
    )
    await db.commit()
    await db.refresh(community)
    return community


async def delete_community(
    db: AsyncSession, community: Community, actor: CommunityMember
) -> None:
    """Soft delete. Section 12: DELETE is an archive workflow, not a DROP."""
    perms.require(actor.role, Permission.COMMUNITY_DELETE)
    community.status = CommunityStatus.deleted
    community.archived_at = community.archived_at or datetime.now(UTC)
    audit.record(
        db, AuditAction.COMMUNITY_DELETED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="community", entity_id=community.id,
    )
    await db.commit()


# --------------------------------------------------------------------------
# Membership
# --------------------------------------------------------------------------

async def bump_members(db: AsyncSession, community_id: uuid.UUID, delta: int) -> None:
    """Adjust member_count in SQL, never through a Python round trip.

    `count = count + 1` computed in Python loses one of two concurrent joins
    under READ COMMITTED; computing it in SQL does not.
    """
    new_value = Community.member_count + delta
    if delta < 0:
        new_value = func.greatest(new_value, 0)
    await db.execute(
        update(Community).where(Community.id == community_id).values(member_count=new_value)
    )


async def _check_member_capacity(db: AsyncSession, community: Community) -> None:
    """The ceiling belongs to whoever owns the community, not to the joiner.

    Which is the whole reason the entitlement flow takes a user id rather than
    reading the caller: a Freemium member joining a Gold member's community is
    held to the Gold ceiling, and a Gold member joining a Freemium one is held
    to Freemium's.
    """
    if community.owner_id is None:
        return
    await ent.require(
        db, community.owner_id, "community.join",
        usage=community.member_count, community_id=community.id,
    )


def _reject_if_banned(membership: CommunityMember | None, now: datetime) -> None:
    if membership is not None and membership.is_banned(now):
        raise errors.forbidden(
            errors.Code.MEMBER_BANNED,
            "You are banned from this community.",
            until=membership.banned_until.isoformat() if membership.banned_until else None,
        )


async def join_community(
    db: AsyncSession, community: Community, user: User
) -> CommunityMember:
    """Self-service join. Open communities admit immediately; request-approval
    ones create a PENDING row instead."""
    require_active(community)
    now = datetime.now(UTC)

    if community.join_policy in (JoinPolicy.invite, JoinPolicy.admin_added):
        raise errors.forbidden(
            errors.Code.JOIN_POLICY_NOT_ALLOWED,
            "This community is invite only.",
            join_policy=community.join_policy.value,
        )

    existing = await membership_of(db, community.id, user.id)
    _reject_if_banned(existing, now)
    if existing is not None:
        if existing.status is MembershipStatus.pending:
            raise errors.conflict(
                errors.Code.JOIN_REQUEST_ALREADY_EXISTS,
                "Your request to join is already pending.",
            )
        if existing.status in ACTIVE_MEMBER_STATUSES:
            raise errors.conflict(
                errors.Code.MEMBER_ALREADY_EXISTS, "You are already a member."
            )
        # Previously left or was removed — reinstate the same row.
        joining = community.join_policy is JoinPolicy.open
        existing.status = MembershipStatus.joined if joining else MembershipStatus.pending
        existing.apply_role(CommunityRole.member)
        if joining:
            await _check_member_capacity(db, community)
            existing.joined_at = now
            await bump_members(db, community.id, +1)
        audit.record(
            db,
            AuditAction.MEMBER_JOINED if joining else AuditAction.JOIN_REQUEST_CREATED,
            actor_user_id=user.id, community_id=community.id,
            entity_type="membership", entity_id=existing.id,
        )
        await db.commit()
        await db.refresh(existing)
        return existing

    joining = community.join_policy is JoinPolicy.open
    if joining:
        await _check_member_capacity(db, community)

    membership = CommunityMember(
        community_id=community.id,
        user_id=user.id,
        status=MembershipStatus.joined if joining else MembershipStatus.pending,
        joined_at=now if joining else None,
    )
    membership.apply_role(CommunityRole.member)
    db.add(membership)
    if joining:
        await bump_members(db, community.id, +1)

    audit.record(
        db,
        AuditAction.MEMBER_JOINED if joining else AuditAction.JOIN_REQUEST_CREATED,
        actor_user_id=user.id, community_id=community.id,
        entity_type="membership", entity_id=membership.id,
    )
    await _notify_admins(
        db, community, actor=user,
        kind=(NotificationKind.community_member_added if joining
              else NotificationKind.community_join_request),
        title=(f"{user.name} joined {community.name}" if joining
               else f"{user.name} asked to join {community.name}"),
        body=None if joining else "Approve or decline from the community's requests.",
    )
    try:
        await db.commit()
    except IntegrityError:
        # Two joins raced; uq_community_user caught the loser.
        await db.rollback()
        raise errors.conflict(
            errors.Code.MEMBER_ALREADY_EXISTS, "You are already a member."
        ) from None
    await db.refresh(membership)
    return membership


async def add_member(
    db: AsyncSession,
    community: Community,
    actor: CommunityMember,
    target: User,
    role: CommunityRole = CommunityRole.member,
) -> CommunityMember:
    """Owner/Admin adds an existing member directly — section 13's add flow."""
    perms.require(actor.role, Permission.MEMBER_ADD)
    require_editable(community)
    now = datetime.now(UTC)

    # Section 13: this endpoint must never create or transfer an OWNER role,
    # and a role may only be granted by someone who outranks it.
    if role is CommunityRole.owner:
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "Ownership is transferred, not assigned when adding a member.",
        )
    if not perms.outranks(actor.role, role):
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "You cannot grant a role at or above your own.",
            role=role.value, actor_role=actor.role.value,
        )
    if role is CommunityRole.moderator:
        await _check_moderator_budget(db, community)

    existing = await membership_of(db, community.id, target.id)
    _reject_if_banned(existing, now)
    if existing is not None and existing.status in ACTIVE_MEMBER_STATUSES:
        raise errors.conflict(
            errors.Code.MEMBER_ALREADY_EXISTS,
            "That person is already a member of this community.",
        )

    await _check_member_capacity(db, community)

    membership = existing or CommunityMember(community_id=community.id, user_id=target.id)
    was_counted = existing is not None and existing.status in ACTIVE_MEMBER_STATUSES
    membership.status = MembershipStatus.joined
    membership.joined_at = now
    membership.banned_until = None
    membership.apply_role(role)
    if existing is None:
        db.add(membership)
    if not was_counted:
        await bump_members(db, community.id, +1)

    audit.record(
        db, AuditAction.MEMBER_ADDED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=membership.id,
        target_user_id=target.id, role=role,
    )
    notifications.notify(
        db, user_id=target.id, actor_id=actor.user_id,
        kind=NotificationKind.community_member_added,
        title=f"You were added to {community.name}",
        body=f"As {role.value}.",
        link=f"/communities?open={community.slug}",
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise errors.conflict(
            errors.Code.MEMBER_ALREADY_EXISTS, "That person is already a member."
        ) from None
    await db.refresh(membership)
    return membership


async def _check_moderator_budget(db: AsyncSession, community: Community) -> None:
    if community.owner_id is None:
        return
    current = await db.scalar(
        select(func.count(CommunityMember.id)).where(
            CommunityMember.community_id == community.id,
            CommunityMember.role == CommunityRole.moderator,
        )
    ) or 0
    await ent.require(
        db, community.owner_id, "community.moderator.promote",
        usage=current, community_id=community.id,
    )


async def leave_community(
    db: AsyncSession, community: Community, user: User
) -> None:
    membership = await membership_of(db, community.id, user.id)
    if membership is None or membership.status in (
        MembershipStatus.left, MembershipStatus.removed
    ):
        raise errors.not_found(
            errors.Code.MEMBER_NOT_FOUND, "You are not a member of this community."
        )
    if membership.role is CommunityRole.owner:
        raise errors.conflict(
            errors.Code.OWNER_REQUIRED,
            "Transfer ownership before leaving, or archive the community.",
        )

    was_counted = membership.status in ACTIVE_MEMBER_STATUSES
    membership.status = MembershipStatus.left
    membership.apply_role(CommunityRole.member)
    if was_counted:
        await bump_members(db, community.id, -1)

    audit.record(
        db, AuditAction.MEMBER_LEFT, actor_user_id=user.id, community_id=community.id,
        entity_type="membership", entity_id=membership.id,
    )
    await db.commit()


async def _target_membership(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> CommunityMember:
    membership = await membership_of(db, community.id, user_id)
    if membership is None:
        raise errors.not_found(
            errors.Code.MEMBER_NOT_FOUND, "That person is not a member of this community."
        )
    return membership


async def remove_member(
    db: AsyncSession, community: Community, actor: CommunityMember, user_id: uuid.UUID
) -> None:
    """Section 13: removal ends the membership and nothing else. The person
    keeps their Deal Network account, and may rejoin if the policy allows."""
    perms.require(actor.role, Permission.MEMBER_REMOVE)
    require_editable(community)
    target = await _target_membership(db, community, user_id)
    if target.user_id == actor.user_id:
        raise errors.conflict(
            errors.Code.MEMBER_REMOVE_NOT_ALLOWED, "Use leave to remove yourself."
        )
    perms.require_outranks(actor.role, target.role, action="remove")

    was_counted = target.status in ACTIVE_MEMBER_STATUSES
    target.status = MembershipStatus.removed
    target.apply_role(CommunityRole.member)
    if was_counted:
        await bump_members(db, community.id, -1)

    audit.record(
        db, AuditAction.MEMBER_REMOVED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=target.id,
        target_user_id=user_id,
    )
    await db.commit()


async def ban_member(
    db: AsyncSession, community: Community, actor: CommunityMember,
    user_id: uuid.UUID, *, days: int | None = None, reason: str | None = None,
) -> CommunityMember:
    """Stronger than removal: blocks rejoining until it expires or is lifted."""
    perms.require(actor.role, Permission.MEMBER_BAN)
    require_editable(community)
    target = await _target_membership(db, community, user_id)
    if target.user_id == actor.user_id:
        raise errors.conflict(
            errors.Code.MEMBER_BAN_NOT_ALLOWED, "You cannot ban yourself."
        )
    perms.require_outranks(actor.role, target.role, action="ban")

    was_counted = target.status in ACTIVE_MEMBER_STATUSES
    target.status = MembershipStatus.banned
    target.banned_until = datetime.now(UTC) + timedelta(days=days) if days else None
    target.apply_role(CommunityRole.member)
    if was_counted:
        await bump_members(db, community.id, -1)

    audit.record(
        db, AuditAction.MEMBER_BANNED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=target.id,
        target_user_id=user_id, days=days, reason=reason,
    )
    await db.commit()
    await db.refresh(target)
    return target


async def unban_member(
    db: AsyncSession, community: Community, actor: CommunityMember, user_id: uuid.UUID
) -> CommunityMember:
    perms.require(actor.role, Permission.MEMBER_BAN)
    target = await _target_membership(db, community, user_id)
    if target.status is not MembershipStatus.banned:
        raise errors.conflict(errors.Code.CONFLICT, "That person is not banned.")

    # Lifting a ban does not re-admit them — they rejoin like anyone else.
    target.status = MembershipStatus.removed
    target.banned_until = None
    audit.record(
        db, AuditAction.MEMBER_UNBANNED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=target.id,
        target_user_id=user_id,
    )
    await db.commit()
    await db.refresh(target)
    return target


async def mute_member(
    db: AsyncSession, community: Community, actor: CommunityMember,
    user_id: uuid.UUID, *, minutes: int = 60,
) -> CommunityMember:
    """A mute keeps the membership and suspends posting for a while."""
    perms.require(actor.role, Permission.MEMBER_MUTE)
    require_editable(community)
    target = await _target_membership(db, community, user_id)
    perms.require_outranks(actor.role, target.role, action="mute")
    if target.status not in ACTIVE_MEMBER_STATUSES:
        raise errors.conflict(
            errors.Code.MEMBER_NOT_FOUND, "That person is not an active member."
        )

    target.status = MembershipStatus.muted
    target.muted_until = datetime.now(UTC) + timedelta(minutes=minutes)
    audit.record(
        db, AuditAction.MEMBER_MUTED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=target.id,
        target_user_id=user_id, minutes=minutes,
    )
    await db.commit()
    await db.refresh(target)
    return target


async def unmute_member(
    db: AsyncSession, community: Community, actor: CommunityMember, user_id: uuid.UUID
) -> CommunityMember:
    perms.require(actor.role, Permission.MEMBER_MUTE)
    target = await _target_membership(db, community, user_id)
    if target.status is not MembershipStatus.muted:
        raise errors.conflict(errors.Code.CONFLICT, "That person is not muted.")

    target.status = MembershipStatus.joined
    target.muted_until = None
    audit.record(
        db, AuditAction.MEMBER_UNMUTED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=target.id,
        target_user_id=user_id,
    )
    await db.commit()
    await db.refresh(target)
    return target


async def change_role(
    db: AsyncSession, community: Community, actor: CommunityMember,
    user_id: uuid.UUID, role: CommunityRole,
) -> CommunityMember:
    """Owners and admins manage roles; ownership moves through its own path.

    An admin may appoint and remove moderators. Creating another admin, or
    acting on one, needs the owner — the rank checks below are what enforce it.
    """
    perms.require(actor.role, Permission.ROLE_MANAGE)
    require_editable(community)
    target = await _target_membership(db, community, user_id)

    if role is CommunityRole.owner:
        return await transfer_ownership(db, community, actor, user_id)
    if target.role is CommunityRole.owner:
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "The owner's role cannot be changed. Transfer ownership instead.",
        )
    # Two rank rules, and both are needed now that admins hold ROLE_MANAGE. This
    # first one stops an admin demoting a peer admin: the target's *current* rank
    # has to sit below the actor's. The second stops them handing out a rank they
    # do not exceed, so an admin cannot mint another admin. The owner, a rank
    # above both, is the only one who can do either.
    if not perms.outranks(actor.role, target.role):
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "You cannot change the role of someone at or above your own.",
            target_role=target.role.value, actor_role=actor.role.value,
        )
    if not perms.outranks(actor.role, role):
        raise errors.forbidden(
            errors.Code.ROLE_CHANGE_NOT_ALLOWED,
            "You cannot grant a role at or above your own.",
            role=role.value, actor_role=actor.role.value,
        )
    if target.status not in ACTIVE_MEMBER_STATUSES:
        raise errors.conflict(
            errors.Code.MEMBER_NOT_FOUND, "That person is not an active member."
        )
    if role is CommunityRole.moderator and target.role is not CommunityRole.moderator:
        await _check_moderator_budget(db, community)

    previous = target.role
    target.apply_role(role)
    audit.record(
        db, AuditAction.MEMBER_ROLE_CHANGED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=target.id,
        target_user_id=user_id, role=role, previous_role=previous,
    )
    notifications.notify(
        db, user_id=user_id, actor_id=actor.user_id,
        kind=NotificationKind.community_role_changed,
        title=f"You are now {role.value} of {community.name}",
        link=f"/communities?open={community.slug}",
    )
    await db.commit()
    await db.refresh(target)
    return target


async def transfer_ownership(
    db: AsyncSession, community: Community, actor: CommunityMember, user_id: uuid.UUID
) -> CommunityMember:
    """Section 4: a community has exactly one owner at a time.

    The new owner's community also counts against *their* plan's ceiling, so the
    transfer is refused if it would put them over.
    """
    perms.require(actor.role, Permission.OWNERSHIP_TRANSFER)
    target = await _target_membership(db, community, user_id)
    if target.status not in ACTIVE_MEMBER_STATUSES:
        raise errors.conflict(
            errors.Code.MEMBER_NOT_FOUND, "The new owner must be an active member."
        )
    if target.user_id == actor.user_id:
        raise errors.conflict(errors.Code.CONFLICT, "You already own this community.")

    await _lock_owner(db, target.user_id)
    handover = await ent.decide(
        db, target.user_id, "community.create", usage=await owned_count(db, target.user_id)
    )
    if handover.blocked:
        raise errors.forbidden(
            handover.reason,
            "That member is already at their plan's community limit.",
            **{k: v for k, v in handover.body().items() if k not in ("allowed", "reason")},
        )

    target.apply_role(CommunityRole.owner)
    actor.apply_role(CommunityRole.admin)
    community.owner_id = target.user_id

    audit.record(
        db, AuditAction.OWNERSHIP_TRANSFERRED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="community", entity_id=community.id,
        new_owner_id=target.user_id,
    )
    await db.commit()
    await db.refresh(target)
    return target


# --------------------------------------------------------------------------
# Join requests
# --------------------------------------------------------------------------

async def list_join_requests(
    db: AsyncSession, community: Community, actor: CommunityMember
) -> list[CommunityMember]:
    perms.require(actor.role, Permission.MEMBER_MANAGE)
    rows = await db.scalars(
        select(CommunityMember)
        .where(
            CommunityMember.community_id == community.id,
            CommunityMember.status == MembershipStatus.pending,
        )
        .order_by(CommunityMember.created_at)
    )
    return list(rows)


async def _pending_request(
    db: AsyncSession, community: Community, request_id: uuid.UUID
) -> CommunityMember:
    """The spec addresses a request by its own id, so resolve either that or a
    user id — the SPA has the user to hand and the id in the list response."""
    membership = await db.scalar(
        select(CommunityMember).where(
            CommunityMember.community_id == community.id,
            or_(
                CommunityMember.id == request_id,
                CommunityMember.user_id == request_id,
            ),
            CommunityMember.status == MembershipStatus.pending,
        )
    )
    if membership is None:
        raise errors.not_found(
            errors.Code.JOIN_REQUEST_NOT_FOUND, "There is no pending request for that member."
        )
    return membership


async def approve_join_request(
    db: AsyncSession, community: Community, actor: CommunityMember, request_id: uuid.UUID
) -> CommunityMember:
    perms.require(actor.role, Permission.MEMBER_MANAGE)
    await ent.require_feature_key(db, actor.user_id, Feature.COMMUNITY_JOIN_APPROVAL)
    require_active(community)

    membership = await _pending_request(db, community, request_id)
    await _check_member_capacity(db, community)

    membership.status = MembershipStatus.joined
    membership.joined_at = datetime.now(UTC)
    membership.apply_role(CommunityRole.member)
    await bump_members(db, community.id, +1)

    audit.record(
        db, AuditAction.JOIN_REQUEST_APPROVED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=membership.id,
        target_user_id=membership.user_id,
    )
    notifications.notify(
        db, user_id=membership.user_id, actor_id=actor.user_id,
        kind=NotificationKind.community_join_approved,
        title=f"You are in {community.name}",
        body="Your request to join was approved.",
        link=f"/communities?open={community.slug}",
    )
    await db.commit()
    await db.refresh(membership)
    return membership


async def reject_join_request(
    db: AsyncSession, community: Community, actor: CommunityMember, request_id: uuid.UUID
) -> None:
    perms.require(actor.role, Permission.MEMBER_MANAGE)
    membership = await _pending_request(db, community, request_id)

    audit.record(
        db, AuditAction.JOIN_REQUEST_REJECTED, actor_user_id=actor.user_id,
        community_id=community.id, entity_type="membership", entity_id=membership.id,
        target_user_id=membership.user_id,
    )
    await db.delete(membership)
    await db.commit()


# --------------------------------------------------------------------------
# Browsing
# --------------------------------------------------------------------------

async def visible_communities_query(user_id: uuid.UUID):
    """The base SELECT for browsing: what this member may see.

    Two things are being filtered, not one. PRIVATE and MEMBER_ONLY communities
    are excluded unless they belong to one — section 32's rule that backend
    authorization, not the UI, is the boundary. Drafts are excluded unless they
    belong to one *regardless of visibility*, because an unpublished community
    has no audience yet by definition.
    """
    mine = (
        select(CommunityMember.community_id)
        .where(
            CommunityMember.user_id == user_id,
            CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
        )
        .scalar_subquery()
    )
    return select(Community).where(
        or_(
            # Live communities, subject to their visibility.
            and_(
                Community.status == CommunityStatus.active,
                or_(
                    Community.visibility == VisibilityLevel.public,
                    Community.id.in_(mine),
                ),
            ),
            # Drafts, only for the people building them. Their visibility is not
            # consulted — a public draft is still nobody else's business.
            and_(Community.status == CommunityStatus.draft, Community.id.in_(mine)),
        )
    )


async def _notify_admins(
    db: AsyncSession, community: Community, *, actor: User, kind, title: str,
    body: str | None = None,
) -> None:
    """Tell everyone who can act on it — the owner and any admins.

    Moderators are left out on purpose: they police content, they do not decide
    membership, so a join request is not theirs to answer.
    """
    rows = await db.scalars(
        select(CommunityMember.user_id).where(
            CommunityMember.community_id == community.id,
            CommunityMember.role.in_((CommunityRole.owner, CommunityRole.admin)),
            CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
        )
    )
    for admin_id in rows:
        notifications.notify(
            db, user_id=admin_id, actor_id=actor.id, kind=kind, title=title,
            body=body, link=f"/communities?open={community.slug}",
        )
