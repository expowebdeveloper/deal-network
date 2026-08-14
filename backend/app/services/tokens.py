"""Token revocation — the storage half of signing out.

See models/token.py for why a denylist is needed at all.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RevokedToken


def _expiry(claims: dict[str, Any]) -> datetime | None:
    exp = claims.get("exp")
    if exp is None:
        return None
    return datetime.fromtimestamp(int(exp), UTC)


async def revoke(
    db: AsyncSession, claims: dict[str, Any], token_type: str, user_id: uuid.UUID
) -> bool:
    """Deny-list one decoded token. Returns False if it carries nothing to store.

    Idempotent: signing out twice with the same token is not an error, so a
    second insert of the same `jti` is dropped rather than raised.
    """
    jti = claims.get("jti")
    expires_at = _expiry(claims)
    if not jti or expires_at is None:
        return False

    await db.execute(
        insert(RevokedToken)
        .values(
            jti=str(jti),
            user_id=user_id,
            token_type=token_type,
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(index_elements=["jti"])
    )
    return True


async def is_revoked(db: AsyncSession, claims: dict[str, Any]) -> bool:
    """True when this token has been signed out.

    Tokens minted before this feature existed have no `jti`; they are treated as
    live so an in-flight session is not broken by the deploy.
    """
    jti = claims.get("jti")
    if not jti:
        return False
    found = await db.scalar(select(RevokedToken.id).where(RevokedToken.jti == str(jti)))
    return found is not None


async def purge_expired(db: AsyncSession) -> int:
    """Drop rows for tokens that have expired — they can no longer be replayed."""
    result = await db.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC))
    )
    return result.rowcount or 0
