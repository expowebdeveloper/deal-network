"""Upload and manage files.

    POST   /api/media          multipart form field `file`
    GET    /api/media          your own uploads
    DELETE /api/media/{id}     owner only

Files are served as static content from /media/{stored_name}.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import MediaAsset, MediaKind, PostAttachment
from app.schemas.common import Message, Page
from app.schemas.media import MediaOut
from app.services import storage

router = APIRouter(prefix="/media", tags=["media"])


@router.post("", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="Photo or document to attach to a post"),
) -> MediaAsset:
    try:
        stored = await storage.save_upload(file)
    except storage.UploadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    asset = MediaAsset(
        owner_id=current_user.id,
        kind=stored.kind,
        original_name=stored.original_name,
        stored_name=stored.stored_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
    )
    db.add(asset)
    try:
        await db.commit()
    except Exception:
        # Never leave an orphan file behind if the row could not be written.
        storage.delete_stored(stored.stored_name)
        raise
    await db.refresh(asset)
    return asset


@router.get("", response_model=Page[MediaOut])
async def list_mine(
    current_user: CurrentUser,
    db: DbSession,
    kind: MediaKind | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[MediaOut]:
    filters = [MediaAsset.owner_id == current_user.id]
    if kind is not None:
        filters.append(MediaAsset.kind == kind)

    total = await db.scalar(select(func.count(MediaAsset.id)).where(*filters)) or 0
    rows = (
        await db.scalars(
            select(MediaAsset)
            .where(*filters)
            .order_by(MediaAsset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return Page(items=list(rows), total=total, limit=limit, offset=offset)


@router.delete("/{media_id}", response_model=Message)
async def delete_media(
    media_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    asset = await db.get(MediaAsset, media_id)
    if asset is None or asset.owner_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    attached = await db.scalar(
        select(func.count(PostAttachment.id)).where(PostAttachment.media_id == asset.id)
    )
    if attached:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This file is attached to a post — delete the post first",
        )

    stored_name = asset.stored_name
    await db.delete(asset)
    await db.commit()
    storage.delete_stored(stored_name)
    return Message(detail="File deleted")
