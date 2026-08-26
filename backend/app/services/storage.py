"""Saving uploaded files to disk safely.

Rules enforced here:
  * only allow-listed types — checked against both the declared content type and
    the file's magic bytes, so renaming evil.html to photo.png does not get through;
  * executables and archives are refused by name, and by extension too, so the
    member is told what the problem is rather than "unsupported type";
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
    # Video. MP4 and WebM cover every current browser; QuickTime is what an
    # iPhone hands over, and the browser labels it video/quicktime.
    "video/mp4": (".mp4", MediaKind.video),
    "video/webm": (".webm", MediaKind.video),
    "video/quicktime": (".mov", MediaKind.video),
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
    # MP4 and MOV are ISO base media files: the 'ftyp' box starts at byte 4,
    # behind a four-byte length. WebM is Matroska, whose EBML header is at 0.
    "video/mp4": (b"ftyp",),
    "video/quicktime": (b"ftyp",),
    "video/webm": (b"\x1a\x45\xdf\xa3",),
}

#: Where the signature sits, for the formats that do not start with it.
MAGIC_OFFSET: dict[str, int] = {
    "video/mp4": 4,
    "video/quicktime": 4,
}

#: Refused by name so the message can say why, rather than falling through to
#: the generic "unsupported type". Executables and archives are the two things
#: members actually try to attach, and neither is something this product should
#: pass between accounts — an archive also hides its contents from every check
#: above it.
BLOCKED: dict[str, str] = {
    "application/x-msdownload": "executable",
    "application/x-msdos-program": "executable",
    "application/vnd.microsoft.portable-executable": "executable",
    "application/x-executable": "executable",
    "application/x-sh": "executable",
    "application/x-msi": "executable",
    "application/zip": "archive",
    "application/x-zip-compressed": "archive",
    "application/x-rar-compressed": "archive",
    "application/vnd.rar": "archive",
    "application/x-7z-compressed": "archive",
    "application/x-tar": "archive",
    "application/gzip": "archive",
}

#: Extensions refused whatever content type is claimed, because a browser will
#: happily send application/octet-stream — or nothing at all — for these.
BLOCKED_EXTENSIONS: dict[str, str] = {
    ".exe": "executable", ".msi": "executable", ".bat": "executable",
    ".cmd": "executable", ".com": "executable", ".scr": "executable",
    ".sh": "executable", ".app": "executable", ".dll": "executable",
    ".zip": "archive", ".rar": "archive", ".7z": "archive",
    ".tar": "archive", ".gz": "archive", ".tgz": "archive",
}


#: Which .env ceiling applies to each kind. A video is allowed to be bigger than
#: an image without loosening the limit on either.
PER_KIND_SETTING: dict[MediaKind, str] = {
    MediaKind.image: "max_image_bytes",
    MediaKind.video: "max_video_bytes",
    MediaKind.document: "max_document_bytes",
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


def _limit_for(kind: MediaKind, plan_ceiling: int | None = None) -> int:
    """The size cap for one upload.

    Two ceilings apply and the smaller wins: the per-type cap from .env
    (MAX_IMAGE_BYTES / MAX_VIDEO_BYTES / MAX_DOCUMENT_BYTES, which keep a file
    sane regardless of tier) and the plan's
    `files.max_file_size_bytes` from the entitlement service. Passing None for
    `plan_ceiling` means "unlimited plan", in which case the .env cap stands
    alone — never the other way round, so a generous plan cannot be used to slip
    past the deployment's own limit.
    """
    base = getattr(settings, PER_KIND_SETTING[kind])
    if plan_ceiling is None:
        return base
    return min(base, plan_ceiling)


def _safe_original_name(name: str | None) -> str:
    """Keep only the basename, and only for display."""
    if not name:
        return "upload"
    cleaned = Path(name).name.replace("\x00", "").strip()
    return cleaned[:255] or "upload"


async def save_upload(upload: UploadFile, *, plan_ceiling: int | None = None) -> StoredFile:
    """Stream one upload to disk, enforcing type and size.

    `plan_ceiling` is the member's per-file entitlement; the effective cap is
    the smaller of it and the per-type cap from .env. This is the check that
    counts, because it measures the bytes actually written rather than trusting
    a declared Content-Length.
    """
    content_type = (upload.content_type or "").split(";")[0].strip().lower()

    suffix = Path(upload.filename or "").suffix.lower()

    if content_type in {"image/svg+xml", "text/html", "application/xhtml+xml"}:
        raise UploadError("That file type is not allowed because it can contain scripts")

    # Named refusals first, so "why not?" has a real answer. The extension is
    # checked as well as the type: a browser sends application/octet-stream for
    # plenty of things, and that would otherwise fall through to the generic
    # message without ever naming the problem.
    blocked = BLOCKED.get(content_type) or BLOCKED_EXTENSIONS.get(suffix)
    if blocked:
        noun = "Executable files" if blocked == "executable" else "Archives"
        why = (
            "they can run code on whoever opens them"
            if blocked == "executable"
            else "their contents cannot be checked"
        )
        raise UploadError(f"{noun} cannot be attached, because {why}.")

    if content_type not in ALLOWED:
        raise UploadError(
            f"Unsupported file type '{content_type or 'unknown'}'. "
            "Allowed: images (JPEG, PNG, GIF, WebP), video (MP4, WebM, MOV), "
            "PDF, TXT, CSV, DOC(X) and XLS(X)."
        )

    extension, kind = ALLOWED[content_type]
    limit = _limit_for(kind, plan_ceiling)

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
                    if expected:
                        at = MAGIC_OFFSET.get(content_type, 0)
                        window = chunk[at:at + max(len(sig) for sig in expected)]
                        if not any(window.startswith(sig) for sig in expected):
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
