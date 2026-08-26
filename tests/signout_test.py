"""Sign-out: what a revoked token can and cannot do.

    uvicorn app.main:app --port 8000 &
    python signout_test.py

Re-runnable: every session it signs out is minted here, and the denylist rows it
creates are cleared at both ends of the run, so no other suite is affected.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import RevokedToken, User

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0

# Reached with the access token; each must stop working once it is revoked.
AUTHENTICATED = ["/auth/me", "/auth/session", "/api/me", "/api/plans"]


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Session:
    """One signed-in device: an access token and the refresh token beside it."""

    def __init__(self, user_id, email: str) -> None:
        self.access = create_access_token(user_id, email)
        self.refresh = create_refresh_token(user_id)

    @property
    def auth(self) -> dict:
        return bearer(self.access)

    @property
    def jtis(self) -> tuple[str, str]:
        return decode_token(self.access)["jti"], decode_token(self.refresh)["jti"]


async def clear_denylist(user_id) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RevokedToken).where(RevokedToken.user_id == user_id))
        await db.commit()


async def denylisted(user_id) -> dict[str, str]:
    """{jti: token_type} currently on the denylist for this member."""
    async with AsyncSessionLocal() as db:
        rows = (
            await db.scalars(select(RevokedToken).where(RevokedToken.user_id == user_id))
        ).all()
        return {row.jti: row.token_type for row in rows}


async def add_expired_row(user_id) -> str:
    """A leftover row for a token that has since expired — purge fodder."""
    jti = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        db.add(
            RevokedToken(
                jti=jti,
                user_id=user_id,
                token_type="access",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await db.commit()
    return jti


async def main() -> None:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "vikram.sethi@example.com"))
        if user is None:
            print("missing seed user — run: python seed.py --reset")
            sys.exit(1)
        user_id, email = user.id, user.email

    await clear_denylist(user_id)

    # Two independent sessions, as if the member were signed in on two devices.
    phone = Session(user_id, email)
    laptop = Session(user_id, email)

    async with httpx.AsyncClient(base_url=BASE, timeout=20) as c:
        print("\nBefore signing out")
        for path in AUTHENTICATED:
            r = await c.get(path, headers=phone.auth)
            check(f"token works: {path}", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        r = await c.post("/auth/refresh", json={"refresh_token": phone.refresh})
        check("refresh token works", r.status_code == 200, f"{r.status_code} {r.text[:120]}")

        print("\nSigning out needs something to sign out")
        r = await c.post("/auth/logout")
        check("no token at all -> 401", r.status_code == 401, f"{r.status_code} {r.text[:80]}")
        r = await c.post("/auth/logout", json={"refresh_token": None})
        check("empty body, no header -> 401", r.status_code == 401, str(r.status_code))
        check("401 asks for a bearer token",
              r.headers.get("www-authenticate") == "Bearer", str(r.headers.get("www-authenticate")))

        r = await c.post("/auth/logout", headers=bearer("not-a-token"))
        check("a junk token is not an error -> 200", r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        check("nothing is denylisted for junk", await denylisted(user_id) == {}, "")

        print("\nSigning out")
        r = await c.post("/auth/logout", headers=phone.auth, json={"refresh_token": phone.refresh})
        check("access + refresh -> 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        check("says it signed out", r.json().get("detail") == "Signed out", r.text[:120])

        access_jti, refresh_jti = phone.jtis
        rows = await denylisted(user_id)
        check("both tokens are denylisted", {access_jti, refresh_jti} <= set(rows), str(rows)[:200])
        check("each is recorded with its type",
              rows.get(access_jti) == "access" and rows.get(refresh_jti) == "refresh",
              str(rows)[:200])

        print("\nAfter signing out")
        for path in AUTHENTICATED:
            r = await c.get(path, headers=phone.auth)
            check(f"revoked token is refused: {path}",
                  r.status_code == 401, f"{r.status_code} {r.text[:80]}")
        check("401 says why", r.json().get("detail") == "Session has been signed out", r.text[:120])

        r = await c.post("/api/plans/select", headers=phone.auth, json={"plan": "early_access"})
        check("writes are refused too", r.status_code == 401, f"{r.status_code} {r.text[:80]}")

        r = await c.post("/auth/refresh", json={"refresh_token": phone.refresh})
        check("the refresh token cannot revive the session -> 401",
              r.status_code == 401, f"{r.status_code} {r.text[:120]}")
        check("refresh 401 says why",
              r.json().get("detail") == "Session has been signed out", r.text[:120])

        r = await c.post("/auth/logout", headers=phone.auth, json={"refresh_token": phone.refresh})
        check("signing out twice is not an error -> 200",
              r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        check("the second sign-out adds no duplicate rows",
              len(await denylisted(user_id)) == 2, str(await denylisted(user_id))[:200])

        print("\nOther sessions and later sign-ins")
        r = await c.get("/auth/me", headers=laptop.auth)
        check("the member's other device is untouched",
              r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        r = await c.post("/auth/refresh", json={"refresh_token": laptop.refresh})
        check("its refresh token still works", r.status_code == 200, f"{r.status_code} {r.text[:120]}")

        fresh = Session(user_id, email)
        r = await c.get("/api/me", headers=fresh.auth)
        check("signing in again works", r.status_code == 200, f"{r.status_code} {r.text[:80]}")

        print("\nSigning out with only half a session")
        access_only = Session(user_id, email)
        r = await c.post("/auth/logout", headers=access_only.auth, json={"refresh_token": None})
        check("header alone (what the SPA sends without a refresh token) -> 200",
              r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        r = await c.get("/auth/me", headers=access_only.auth)
        check("that access token is dead", r.status_code == 401, str(r.status_code))

        refresh_only = Session(user_id, email)
        r = await c.post("/auth/logout", json={"refresh_token": refresh_only.refresh})
        check("body alone (expired access token) -> 200",
              r.status_code == 200, f"{r.status_code} {r.text[:80]}")
        r = await c.post("/auth/refresh", json={"refresh_token": refresh_only.refresh})
        check("that refresh token is dead", r.status_code == 401, str(r.status_code))
        r = await c.get("/auth/me", headers=refresh_only.auth)
        check("its access token was never presented, so it lives on",
              r.status_code == 200, str(r.status_code))

        print("\nHousekeeping")
        stale = await add_expired_row(user_id)
        check("a stale row is there to begin with", stale in await denylisted(user_id), stale)
        await c.post("/auth/logout", headers=fresh.auth, json={"refresh_token": fresh.refresh})
        check("signing out purges rows for tokens that have expired",
              stale not in await denylisted(user_id), stale)
        check("live rows survive the purge",
              access_jti in await denylisted(user_id), str(await denylisted(user_id))[:200])

        print("\nWrong token in the wrong place")
        r = await c.post("/auth/refresh", json={"refresh_token": laptop.access})
        check("an access token is not a refresh token -> 401", r.status_code == 401, str(r.status_code))
        r = await c.get("/auth/me", headers=bearer(laptop.refresh))
        check("a refresh token is not an access token -> 401", r.status_code == 401, str(r.status_code))
        r = await c.get("/auth/me", headers=laptop.auth)
        check("neither attempt revoked the good session",
              r.status_code == 200, f"{r.status_code} {r.text[:80]}")

    await clear_denylist(user_id)

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
