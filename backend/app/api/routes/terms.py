"""The terms members agree to between signing in and choosing a plan.

`GET /api/terms` is open: the sign-in screen links to the same text before there
is anyone to attach an acceptance to.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.models import TermsAcceptance
from app.schemas.terms import TermsAccept, TermsAcceptanceOut, TermsDocument, TermsSection
from app.services import terms as terms_service

router = APIRouter(prefix="/terms", tags=["terms"])


@router.get("", response_model=TermsDocument)
async def read_terms(db: DbSession, current_user: OptionalUser) -> TermsDocument:
    """The text in force, and whether the caller has already agreed to it."""
    latest = (
        await terms_service.latest_acceptance(db, current_user.id) if current_user else None
    )
    return TermsDocument(
        version=terms_service.TERMS_VERSION,
        sections=[TermsSection(**section) for section in terms_service.TERMS_SECTIONS],
        accepted=latest is not None,
        accepted_at=latest.accepted_at if latest else None,
    )


@router.post("/accept", response_model=TermsAcceptanceOut, status_code=status.HTTP_201_CREATED)
async def accept_terms(
    payload: TermsAccept, current_user: CurrentUser, db: DbSession
) -> TermsAcceptance:
    """Agree to the terms. This is what opens the plan step.

    Appends a row to `terms_acceptances`; accepting again (a re-tick, or a new
    version) appends another rather than overwriting the first.
    """
    if payload.version != terms_service.TERMS_VERSION:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "terms_version_changed",
        )
    if not payload.accept_terms or not payload.accept_unverified:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Both required terms must be accepted",
        )

    acceptance = terms_service.build_acceptance(current_user, payload.marketing_opt_in)
    db.add(acceptance)
    await db.commit()
    await db.refresh(acceptance)
    return acceptance


@router.get("/acceptance", response_model=TermsAcceptanceOut | None)
async def read_acceptance(current_user: CurrentUser, db: DbSession) -> TermsAcceptance | None:
    """The member's acceptance of the current version, or null."""
    return await terms_service.latest_acceptance(db, current_user.id)
