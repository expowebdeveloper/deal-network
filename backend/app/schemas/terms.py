"""Terms document and acceptance payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class TermsSection(BaseModel):
    heading: str
    body: str


class TermsDocument(BaseModel):
    """What the consent screen renders, plus where the caller stands on it."""

    version: str
    sections: list[TermsSection]
    accepted: bool = False
    accepted_at: datetime | None = None


class TermsAccept(BaseModel):
    """Both required boxes must be sent as true; the third is a preference.

    `version` is the one the member was shown — it is checked against the version
    in force, so a stale tab cannot record consent to text nobody read.
    """

    version: str
    accept_terms: bool
    accept_unverified: bool
    marketing_opt_in: bool = False


class TermsAcceptanceOut(ORMModel):
    id: uuid.UUID
    version: str
    accepted_terms: bool
    accepted_unverified: bool
    marketing_opt_in: bool
    accepted_at: datetime
