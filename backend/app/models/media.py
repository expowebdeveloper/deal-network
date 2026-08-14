"""Uploaded files and their attachment to posts.

Files live on disk under `settings.upload_dir` with a random stored name; the
database keeps the metadata. The original filename is only ever echoed back for
display — it never touches the filesystem path.
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import MediaKind, TimestampMixin, UUIDMixin, media_kind_enum


class MediaAsset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "media_assets"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[MediaKind] = mapped_column(media_kind_enum, nullable=False)

    # What the member called it — display only.
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # What it is called on disk — random, extension-checked, never user-supplied.
    stored_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    owner: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821


class PostAttachment(UUIDMixin, TimestampMixin, Base):
    """Join row so one post can carry several files and keep their order."""

    __tablename__ = "post_attachments"
    __table_args__ = (UniqueConstraint("post_id", "media_id", name="uq_post_media"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    media: Mapped[MediaAsset] = relationship(lazy="selectin")
