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


class StorageUsageOut(BaseModel):
    """Storage used against the plan's allowance — backend_flow.md section 19.

    Two per-file numbers, because they can differ: `plan_max_file_bytes` is what
    the tier grants, `max_file_bytes` is what this deployment will actually
    accept. `capped_by_deployment` is true when the second is the binding one,
    so the UI can show the real figure rather than a promise it cannot keep.
    """

    used_bytes: int
    # None means unlimited.
    storage_limit_bytes: int | None = None
    remaining_bytes: int | None = None
    max_file_bytes: int | None = None
    plan_max_file_bytes: int | None = None
    capped_by_deployment: bool = False
    percent_used: float | None = None

    used_display: str
    storage_limit_display: str
    max_file_display: str
