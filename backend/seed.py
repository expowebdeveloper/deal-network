"""Seed the database with the demo content the frontend was designed against.

    python seed.py           # insert if the tables are empty
    python seed.py --reset   # wipe and re-insert

Safe to run repeatedly: without --reset it does nothing when members exist.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal, create_all
from app.models import (
    Community, CommunityChannel, CommunityKind, CommunityMember, Contact, ContactStage,
    FieldVisibility, IntroductionRequest, IntroStatus, InvestorFollow, JoinPolicy, Mandate,
    MemberRole, MembershipStatus, PlanSelection, PlanTier, Post, PostComment, PostLike,
    Subscription, TermsAcceptance, User, VisibilityLevel,
)
from app.models.user import Connection, OAuthIdentity
from app.services import terms as terms_service
from app.services.users import DEFAULT_VISIBILITY

MEMBERS = [
    ("Vikram Sethi", "vikram.sethi@example.com", "VS", "a1", MemberRole.developer,
     "Meridian Developments", "Managing Partner", "Mohali, IN", "Residential & mixed-use", 11, 940, 2),
    ("Sarah Whitfield", "sarah.whitfield@example.com", "SW", "a2", MemberRole.investor,
     "Whitfield Capital", "Principal", "New York, US", "Multifamily", 0, 0, 0),
    ("Priya Nair", "priya.nair@example.com", "PN", "a3", MemberRole.developer,
     "Nair Estates", "Director", "Bangalore, IN", "Residential", 7, 620, 3),
    ("Daniel Ortiz", "daniel.ortiz@example.com", "DO", "a2", MemberRole.investor,
     "Cascade Equity", "Partner", "Bay Area, US", "Mixed-use", 0, 0, 0),
    ("James Fenwick", "james.fenwick@example.com", "JF", "a4", MemberRole.broker,
     "Fenwick Realty", "Broker", "New York, US", "Multifamily", 0, 0, 0),
    ("Anita Rao", "anita.rao@example.com", "AR", "a5", MemberRole.lender,
     "Southbridge Credit", "Head of Origination", "Bangalore, IN", "Construction finance", 0, 0, 0),
    ("Michael Trent", "michael.trent@example.com", "MT", "a6", MemberRole.developer,
     "Coastal Ridge Partners", "Managing Director", "New York, US", "Conversions", 9, 780, 1),
    ("Harpreet Singh", "harpreet.singh@example.com", "HS", "a1", MemberRole.developer,
     "Tricity Build Co", "Founder", "Mohali, IN", "Residential", 5, 340, 2),
    ("Elena Novak", "elena.novak@example.com", "EN", "a4", MemberRole.investor,
     "Ridgeline LP", "Investment Manager", "Bay Area, US", "Workforce housing", 0, 0, 0),
]

COMMUNITIES = [
    ("Bangalore Developers", CommunityKind.region, "Bangalore, IN", "b1", "BD", 342,
     "Residential and mixed-use developers operating across Bangalore and the wider Karnataka corridor.",
     ["Priya Nair", "Anita Rao", "Vikram Sethi"]),
    # Vikram is listed last so the facepile still shows SW/MT/JF (first three joined).
    ("New York Multifamily", CommunityKind.region, "New York, US", "b2", "NY", 1204,
     "Sponsors, brokers and LPs active in the five boroughs and the tri-state multifamily market.",
     ["Sarah Whitfield", "Michael Trent", "James Fenwick", "Vikram Sethi"]),
    ("Mohali & Tricity Builders", CommunityKind.region, "Mohali, IN", "b6", "MT", 187,
     "Builders and land aggregators across Mohali, Chandigarh and Panchkula.",
     ["Vikram Sethi", "Harpreet Singh"]),
    ("Apartment Operators", CommunityKind.industry, "Global", "b4", "AO", 890,
     "Anyone building, owning or operating multifamily and serviced apartment stock.",
     ["Sarah Whitfield", "Vikram Sethi"]),
    ("Medical & Healthcare Property", CommunityKind.industry, "Global", "b5", "MH", 265,
     "Hospitals, clinics, diagnostic centres and senior living — development and acquisition.", []),
    ("Mixed-Use Developers", CommunityKind.industry, "Global", "b3", "MU", 431,
     "Ground-floor retail over residential, live-work schemes and podium developments.",
     ["Michael Trent"]),
    ("Valley Developers", CommunityKind.industry, "Bay Area, US", "b1", "VD", 156,
     "Tech-corridor development — campus, R&D and workforce housing around the Bay Area.",
     ["Daniel Ortiz", "Elena Novak"]),
    ("Industrial & Warehousing", CommunityKind.industry, "Global", "b6", "IW", 298,
     "Logistics parks, cold storage and last-mile distribution assets.", ["Anita Rao"]),
]

CHANNELS = ["# general", "# approvals", "# finance", "# introductions"]

POSTS = [
    ("Priya Nair", "Bangalore Developers",
     "Approvals came through this week on our 120-unit build in Whitefield. Two years from land "
     "acquisition to sanction, which is faster than the last one. Happy to compare notes with anyone "
     "navigating BBMP timelines right now — the pre-submission checklist made most of the difference.",
     None, None, 2),
    ("Sarah Whitfield", "New York Multifamily",
     "Genuine question for the operators here — are you seeing cap rates settle in the outer boroughs, "
     "or is the spread still all over the place? Everything I've underwritten this quarter has come "
     "back 40–60bps apart on comparable assets.",
     None, None, 5),
    ("Michael Trent", None,
     "Wrapped construction on the Bay Street conversion. 64 units, mixed-use ground floor. "
     "Full write-up going out to the investor group this week.",
     "Bay Street Conversion — completion note",
     "64 residential units · 8,400 sq ft retail · Staten Island, NY", 24),
]

CONTACTS = [
    ("Sarah Whitfield", ContactStage.in_discussion, "New York Multifamily", "NY", 2),
    ("Daniel Ortiz", ContactStage.committed, "Introduction", "Bay Area", 5),
    ("Anita Rao", ContactStage.contacted, "Bangalore Developers", "Bangalore", 7),
    ("James Fenwick", ContactStage.new_lead, "Profile view", "NY", 1),
    ("Elena Novak", ContactStage.new_lead, "Apartment Operators", "Bay Area", 4),
    ("Priya Nair", ContactStage.closed, "Bangalore Developers", "Bangalore", 21),
]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def wipe(db) -> None:
    for model in (
        PostComment, PostLike, Post, Contact, IntroductionRequest, InvestorFollow,
        Connection, CommunityMember, CommunityChannel, Community, FieldVisibility,
        Mandate, Subscription, PlanSelection, TermsAcceptance, OAuthIdentity, User,
    ):
        await db.execute(delete(model))
    await db.commit()


async def seed() -> None:
    reset = "--reset" in sys.argv
    await create_all()

    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(func.count(User.id)))
        if existing and not reset:
            print(f"{existing} members already exist — nothing to do. Use --reset to replace.")
            return
        if reset:
            await wipe(db)
            print("Cleared existing data.")

        now = datetime.now(UTC)

        # Members
        users: dict[str, User] = {}
        for (name, email, initials, color, role, company, title,
             location, focus, completed, units, active) in MEMBERS:
            user = User(
                email=email, name=name, initials=initials, avatar_color=color, role=role,
                company=company, title=title, location=location, focus=focus,
                completed_projects=completed, units_delivered=units, active_projects=active,
                profile_views=342 if name == "Vikram Sethi" else 0,
                onboarded=True, last_login_at=now,
            )
            db.add(user)
            users[name] = user
        await db.flush()

        # Demo members are established users, so they start past both gates:
        # terms agreed to, and on a plan. Member rather than early access, because
        # the demo content includes communities they created and a populated
        # pipeline board — both Member features (see services/entitlements.py).
        for user in users.values():
            for field_key, level in DEFAULT_VISIBILITY.items():
                db.add(FieldVisibility(user_id=user.id, field_key=field_key, level=level))
            db.add(Subscription(user_id=user.id, plan=PlanTier.member))
            db.add(terms_service.build_acceptance(user, marketing_opt_in=False))
            db.add(PlanSelection(
                user_id=user.id, user_name=user.name, user_email=user.email,
                user_company=user.company, plan=PlanTier.member,
                plan_name="Member", price_usd=25, billing_period="monthly",
                selected_at=now, is_current=True, source="onboarding",
            ))

        db.add(Mandate(
            user_id=users["Vikram Sethi"].id,
            asset_classes="Residential, Mixed-use", markets="Mohali, Chandigarh",
            typical_raise="₹8–25 Cr", stage="Pre-construction",
            visible_to=VisibilityLevel.members,
        ))
        for name, user in users.items():
            if name != "Vikram Sethi":
                db.add(Mandate(user_id=user.id))

        # Communities
        communities: dict[str, Community] = {}
        for name, kind, location, banner, initials, count, description, members in COMMUNITIES:
            community = Community(
                name=name, slug=slugify(name), kind=kind, location=location, banner=banner,
                initials=initials, member_count=count, description=description,
                join_policy=JoinPolicy.open, created_by_id=users["Vikram Sethi"].id,
            )
            db.add(community)
            communities[name] = community
        await db.flush()

        for community in communities.values():
            for channel in CHANNELS:
                db.add(CommunityChannel(community_id=community.id, name=channel))

        for name, *_rest in COMMUNITIES:
            for member_name in _rest[-1]:
                db.add(CommunityMember(
                    community_id=communities[name].id,
                    user_id=users[member_name].id,
                    status=MembershipStatus.joined,
                    is_admin=member_name == "Vikram Sethi",
                ))

        # Feed
        for author, community_name, body, embed_title, embed_detail, hours in POSTS:
            post = Post(
                author_id=users[author].id,
                community_id=communities[community_name].id if community_name else None,
                body=body, embed_title=embed_title, embed_detail=embed_detail,
                created_at=now - timedelta(hours=hours),
            )
            db.add(post)
        await db.flush()

        # Vikram's contact book
        vikram = users["Vikram Sethi"]
        for name, stage, source, short, days in CONTACTS:
            person = users[name]
            db.add(Contact(
                owner_id=vikram.id, person_id=person.id, name=person.name,
                company=person.company, role=person.role, market=person.location,
                market_short=short, stage=stage, source=source,
                initials=person.initials, avatar_color=person.avatar_color,
                last_touch_at=now - timedelta(days=days),
            ))

        # Introduction requests and follows pointed at Vikram
        db.add(IntroductionRequest(
            from_user_id=users["Sarah Whitfield"].id, to_user_id=vikram.id,
            status=IntroStatus.pending, created_at=now - timedelta(days=2),
            message="Looking at pre-construction residential in the Tricity area.",
        ))
        db.add(IntroductionRequest(
            from_user_id=users["Elena Novak"].id, to_user_id=vikram.id,
            via_community_id=communities["Apartment Operators"].id,
            status=IntroStatus.pending, created_at=now - timedelta(days=4),
        ))
        db.add(IntroductionRequest(
            from_user_id=users["Daniel Ortiz"].id, to_user_id=vikram.id,
            status=IntroStatus.accepted, created_at=now - timedelta(days=7),
            responded_at=now - timedelta(days=6),
        ))

        for investor in ("Sarah Whitfield", "Daniel Ortiz", "Elena Novak"):
            db.add(InvestorFollow(investor_id=users[investor].id, member_id=vikram.id))

        await db.commit()

    print(f"Seeded {len(MEMBERS)} members, {len(COMMUNITIES)} communities, "
          f"{len(POSTS)} posts, {len(CONTACTS)} contacts.")
    print("Demo account: vikram.sethi@example.com")


if __name__ == "__main__":
    asyncio.run(seed())
