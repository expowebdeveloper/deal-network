"""The terms gate: what a member can reach before agreeing, and what is recorded.

    uvicorn app.main:app --port 8000 &
    python terms_test.py

Re-runnable: it clears the demo member's acceptances at the start and puts one
back at the end, so the other suites are unaffected.
"""

from __future__ import annotations

import asyncio
import sys

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models import TermsAcceptance, User
from app.services.terms import TERMS_VERSION

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0

# Behind the terms gate, including the plan step the member goes to next.
GATED = [
    "/api/plans",
    "/api/plans/selection",
    "/api/communities",
    "/api/posts",
    "/api/contacts",
    "/api/members",
    "/api/investors/overview",
]

# Reachable before agreeing, or the member could never agree.
OPEN = ["/api/me", "/api/me/stats", "/api/terms", "/api/terms/acceptance", "/health"]


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


async def clear_acceptances(user_id) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(TermsAcceptance).where(TermsAcceptance.user_id == user_id))
        await db.commit()


async def stored_rows(user_id) -> list[TermsAcceptance]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(
            select(TermsAcceptance)
            .where(TermsAcceptance.user_id == user_id)
            .order_by(TermsAcceptance.accepted_at)
        )).all())


async def main() -> None:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "vikram.sethi@example.com"))
        if user is None:
            print("missing seed user — run: python seed.py --reset")
            sys.exit(1)
        auth = {"Authorization": f"Bearer {create_access_token(user.id, user.email)}"}
        user_id, user_name, user_email = user.id, user.name, user.email

    await clear_acceptances(user_id)

    async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
        print("\nThe terms themselves")
        r = await c.get("/api/terms")
        doc = r.json()
        check("GET /api/terms works without signing in", r.status_code == 200, r.text[:120])
        check("it carries a version", doc["version"] == TERMS_VERSION, str(doc.get("version")))
        check("it carries the summary sections",
              len(doc["sections"]) >= 4 and all({"heading", "body"} <= set(s) for s in doc["sections"]),
              str(doc["sections"])[:160])
        check("anonymous callers have not accepted", doc["accepted"] is False, str(doc["accepted"]))

        r = await c.get("/api/terms", headers=auth)
        check("signed in, it reports this member has not accepted",
              r.json()["accepted"] is False and r.json()["accepted_at"] is None, r.text[:140])

        print("\nBefore agreeing")
        r = await c.get("/api/me", headers=auth)
        check("/api/me reports terms_accepted=false",
              r.status_code == 200 and r.json()["terms_accepted"] is False, r.text[:160])

        for path in GATED:
            r = await c.get(path, headers=auth)
            check(f"blocked: {path}",
                  r.status_code == 403 and r.json().get("detail") == "terms_not_accepted",
                  f"{r.status_code} {r.text[:80]}")

        for path in OPEN:
            r = await c.get(path, headers=auth if path != "/health" else None)
            check(f"still open: {path}", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        r = await c.post("/api/plans/select", headers=auth, json={"plan": "early_access"})
        check("the plan step is blocked too — terms come first",
              r.status_code == 403 and r.json().get("detail") == "terms_not_accepted",
              f"{r.status_code} {r.text[:80]}")

        r = await c.get("/api/terms/acceptance", headers=auth)
        check("acceptance is null before agreeing", r.json() is None, r.text[:120])

        print("\nAgreeing, and what it will not accept")
        r = await c.post("/api/terms/accept",
                         json={"version": TERMS_VERSION, "accept_terms": True,
                               "accept_unverified": True})
        check("agreeing requires a token -> 401", r.status_code == 401, str(r.status_code))

        r = await c.post("/api/terms/accept", headers=auth,
                         json={"version": TERMS_VERSION, "accept_terms": False,
                               "accept_unverified": True})
        check("the first box unticked -> 422", r.status_code == 422, f"{r.status_code} {r.text[:100]}")
        r = await c.post("/api/terms/accept", headers=auth,
                         json={"version": TERMS_VERSION, "accept_terms": True,
                               "accept_unverified": False})
        check("the second box unticked -> 422", r.status_code == 422, f"{r.status_code} {r.text[:100]}")
        r = await c.post("/api/terms/accept", headers=auth,
                         json={"version": "1999-01-01", "accept_terms": True,
                               "accept_unverified": True})
        check("agreeing to a version that is not in force -> 409",
              r.status_code == 409 and r.json().get("detail") == "terms_version_changed",
              f"{r.status_code} {r.text[:100]}")
        r = await c.post("/api/terms/accept", headers=auth, json={"accept_terms": True})
        check("a body missing the version -> 422", r.status_code == 422, str(r.status_code))

        check("none of the rejected attempts were recorded",
              len(await stored_rows(user_id)) == 0, str(await stored_rows(user_id)))
        r = await c.get("/api/communities", headers=auth)
        check("and the gate is still shut", r.status_code == 403, str(r.status_code))

        r = await c.post("/api/terms/accept", headers=auth,
                         json={"version": TERMS_VERSION, "accept_terms": True,
                               "accept_unverified": True, "marketing_opt_in": True})
        check("both boxes ticked -> 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
        row = r.json()
        check("the response records the version", row["version"] == TERMS_VERSION, str(row)[:160])
        check("both consents are recorded separately",
              row["accepted_terms"] is True and row["accepted_unverified"] is True, str(row)[:160])
        check("the optional opt-in is kept", row["marketing_opt_in"] is True, str(row)[:160])
        check("it records when they agreed",
              bool(row["accepted_at"]) and "T" in row["accepted_at"], str(row["accepted_at"]))

        print("\nWhat reached the database")
        rows = await stored_rows(user_id)
        check("exactly one row was written", len(rows) == 1, str(len(rows)))
        check("it snapshots who agreed",
              rows[0].user_name == user_name and rows[0].user_email == user_email,
              f"{rows[0].user_name} / {rows[0].user_email}")
        check("against the version in force", rows[0].version == TERMS_VERSION, rows[0].version)
        check("with both consents and the opt-in",
              rows[0].accepted_terms and rows[0].accepted_unverified and rows[0].marketing_opt_in,
              str(rows[0].__dict__)[:160])

        print("\nAfter agreeing")
        r = await c.get("/api/me", headers=auth)
        check("/api/me reports terms_accepted=true", r.json()["terms_accepted"] is True, r.text[:160])
        r = await c.get("/api/terms", headers=auth)
        check("GET /api/terms now says accepted",
              r.json()["accepted"] is True and r.json()["accepted_at"], r.text[:160])
        r = await c.get("/api/terms/acceptance", headers=auth)
        check("the acceptance can be read back",
              r.status_code == 200 and r.json()["version"] == TERMS_VERSION, r.text[:140])

        r = await c.get("/api/plans", headers=auth)
        check("the plan step opens", r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        r = await c.post("/api/plans/select", headers=auth, json={"plan": "early_access"})
        check("and a plan can now be chosen", r.status_code == 201, f"{r.status_code} {r.text[:120]}")

        for path in GATED:
            r = await c.get(path, headers=auth)
            check(f"unlocked: {path}", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        print("\nAgreeing again")
        r = await c.post("/api/terms/accept", headers=auth,
                         json={"version": TERMS_VERSION, "accept_terms": True,
                               "accept_unverified": True, "marketing_opt_in": False})
        check("re-agreeing is accepted -> 201", r.status_code == 201, str(r.status_code))
        rows = await stored_rows(user_id)
        check("history is appended, not overwritten", len(rows) == 2, str(len(rows)))
        check("the opt-in change is kept on the newer row",
              rows[0].marketing_opt_in is True and rows[1].marketing_opt_in is False,
              str([r_.marketing_opt_in for r_ in rows]))

    # One clean acceptance left behind, so suite order does not matter.
    await clear_acceptances(user_id)
    async with AsyncSessionLocal() as db:
        member = await db.get(User, user_id)
        from app.services.terms import build_acceptance
        db.add(build_acceptance(member, marketing_opt_in=False))
        await db.commit()

    # Same for the tier: proving the plan step opens put this member on early
    # access, and the demo data — and the other suites — assume Member.
    async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
        await c.post("/api/plans/select", headers=auth, json={"plan": "member"})

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
