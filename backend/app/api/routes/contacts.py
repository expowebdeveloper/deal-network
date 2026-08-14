"""The private contact book and pipeline board.

Every query here is scoped to the signed-in owner. Contacts are never visible
to another member.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession, require_feature
from app.models import Contact, ContactStage, PlanTier, Subscription, User
from app.schemas.common import Message, Page
from app.schemas.crm import (
    ContactCreate, ContactOut, ContactUpdate, Pipeline, PipelineColumn, StageUpdate,
)
from app.services import entitlements as entitlement_service

router = APIRouter(prefix="/contacts", tags=["contacts"])


async def plan_contact_limit(db: DbSession, user_id) -> int | None:
    """How many contacts this member's plan allows, or None for unlimited."""
    subscription = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    plan = subscription.plan if subscription else PlanTier.early_access
    return entitlement_service.contact_limit(plan)


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (parts[0][:2].upper() if parts else "??")


async def _owned(db: DbSession, contact_id: uuid.UUID, owner_id: uuid.UUID) -> Contact:
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.owner_id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


@router.get("", response_model=Page[ContactOut])
async def list_contacts(
    db: DbSession,
    current_user: CurrentUser,
    stage: ContactStage | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ContactOut]:
    filters = [Contact.owner_id == current_user.id]
    if stage is not None:
        filters.append(Contact.stage == stage)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Contact.name.ilike(pattern), Contact.company.ilike(pattern)))

    total = await db.scalar(select(func.count(Contact.id)).where(*filters)) or 0
    rows = (
        await db.scalars(
            select(Contact)
            .where(*filters)
            .order_by(Contact.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return Page(items=list(rows), total=total, limit=limit, offset=offset)


@router.get(
    "/pipeline", response_model=Pipeline,
    dependencies=[Depends(require_feature("pipeline_board"))],
)
async def read_pipeline(db: DbSession, current_user: CurrentUser) -> Pipeline:
    """Every contact grouped into the five board columns."""
    rows = (
        await db.scalars(
            select(Contact)
            .where(Contact.owner_id == current_user.id)
            .order_by(Contact.updated_at)
        )
    ).all()

    grouped: dict[ContactStage, list[Contact]] = {stage: [] for stage in ContactStage}
    for contact in rows:
        grouped[contact.stage].append(contact)

    return Pipeline(
        columns=[
            PipelineColumn(
                stage=stage,
                count=len(items),
                contacts=[ContactOut.model_validate(c) for c in items],
            )
            for stage, items in grouped.items()
        ]
    )


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate, current_user: CurrentUser, db: DbSession
) -> Contact:
    # "Up to 25 contacts" on early access; the paid tiers are unlimited.
    limit = await plan_contact_limit(db, current_user.id)
    if limit is not None:
        used = await db.scalar(
            select(func.count(Contact.id)).where(Contact.owner_id == current_user.id)
        )
        if (used or 0) >= limit:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="contact_limit_reached",
                headers={
                    "X-Required-Plan": PlanTier.member.value,
                    "X-Contact-Limit": str(limit),
                },
            )

    data = payload.model_dump()
    person_id = data.pop("person_id", None)

    avatar_color = "a1"
    if person_id is not None:
        person = await db.get(User, person_id)
        if person is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Linked member not found")
        avatar_color = person.avatar_color

    contact = Contact(
        owner_id=current_user.id,
        person_id=person_id,
        initials=_initials(payload.name),
        avatar_color=avatar_color,
        last_touch_at=datetime.now(UTC),
        **data,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/{contact_id}", response_model=ContactOut)
async def read_contact(
    contact_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Contact:
    return await _owned(db, contact_id, current_user.id)


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> Contact:
    contact = await _owned(db, contact_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(contact, field, value)
    if "name" in changes and changes["name"]:
        contact.initials = _initials(changes["name"])
    if changes:
        contact.last_touch_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(contact)
    return contact


@router.put("/{contact_id}/stage", response_model=ContactOut)
async def move_stage(
    contact_id: uuid.UUID,
    payload: StageUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> Contact:
    """Backs the drag-and-drop board — one call per card move."""
    contact = await _owned(db, contact_id, current_user.id)
    contact.stage = payload.stage
    contact.last_touch_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.delete("/{contact_id}", response_model=Message)
async def delete_contact(
    contact_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Message:
    contact = await _owned(db, contact_id, current_user.id)
    await db.delete(contact)
    await db.commit()
    return Message(detail="Contact deleted")
