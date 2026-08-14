"""Profile setup — the two steps a member walks after choosing a plan.

One row per member, updated as they go, so a half-finished setup can be resumed
rather than restarted. This is working state, not an audit trail, which is why it
is not append-only like `plan_selections` or `terms_acceptances`.

What the member enters is copied onto their `User` (and mandate) when they finish,
because that is what the rest of the app reads; the row keeps the answers that
have nowhere else to live, such as team size.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import MemberRole, TimestampMixin, UUIDMixin, member_role_enum


class MemberOnboarding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "member_onboarding"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, index=True,
    )

    # Step 1 — what describes you best.
    role: Mapped[MemberRole | None] = mapped_column(member_role_enum)
    role_chosen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Step 2 — company details.
    company: Mapped[str | None] = mapped_column(String(160))
    primary_market: Mapped[str | None] = mapped_column(String(160))
    team_size: Mapped[str | None] = mapped_column(String(40))
    # Comma-joined, mirroring User.focus and Mandate.asset_classes.
    asset_classes: Mapped[str | None] = mapped_column(String(255))
    short_description: Mapped[str | None] = mapped_column(Text)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
