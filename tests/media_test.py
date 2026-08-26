"""Media upload and Home-rail suggestion endpoints.

    uvicorn app.main:app --port 8000 &
    python media_test.py

Re-runnable: uploads and posts created here are deleted in a finally block.
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid
import zlib

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models import User

BASE = "http://127.0.0.1:8000"
RUN = uuid.uuid4().hex[:6]
passed, failed = 0, 0
media_ids: list[str] = []
post_ids: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


def png_bytes(size: int = 1) -> bytes:
    """Smallest valid PNG, padded so we can make a big one when needed."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            len(data).to_bytes(4, "big") + tag + data
            + zlib.crc32(tag + data).to_bytes(4, "big")
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0]))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    body = header + ihdr + idat + iend
    if size > len(body):
        # Pad with a junk chunk so the signature still leads.
        body = body[:-12] + chunk(b"teXt", b"x" * (size - len(body))) + iend
    return body


async def auth_for(email: str) -> tuple[dict, str]:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"missing seed user {email} — run: python seed.py --reset")
            sys.exit(1)
        return {"Authorization": f"Bearer {create_access_token(user.id, user.email)}"}, str(user.id)


async def run(c: httpx.AsyncClient, owner, owner_id, other, other_id) -> None:
    print("\nUpload validation")
    r = await c.post("/api/media", headers=owner,
                     files={"file": ("evil.html", b"<script>alert(1)</script>", "text/html")})
    check("HTML is rejected", r.status_code == 422, f"{r.status_code} {r.text[:120]}")

    r = await c.post("/api/media", headers=owner,
                     files={"file": ("evil.svg", b"<svg onload=alert(1)>", "image/svg+xml")})
    check("SVG is rejected (script vector)", r.status_code == 422, f"{r.status_code} {r.text[:120]}")

    r = await c.post("/api/media", headers=owner,
                     files={"file": ("thing.bin", b"\x00\x01\x02", "application/octet-stream")})
    check("unknown type is rejected", r.status_code == 422, f"{r.status_code} {r.text[:120]}")

    r = await c.post("/api/media", headers=owner,
                     files={"file": ("fake.png", b"<script>alert(1)</script>", "image/png")})
    check("content-type lie is caught by magic bytes",
          r.status_code == 422, f"{r.status_code} {r.text[:120]}")

    r = await c.post("/api/media", headers=owner,
                     files={"file": ("empty.png", b"", "image/png")})
    check("empty file is rejected", r.status_code == 422, f"{r.status_code} {r.text[:120]}")

    oversize = png_bytes(settings.max_image_bytes + 2048)
    r = await c.post("/api/media", headers=owner,
                     files={"file": ("huge.png", oversize, "image/png")})
    check("oversize image is rejected", r.status_code == 422, f"{r.status_code} {r.text[:120]}")

    r = await c.post("/api/media", files={"file": ("a.png", png_bytes(), "image/png")})
    check("upload requires a token -> 401", r.status_code == 401, str(r.status_code))

    # Regression: the whole multipart body used to be spooled to the temp
    # directory before auth ran, so an anonymous client could fill the disk.
    huge = b"x" * (settings.max_document_bytes + 4 * 1024 * 1024)
    r = await c.post("/api/media", files={"file": ("huge.pdf", huge, "application/pdf")})
    check("oversized body is rejected with 413 before parsing, without a token",
          r.status_code == 413, f"{r.status_code} {r.text[:120]}")
    r = await c.post("/api/media", headers=owner,
                     files={"file": ("huge.pdf", huge, "application/pdf")})
    check("oversized body is rejected with 413 even with a token",
          r.status_code == 413, f"{r.status_code} {r.text[:120]}")

    print("\nUpload success")
    r = await c.post("/api/media", headers=owner,
                     files={"file": ("../../escape.png", png_bytes(), "image/png")})
    check("valid PNG uploads -> 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
    image = r.json()
    media_ids.append(image["id"])
    check("stored name is random, not the supplied path",
          "/" not in image["stored_name"] and ".." not in image["stored_name"],
          image["stored_name"])
    check("original name is kept for display only",
          image["original_name"] == "escape.png", image["original_name"])
    check("kind classified as image", image["kind"] == "image", str(image))
    check("url points at /media", image["url"].startswith("/media/"), image["url"])

    r = await c.get(image["url"])
    check("file is served back", r.status_code == 200 and r.content.startswith(b"\x89PNG"),
          str(r.status_code))
    check("served with nosniff",
          r.headers.get("x-content-type-options") == "nosniff", str(dict(r.headers))[:160])

    r = await c.get("/media/../app/main.py")
    check("path traversal on the static mount is blocked",
          r.status_code in (400, 404), str(r.status_code))

    r = await c.post("/api/media", headers=owner,
                     files={"file": ("brief.pdf", b"%PDF-1.4\n%test\n", "application/pdf")})
    check("PDF uploads", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
    doc = r.json()
    media_ids.append(doc["id"])
    check("kind classified as document", doc["kind"] == "document", str(doc))

    print("\nAttaching to a post")
    r = await c.post("/api/posts", headers=owner, json={
        "body": f"Site photos {RUN}",
        "attachment_ids": [image["id"], doc["id"]],
        "embed_title": "Bay Street Conversion",
        "embed_detail": "64 residential units · Staten Island, NY",
    })
    check("post with attachments -> 201", r.status_code == 201, f"{r.status_code} {r.text[:200]}")
    post = r.json()
    post_ids.append(post["id"])
    check("attachments come back in order",
          [a["id"] for a in post["attachments"]] == [image["id"], doc["id"]],
          str(post["attachments"])[:200])
    check("project update embed stored",
          post["embed_title"] == "Bay Street Conversion", str(post)[:200])

    r = await c.post("/api/posts", headers=other, json={
        "body": "Stealing your file", "attachment_ids": [image["id"]]})
    check("cannot attach someone else's upload -> 404",
          r.status_code == 404, f"{r.status_code} {r.text[:140]}")

    r = await c.post("/api/posts", headers=owner, json={
        "body": "Ghost", "attachment_ids": [str(uuid.uuid4())]})
    check("unknown attachment id -> 404", r.status_code == 404, str(r.status_code))

    # Regression: duplicate ids used to violate uq_post_media and 500.
    r = await c.post("/api/posts", headers=owner, json={
        "body": f"Duplicate ids {RUN}", "attachment_ids": [doc["id"], doc["id"]]})
    check("duplicate attachment ids are collapsed, not a 500",
          r.status_code == 201 and len(r.json()["attachments"]) == 1,
          f"{r.status_code} {r.text[:160]}")
    if r.status_code == 201:
        post_ids.append(r.json()["id"])

    print("\nPost visibility")
    # Regression: `visibility` was stored and returned but never applied.
    r = await c.post("/api/posts", headers=owner, json={
        "body": f"Private note {RUN}", "visibility": "Private"})
    check("private post created", r.status_code == 201, r.text[:160])
    private_id = r.json()["id"]
    post_ids.append(private_id)

    r = await c.get("/api/posts", headers=other)
    check("another member never sees a Private post",
          all(p["id"] != private_id for p in r.json()["items"]), "leaked into the feed")
    r = await c.get(f"/api/posts/{private_id}", headers=other)
    check("another member cannot fetch it directly -> 403",
          r.status_code == 403, f"{r.status_code} {r.text[:120]}")
    r = await c.get("/api/posts", headers=owner)
    check("the author still sees their own Private post",
          any(p["id"] == private_id for p in r.json()["items"]), "author cannot see it")

    r = await c.get("/api/posts", headers=owner)
    mine = next((p for p in r.json()["items"] if p["id"] == post["id"]), None)
    check("feed carries the attachments", mine and len(mine["attachments"]) == 2,
          str(mine)[:180] if mine else "post missing from feed")

    print("\nMedia ownership")
    r = await c.get("/api/media", headers=owner)
    check("owner lists their uploads", r.status_code == 200 and r.json()["total"] >= 2,
          r.text[:140])
    r = await c.delete(f"/api/media/{image['id']}", headers=other)
    check("cannot delete someone else's upload -> 404", r.status_code == 404, str(r.status_code))
    r = await c.delete(f"/api/media/{image['id']}", headers=owner)
    check("cannot delete a file that is attached -> 409",
          r.status_code == 409, f"{r.status_code} {r.text[:140]}")

    r = await c.post("/api/media", headers=owner,
                     files={"file": ("spare.png", png_bytes(), "image/png")})
    spare = r.json()
    r = await c.delete(f"/api/media/{spare['id']}", headers=owner)
    check("unattached file deletes", r.status_code == 200, f"{r.status_code} {r.text[:140]}")
    r = await c.get(spare["url"])
    check("deleted file is gone from disk", r.status_code == 404, str(r.status_code))

    print("\nHome rails")
    r = await c.get("/api/me/stats", headers=owner)
    check("GET /api/me/stats", r.status_code == 200 and "connections" in r.json(), r.text[:140])

    r = await c.get("/api/communities/suggested", headers=owner)
    suggested = r.json() if r.status_code == 200 else []
    check("GET /api/communities/suggested", r.status_code == 200, r.text[:140])
    check("suggestions default to 3", len(suggested) <= 3, str(len(suggested)))
    check("never suggests one you already joined",
          all(not s["joined"] for s in suggested), str(suggested)[:180])
    check("never suggests an invite-only community",
          all(s["join_policy"] != "invite" for s in suggested), str(suggested)[:180])
    check("'suggested' is not read as a slug",
          not isinstance(suggested, dict), str(suggested)[:100])

    r = await c.get("/api/members/suggested", headers=owner)
    people = r.json() if r.status_code == 200 else []
    check("GET /api/members/suggested", r.status_code == 200, r.text[:140])
    check("suggestions default to 2", len(people) <= 2, str(len(people)))
    check("never suggests yourself", all(p["id"] != owner_id for p in people), str(people)[:180])
    check("members/suggested is not read as a user id",
          all("id" in p and "name" in p for p in people), str(people)[:180])

    r = await c.get("/api/communities/suggested?limit=1", headers=owner)
    check("limit is honoured", len(r.json()) <= 1, r.text[:140])


async def main() -> None:
    owner, owner_id = await auth_for("vikram.sethi@example.com")
    other, other_id = await auth_for("sarah.whitfield@example.com")

    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        try:
            await run(c, owner, owner_id, other, other_id)
        finally:
            for pid in post_ids:
                await c.delete(f"/api/posts/{pid}", headers=owner)
            for mid in media_ids:
                await c.delete(f"/api/media/{mid}", headers=owner)

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
