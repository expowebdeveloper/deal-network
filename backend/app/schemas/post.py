"""Feed post schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.base import VisibilityLevel
from app.schemas.common import ORMModel
from app.schemas.media import MediaRef
from app.schemas.user import UserSummary


class PostCommunity(ORMModel):
    id: uuid.UUID
    name: str
    slug: str


class PostOut(ORMModel):
    id: uuid.UUID
    body: str
    embed_title: str | None = None
    embed_detail: str | None = None
    visibility: VisibilityLevel
    created_at: datetime
    author: UserSummary
    community: PostCommunity | None = None

    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    attachments: list[MediaRef] = Field(default_factory=list)


class PostCreate(BaseModel):
    # May be empty when the post is just files — validated below.
    body: str = Field(default="", max_length=10000)
    community_id: uuid.UUID | None = None
    embed_title: str | None = Field(default=None, max_length=200)
    embed_detail: str | None = Field(default=None, max_length=400)
    visibility: VisibilityLevel = VisibilityLevel.members
    # Ids returned by POST /api/media, in display order.
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _needs_content(self):
        """A post has to say something or carry something."""
        self.body = self.body.strip()
        if not self.body and not self.attachment_ids:
            raise ValueError("Write something or attach a file")
        return self


class CommentOut(ORMModel):
    id: uuid.UUID
    body: str
    created_at: datetime
    author: UserSummary


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class LikeState(BaseModel):
    liked: bool
    like_count: int
