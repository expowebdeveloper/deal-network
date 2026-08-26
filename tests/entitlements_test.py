"""What each plan unlocks, and what the API refuses without it.

    uvicorn app.main:app --port 8000 &
    python entitlements_test.py

Re-runnable: it works on its own throwaway member, created and deleted here, and
moves that member between plans as it goes. No seed data is touched.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models import Contact, OAuthProvider, PlanSelection, PlanTier, Subscription, User
from app.services.oauth import OAuthProfile
from app.services.terms import build_acceptance
from app.services.users import resolve_user

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0

# Which build phases each tier should reach. Free stops at phase 1, Member runs
# to phase 4, Professional opens all seven.
EXPECTED = {
    "early_access": [1],
    "member": [1, 2, 3, 4],
    "professional": [1, 2, 3, 4, 5, 6, 7],
}


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


async def make_member(marker: str) -> tuple:
    async with AsyncSessionLocal() as db:
        user, _ = await resolve_user(db, OAuthProfile(
            provider=OAuthProvider.google, subject=f"google-{marker}",
            email=f"tiers.{marker}@example.com", email_verified=True, name="Tessa Tiers",
        ))
        await db.flush()
        db.add(build_acceptance(user, marketing_opt_in=False))
        db.add(PlanSelection(
            user_id=user.id, user_name=user.name, user_email=user.email,
            user_company=None, plan=PlanTier.early_access, plan_name="Early access",
            price_usd=0, billing_period="none", is_current=True, source="onboarding",
        ))
        await db.commit()
        await db.refresh(user)
        return user.id, user.email


async def set_plan(user_id, plan: PlanTier) -> None:
    async with AsyncSessionLocal() as db:
        subscription = await db.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription.plan = plan
        await db.commit()


async def fill_contacts(user_id, count: int) -> None:
    """Put the member right up against the free tier's ceiling."""
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Contact).where(Contact.owner_id == user_id))
        for i in range(count):
            db.add(Contact(owner_id=user_id, name=f"Filler {i}", initials="FL"))
        await db.commit()


async def check_phase_guard(user_id) -> None:
    """`require_phase` guards routes a phase has not shipped yet, so there is no
    endpoint to call. Exercise the dependency itself instead."""
    from fastapi import HTTPException

    from app.api.deps import require_phase
    from app.models import User

    async def ask(plan: PlanTier, phase: int):
        """-> (allowed, headers). Headers are what the 403 would carry."""
        await set_plan(user_id, plan)
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            try:
                await require_phase(phase)(db, user)
                return True, {}
            except HTTPException as exc:
                return False, exc.headers or {}

    allowed, _ = await ask(PlanTier.early_access, 1)
    check("free passes the phase 1 guard", allowed is True, str(allowed))

    allowed, headers = await ask(PlanTier.early_access, 2)
    check("free is refused at phase 2", allowed is False, str(allowed))
    check("  and is told Member unlocks it",
          headers.get("X-Required-Plan") == "member", str(headers))
    check("  and which phase it was", headers.get("X-Required-Phase") == "2", str(headers))

    allowed, headers = await ask(PlanTier.early_access, 5)
    check("free is refused at phase 5, pointed at Professional",
          allowed is False and headers.get("X-Required-Plan") == "professional", str(headers))

    for phase in (1, 2, 3, 4):
        allowed, _ = await ask(PlanTier.member, phase)
        check(f"member passes the phase {phase} guard", allowed is True, str(allowed))

    allowed, headers = await ask(PlanTier.member, 5)
    check("member is refused at phase 5", allowed is False, str(allowed))
    check("  and is told Professional unlocks it",
          headers.get("X-Required-Plan") == "professional", str(headers))

    for phase in (1, 4, 5, 6, 7):
        allowed, _ = await ask(PlanTier.professional, phase)
        check(f"professional passes the phase {phase} guard", allowed is True, str(allowed))


