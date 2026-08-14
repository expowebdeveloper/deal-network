"""Revoked JWTs — the denylist that makes signing out mean something.

Access and refresh tokens are self-contained, so nothing on the server stops a
copy of one being replayed until it expires. Signing out writes the token's `jti`
here; `get_current_user` and `/auth/refresh` refuse anything listed.

Rows are only useful until the token they name would have expired anyway, so
`expires_at` is kept and old rows are purged on each sign-out.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class RevokedToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "revoked_tokens"

    # The `jti` claim minted in core/security.py — unique per issued token.
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # "access" or "refresh" — kept for support questions, not used for lookups.
    token_type: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
