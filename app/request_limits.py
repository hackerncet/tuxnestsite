"""Streaming request-body limits for multipart upload routes."""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

MiB = 1024 * 1024

# These caps include multipart framing and form fields. Individual file limits
# remain enforced by the route handlers in app.storage and their own validators.
UPLOAD_BODY_LIMITS = {
    "/api/documents": 12 * MiB,
    "/api/tasks/batches": 64 * MiB,  # endpoint accepts up to 60 MiB of files
    "/api/bca/students/import": 512 * 1024,
    "/api/bca/students/import-excel": 512 * 1024,
    "/api/bca/showcase/me/photo": 256 * 1024,
}
TASK_SUBMISSION_LIMIT = 12 * MiB
_DOCUMENT_RESUBMIT = re.compile(r"^/api/documents/[^/]+/resubmit$")
_TASK_SUBMISSION = re.compile(r"^/api/tasks/[0-9]+/submit$")


def upload_body_limit(path: str) -> int | None:
    """Return the maximum HTTP body size for a route that accepts uploads."""
    if path in UPLOAD_BODY_LIMITS:
        return UPLOAD_BODY_LIMITS[path]
    if _DOCUMENT_RESUBMIT.fullmatch(path):
        return UPLOAD_BODY_LIMITS["/api/documents"]
    if _TASK_SUBMISSION.fullmatch(path):
        return TASK_SUBMISSION_LIMIT
    return None


async def _reject(send: Callable[..., Awaitable[None]], status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
            (b"x-content-type-options", b"nosniff"),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class RequestBodyLimitMiddleware:
    """Enforce upload request caps before Starlette parses/spools multipart data.

    Content-Length is rejected early when present. The receive wrapper also
    counts streamed/chunked bodies, so omitting that header does not bypass the
    cap. Ordinary non-upload routes are not affected.
    """

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[dict[str, Any]]],
                       send: Callable[..., Awaitable[None]]) -> None:
        if scope.get("type") != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        limit = upload_body_limit(scope.get("path", ""))
        if limit is None:
            await self.app(scope, receive, send)
            return

        lengths = [value.strip() for name, value in scope.get("headers", [])
                   if name.lower() == b"content-length"]
        if lengths:
            # Multiple or malformed values are invalid; do not let them escape
            # into an int() exception in application middleware.
            if len(lengths) != 1 or not lengths[0].isdigit():
                await _reject(send, 400, "Invalid Content-Length header.")
                return
            if int(lengths[0]) > limit:
                await _reject(send, 413, "Upload request exceeds the permitted size.")
                return

        received = 0
        exceeded = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received, exceeded
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: dict[str, Any]) -> None:
            # Once the limit is crossed, discard any error response produced
            # while the multipart parser unwinds; the outer layer sends one 413.
            if not exceeded:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded:
            await _reject(send, 413, "Upload request exceeds the permitted size.")
