"""Raising and reading in-app notifications.

`notify` never raises into the caller. A notification is a side effect of
something the member actually did — accepting a connection, approving a join
request — and failing to write one must not roll back the thing itself. The
worst outcome of a bug here should be a missing bell entry, not a lost approval.

It also never notifies you about your own action: liking your own post, or
approving a request you made, would produce a notification nobody wants.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, NotificationKind

logger = logging.getLogger(__name__)

#: Read-endpoint ceiling. The bell shows a short list, not an archive.
MAX_PAGE = 50


def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str | None = None,
    link: str | None = None,
    actor_id: uuid.UUID | None = None,
    **meta,
) -> Notification | None:
    """Stage one notification. The caller's commit is what makes it real.

    Staged rather than committed so it lands in the same transaction as the
    change it describes — a rolled-back approval must not leave a notification
    claiming it happened.

    Returns None when the recipient is the actor, which is not an error.
    """
    if actor_id is not None and actor_id == user_id:
        return None
    try:
        row = Notification(
            user_id=user_id,
            kind=kind,
            actor_id=actor_id,
            title=title[:200],
            body=body,
            link=link,
            meta={k: str(v) for k, v in meta.items() if v is not None},
        )
        db.add(row)
        return row
    except Exception:
        # Never let a notification break the action that triggered it.
        logger.exception("Could not stage a %s notification for %s", kind, user_id)
        return None


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
    ) or 0)


async def recent(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int = 15, unread_only: bool = False
) -> list[Notification]:
    statement = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    rows = await db.scalars(
        statement.order_by(Notification.created_at.desc()).limit(min(limit, MAX_PAGE))
    )
    return list(rows)


async def mark_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> bool:
    """Mark one as read. Scoped to the owner, so an id alone is not enough."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    return bool(result.rowcount)


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    return result.rowcount or 0
