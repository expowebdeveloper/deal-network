"""Saving uploaded files to disk safely.

Rules enforced here:
  * only allow-listed types — checked against both the declared content type and
    the file's magic bytes, so renaming evil.html to photo.png does not get through;
  * SVG is refused outright (it can carry script and would run on our origin);
  * the stored filename is random, so a crafted name cannot escape the directory
    or overwrite anything;
  * size is capped as the file is read here.

Note on the size cap: this runs *after* FastAPI has parsed the multipart body, so
by itself it cannot stop a huge upload from being spooled to the temp directory
first. `BodySizeLimitMiddleware` in core/limits.py rejects oversized bodies before
they are parsed; this check is the second line of defence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.models.base import MediaKind

CHUNK = 64 * 1024

# content type -> (extension, kind)
ALLOWED: dict[str, tuple[str, MediaKind]] = {
    "image/jpeg": (".jpg", MediaKind.image),
    "image/png": (".png", MediaKind.image),
    "image/gif": (".gif", MediaKind.image),
    "image/webp": (".webp", MediaKind.image),
    "application/pdf": (".pdf", MediaKind.document),
    "text/plain": (".txt", MediaKind.document),
    "text/csv": (".csv", MediaKind.document),
    "application/msword": (".doc", MediaKind.document),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        (".docx", MediaKind.document),
    "application/vnd.ms-excel": (".xls", MediaKind.document),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        (".xlsx", MediaKind.document),
}

# Leading bytes we insist on for the formats that have a stable signature.
MAGIC: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF-",),
    # OOXML files are zip archives.
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (b"PK\x03\x04",),
    "application/msword": (b"\xd0\xcf\x11\xe0",),
    "application/vnd.ms-excel": (b"\xd0\xcf\x11\xe0",),
}


class UploadError(Exception):
    """Raised for anything the caller did wrong — surfaces as a 4xx."""


@dataclass(slots=True)
class StoredFile:
    stored_name: str
    original_name: str
    content_type: str
    kind: MediaKind
    size_bytes: int


def _limit_for(kind: MediaKind) -> int:
    return settings.max_image_bytes if kind is MediaKind.image else settings.max_document_bytes


def _safe_original_name(name: str | None) -> str:
    """Keep only the basename, and only for display."""
    if not name:
        return "upload"
    cleaned = Path(name).name.replace("\x00", "").strip()
    return cleaned[:255] or "upload"


async def save_upload(upload: UploadFile) -> StoredFile:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()

    if content_type in {"image/svg+xml", "text/html", "application/xhtml+xml"}:
        raise UploadError("That file type is not allowed because it can contain scripts")
    if content_type not in ALLOWED:
        raise UploadError(
            f"Unsupported file type '{content_type or 'unknown'}'. "
            "Allowed: JPEG, PNG, GIF, WebP, PDF, TXT, CSV, DOC(X), XLS(X)."
        )

    extension, kind = ALLOWED[content_type]
    limit = _limit_for(kind)

    directory = settings.upload_path
    directory.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = directory / stored_name

    size = 0
    first_chunk = b""
    try:
        with destination.open("wb") as handle:
            while chunk := await upload.read(CHUNK):
                if not first_chunk:
                    first_chunk = chunk
                    expected = MAGIC.get(content_type)
                    if expected and not chunk.startswith(expected):
                        raise UploadError(
                            f"File contents do not look like {content_type}"
                        )
                size += len(chunk)
                if size > limit:
                    raise UploadError(
                        f"File is larger than the {limit // (1024 * 1024)}MB limit"
                    )
                handle.write(chunk)
    except UploadError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise UploadError("Could not store the file") from exc

    if size == 0:
        destination.unlink(missing_ok=True)
        raise UploadError("File is empty")

    return StoredFile(
        stored_name=stored_name,
        original_name=_safe_original_name(upload.filename),
        content_type=content_type,
        kind=kind,
        size_bytes=size,
    )


def delete_stored(stored_name: str) -> None:
    """Remove a file, ignoring anything that is not a plain name in the upload dir."""
    if not stored_name or "/" in stored_name or "\\" in stored_name or ".." in stored_name:
        return
    (settings.upload_path / stored_name).unlink(missing_ok=True)
