"""In-app notifications, and the internal presenter notes.

Two unrelated tables share this module only because both are small and both back
a single button in the header.

`Notification` is deliberately denormalised: `title` and `body` are rendered
when the event happens and stored as text, rather than being rebuilt from ids at
read time. A notification is a record of what was true *then* — "Sarah asked to
join Bangalore Developers" should keep reading that way even if she later leaves,
or the community is renamed. The ids are kept alongside so the row can still
link somewhere, and the link degrades to nothing if the target is gone.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class NotificationKind(str, enum.Enum):
    connection_request = "connection_request"
    connection_accepted = "connection_accepted"
    community_join_request = "community_join_request"
    community_join_approved = "community_join_approved"
    community_member_added = "community_member_added"
    community_role_changed = "community_role_changed"
    community_invite = "community_invite"
    community_invite_accepted = "community_invite_accepted"
    community_invite_declined = "community_invite_declined"
    introduction_request = "introduction_request"
    introduction_answered = "introduction_answered"
    post_comment = "post_comment"
    post_like = "post_like"
    plan_changed = "plan_changed"
    system = "system"


notification_kind_enum = SAEnum(NotificationKind, name="notification_kind")


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # The list query is always "mine, newest first", and the badge is
        # "mine, unread". One composite index serves both.
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )

    #: Who sees it.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[NotificationKind] = mapped_column(notification_kind_enum, nullable=False)

    #: Who caused it. Null for anything the system raised on its own.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)

    #: Where clicking it goes — a relative SPA path, resolved when the row was
    #: written. Null means the notification is not actionable.
    link: Mapped[str | None] = mapped_column(String(300))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    actor: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[actor_id], lazy="selectin"
    )

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class PresenterSection(str, enum.Enum):
    """The four blocks the presenter drawer renders, in display order."""

    decision = "decision"
    change = "change"
    reference = "reference"
    standing = "standing"


presenter_section_enum = SAEnum(PresenterSection, name="presenter_section")


class PresenterNote(UUIDMixin, TimestampMixin, Base):
    """One row of the internal presenter panel.

    The four sections hold different shapes — a decision has a question, a
    proposal and a risk; a change has item/was/now — so the fields live in three
    generic text columns rather than a column per section. `section` decides how
    they are labelled and rendered.

    Not member-facing. Reading needs a session; writing needs `User.is_staff`.
    """

    __tablename__ = "presenter_notes"

    section: Mapped[PresenterSection] = mapped_column(
        presenter_section_enum, nullable=False, index=True
    )
    #: Sort order within a section. Gaps are fine and expected after deletes.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Generic slots. What they mean per section:
    #   decision   heading=question   detail=what was built   extra=the risk
    #   change     heading=item       detail=was              extra=now
    #   reference  heading=product    detail=what to show     extra=unused
    #   standing   heading=the note   detail/extra unused
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
