"""Focused test for the communities API, including admin and moderation paths.

    uvicorn app.main:app --port 8000 &
    python seed.py --reset      # only needed once
    python communities_test.py

Re-runnable: every community it creates carries a unique run token and is deleted
in a finally block, and all counts are asserted relative to a baseline taken at
start — so it does not care about other data in the database.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models import (
    Community, CommunityChannel, CommunityMember, PlanTier, Subscription, User,
)

BASE = "http://127.0.0.1:8000"
RUN = uuid.uuid4().hex[:6]
passed, failed = 0, 0
created_slugs: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


async def auth_for(email: str) -> tuple[dict, str]:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"missing seed user {email} — run: python seed.py --reset")
            sys.exit(1)
        return {"Authorization": f"Bearer {create_access_token(user.id, user.email)}"}, str(user.id)


async def ensure_paid_plan(email: str) -> None:
    """Communities, the pipeline board and introductions are Member features now
    (see services/entitlements.py). State that prerequisite instead of relying on
    whatever plan the database happens to hold."""
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        subscription = await db.scalar(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        if subscription is None:
            db.add(Subscription(user_id=user.id, plan=PlanTier.member))
        else:
            subscription.plan = PlanTier.member
        await db.commit()


async def run(c: httpx.AsyncClient, owner, owner_id, other, other_id, third, third_id) -> None:
    print("\nBrowse")
    r = await c.get("/api/communities", headers=owner)
    baseline = r.json()["total"]
    check("GET /api/communities", r.status_code == 200 and baseline >= 8, r.text[:120])
    first = r.json()["items"][0]
    check("card carries joined + faces + member_count",
          {"joined", "faces", "member_count"} <= set(first), str(first)[:140])

    r = await c.get("/api/communities?kind=region", headers=owner)
    regions_before = r.json()["total"]
    check("filter kind=region works", r.status_code == 200 and regions_before >= 3, r.text[:120])
    r = await c.get("/api/communities?joined=true", headers=owner)
    joined_before = r.json()["total"]
    check("filter joined=true works", r.status_code == 200 and joined_before >= 4, r.text[:120])
    r = await c.get("/api/communities?q=bangalore", headers=owner)
    check("search q=bangalore -> 1", r.json()["total"] == 1, r.text[:120])

    print("\nCreate")
    name = f"Pune Residential {RUN}"
    r = await c.post("/api/communities", headers=owner, json={
        "name": name, "kind": "region", "location": "Pune, IN",
        "description": "Testing", "banner": "b3", "join_policy": "open",
        "channels": ["# general", "# general", "# deals"],
    })
    check("POST /api/communities -> 201", r.status_code == 201, r.text[:160])
    created = r.json()
    slug = created["slug"]
    created_slugs.append(slug)
    check("creator is joined and counted",
          created["joined"] is True and created["member_count"] == 1, str(created)[:160])
    check("duplicate channel names are collapsed",
          sorted(created["channels"]) == ["# deals", "# general"], str(created["channels"]))

    r = await c.post("/api/communities", headers=owner, json={"name": name, "kind": "region"})
    check("duplicate name gets a suffixed slug, not a 409",
          r.status_code == 201 and r.json()["slug"] == f"{slug}-2", r.text[:160])
    created_slugs.append(r.json()["slug"])

    r = await c.get("/api/communities", headers=owner)
    check("new communities show up in the list",
          r.json()["total"] == baseline + 2, f"{r.json()['total']} vs {baseline + 2}")

    # The response above is what the API *said*; this is what actually landed in
    # Postgres. Creating a community writes three tables, so check all three.
    print("\nCreate — what reached the database")
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(Community).where(Community.slug == slug))
        channels = (await db.scalars(
            select(CommunityChannel).where(CommunityChannel.community_id == row.id)
        )).all() if row else []
        members = (await db.scalars(
            select(CommunityMember).where(CommunityMember.community_id == row.id)
        )).all() if row else []

    check("the community row is committed", row is not None, "no row for " + slug)
    check("every field from the form is stored",
          row.name == name and row.kind.value == "region" and row.location == "Pune, IN"
          and row.description == "Testing" and row.banner == "b3"
          and row.join_policy.value == "open",
          str((row.name, row.kind, row.location, row.description, row.banner, row.join_policy)))
    check("initials are derived for the card", row.initials == "PR", row.initials)
    check("the row records who created it", str(row.created_by_id) == owner_id, str(row.created_by_id))
    check("the stored member count agrees with the response", row.member_count == 1,
          str(row.member_count))
    check("its channel rows are committed too",
          sorted(ch.name for ch in channels) == ["# deals", "# general"],
          str([ch.name for ch in channels]))
    check("the creator is committed as a joined admin",
          len(members) == 1 and str(members[0].user_id) == owner_id
          and members[0].is_admin and members[0].status.value == "joined",
          str([(str(m.user_id), m.is_admin, m.status) for m in members]))

    print("\nAdmin edit")
    r = await c.patch(f"/api/communities/{slug}", headers=owner,
                      json={"description": "Updated copy", "banner": "b5"})
    check("PATCH by admin", r.status_code == 200 and r.json()["banner"] == "b5", r.text[:160])
    r = await c.patch(f"/api/communities/{slug}", headers=other, json={"description": "nope"})
    check("PATCH by non-member -> 403", r.status_code == 403, str(r.status_code))
    r = await c.patch(f"/api/communities/{slug}", headers=owner, json={"name": None})
    check("PATCH with an explicit null -> 422, not a 500",
          r.status_code == 422, f"{r.status_code} {r.text[:120]}")
    r = await c.patch(f"/api/communities/{slug}", headers=owner, json={"description": None})
    check("PATCH clearing the nullable description is allowed",
          r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    r = await c.delete(f"/api/communities/{slug}", headers=other)
    check("DELETE by non-member -> 403", r.status_code == 403, str(r.status_code))

    print("\nJoin / leave")
    r = await c.post(f"/api/communities/{slug}/join", headers=other)
    check("join open community -> joined",
          r.status_code == 201 and r.json()["status"] == "joined", r.text[:160])
    check("member_count incremented", r.json()["community"]["member_count"] == 2, r.text[:160])
    r = await c.post(f"/api/communities/{slug}/join", headers=other)
    check("join twice -> 409", r.status_code == 409, str(r.status_code))
    r = await c.delete(f"/api/communities/{slug}/leave", headers=other)
    check("leave -> 200", r.status_code == 200, r.text[:120])
    r = await c.delete(f"/api/communities/{slug}/leave", headers=other)
    check("leave when not a member -> 404", r.status_code == 404, str(r.status_code))
    r = await c.get(f"/api/communities/{slug}/members", headers=third)
    check("non-member cannot read the roster -> 403", r.status_code == 403, str(r.status_code))
    r = await c.delete(f"/api/communities/{slug}/leave", headers=owner)
    check("last admin cannot leave -> 409", r.status_code == 409, r.text[:160])

    print("\nRequest-to-join moderation")
    r = await c.post("/api/communities", headers=owner, json={
        "name": f"Gated Group {RUN}", "kind": "region", "location": "Delhi, IN",
        "join_policy": "request"})
    gated = r.json()["slug"]
    created_slugs.append(gated)

    r = await c.post(f"/api/communities/{gated}/join", headers=other)
    check("join request community -> pending",
          r.status_code == 201 and r.json()["status"] == "pending", r.text[:160])
    check("pending does not raise member_count",
          r.json()["community"]["member_count"] == 1, r.text[:160])
    r = await c.get(f"/api/communities/{gated}/requests", headers=owner)
    check("admin sees 1 pending request", r.status_code == 200 and len(r.json()) == 1, r.text[:160])
    r = await c.get(f"/api/communities/{gated}/requests", headers=other)
    check("non-admin cannot list requests -> 403", r.status_code == 403, str(r.status_code))
    r = await c.get(f"/api/communities/{gated}/members", headers=owner)
    check("pending member is not in the members list", r.json()["total"] == 1, r.text[:160])
    r = await c.get(f"/api/communities/{gated}/members", headers=other)
    check("pending member cannot read the roster -> 403", r.status_code == 403, str(r.status_code))
    r = await c.get("/api/communities", headers=other)
    entry = next(x for x in r.json()["items"] if x["slug"] == gated)
    check("card reports pending, not joined",
          entry["pending"] is True and entry["joined"] is False, str(entry)[:160])

    r = await c.post(f"/api/communities/{gated}/requests/{other_id}/approve", headers=owner)
    check("approve -> joined", r.status_code == 200 and r.json()["status"] == "joined", r.text[:160])
    r = await c.get(f"/api/communities/{gated}/members", headers=owner)
    check("approved member now listed", r.json()["total"] == 2, r.text[:160])
    r = await c.post(f"/api/communities/{gated}/requests/{other_id}/approve", headers=owner)
    check("approving twice -> 404", r.status_code == 404, str(r.status_code))

    r = await c.post(f"/api/communities/{gated}/join", headers=third)
    check("third member requests", r.status_code == 201, r.text[:120])
    r = await c.post(f"/api/communities/{gated}/requests/{third_id}/decline", headers=owner)
    check("decline -> 200", r.status_code == 200, r.text[:120])
    r = await c.get(f"/api/communities/{gated}/requests", headers=owner)
    check("no pending requests left", len(r.json()) == 0, r.text[:120])

    print("\nInvite-only")
    r = await c.post("/api/communities", headers=owner, json={
        "name": f"Private Syndicate {RUN}", "kind": "industry", "join_policy": "invite"})
    invite = r.json()["slug"]
    created_slugs.append(invite)
    r = await c.post(f"/api/communities/{invite}/join", headers=other)
    check("cannot join invite-only -> 403", r.status_code == 403, str(r.status_code))

    print("\nChannels")
    r = await c.post(f"/api/communities/{slug}/channels", headers=owner, json={"name": "# finance"})
    check("admin adds a channel", r.status_code == 201, r.text[:160])
    channel_id = r.json()["id"]
    r = await c.post(f"/api/communities/{slug}/channels", headers=owner, json={"name": "# FINANCE"})
    check("duplicate channel (case-insensitive) -> 409", r.status_code == 409, str(r.status_code))
    r = await c.post(f"/api/communities/{slug}/channels", headers=other, json={"name": "# x"})
    check("non-admin cannot add a channel -> 403", r.status_code == 403, str(r.status_code))
    r = await c.get(f"/api/communities/{slug}/channels", headers=owner)
    check("channels listed", r.status_code == 200 and len(r.json()) == 3, r.text[:160])
    r = await c.delete(f"/api/communities/{slug}/channels/{channel_id}", headers=owner)
    check("admin deletes a channel", r.status_code == 200, r.text[:120])

    print("\nPosting into a community")
    r = await c.post("/api/posts", headers=third,
                     json={"body": "Should be blocked", "community_id": created["id"]})
    check("non-member cannot post -> 403", r.status_code == 403, str(r.status_code))
    r = await c.post("/api/posts", headers=owner,
                     json={"body": "First post", "community_id": created["id"]})
    check("member can post", r.status_code == 201, r.text[:160])
    r = await c.get(f"/api/posts?community_id={created['id']}", headers=owner)
    check("community feed returns it", r.json()["total"] == 1, r.text[:160])

    print("\nPrivate community posts stay private")
    # Regression: the feed used to return any community's posts to any signed-in
    # member, including invite-only ones.
    r = await c.post("/api/posts", headers=owner,
                     json={"body": f"CONFIDENTIAL {RUN}", "community_id": created["id"],
                           "visibility": "Private"})
    check("owner posts into their community", r.status_code == 201, r.text[:160])
    secret_id = r.json()["id"]

    r = await c.get(f"/api/posts?community_id={created['id']}", headers=third)
    check("non-member cannot read the community feed -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:120]}")
    r = await c.get(f"/api/posts/{secret_id}", headers=third)
    check("non-member cannot read the post directly -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:120]}")
    r = await c.get(f"/api/posts/{secret_id}/comments", headers=third)
    check("non-member cannot read its comments -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:120]}")
    r = await c.post(f"/api/posts/{secret_id}/like", headers=third)
    check("non-member cannot like it -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:120]}")
    r = await c.post(f"/api/posts/{secret_id}/comments", headers=third, json={"body": "hi"})
    check("non-member cannot comment on it -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:120]}")

    r = await c.get("/api/posts", headers=third)
    bodies = [p["body"] for p in r.json()["items"]]
    check("global feed excludes communities you have not joined",
          all(f"CONFIDENTIAL {RUN}" not in b for b in bodies), str(bodies)[:200])

    r = await c.get(f"/api/posts?community_id={created['id']}", headers=owner)
    check("a member still sees their own community feed",
          r.status_code == 200 and r.json()["total"] >= 1, r.text[:160])

    print("\nNot found")
    r = await c.get("/api/communities/does-not-exist", headers=owner)
    check("unknown slug -> 404", r.status_code == 404, str(r.status_code))

    return baseline


async def main() -> None:
    for email in ("vikram.sethi@example.com", "sarah.whitfield@example.com",
                  "harpreet.singh@example.com"):
        await ensure_paid_plan(email)

    owner, owner_id = await auth_for("vikram.sethi@example.com")
    other, other_id = await auth_for("sarah.whitfield@example.com")
    third, third_id = await auth_for("harpreet.singh@example.com")

    baseline = None
    async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
        try:
            baseline = await run(c, owner, owner_id, other, other_id, third, third_id)
        finally:
            # Always tidy up, even when an assertion above failed.
            for slug in created_slugs:
                await c.delete(f"/api/communities/{slug}", headers=owner)

        if baseline is not None:
            r = await c.get("/api/communities", headers=owner)
            check("cleanup restored the original count",
                  r.json()["total"] == baseline, f"{r.json()['total']} vs {baseline}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
