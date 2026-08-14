"""End-to-end smoke test against a running server.

    python seed.py --reset
    uvicorn app.main:app --port 8000 &
    python smoke_test.py

Signs in as the seeded demo member by minting a token directly, which is what
the Google callback does once GOOGLE_CLIENT_ID/SECRET are filled in.
"""

from __future__ import annotations

import asyncio
import sys

import httpx
from sqlalchemy import delete, or_, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, create_refresh_token
from app.models import (
    Connection, IntroductionRequest, PlanTier, Subscription, User,
)

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label} {detail}")


async def token_for_demo_user() -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "vikram.sethi@example.com"))
        if user is None:
            print("Demo user missing — run: python seed.py --reset")
            sys.exit(1)
        return create_access_token(user.id, user.email), str(user.id)


async def clear_connections(user_id: str) -> None:
    """Connection requests cannot be withdrawn over HTTP, so reset them directly.

    Without this the suite only passes once per seed.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(Connection).where(
                or_(Connection.requester_id == user_id, Connection.addressee_id == user_id)
            )
        )
        await db.commit()


async def auth_header_for(email: str) -> dict:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        return {"Authorization": f"Bearer {create_access_token(user.id, user.email)}"}


async def clear_introductions(user_id: str) -> None:
    """Introduction requests cannot be withdrawn over HTTP — reset them directly."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(IntroductionRequest).where(
                or_(
                    IntroductionRequest.from_user_id == user_id,
                    IntroductionRequest.to_user_id == user_id,
                )
            )
        )
        await db.commit()


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


