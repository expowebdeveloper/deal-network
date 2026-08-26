"""Writing the audit trail — backend_flow.md sections 21 and 27.

`record` only adds to the session; it never commits. That is deliberate: section
27 wants the audit row to land in the *same* transaction as the change it
describes, so a rolled-back membership change cannot leave behind a log line
claiming it happened.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def record(
    db: AsyncSession,
    action: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    community_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    **meta: Any,
) -> AuditLog:
    """Stage one audit row. The caller's commit is what makes it real."""
    row = AuditLog(
        actor_user_id=actor_user_id,
        community_id=community_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        meta={k: _plain(v) for k, v in meta.items() if v is not None},
    )
    db.add(row)
    return row


def _plain(value: Any) -> Any:
    """UUIDs, enums and datetimes have to be JSON before they reach JSONB."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value") and hasattr(value, "name"):  # an Enum
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


async def for_community(
    db: AsyncSession, community_id: uuid.UUID, *, limit: int = 50, offset: int = 0
) -> list[AuditLog]:
    rows = await db.scalars(
        select(AuditLog)
        .where(AuditLog.community_id == community_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(rows)
