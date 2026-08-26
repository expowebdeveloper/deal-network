"""The bell, and the internal presenter notes behind the icon beside it.

Both are small read-mostly surfaces for the header, so they share a module.

The presenter notes are *not* member-facing: they are notes about the client
engagement. Reading them needs a session — the drawer is already reachable by
any signed-in member and this is not a regression — but writing needs
`User.is_staff`, which is granted in the database and never through an API.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import Notification, PresenterNote, PresenterSection
from app.schemas.common import Message
from app.schemas.notification import (
    NotificationFeed, NotificationOut, PresenterBoard, PresenterNoteCreate,
    PresenterNoteOut, PresenterNoteUpdate,
)
from app.services import notifications as service

router = APIRouter(tags=["notifications"])


# --- Notifications ---------------------------------------------------------

@router.get("/notifications", response_model=NotificationFeed)
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=15, ge=1, le=50),
    unread_only: bool = Query(default=False),
) -> NotificationFeed:
    """Your notifications, newest first, with the unread count for the badge.

    The count is always the true unread total, not the number in `items` — the
    badge must not change just because the list was truncated.
    """
    return NotificationFeed(
        items=[
            NotificationOut.model_validate(row)
            for row in await service.recent(
                db, current_user.id, limit=limit, unread_only=unread_only
            )
        ],
        unread=await service.unread_count(db, current_user.id),
    )


@router.get("/notifications/unread-count", response_model=dict)
async def unread(db: DbSession, current_user: CurrentUser) -> dict:
    """Just the number — cheap enough to poll."""
    return {"unread": await service.unread_count(db, current_user.id)}


@router.post("/notifications/{notification_id}/read", response_model=Message)
async def read_one(
    notification_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> Message:
    # Scoped to the owner in the UPDATE itself, so someone else's id simply
    # matches nothing rather than being readable or writable.
    changed = await service.mark_read(db, current_user.id, notification_id)
    if not changed:
        exists = await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
        if not exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return Message(detail="Marked as read")


@router.post("/notifications/read-all", response_model=Message)
async def read_all(db: DbSession, current_user: CurrentUser) -> Message:
    count = await service.mark_all_read(db, current_user.id)
    return Message(detail=f"Marked {count} as read")


# --- Presenter notes -------------------------------------------------------

def _require_staff(current_user) -> None:
    """Writing internal notes is staff-only.

    404 rather than 403 on purpose: a member who is not staff has no business
    knowing this endpoint accepts writes at all.
    """
    if not getattr(current_user, "is_staff", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


async def _board(db: DbSession, current_user) -> PresenterBoard:
    rows = (await db.scalars(
        select(PresenterNote)
        .where(PresenterNote.is_active.is_(True))
        .order_by(PresenterNote.section, PresenterNote.position, PresenterNote.created_at)
    )).all()

    def group(section: PresenterSection) -> list[PresenterNoteOut]:
        return [PresenterNoteOut.model_validate(r) for r in rows if r.section is section]

    return PresenterBoard(
        decisions=group(PresenterSection.decision),
        changes=group(PresenterSection.change),
        references=group(PresenterSection.reference),
        standing=group(PresenterSection.standing),
        can_edit=bool(getattr(current_user, "is_staff", False)),
    )


@router.get("/presenter", response_model=PresenterBoard)
async def read_presenter(db: DbSession, current_user: CurrentUser) -> PresenterBoard:
    """The drawer's content, grouped by section."""
    return await _board(db, current_user)


@router.post("/presenter", response_model=PresenterNoteOut,
             status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: PresenterNoteCreate, db: DbSession, current_user: CurrentUser
) -> PresenterNote:
    _require_staff(current_user)
    position = payload.position
    if position is None:
        # Append: one past the current highest in this section.
        highest = await db.scalar(
            select(func.max(PresenterNote.position))
            .where(PresenterNote.section == payload.section)
        )
        position = (highest or 0) + 1

    note = PresenterNote(
        section=payload.section, heading=payload.heading,
        detail=payload.detail, extra=payload.extra, position=position,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.patch("/presenter/{note_id}", response_model=PresenterNoteOut)
async def update_note(
    note_id: uuid.UUID, payload: PresenterNoteUpdate, db: DbSession, current_user: CurrentUser
) -> PresenterNote:
    _require_staff(current_user)
    note = await db.get(PresenterNote, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("heading") is None and "heading" in changes:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "heading cannot be cleared"
        )
    for field, value in changes.items():
        setattr(note, field, value)

    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/presenter/{note_id}", response_model=Message)
async def delete_note(
    note_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> Message:
    """Soft delete — `is_active` goes false so a note removed mid-call can be
    put back without retyping it."""
    _require_staff(current_user)
    note = await db.get(PresenterNote, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    note.is_active = False
    await db.commit()
    return Message(detail="Note removed")
