"""Per-plan file size and storage quota — backend_flow.md section 19.

    Early Access   25 MB per file,   1 GB stored
    Member        250 MB per file,  10 GB stored
    Professional    2 GB per file, 100 GB stored

Both numbers come from the entitlement service, so they are configurable in the
plan tables rather than compiled in ("recommended storage allowance, configurable
server-side").

Two checks, in this order, and the order matters:

  1. **Declared size, before a byte is read.** `Content-Length` is a claim, not a
     fact, but refusing an oversized upload on the claim saves reading gigabytes
     only to reject them. It cannot be the only check, because the header can lie.
  2. **Actual size, as the file is written.** `services/storage.py` counts bytes
     as it streams and aborts past the ceiling. That one is authoritative.

The storage quota is checked against what is already stored plus the incoming
file, and re-checked after the write for the same reason.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.config import settings
from app.models import MediaAsset
from app.services import entitlements as ent
from app.services.entitlements import Limit

MB = 1024 * 1024
GB = 1024 * MB


def human(size: int | None) -> str:
    """Byte counts as something an error message can say out loud."""
    if size is None:
        return "unlimited"
    if size >= GB:
        value = size / GB
        return f"{value:.0f}GB" if value == int(value) else f"{value:.1f}GB"
    if size >= MB:
        value = size / MB
        return f"{value:.0f}MB" if value == int(value) else f"{value:.1f}MB"
    return f"{size}B"


def deployment_ceiling() -> int:
    """The largest single upload this deployment will accept, whatever the plan.

    Two ceilings exist and they answer different questions:

        plan       — what the member has paid for   (250MB on Member, 2GB on Pro)
        deployment — what this server can carry     (the largest MAX_*_BYTES)

    They are not interchangeable. Uploads currently stream to local disk through
    this process; backend_flow.md section 19 wants object storage with
    presigned uploads, and until that exists the deployment number is the real
    constraint. The effective ceiling is the smaller of the two, and
    `plan_exceeds_deployment` reports when that is capping a paying member so it
    shows up at startup instead of as a confusing 422.

    This is the widest gate; `storage._limit_for` then applies the ceiling for
    the specific kind, so a 30MB video allowance never lifts the image limit.
    """
    return max(
        settings.max_image_bytes,
        settings.max_video_bytes,
        settings.max_document_bytes,
    )


def plan_exceeds_deployment() -> tuple[bool, int, int]:
    """(is_capped, largest configured plan ceiling, deployment ceiling)."""
    largest = max(
        (ent.LIMIT_MATRIX[tier].get(Limit.FILES_MAX_FILE_SIZE_BYTES) or 0)
        for tier in ent.PLAN_ORDER
    )
    ceiling = deployment_ceiling()
    return largest > ceiling, largest, ceiling


async def plan_file_bytes(db: AsyncSession, user_id: uuid.UUID) -> int | None:
    """What the member's *plan* allows per file, ignoring infrastructure."""
    return await ent.get_limit(db, user_id, Limit.FILES_MAX_FILE_SIZE_BYTES)


async def max_file_bytes(db: AsyncSession, user_id: uuid.UUID) -> int | None:
    """What this member may actually upload — the smaller of the two ceilings."""
    allowed = await plan_file_bytes(db, user_id)
    ceiling = deployment_ceiling()
    if allowed is None:
        return ceiling
    return min(allowed, ceiling)


async def max_storage_bytes(db: AsyncSession, user_id: uuid.UUID) -> int | None:
    """Total allowance. No infrastructure ceiling applies — it is disk, not RAM."""
    return await ent.get_limit(db, user_id, Limit.FILES_MAX_STORAGE_BYTES)


