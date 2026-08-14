"""Request body size limit.

This has to be pure ASGI middleware, not a route dependency or a check inside the
upload handler. FastAPI parses the whole multipart body (`await request.form()`)
*before* it resolves dependencies, so by the time either the auth dependency or
`storage.save_upload` runs, Starlette has already spooled the entire file to the
temp directory. An anonymous client could therefore push arbitrarily many bytes
onto the disk and only then receive a 401.

Running ahead of routing means we can reject on Content-Length, and also count
bytes as they arrive for chunked bodies where no length is declared.
"""

from __future__ import annotations

import logging

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        declared = headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await self._reject(scope, send)
                    return
            except ValueError:
                pass  # malformed header — let the byte counter below handle it

        received = 0
        too_large = False

        async def counting_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    # Stop the stream so the parser cannot keep buffering.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            # If we cut the body short the app will error; make sure the client
            # is told why rather than getting a confusing 400/500.
            if too_large and message["type"] == "http.response.start":
                message = {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", b"48"),
                    ],
                }
            elif too_large and message["type"] == "http.response.body":
                message = {"type": "http.response.body", "body": _PAYLOAD, "more_body": False}
            await send(message)

        await self.app(scope, counting_receive, guarded_send)

    async def _reject(self, scope: Scope, send: Send) -> None:
        logger.warning(
            "Rejected oversized body on %s %s", scope.get("method"), scope.get("path")
        )
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_PAYLOAD)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": _PAYLOAD})


_PAYLOAD = b'{"detail":"Request body is too large"}'