async def main() -> None:
    run = uuid.uuid4().hex[:8]
    user_id, email = await make_member(run)
    auth = {"Authorization": f"Bearer {create_access_token(user_id, email)}"}

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
            print("\nWhat each plan reaches")
            for tier, expected in EXPECTED.items():
                r = await c.get(f"/api/plans/{tier}/entitlements", headers=auth)
                body = r.json()
                included = [p["n"] for p in body["phases"] if p["included"]]
                label = ", ".join(f"phase {n}" for n in expected)
                check(f"{tier}: {label}",
                      r.status_code == 200 and included == expected,
                      f"{r.status_code} {included}")
                check(f"{tier}: all seven phases are listed, open or not",
                      [p["n"] for p in body["phases"]] == [1, 2, 3, 4, 5, 6, 7],
                      str([p["n"] for p in body["phases"]]))

            r = await c.get("/api/plans/early_access/entitlements", headers=auth)
            body = r.json()
            check("free stops at phase 1", body["max_phase"] == 1, str(body["max_phase"]))
            check("free is not pro", body["pro"] is False, str(body["pro"]))
            check("free caps contacts at 25", body["contact_limit"] == 25, str(body["contact_limit"]))
            check("free has no team seats", body["team_seats"] == 0, str(body["team_seats"]))
            check("phase 1 carries its name from card.txt",
                  next(p for p in body["phases"] if p["n"] == 1)["name"] == "Basic Platform",
                  str(body["phases"][0]))
            locked = {p["n"]: p["unlocked_by"] for p in body["phases"] if not p["included"]}
            check("it says which plan unlocks each locked phase",
                  locked == {2: "member", 3: "member", 4: "member",
                             5: "professional", 6: "professional", 7: "professional"},
                  str(locked))

            r = await c.get("/api/plans/member/entitlements", headers=auth)
            body = r.json()
            check("member reaches phase 4", body["max_phase"] == 4, str(body["max_phase"]))
            check("member is unlimited on contacts",
                  body["contact_limit"] is None, str(body["contact_limit"]))
            check("member carries its four ticks",
                  all(body["features"][f] for f in
                      ["unlimited_contacts", "pipeline_board", "create_communities",
                       "introduction_requests"]), str(body["features"]))
            check("but not team seats", body["features"]["team_seats"] is False,
                  str(body["features"]["team_seats"]))
            check("phases 5 to 7 stay locked",
                  [p["n"] for p in body["phases"] if not p["included"]] == [5, 6, 7],
                  str([p["n"] for p in body["phases"] if not p["included"]]))
            check("and Professional is what opens them",
                  all(p["unlocked_by"] == "professional"
                      for p in body["phases"] if not p["included"]), "")

            r = await c.get("/api/plans/professional/entitlements", headers=auth)
            body = r.json()
            check("professional reaches the last phase", body["max_phase"] == 7, str(body["max_phase"]))
            check("professional is pro", body["pro"] is True, str(body["pro"]))
            check("professional includes 5 seats", body["team_seats"] == 5, str(body["team_seats"]))
            check("nothing is locked on professional",
                  all(p["included"] for p in body["phases"]), str(body["phases"])[:160])
            check("and every card tick",
                  all(body["features"].values()), str(body["features"]))

            r = await c.get("/api/plans/nonsense/entitlements", headers=auth)
            check("an unknown plan -> 422", r.status_code == 422, str(r.status_code))

            print("\nOn the free plan")
            r = await c.get("/api/plans/entitlements", headers=auth)
            body = r.json()
            check("/api/plans/entitlements reports my own plan",
                  r.status_code == 200 and body["plan"] == "early_access", r.text[:120])
            check("and how much of the contact limit is used",
                  body["contacts_used"] == 0 and body["contact_limit"] == 25, str(body)[:160])

            r = await c.get("/api/contacts/pipeline", headers=auth)
            check("the pipeline board is refused -> 403 upgrade_required",
                  r.status_code == 403 and r.json().get("detail") == "upgrade_required",
                  f"{r.status_code} {r.text[:90]}")
            check("it names the plan that unlocks it",
                  r.headers.get("x-required-plan") == "member", str(r.headers.get("x-required-plan")))
            check("and the feature that was missing",
                  r.headers.get("x-required-feature") == "pipeline_board",
                  str(r.headers.get("x-required-feature")))

            r = await c.post("/api/communities", headers=auth,
                             json={"name": f"Blocked {run}", "kind": "region"})
            check("creating a community is refused -> 403",
                  r.status_code == 403 and r.json().get("detail") == "upgrade_required",
                  f"{r.status_code} {r.text[:90]}")

            r = await c.post("/api/investors/introductions", headers=auth,
                             json={"investor_id": str(user_id), "note": "hello"})
            check("an introduction request is refused -> 403",
                  r.status_code == 403 and r.json().get("detail") == "upgrade_required",
                  f"{r.status_code} {r.text[:90]}")

            print("   what the free plan can still do")
            for path in ["/api/communities", "/api/contacts", "/api/posts", "/api/members",
                         "/api/investors/overview", "/api/plans"]:
                r = await c.get(path, headers=auth)
                check(f"still open: {path}", r.status_code == 200, f"{r.status_code} {r.text[:70]}")

            print("\nThe 25-contact ceiling")
            r = await c.post("/api/contacts", headers=auth, json={"name": "First Contact"})
            check("a contact can be added under the limit", r.status_code == 201,
                  f"{r.status_code} {r.text[:90]}")

            await fill_contacts(user_id, 25)
            r = await c.get("/api/plans/entitlements", headers=auth)
            check("the count reflects what is stored",
                  r.json()["contacts_used"] == 25, str(r.json()["contacts_used"]))

            r = await c.post("/api/contacts", headers=auth, json={"name": "Twenty Sixth"})
            check("the 26th is refused -> 403 contact_limit_reached",
                  r.status_code == 403 and r.json().get("detail") == "contact_limit_reached",
                  f"{r.status_code} {r.text[:90]}")
            check("the response says what the limit was",
                  r.headers.get("x-contact-limit") == "25", str(r.headers.get("x-contact-limit")))
            async with AsyncSessionLocal() as db:
                stored = await db.scalar(
                    select(Contact.id).where(Contact.owner_id == user_id,
                                             Contact.name == "Twenty Sixth")
                )
            check("and nothing was written", stored is None, str(stored))

            print("\nOn the Member plan")
            await set_plan(user_id, PlanTier.member)

            r = await c.post("/api/contacts", headers=auth, json={"name": "Twenty Sixth"})
            check("the 26th contact now goes through -> 201", r.status_code == 201,
                  f"{r.status_code} {r.text[:90]}")
            r = await c.get("/api/plans/entitlements", headers=auth)
            check("the limit is gone", r.json()["contact_limit"] is None, str(r.json())[:120])

            r = await c.get("/api/contacts/pipeline", headers=auth)
            check("the pipeline board opens", r.status_code == 200, f"{r.status_code} {r.text[:70]}")

            r = await c.post("/api/communities", headers=auth,
                             json={"name": f"Member Community {run}", "kind": "region"})
            check("communities can be created -> 201", r.status_code == 201,
                  f"{r.status_code} {r.text[:90]}")
            slug = r.json()["slug"] if r.status_code == 201 else None

            print("\nOn the Professional plan")
            await set_plan(user_id, PlanTier.professional)
            r = await c.get("/api/plans/entitlements", headers=auth)
            body = r.json()
            check("every phase is included",
                  all(p["included"] for p in body["phases"]), str(body["phases"])[:160])
            check("including phase 7",
                  next(p for p in body["phases"] if p["n"] == 7)["included"] is True, "")
            check("with the 5 seats", body["team_seats"] == 5, str(body["team_seats"]))
            r = await c.get("/api/contacts/pipeline", headers=auth)
            check("everything Member could do still works", r.status_code == 200, str(r.status_code))

            print("\nDropping back to free")
            await set_plan(user_id, PlanTier.early_access)
            r = await c.get("/api/contacts/pipeline", headers=auth)
            check("the paid features close again -> 403", r.status_code == 403, str(r.status_code))
            r = await c.get("/api/plans/entitlements", headers=auth)
            check("and the entitlements follow the downgrade",
                  r.json()["max_phase"] == 1
                  and [p["n"] for p in r.json()["phases"] if p["included"]] == [1],
                  str(r.json()["max_phase"]))

            if slug:
                await c.delete(f"/api/communities/{slug}", headers=auth)

            print("\nUnauthenticated")
            r = await c.get("/api/plans/entitlements")
            check("entitlements need a token -> 401", r.status_code == 401, str(r.status_code))

        print("\nThe phase guard itself (require_phase)")
        await check_phase_guard(user_id)
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