async def storage_used(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Total bytes this member currently has stored."""
    return int(await db.scalar(
        select(func.coalesce(func.sum(MediaAsset.size_bytes), 0))
        .where(MediaAsset.owner_id == user_id)
    ) or 0)


async def usage(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """What the member has used, what their plan allows, and what actually applies.

    Both per-file numbers are reported: `plan_max_file_bytes` is what the tier
    grants, `max_file_bytes` is what this deployment will really take. When they
    differ, the UI can show the real one rather than promising a size that would
    be refused.
    """
    used = await storage_used(db, user_id)
    allowance = await max_storage_bytes(db, user_id)
    plan_per_file = await plan_file_bytes(db, user_id)
    effective_per_file = await max_file_bytes(db, user_id)
    return {
        "used_bytes": used,
        "storage_limit_bytes": allowance,
        "remaining_bytes": None if allowance is None else max(0, allowance - used),
        "max_file_bytes": effective_per_file,
        "plan_max_file_bytes": plan_per_file,
        "capped_by_deployment": (
            plan_per_file is not None and effective_per_file < plan_per_file
        ),
        "used_display": human(used),
        "storage_limit_display": human(allowance),
        "max_file_display": human(effective_per_file),
        "percent_used": (
            None if allowance in (None, 0) else round(min(100.0, used * 100 / allowance), 1)
        ),
    }


def _with_display(decision, **extra) -> dict:
    """A decision's details, plus the human-readable sizes this module adds."""
    details = {
        k: v for k, v in decision.body().items() if k not in ("allowed", "reason")
    }
    details.update(extra)
    return details


async def check_file_size(
    db: AsyncSession, user_id: uuid.UUID, size_bytes: int
) -> None:
    """Refuse a file larger than the plan's per-file ceiling.

    The plan's figure comes from the entitlement flow, which is also where any
    storage add-on is folded in. The *deployment* ceiling is a separate
    question — infrastructure, not entitlement — so it is compared here and
    reported as `deployment_limit` rather than being pushed into the plan
    tables, where it would look like something an upgrade could lift.
    """
    decision = await ent.decide(
        db, user_id, "dataroom.file.size", amount=size_bytes
    )
    if decision.blocked:
        raise errors.forbidden(
            decision.reason,
            f"That file is {human(size_bytes)}. Your plan allows up to "
            f"{human(decision.limit)} per file.",
            **_with_display(
                decision,
                limit_display=human(decision.limit),
                requested_display=human(size_bytes),
            ),
        )

    hard_ceiling = deployment_ceiling()
    if size_bytes > hard_ceiling:
        raise errors.forbidden(
            errors.Code.FILE_SIZE_LIMIT_EXCEEDED,
            f"That file is {human(size_bytes)}. This deployment accepts up to "
            f"{human(hard_ceiling)} per file.",
            limit=hard_ceiling,
            limit_display=human(hard_ceiling),
            requested=size_bytes,
            deployment_limit=hard_ceiling,
            current_plan=(await ent.effective_plan(db, user_id)).value,
            upgrade_plan=None,
            upgrade_available=False,
            addon_available=False,
        )


async def check_quota(
    db: AsyncSession, user_id: uuid.UUID, incoming_bytes: int
) -> None:
    """Refuse an upload that would take the member past their storage allowance."""
    decision = await ent.decide(
        db, user_id, "dataroom.file.upload", amount=incoming_bytes
    )
    if decision.blocked:
        used = decision.current_usage or 0
        raise errors.forbidden(
            decision.reason,
            f"That upload would use {human(used + incoming_bytes)} of your "
            f"{human(decision.limit)} storage allowance.",
            **_with_display(
                decision,
                used=used,
                limit_display=human(decision.limit),
                used_display=human(used),
            ),
        )


async def check_upload(
    db: AsyncSession, user_id: uuid.UUID, declared_bytes: int | None
) -> int | None:
    """Both pre-flight checks, against the size the client declares.

    Returns the effective per-file ceiling so the caller can hand it to
    `storage.save_upload`, which enforces it against the bytes actually read —
    the check that cannot be lied to.
    """
    await ent.require_feature_key(db, user_id, ent.Feature.FILES_UPLOAD)
    ceiling = await max_file_bytes(db, user_id)
    if declared_bytes:
        await check_file_size(db, user_id, declared_bytes)
        await check_quota(db, user_id, declared_bytes)
    return ceiling
