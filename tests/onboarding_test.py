"""Profile setup: the two steps, what they accept, and what they write.

    uvicorn app.main:app --port 8000 &
    python onboarding_test.py

Re-runnable: it works on its own throwaway member, created and deleted here, so
no seed data is touched.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models import (
    Mandate, MemberOnboarding, OAuthProvider, PlanSelection, PlanTier, User,
)
from app.services.oauth import OAuthProfile
from app.services.onboarding import TOTAL_STEPS
from app.services.terms import build_acceptance
from app.services.users import resolve_user

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


async def make_member(marker: str, *, past_gates: bool) -> tuple:
    """A fresh member, optionally already past the terms and plan gates."""
    async with AsyncSessionLocal() as db:
        user, _ = await resolve_user(db, OAuthProfile(
            provider=OAuthProvider.google, subject=f"google-{marker}",
            email=f"setup.{marker}@example.com", email_verified=True, name="Nina Setup",
        ))
        await db.flush()
        if past_gates:
            db.add(build_acceptance(user, marketing_opt_in=False))
            db.add(PlanSelection(
                user_id=user.id, user_name=user.name, user_email=user.email,
                user_company=user.company, plan=PlanTier.member, plan_name="Member",
                price_usd=25, billing_period="monthly", is_current=True, source="onboarding",
            ))
        await db.commit()
        await db.refresh(user)
        return user.id, user.email


async def row_for(user_id) -> MemberOnboarding | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(MemberOnboarding).where(MemberOnboarding.user_id == user_id)
        )


async def profile_of(user_id) -> User:
    async with AsyncSessionLocal() as db:
        return await db.get(User, user_id)


async def mandate_of(user_id) -> Mandate | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(Mandate).where(Mandate.user_id == user_id))


async def drop(user_id) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


async def main() -> None:
    run = uuid.uuid4().hex[:8]
    user_id, email = await make_member(run, past_gates=True)
    auth = {"Authorization": f"Bearer {create_access_token(user_id, email)}"}

    # A second member who has agreed to nothing, to prove the ordering.
    early_id, early_email = await make_member(uuid.uuid4().hex[:8], past_gates=False)
    early_auth = {"Authorization": f"Bearer {create_access_token(early_id, early_email)}"}

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
            print("\nSetup comes after the other two steps")
            r = await c.get("/api/onboarding", headers=early_auth)
            check("no terms agreed -> 403 terms_not_accepted",
                  r.status_code == 403 and r.json().get("detail") == "terms_not_accepted",
                  f"{r.status_code} {r.text[:80]}")
            r = await c.get("/api/onboarding")
            check("and it needs a token at all -> 401", r.status_code == 401, str(r.status_code))

            print("\nWhat the first step offers")
            r = await c.get("/api/onboarding", headers=auth)
            state = r.json()
            check("GET /api/onboarding -> 200", r.status_code == 200, r.text[:140])
            check("it starts on step 1", state["step"] == 1, str(state["step"]))
            check("it reports how many steps there are",
                  state["total_steps"] == TOTAL_STEPS, str(state["total_steps"]))
            check("not finished yet",
                  state["completed"] is False and state["completed_at"] is None, str(state)[:120])
            check("nothing is answered yet",
                  state["role"] is None and state["company"] is None
                  and state["asset_classes"] == [], str(state)[:160])

            options = state["options"]
            check("the five roles are offered with their copy",
                  len(options["roles"]) == 5
                  and all({"id", "title", "description"} <= set(o) for o in options["roles"]),
                  str(options["roles"])[:160])
            check("Developer / Sponsor is one of them",
                  any(o["title"] == "Developer / Sponsor" and o["id"] == "Developer"
                      for o in options["roles"]), str(options["roles"])[:160])
            check("markets, team sizes and asset classes come with it",
                  options["markets"] and options["team_sizes"] and options["asset_classes"],
                  str(options)[:200])

            print("\nStep 2 will not run before step 1")
            r = await c.post("/api/onboarding/profile", headers=auth, json={
                "company": "Too Early Ltd", "primary_market": options["markets"][0],
                "team_size": options["team_sizes"][0], "asset_classes": [],
            })
            check("finishing without a role -> 409 role_not_chosen",
                  r.status_code == 409 and r.json().get("detail") == "role_not_chosen",
                  f"{r.status_code} {r.text[:100]}")

            print("\nStep 1 — what describes you best")
            r = await c.post("/api/onboarding/role", headers=auth, json={"role": "Nonsense"})
            check("an unknown role -> 422", r.status_code == 422, str(r.status_code))

            r = await c.post("/api/onboarding/role", headers=auth, json={"role": "Developer"})
            check("choosing a role -> 200", r.status_code == 200, r.text[:140])
            check("it moves on to step 2", r.json()["step"] == 2, str(r.json()["step"]))
            check("and remembers the choice", r.json()["role"] == "Developer", str(r.json())[:120])

            row = await row_for(user_id)
            check("the row records the role and when", row.role.value == "Developer"
                  and row.role_chosen_at is not None, str(row.role))
            check("the role lands on the profile immediately",
                  (await profile_of(user_id)).role.value == "Developer", "")
            check("but setup is not finished yet",
                  (await profile_of(user_id)).onboarded is False, "")

            print("\nStep 2 — company details, and what it refuses")
            good = {
                "company": "Meridian Developments",
                "primary_market": "Mohali, IN",
                "team_size": "Just me",
                "asset_classes": ["Residential", "Mixed-use"],
                "short_description": "Residential and mixed-use across the Tricity.",
            }
            for field, value, why in [
                ("company", "", "an empty company"),
                ("primary_market", "Atlantis", "a market that is not on the list"),
                ("team_size", "Thousands", "a team size that is not on the list"),
                ("asset_classes", ["Spaceports"], "an asset class that is not on the list"),
            ]:
                r = await c.post("/api/onboarding/profile", headers=auth, json={**good, field: value})
                check(f"{why} -> 422", r.status_code == 422, f"{r.status_code} {r.text[:100]}")

            check("none of that was saved", (await row_for(user_id)).company is None, "")

            r = await c.post("/api/onboarding/profile", headers=auth, json={
                **good, "asset_classes": ["Residential", " Residential ", "Mixed-use"],
            })
            check("finishing setup -> 200", r.status_code == 200, r.text[:160])
            done = r.json()
            check("it reports itself finished",
                  done["completed"] is True and done["completed_at"], str(done)[:160])
            check("duplicate asset classes are collapsed",
                  done["asset_classes"] == ["Residential", "Mixed-use"], str(done["asset_classes"]))

            print("\nWhat reached the database")
            row = await row_for(user_id)
            check("the company is stored", row.company == "Meridian Developments", str(row.company))
            check("the market is stored", row.primary_market == "Mohali, IN", str(row.primary_market))
            check("the team size is stored — it has no other home",
                  row.team_size == "Just me", str(row.team_size))
            check("the asset classes are stored",
                  row.asset_classes == "Residential, Mixed-use", str(row.asset_classes))
            check("the description is stored",
                  row.short_description == good["short_description"], str(row.short_description))
            check("and when setup finished", row.completed_at is not None, "")

            print("\nAnd what it put on the profile")
            profile = await profile_of(user_id)
            check("company", profile.company == "Meridian Developments", str(profile.company))
            check("location comes from the primary market",
                  profile.location == "Mohali, IN", str(profile.location))
            check("focus comes from the asset classes",
                  profile.focus == "Residential, Mixed-use", str(profile.focus))
            check("bio comes from the description",
                  profile.bio == good["short_description"], str(profile.bio))
            check("the member is marked onboarded", profile.onboarded is True, "")

            mandate = await mandate_of(user_id)
            check("the mandate picks up the same markets and asset classes",
                  mandate is not None and mandate.markets == "Mohali, IN"
                  and mandate.asset_classes == "Residential, Mixed-use", str(mandate))

            r = await c.get("/api/me", headers=auth)
            check("/api/me reports onboarded=true", r.json()["onboarded"] is True, r.text[:140])

            print("\nGoing back over it")
            r = await c.get("/api/onboarding", headers=auth)
            check("it reads back what was entered",
                  r.json()["company"] == "Meridian Developments"
                  and r.json()["team_size"] == "Just me"
                  and r.json()["completed"] is True, r.text[:200])

            r = await c.post("/api/onboarding/profile", headers=auth, json={
                **good, "company": "Meridian Developments II", "team_size": "2–10",
            })
            check("setup can be run again -> 200", r.status_code == 200, str(r.status_code))
            check("the row is updated, not duplicated",
                  (await row_for(user_id)).company == "Meridian Developments II", "")
            async with AsyncSessionLocal() as db:
                count = len((await db.scalars(
                    select(MemberOnboarding).where(MemberOnboarding.user_id == user_id)
                )).all())
            check("still exactly one row per member", count == 1, str(count))
            check("the profile follows the change",
                  (await profile_of(user_id)).company == "Meridian Developments II", "")
    finally:
        await drop(user_id)
        await drop(early_id)

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
