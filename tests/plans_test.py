"""Plan selection and the access gate.

    uvicorn app.main:app --port 8000 &
    python plans_test.py

Re-runnable: it clears the demo member's selections at the start and restores a
selection at the end, so the other suites are unaffected.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models import PlanSelection, PlanTier, User

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0

# Everything a member must not reach before choosing.
GATED = [
    "/api/communities",
    "/api/communities/suggested",
    "/api/posts",
    "/api/media",
    "/api/contacts",
    "/api/members",
    "/api/members/suggested",
    "/api/connections",
    "/api/investors/overview",
    "/api/investors/introductions",
]

# Gated before choosing, and still paid-for afterwards: choosing the free plan
# opens the app but not the Member ticks. See entitlements_test.py.
PAID = ["/api/contacts/pipeline"]

# Everything they must still reach, or they could never choose.
OPEN = ["/api/me", "/api/me/stats", "/api/plans", "/api/plans/selection", "/health"]


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


async def clear_selections(user_id) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PlanSelection).where(PlanSelection.user_id == user_id))
        await db.commit()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "vikram.sethi@example.com"))
        if user is None:
            print("missing seed user — run: python seed.py --reset")
            sys.exit(1)
        auth = {"Authorization": f"Bearer {create_access_token(user.id, user.email)}"}
        user_id, user_name, user_email = user.id, user.name, user.email

    await clear_selections(user_id)

    async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
        print("\nThe public price list — no token at all")
        r = await c.get("/api/plans/catalogue")
        check("readable while signed out -> 200", r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        catalogue = r.json() if r.status_code == 200 else []
        check("all three tiers, in order",
              [p["id"] for p in catalogue] == ["early_access", "member", "professional"],
              str([p.get("id") for p in catalogue]))
        check("with their prices",
              [p["price"] for p in catalogue] == ["$0", "$25", "$100"],
              str([p.get("price") for p in catalogue]))
        check("and how far up the roadmap each one reaches",
              [p["max_phase"] for p in catalogue] == [1, 4, 7],
              str([p.get("max_phase") for p in catalogue]))
        check("only the top tier is pro",
              [p["pro"] for p in catalogue] == [False, False, True],
              str([p.get("pro") for p in catalogue]))
        check("nothing is marked current — there is nobody to be current for",
              all(p["is_current"] is False for p in catalogue), r.text[:120])
        check("feature ticks come through, crosses included",
              any(f["label"] == "Team seats" and f["included"] is False
                  for f in catalogue[1]["features"]), str(catalogue[1]["features"])[:160])
        r = await c.get("/api/plans")
        check("the signed-in list still needs a token -> 401", r.status_code == 401, str(r.status_code))

        print("\nBefore choosing a plan")
        r = await c.get("/api/me", headers=auth)
        check("/api/me reports plan_selected=false",
              r.status_code == 200 and r.json()["plan_selected"] is False, r.text[:140])
        check("/api/me reports no current plan", r.json()["current_plan"] is None, r.text[:140])

        for path in GATED + PAID:
            r = await c.get(path, headers=auth)
            check(f"blocked: {path}",
                  r.status_code == 403 and r.json().get("detail") == "plan_not_selected",
                  f"{r.status_code} {r.text[:80]}")

        for path in OPEN:
            r = await c.get(path, headers=auth if path != "/health" else None)
            check(f"still open: {path}", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        r = await c.post("/api/posts", headers=auth, json={"body": "should be blocked"})
        check("writes are blocked too", r.status_code == 403, str(r.status_code))

        r = await c.get("/api/plans/selection", headers=auth)
        check("selection is null before choosing", r.json() is None, r.text[:120])

        print("\nChoosing")
        r = await c.post("/api/plans/select", headers=auth, json={"plan": "nonsense"})
        check("unknown plan -> 422", r.status_code == 422, str(r.status_code))

        r = await c.post("/api/plans/select", headers=auth, json={"plan": "early_access"})
        check("free plan can be chosen -> 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
        row = r.json()
        check("records the member's name", row["user_name"] == user_name, str(row)[:160])
        check("records the email", row["user_email"] == user_email, str(row)[:160])
        check("records the plan and its display name",
              row["plan"] == "early_access" and row["plan_name"] == "Early access", str(row)[:160])
        check("records the price", float(row["price_usd"]) == 0.0, str(row["price_usd"]))
        check("free plan has no billing period", row["billing_period"] == "none", row["billing_period"])
        check("records when it was chosen",
              bool(row["selected_at"]) and "T" in row["selected_at"], str(row["selected_at"]))
        check("first choice is tagged onboarding", row["source"] == "onboarding", row["source"])
        check("marked current", row["is_current"] is True, str(row))

        print("\nAfter choosing")
        r = await c.get("/api/me", headers=auth)
        check("/api/me reports plan_selected=true", r.json()["plan_selected"] is True, r.text[:140])
        check("/api/me reports the chosen plan",
              r.json()["current_plan"] == "early_access", r.text[:140])

        for path in GATED:
            r = await c.get(path, headers=auth)
            check(f"unlocked: {path}", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        for path in PAID:
            r = await c.get(path, headers=auth)
            check(f"still needs a paid plan: {path}",
                  r.status_code == 403 and r.json().get("detail") == "upgrade_required",
                  f"{r.status_code} {r.text[:80]}")

        print("\nChanging plan")
        r = await c.post("/api/plans/select", headers=auth, json={"plan": "member"})
        check("can move to a paid tier", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
        check("later change is tagged change", r.json()["source"] == "change", r.json()["source"])
        check("paid tier records the price", float(r.json()["price_usd"]) == 25.0, str(r.json()))
        check("paid tier is billed monthly", r.json()["billing_period"] == "monthly", str(r.json()))

        r = await c.get("/api/plans/selections", headers=auth)
        history = r.json()
        check("history keeps both choices", len(history) == 2, str(len(history)))
        check("only one row is current",
              sum(1 for h in history if h["is_current"]) == 1, str(history)[:200])
        check("newest first", history[0]["plan"] == "member", str(history[0])[:120])

        r = await c.get("/api/plans/selection", headers=auth)
        check("selection returns the newest", r.json()["plan"] == "member", r.text[:140])

        r = await c.get("/api/plans", headers=auth)
        check("catalogue marks it current",
              any(p["id"] == "member" and p["is_current"] for p in r.json()), r.text[:200])

        for path in PAID:
            r = await c.get(path, headers=auth)
            check(f"the paid tier opens it: {path}", r.status_code == 200,
                  f"{r.status_code} {r.text[:80]}")

        print("\nUnauthenticated")
        r = await c.post("/api/plans/select", json={"plan": "member"})
        check("choosing requires a token -> 401", r.status_code == 401, str(r.status_code))

        # Leave the member on the tier the demo data assumes, so suite order does
        # not matter — the other suites exercise Member features.
        await c.post("/api/plans/select", headers=auth, json={"plan": "member"})

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
