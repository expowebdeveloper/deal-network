"""Shapes for the header search. Compact on purpose — a result row shows a
name, a line of context and an avatar, so anything more is wasted bytes on a
request that fires as the member types."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.base import CommunityKind, ContactStage, MemberRole
from app.schemas.common import ORMModel


class SearchPerson(ORMModel):
    id: uuid.UUID
    name: str
    initials: str
    avatar_color: str
    role: MemberRole | None = None
    company: str | None = None
    location: str | None = None


class SearchCommunity(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    kind: CommunityKind
    location: str
    member_count: int
    initials: str
    banner: str
    joined: bool = False


class SearchContact(ORMModel):
    id: uuid.UUID
    name: str
    initials: str
    avatar_color: str
    company: str | None = None
    stage: ContactStage


class SearchResults(BaseModel):
    query: str
    people: list[SearchPerson]
    communities: list[SearchCommunity]
    contacts: list[SearchContact]
    total: int
