"""Media schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field

from app.models.base import MediaKind
from app.schemas.common import ORMModel


class MediaOut(ORMModel):
    id: uuid.UUID
    kind: MediaKind
    original_name: str
    stored_name: str
    content_type: str
    size_bytes: int
    created_at: datetime

    @computed_field
    @property
    def url(self) -> str:
        """Path the frontend can fetch; the API mounts /media as static files."""
        return f"/media/{self.stored_name}"


class MediaRef(BaseModel):
    """Compact form embedded in a post."""

    id: uuid.UUID
    kind: MediaKind
    url: str
    original_name: str
    content_type: str
    size_bytes: int