async def main() -> None:
    # The communities, pipeline and introduction flows below are Member features.
    for email in ("vikram.sethi@example.com", "sarah.whitfield@example.com",
                  "michael.trent@example.com"):
        await ensure_paid_plan(email)

    token, user_id = await token_for_demo_user()
    auth = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, timeout=20, follow_redirects=False) as c:
        print("\nMeta")
        r = await c.get("/health")
        check("GET /health", r.status_code == 200, r.text[:120])
        r = await c.get("/auth/providers")
        check("GET /auth/providers", r.status_code == 200, r.text[:120])

        print("\nAuth")
        r = await c.get("/api/me")
        check("GET /api/me without token -> 401", r.status_code == 401, str(r.status_code))
        r = await c.get("/api/me", headers={"Authorization": "Bearer nonsense"})
        check("GET /api/me with bad token -> 401", r.status_code == 401, str(r.status_code))
        r = await c.get("/api/me", headers=auth)
        check("GET /api/me", r.status_code == 200 and r.json()["email"] == "vikram.sethi@example.com",
              r.text[:160])
        r = await c.get("/auth/session", headers=auth)
        check("GET /auth/session returns an access token",
              r.status_code == 200 and "access_token" in r.json(), r.text[:120])
        check("GET /auth/session does NOT mint a refresh token",
              "refresh_token" not in r.json(), r.text[:160])
        refresh = create_refresh_token(user_id)
        r = await c.post("/auth/refresh", json={"refresh_token": refresh})
        check("POST /auth/refresh", r.status_code == 200 and "access_token" in r.json(),
              r.text[:120])
        r = await c.get("/health")
        google_on = r.json()["oauth_providers"] == ["google"]
        r = await c.get("/auth/google/login", follow_redirects=False)
        check(
            "GET /auth/google/login redirects when configured, 503 when not",
            r.status_code == (307 if google_on else 503),
            f"configured={google_on} status={r.status_code}",
        )

        print("\nProfile")
        r = await c.patch("/api/me", headers=auth, json={"focus": "Residential & mixed-use"})
        check("PATCH /api/me", r.status_code == 200, r.text[:120])
        r = await c.get("/api/me/stats", headers=auth)
        check("GET /api/me/stats", r.status_code == 200, r.text[:120])
        r = await c.get("/api/me/visibility", headers=auth)
        check("GET /api/me/visibility has 8 fields",
              r.status_code == 200 and len(r.json()) == 8, r.text[:160])
        r = await c.put("/api/me/visibility", headers=auth,
                        json={"field_key": "raise", "level": "Private"})
        check("PUT /api/me/visibility", r.status_code == 200 and r.json()["level"] == "Private",
              r.text[:120])
        r = await c.put("/api/me/visibility", headers=auth,
                        json={"field_key": "bogus", "level": "Public"})
        check("PUT /api/me/visibility rejects unknown field", r.status_code == 422,
              str(r.status_code))
        r = await c.get("/api/me/mandate", headers=auth)
        check("GET /api/me/mandate", r.status_code == 200, r.text[:120])
        r = await c.put("/api/me/mandate", headers=auth, json={"stage": "Pre-construction"})
        check("PUT /api/me/mandate", r.status_code == 200, r.text[:120])

        print("\nMembers")
        r = await c.get("/api/members", headers=auth)
        body = r.json()
        check("GET /api/members excludes self",
              r.status_code == 200 and body["total"] >= 8
              and all(m["id"] != user_id for m in body["items"]), r.text[:160])
        r = await c.get("/api/members?role=Investor", headers=auth)
        check("GET /api/members?role=Investor -> at least the 3 seeded",
              r.status_code == 200 and r.json()["total"] >= 3, r.text[:160])
        r = await c.get("/api/members?q=whitfield", headers=auth)
        check("GET /api/members?q= search",
              r.status_code == 200 and r.json()["total"] == 1, r.text[:160])
        other_id = r.json()["items"][0]["id"]
        r = await c.get(f"/api/members/{other_id}", headers=auth)
        check("GET /api/members/{id}", r.status_code == 200, r.text[:120])

        print("\nConnections")
        await clear_connections(user_id)
        r = await c.post("/api/connections", headers=auth,
                         json={"addressee_id": other_id, "note": "Comparing notes on cap rates."})
        check("POST /api/connections", r.status_code == 201, r.text[:160])
        r = await c.post("/api/connections", headers=auth, json={"addressee_id": other_id})
        check("POST /api/connections duplicate -> 409", r.status_code == 409, str(r.status_code))
        r = await c.post("/api/connections", headers=auth, json={"addressee_id": user_id})
        check("POST /api/connections to self -> 422", r.status_code == 422, str(r.status_code))
        r = await c.get("/api/connections", headers=auth)
        check("GET /api/connections", r.status_code == 200 and len(r.json()) == 1, r.text[:120])

        print("\nCommunities")
        r = await c.get("/api/communities", headers=auth)
        check("GET /api/communities -> at least the 8 seeded",
              r.status_code == 200 and r.json()["total"] >= 8, r.text[:160])
        first = r.json()["items"][0]
        check("community has faces + joined flag",
              "faces" in first and "joined" in first, str(first)[:160])
        r = await c.get("/api/communities?kind=region", headers=auth)
        check("GET /api/communities?kind=region -> at least 3",
              r.status_code == 200 and r.json()["total"] >= 3, r.text[:160])
        r = await c.get("/api/communities?joined=true", headers=auth)
        check("GET /api/communities?joined=true -> at least 4",
              r.status_code == 200 and r.json()["total"] >= 4, r.text[:160])
        r = await c.get("/api/communities/valley-developers", headers=auth)
        check("GET /api/communities/{slug} has channels",
              r.status_code == 200 and len(r.json()["channels"]) == 4, r.text[:160])
        r = await c.post("/api/communities/valley-developers/join", headers=auth)
        check("POST join community", r.status_code == 201, r.text[:160])
        r = await c.post("/api/communities/valley-developers/join", headers=auth)
        check("POST join twice -> 409", r.status_code == 409, str(r.status_code))
        r = await c.delete("/api/communities/valley-developers/leave", headers=auth)
        check("DELETE leave community", r.status_code == 200, r.text[:160])
        r = await c.post("/api/communities", headers=auth,
                         json={"name": "Pune Residential Developers", "kind": "region",
                               "location": "Pune, IN", "description": "Test",
                               "join_policy": "open"})
        check("POST /api/communities", r.status_code == 201 and r.json()["joined"] is True,
              r.text[:160])
        new_slug = r.json().get("slug", "")
        r = await c.post("/api/communities", headers=auth,
                         json={"name": "Pune Residential Developers", "kind": "region"})
        check("duplicate name gets a suffixed slug rather than failing",
              r.status_code == 201 and r.json()["slug"].startswith(new_slug),
              r.text[:160])
        dup_slug = r.json().get("slug", "")

        print("\nFeed")
        r = await c.get("/api/posts", headers=auth)
        check("GET /api/posts -> at least the 3 seeded",
              r.status_code == 200 and r.json()["total"] >= 3, r.text[:160])
        r = await c.post("/api/posts", headers=auth,
                         json={"body": "Testing the feed endpoint.", "visibility": "Members"})
        check("POST /api/posts", r.status_code == 201, r.text[:160])
        post_id = r.json()["id"]
        r = await c.post(f"/api/posts/{post_id}/like", headers=auth)
        check("POST like -> liked",
              r.status_code == 200 and r.json() == {"liked": True, "like_count": 1}, r.text[:120])
        r = await c.post(f"/api/posts/{post_id}/like", headers=auth)
        check("POST like again -> unliked",
              r.status_code == 200 and r.json() == {"liked": False, "like_count": 0}, r.text[:120])
        r = await c.post(f"/api/posts/{post_id}/comments", headers=auth, json={"body": "Nice."})
        check("POST comment", r.status_code == 201, r.text[:160])
        r = await c.get(f"/api/posts/{post_id}/comments", headers=auth)
        check("GET comments -> 1", r.status_code == 200 and len(r.json()) == 1, r.text[:120])
        r = await c.get(f"/api/posts/{post_id}", headers=auth)
        check("GET post has counts",
              r.status_code == 200 and r.json()["comment_count"] == 1, r.text[:160])
        r = await c.post("/api/posts", headers=auth,
                         json={"body": "Should fail", "community_id": first["id"]}) \
            if not first["joined"] else None
        if r is not None:
            check("POST to un-joined community -> 403", r.status_code == 403, str(r.status_code))
        r = await c.delete(f"/api/posts/{post_id}", headers=auth)
        check("DELETE post", r.status_code == 200, r.text[:120])

        print("\nContacts")
        r = await c.get("/api/contacts", headers=auth)
        contacts_before = r.json()["total"]
        check("GET /api/contacts -> at least the 6 seeded",
              r.status_code == 200 and contacts_before >= 6, r.text[:160])
        r = await c.get("/api/contacts/pipeline", headers=auth)
        columns = r.json().get("columns", []) if r.status_code == 200 else []
        check("GET /api/contacts/pipeline has 5 columns", len(columns) == 5, r.text[:160])
        check("pipeline counts total 6", sum(col["count"] for col in columns) == 6,
              str([col["count"] for col in columns]))
        r = await c.post("/api/contacts", headers=auth,
                         json={"name": "Test Person", "company": "Test Co", "role": "Broker",
                               "market": "Delhi, IN", "stage": "New lead"})
        check("POST /api/contacts", r.status_code == 201 and r.json()["initials"] == "TP",
              r.text[:160])
        contact_id = r.json()["id"]
        r = await c.put(f"/api/contacts/{contact_id}/stage", headers=auth,
                        json={"stage": "Committed"})
        check("PUT stage (board move)",
              r.status_code == 200 and r.json()["stage"] == "Committed", r.text[:160])
        r = await c.patch(f"/api/contacts/{contact_id}", headers=auth,
                          json={"notes": "Met at the Delhi expo."})
        check("PATCH contact", r.status_code == 200, r.text[:120])
        r = await c.get("/api/contacts?stage=Committed", headers=auth)
        check("GET contacts?stage= filters", r.status_code == 200 and r.json()["total"] >= 2,
              r.text[:160])
        r = await c.delete(f"/api/contacts/{contact_id}", headers=auth)
        check("DELETE contact", r.status_code == 200, r.text[:120])

        print("\nInvestors")
        # Build the fixtures this section needs, so it does not depend on how a
        # previous run left the seeded introduction requests.
        await clear_introductions(user_id)
        sarah_auth = await auth_header_for("sarah.whitfield@example.com")
        michael_auth = await auth_header_for("michael.trent@example.com")

        r = await c.post("/api/investors/introductions", headers=sarah_auth,
                         json={"to_user_id": user_id, "message": "Pre-construction residential."})
        check("introduction request created", r.status_code == 201, r.text[:160])
        sarah_intro_id = r.json()["id"]

        r = await c.get("/api/investors/overview", headers=auth)
        body = r.json() if r.status_code == 200 else {}
        check("GET /api/investors/overview",
              r.status_code == 200 and body.get("investors_following") == 3, r.text[:200])
        check("overview counts the pending request", body.get("awaiting_reply") == 1, str(body))
        r = await c.get("/api/investors/introductions", headers=auth)
        intros = r.json() if r.status_code == 200 else []
        check("GET introductions -> 1", r.status_code == 200 and len(intros) == 1, r.text[:160])

        # Sarah is already in the contact book, so accepting must not duplicate her.
        r = await c.post(f"/api/investors/introductions/{sarah_intro_id}/respond",
                         headers=auth, json={"accept": True})
        check("POST respond accept", r.status_code == 200 and r.json()["status"] == "accepted",
              r.text[:160])
        r = await c.get("/api/contacts", headers=auth)
        check("accepting an existing contact does not duplicate",
              r.json()["total"] == contacts_before, r.text[:120])
        r = await c.post(f"/api/investors/introductions/{sarah_intro_id}/respond",
                         headers=auth, json={"accept": True})
        check("POST respond twice -> 409", r.status_code == 409, str(r.status_code))

        # Michael is not in the contact book, so accepting his request must add him.
        r = await c.post("/api/investors/introductions", headers=michael_auth,
                         json={"to_user_id": user_id, "message": "Comparing conversion timelines."})
        check("POST introduction from another member", r.status_code == 201, r.text[:160])
        new_intro_id = r.json().get("id")
        r = await c.post("/api/investors/introductions", headers=michael_auth,
                         json={"to_user_id": user_id})
        check("POST duplicate introduction -> 409", r.status_code == 409, str(r.status_code))
        r = await c.post(f"/api/investors/introductions/{new_intro_id}/respond",
                         headers=michael_auth, json={"accept": True})
        check("only the recipient can respond -> 403", r.status_code == 403, str(r.status_code))
        r = await c.post(f"/api/investors/introductions/{new_intro_id}/respond",
                         headers=auth, json={"accept": True})
        check("POST respond accept (new person)", r.status_code == 200, r.text[:160])
        r = await c.get("/api/contacts", headers=auth)
        check("accepting a new person creates a contact",
              r.json()["total"] == contacts_before + 1, r.text[:120])
        # Drop it again so the next run starts from the same contact count.
        michael_contact = next(
            (x for x in r.json()["items"] if x["name"] == "Michael Trent"), None)
        if michael_contact:
            await c.delete(f"/api/contacts/{michael_contact['id']}", headers=auth)
        r = await c.post(f"/api/investors/follow/{other_id}", headers=auth)
        check("POST follow member", r.status_code in (200, 201), r.text[:120])
        r = await c.delete(f"/api/investors/follow/{other_id}", headers=auth)
        check("DELETE unfollow", r.status_code == 200, r.text[:120])

        print("\nPlans")
        r = await c.get("/api/plans", headers=auth)
        plans = r.json() if r.status_code == 200 else []
        check("GET /api/plans -> 3", r.status_code == 200 and len(plans) == 3, r.text[:160])
        r2 = await c.get("/api/plans/subscription", headers=auth)
        check("exactly one plan is marked current, and it is the subscribed one",
              sum(1 for p in plans if p["is_current"]) == 1
              and next(p["id"] for p in plans if p["is_current"]) == r2.json()["plan"],
              f"{[p['id'] for p in plans if p['is_current']]} vs {r2.json().get('plan')}")
        r = await c.post("/api/plans/subscribe", headers=auth,
                         json={"plan": "member", "card_number": "4242 4242 4242 4242",
                               "card_name": "Vikram Sethi", "expiry": "12/29", "cvc": "123",
                               "billing_country": "India"})
        check("POST subscribe stores last4 only",
              r.status_code == 200 and r.json()["card_last4"] == "4242", r.text[:200])
        r = await c.get("/api/plans/subscription", headers=auth)
        check("GET subscription -> member",
              r.status_code == 200 and r.json()["plan"] == "member", r.text[:160])
        r = await c.post("/api/plans/subscribe", headers=auth,
                         json={"plan": "member", "card_number": "123", "card_name": "X",
                               "expiry": "12/29", "cvc": "123", "billing_country": "India"})
        check("POST subscribe rejects short card", r.status_code == 422, str(r.status_code))
        r = await c.post("/api/plans/cancel", headers=auth)
        check("POST cancel", r.status_code == 200, r.text[:120])

        print("\nOwnership isolation")
        async with AsyncSessionLocal() as db:
            other = await db.scalar(
                select(User).where(User.email == "sarah.whitfield@example.com")
            )
            other_token = create_access_token(other.id, other.email)
        r = await c.get("/api/contacts", headers={"Authorization": f"Bearer {other_token}"})
        check("another member sees none of Vikram's contacts",
              r.status_code == 200 and r.json()["total"] == 0, r.text[:160])

        # tidy up the community this run created
        for s in filter(None, (new_slug, dup_slug)):
            await c.delete(f"/api/communities/{s}", headers=auth)

    # Cancelling above dropped the member back to early access. Put them back on
    # the tier the demo data assumes, so suite order does not matter.
    await ensure_paid_plan("vikram.sethi@example.com")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
