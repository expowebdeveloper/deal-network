"""Feed posts, likes and comments."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import (
    TimestampMixin, UUIDMixin, VisibilityLevel, visibility_level_enum,
)


class Post(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "posts"

    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("communities.id", ondelete="SET NULL"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional "project update" card attached to a post.
    embed_title: Mapped[str | None] = mapped_column(String(200))
    embed_detail: Mapped[str | None] = mapped_column(String(400))

    visibility: Mapped[VisibilityLevel] = mapped_column(
        visibility_level_enum,
        default=VisibilityLevel.members,
        nullable=False,
    )

    author: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
    community: Mapped["Community | None"] = relationship(lazy="selectin")  # noqa: F821
    likes: Mapped[list[PostLike]] = relationship(
        back_populates="post", cascade="all, delete-orphan", lazy="selectin"
    )
    comments: Mapped[list[PostComment]] = relationship(
        back_populates="post", cascade="all, delete-orphan", lazy="selectin"
    )
    attachments: Mapped[list["PostAttachment"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan", lazy="selectin",
        order_by="PostAttachment.position",
    )


class PostLike(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_like"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    post: Mapped[Post] = relationship(back_populates="likes")


class PostComment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "post_comments"

    post_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    post: Mapped[Post] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
