"""Communities, their membership rows and channels.

The columns backend_flow.md section 9 asks for are all here. Two of its names
are spelled differently because the column already existed and holds data:

  * the spec's MEMBER_ONLY visibility is `VisibilityLevel.members` — the same
    enum the posts and profile-field tables already use, so community
    visibility does not introduce a second Postgres type meaning the same thing;
  * the spec's ACTIVE membership state is `MembershipStatus.joined`.

`created_by_id` records who first made the community and never moves.
`owner_id` is the current owner and does move, on ownership transfer. They are
the same person until someone transfers.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import (
    CommunityKind, CommunityRole, CommunityStatus, InviteStatus, JoinPolicy, MembershipStatus,
    TimestampMixin, UUIDMixin, VisibilityLevel, community_kind_enum, community_role_enum,
    community_status_enum, invite_status_enum, join_policy_enum, membership_status_enum,
    visibility_level_enum,
)


class Community(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communities"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    kind: Mapped[CommunityKind] = mapped_column(
        community_kind_enum, nullable=False
    )
    # Free-text grouping from the spec's create payload ("Commercial Real
    # Estate"). `kind` stays the two-way region/industry split the cards filter on.
    category: Mapped[str | None] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(160), default="Global", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[str | None] = mapped_column(Text)
    banner: Mapped[str] = mapped_column(String(4), default="b1", nullable=False)
    initials: Mapped[str] = mapped_column(String(4), default="", nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(500))

    visibility: Mapped[VisibilityLevel] = mapped_column(
        visibility_level_enum, default=VisibilityLevel.public, nullable=False, index=True
    )
    join_policy: Mapped[JoinPolicy] = mapped_column(
        join_policy_enum, default=JoinPolicy.open, nullable=False
    )
    # The lowest role allowed to post. Stored as a role rather than a policy of
    # its own so it compares through ROLE_RANK like every other rank question in
    # the app, and so it needs no second Postgres type. `member` is "everyone",
    # and is the default; `moderator` and `admin` narrow it. The owner outranks
    # all three, so a community can never be locked away from its owner.
    post_min_role: Mapped[CommunityRole] = mapped_column(
        community_role_enum, default=CommunityRole.member, nullable=False
    )
    # The lowest role allowed to invite, stored the same way and for the same
    # reasons as `post_min_role`. `admin` is the default and the historical
    # behaviour; setting it to `member` is what turns a public community into
    # one its own members grow — anyone inside can bring someone in, while
    # joining still requires an invitation.
    invite_min_role: Mapped[CommunityRole] = mapped_column(
        community_role_enum, default=CommunityRole.admin, nullable=False
    )
    status: Mapped[CommunityStatus] = mapped_column(
        community_status_enum, default=CommunityStatus.active, nullable=False, index=True
    )
    member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: When it left draft. Null on a community that has never been published.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Who made it — historical, never reassigned.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Who owns it now. Counted against community.max_owned, so it is indexed.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    memberships: Mapped[list[CommunityMember]] = relationship(
        back_populates="community", cascade="all, delete-orphan"
    )
    channels: Mapped[list[CommunityChannel]] = relationship(
        back_populates="community", cascade="all, delete-orphan", lazy="selectin"
    )
    invites: Mapped[list[CommunityInvite]] = relationship(
        back_populates="community", cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        return self.status is CommunityStatus.active

    @property
    def is_draft(self) -> bool:
        return self.status is CommunityStatus.draft

    @property
    def is_published(self) -> bool:
        """Has it ever gone live? An archived community stays published — it is
        taken down, not returned to draft."""
        return self.published_at is not None


class CommunityMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "community_members"
    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_community_user"),
    )

    community_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[MembershipStatus] = mapped_column(
        membership_status_enum,
        default=MembershipStatus.joined,
        nullable=False,
    )
    role: Mapped[CommunityRole] = mapped_column(
        community_role_enum, default=CommunityRole.member, nullable=False
    )
    # Kept in step with `role` by CommunityMember.apply_role, because the
    # pre-v1 routes and the SPA both still read it.
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Null means "not muted/banned"; a past timestamp means the restriction has
    # lapsed and is treated as lifted (see `is_muted` / `is_banned`).
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    community: Mapped[Community] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821

    def apply_role(self, role: CommunityRole) -> None:
        """Set the role and the legacy `is_admin` flag together.

        Nothing should assign `role` directly — the two would drift, and the
        pre-v1 admin checks read `is_admin`.
        """
        self.role = role
        self.is_admin = role in (CommunityRole.owner, CommunityRole.admin)

    def is_muted(self, now: datetime) -> bool:
        return self.muted_until is not None and self.muted_until > now

    def is_banned(self, now: datetime) -> bool:
        if self.status is not MembershipStatus.banned:
            return False
        # A ban with no expiry is permanent until it is lifted.
        return self.banned_until is None or self.banned_until > now


class CommunityChannel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "community_channels"
    __table_args__ = (UniqueConstraint("community_id", "name", name="uq_channel_name"),)

    community_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    community: Mapped[Community] = relationship(back_populates="channels")


class CommunityInvite(UUIDMixin, TimestampMixin, Base):
    """An offer of membership, which the invitee accepts or declines.

    Deliberately a table of its own rather than a `MembershipStatus.invited`
    row, for three reasons:

      * an invitation can be addressed to an *email* that has no account yet,
        and `community_members.user_id` is NOT NULL;
      * a declined or revoked invitation must survive as history, whereas a
        membership row is reused when someone rejoins;
      * an invitation carries things a membership does not — who sent it, the
        role being offered, an expiry, and a token.

    The direction is what separates this from a join request. An invite travels
    from the community outward and is accepted by the invitee; a join request
    travels inward and is approved by an admin. Both end at the same place, a
    `CommunityMember` row, and both are refused when the community is full.
    """

    __tablename__ = "community_invites"
    __table_args__ = (
        # One live invitation per person per community. Partial, so declining
        # and being re-invited works, and so the history rows do not collide.
        Index(
            "uq_invite_pending_user",
            "community_id", "invited_user_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND invited_user_id IS NOT NULL"),
        ),
        Index(
            "uq_invite_pending_email",
            "community_id", "email",
            unique=True,
            postgresql_where=text("status = 'pending' AND email IS NOT NULL"),
        ),
    )

    community_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    # Exactly one of these two is set. `invited_user_id` when the invitee
    # already has an account, `email` when they do not — the service resolves an
    # email to a user id whenever it can, so the id path is the common one.
    invited_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str | None] = mapped_column(String(320), index=True)

    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    #: The role granted on acceptance. Never `owner` — ownership transfers.
    role: Mapped[CommunityRole] = mapped_column(
        community_role_enum, default=CommunityRole.member, nullable=False
    )
    status: Mapped[InviteStatus] = mapped_column(
        invite_status_enum, default=InviteStatus.pending, nullable=False, index=True
    )
    #: Bearer secret for the accept-by-link path, so an emailed invitee can act
    #: without first being told which invite id is theirs. Unique and indexed
    #: because it is looked up directly.
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    community: Mapped[Community] = relationship(back_populates="invites")
    invited_user: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[invited_user_id], lazy="selectin"
    )
    invited_by: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[invited_by_id], lazy="selectin"
    )

    def has_expired(self, now: datetime) -> bool:
        """Past its expiry. Independent of `status`, which is stamped lazily."""
        return self.expires_at is not None and self.expires_at <= now

    def is_actionable(self, now: datetime) -> bool:
        """Still open to accept or decline."""
        return self.status is InviteStatus.pending and not self.has_expired(now)
