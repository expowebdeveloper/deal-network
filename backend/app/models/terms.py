"""Record of a member accepting the terms.

Append-only, like `plan_selections`: every acceptance is kept, so there is a
record of who agreed to which version and when. The member's name and email are
snapshotted onto the row so the record still reads correctly if they later change
their profile.

A member has accepted "the terms" when they have a row for the current version —
publishing a new version therefore asks everyone again.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class TermsAcceptance(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "terms_acceptances"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Snapshot of who agreed, as they were at the time of agreeing.
    user_name: Mapped[str] = mapped_column(String(160), nullable=False)
    user_email: Mapped[str] = mapped_column(String(320), nullable=False)

    version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # The two required consents are stored separately rather than as one flag:
    # they are distinct statements, and the record should show both were given.
    accepted_terms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepted_unverified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # The optional one. Not consent to the terms — a marketing preference.
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
