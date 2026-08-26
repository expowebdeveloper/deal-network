"""One search across people, communities and your contacts.

The search box in the header is the only place in the product that looks in more
than one table, so it gets its own endpoint rather than making the SPA fire three
requests and stitch the answers together.

Three rules decide what comes back, and they are not the same rule:

  * **People** — the member directory. Anyone may find anyone; the network is
    deliberately not partitioned by market. You are excluded, as you are from
    /api/members, because a result you cannot act on is only noise.
  * **Communities** — only what you are allowed to see. Public ones are open to
    everyone; private and member-only ones appear only if you belong to them, so
    search cannot be used to discover that a private community exists.
  * **Contacts** — yours alone. A contact book is private to its owner, and this
    is the one group here that is never shared.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession
from app.models import ACTIVE_MEMBER_STATUSES, Community, CommunityMember, Contact, User
from app.schemas.search import (
    SearchCommunity, SearchContact, SearchPerson, SearchResults,
)
from app.services import communities as community_service

router = APIRouter(prefix="/search", tags=["search"])

#: Below this, a query matches so much that the results are meaningless — and it
#: stops a single keystroke scanning every table.
MIN_QUERY = 2


@router.get("", response_model=SearchResults)
async def search(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(default="", description="What to look for"),
    limit: int = Query(default=5, ge=1, le=20, description="Results per group"),
) -> SearchResults:
    """Search people, communities and your own contacts in one call."""
    term = (q or "").strip()
    if len(term) < MIN_QUERY:
        return SearchResults(query=term, people=[], communities=[], contacts=[], total=0)

    # `ilike` needs the wildcards escaped, or a query containing % or _ turns
    # into a pattern that matches far more than the member typed.
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"

    people = (await db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.id != current_user.id,
            or_(
                User.name.ilike(pattern, escape="\\"),
                User.company.ilike(pattern, escape="\\"),
                User.location.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(User.name)
        .limit(limit)
    )).all()

    # Reuses the visibility rule from the v1 service, so a private community
    # cannot surface here that would be hidden on the Communities page.
    visible = await community_service.visible_communities_query(current_user.id)
    communities = (await db.scalars(
        visible
        .where(or_(
            Community.name.ilike(pattern, escape="\\"),
            Community.description.ilike(pattern, escape="\\"),
            Community.location.ilike(pattern, escape="\\"),
        ))
        .order_by(Community.member_count.desc(), Community.name)
        .limit(limit)
    )).all()

    contacts = (await db.scalars(
        select(Contact)
        .where(
            Contact.owner_id == current_user.id,
            or_(
                Contact.name.ilike(pattern, escape="\\"),
                Contact.company.ilike(pattern, escape="\\"),
                Contact.email.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(Contact.name)
        .limit(limit)
    )).all()

    joined = set()
    if communities:
        joined = {
            row for row in (await db.scalars(
                select(CommunityMember.community_id).where(
                    CommunityMember.user_id == current_user.id,
                    CommunityMember.community_id.in_([c.id for c in communities]),
                    CommunityMember.status.in_(ACTIVE_MEMBER_STATUSES),
                )
            )).all()
        }

    return SearchResults(
        query=term,
        people=[SearchPerson.model_validate(p) for p in people],
        communities=[
            SearchCommunity(
                **SearchCommunity.model_validate(c).model_dump(exclude={"joined"}),
                joined=c.id in joined,
            )
            for c in communities
        ],
        contacts=[SearchContact.model_validate(c) for c in contacts],
        total=len(people) + len(communities) + len(contacts),
    )
