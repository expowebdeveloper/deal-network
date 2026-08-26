"""Editing a profile: what PATCH /api/me accepts, refuses and stores.

    uvicorn app.main:app --port 8000 &
    python profile_test.py

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
    FieldVisibility, Mandate, OAuthProvider, PlanSelection, PlanTier, User,
)
from app.services.oauth import OAuthProfile
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


async def make_member(marker: str) -> tuple:
    """A member past the gates, so the whole profile area is reachable."""
    async with AsyncSessionLocal() as db:
        user, _ = await resolve_user(db, OAuthProfile(
            provider=OAuthProvider.google, subject=f"google-{marker}",
            email=f"edit.{marker}@example.com", email_verified=True, name="Original Name",
        ))
        await db.flush()
        db.add(build_acceptance(user, marketing_opt_in=False))
        db.add(PlanSelection(
            user_id=user.id, user_name=user.name, user_email=user.email,
            user_company=user.company, plan=PlanTier.member, plan_name="Member",
            price_usd=25, billing_period="monthly", is_current=True, source="onboarding",
        ))
        await db.commit()
        await db.refresh(user)
        return user.id, user.email


async def stored(user_id) -> User:
    async with AsyncSessionLocal() as db:
        return await db.get(User, user_id)


async def stored_mandate(user_id) -> Mandate | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(Mandate).where(Mandate.user_id == user_id))


async def stored_visibility(user_id) -> dict:
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(
            select(FieldVisibility).where(FieldVisibility.user_id == user_id)
        )).all()
        return {row.field_key: row.level.value for row in rows}


async def main() -> None:
    run = uuid.uuid4().hex[:8]
    user_id, email = await make_member(run)
    auth = {"Authorization": f"Bearer {create_access_token(user_id, email)}"}

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
            print("\nReading the profile back")
            r = await c.get("/api/me", headers=auth)
            check("GET /api/me -> 200", r.status_code == 200, r.text[:120])
            check("a fresh member has nothing filled in",
                  r.json()["company"] is None and r.json()["title"] is None
                  and r.json()["role"] is None, r.text[:200])

            r = await c.patch("/api/me", json={"name": "No Token"})
            check("editing requires a token -> 401", r.status_code == 401, str(r.status_code))

            print("\nEditing every field the form offers")
            edit = {
                "name": "Ranjan Chaudhary",
                "role": "Developer",
                "title": "Managing Partner",
                "company": "Meridian Developments",
                "location": "Mohali, IN",
                "focus": "Residential, Mixed-use",
                "bio": "Residential and mixed-use across the Tricity.",
                "completed_projects": 11,
                "units_delivered": 940,
                "active_projects": 2,
            }
            r = await c.patch("/api/me", headers=auth, json=edit)
            check("PATCH /api/me -> 200", r.status_code == 200, r.text[:160])
            body = r.json()
            check("the response is the updated profile",
                  all(body[k] == v for k, v in edit.items()), str(body)[:220])
            check("it still reports the gate state the SPA routes on",
                  {"terms_accepted", "plan_selected", "onboarded"} <= set(body), str(body)[:200])

            row = await stored(user_id)
            check("the name reached the database", row.name == edit["name"], row.name)
            check("the role reached it as an enum", row.role.value == "Developer", str(row.role))
            check("the text fields reached it",
                  row.title == edit["title"] and row.company == edit["company"]
                  and row.location == edit["location"] and row.focus == edit["focus"]
                  and row.bio == edit["bio"], str((row.title, row.company, row.location))[:160])
            check("the numbers reached it",
                  row.completed_projects == 11 and row.units_delivered == 940
                  and row.active_projects == 2,
                  str((row.completed_projects, row.units_delivered, row.active_projects)))

            print("\nOnly what is sent is touched")
            r = await c.patch("/api/me", headers=auth, json={"title": "Founder"})
            check("a one-field edit -> 200", r.status_code == 200, r.text[:120])
            row = await stored(user_id)
            check("that field changed", row.title == "Founder", str(row.title))
            check("and nothing else did",
                  row.company == edit["company"] and row.name == edit["name"]
                  and row.completed_projects == 11, str((row.company, row.name))[:120])

            print("\nWhitespace and clearing")
            r = await c.patch("/api/me", headers=auth, json={"company": "  Spaced Out Ltd  "})
            check("surrounding whitespace is trimmed",
                  r.json()["company"] == "Spaced Out Ltd", str(r.json()["company"]))
            r = await c.patch("/api/me", headers=auth, json={"company": "   "})
            check("a field cleared to blank comes back null",
                  r.json()["company"] is None, str(r.json()["company"]))
            check("and is null in the database", (await stored(user_id)).company is None, "")
            r = await c.patch("/api/me", headers=auth, json={"title": None})
            check("an explicit null clears it too", r.json()["title"] is None, str(r.json()["title"]))

            print("\nWhat it refuses")
            for payload, why in [
                ({"name": "   "}, "a blank name"),
                ({"name": ""}, "an empty name"),
                ({"role": "Astronaut"}, "a role that is not a member role"),
                ({"completed_projects": -1}, "a negative project count"),
                ({"name": "x" * 200}, "a name past the column length"),
            ]:
                r = await c.patch("/api/me", headers=auth, json=payload)
                check(f"{why} -> 422", r.status_code == 422, f"{r.status_code} {r.text[:90]}")

            check("the name survived every rejection",
                  (await stored(user_id)).name == "Ranjan Chaudhary", "")

            print("\nThe investor mandate saves alongside it")
            r = await c.get("/api/me/mandate", headers=auth)
            check("GET /api/me/mandate -> 200", r.status_code == 200, r.text[:120])
            r = await c.put("/api/me/mandate", headers=auth,
                            json={"markets": "  Mohali, Chandigarh  ", "typical_raise": "₹8–25 Cr"})
            check("PUT /api/me/mandate -> 200", r.status_code == 200, r.text[:140])
            check("it trims too", r.json()["markets"] == "Mohali, Chandigarh", str(r.json())[:140])
            mandate = await stored_mandate(user_id)
            check("the mandate reached the database",
                  mandate.markets == "Mohali, Chandigarh" and mandate.typical_raise == "₹8–25 Cr",
                  str((mandate.markets, mandate.typical_raise)))
            r = await c.put("/api/me/mandate", headers=auth, json={"typical_raise": "  "})
            check("blanking a mandate field clears it",
                  r.json()["typical_raise"] is None, str(r.json())[:120])

            print("\nField visibility is per field and persists")
            r = await c.get("/api/me/visibility", headers=auth)
            check("GET /api/me/visibility lists all 8 fields",
                  r.status_code == 200 and len(r.json()) == 8, str(len(r.json())))
            r = await c.put("/api/me/visibility", headers=auth,
                            json={"field_key": "company", "level": "Private"})
            check("PUT /api/me/visibility -> 200",
                  r.status_code == 200 and r.json()["level"] == "Private", r.text[:120])
            check("it reached the database",
                  (await stored_visibility(user_id))["company"] == "Private", "")
            check("the other fields are untouched",
                  (await stored_visibility(user_id))["markets"] == "Public", "")
            r = await c.put("/api/me/visibility", headers=auth,
                            json={"field_key": "company", "level": "Members"})
            check("changing it again updates the same row",
                  r.status_code == 200 and (await stored_visibility(user_id))["company"] == "Members",
                  r.text[:120])
            check("still 8 rows, not 9", len(await stored_visibility(user_id)) == 8, "")
            r = await c.put("/api/me/visibility", headers=auth,
                            json={"field_key": "salary", "level": "Public"})
            check("an unknown field -> 422", r.status_code == 422, str(r.status_code))
            r = await c.put("/api/me/visibility", headers=auth,
                            json={"field_key": "company", "level": "Sometimes"})
            check("an unknown level -> 422", r.status_code == 422, str(r.status_code))

            print("\nWhat other members see")
            r = await c.get("/api/me", headers=auth)
            check("the edited profile reads back whole",
                  r.json()["name"] == "Ranjan Chaudhary" and r.json()["focus"] == edit["focus"]
                  and r.json()["units_delivered"] == 940, r.text[:200])
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
