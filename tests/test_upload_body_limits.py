import asyncio

from app.request_limits import RequestBodyLimitMiddleware, upload_body_limit


def _run(scope, chunks, app):
    async def run():
        messages = list(chunks)
        sent = []

        async def receive():
            if messages:
                return messages.pop(0)
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        await RequestBodyLimitMiddleware(app)(scope, receive, send)
        return sent

    return asyncio.run(run())


def _scope(path, headers=()):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": list(headers),
        "client": ("127.0.0.1", 12345),
        "server": ("example.test", 443),
    }


async def _consume_body(scope, receive, send):
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def test_upload_limits_preserve_supported_workflows():
    assert upload_body_limit("/api/documents") == 12 * 1024 * 1024
    assert upload_body_limit("/api/documents/public-id/resubmit") == 12 * 1024 * 1024
    assert upload_body_limit("/api/tasks/42/submit") == 12 * 1024 * 1024
    assert upload_body_limit("/api/tasks/batches") == 64 * 1024 * 1024
    assert upload_body_limit("/api/bca/students/import") == 512 * 1024
    assert upload_body_limit("/api/bca/students/import-excel") == 512 * 1024
    assert upload_body_limit("/api/bca/showcase/me/photo") == 256 * 1024
    assert upload_body_limit("/api/tasks") is None


def test_chunked_upload_over_limit_is_rejected_before_route_response(monkeypatch):
    import app.request_limits as request_limits

    monkeypatch.setitem(request_limits.UPLOAD_BODY_LIMITS, "/api/documents", 4)
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True
        await _consume_body(scope, receive, send)

    sent = _run(
        _scope("/api/documents"),
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ],
        downstream,
    )

    assert called
    assert sent[0]["status"] == 413
    assert b"exceeds the permitted size" in sent[1]["body"]
    assert not any(message["type"] == "http.response.start" and message.get("status") == 200
                   for message in sent)


def test_content_length_over_limit_is_rejected_without_calling_route(monkeypatch):
    import app.request_limits as request_limits

    monkeypatch.setitem(request_limits.UPLOAD_BODY_LIMITS, "/api/documents", 4)
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    sent = _run(
        _scope("/api/documents", [(b"content-length", b"5")]),
        [],
        downstream,
    )

    assert not called
    assert sent[0]["status"] == 413


def test_exact_stream_limit_is_accepted(monkeypatch):
    import app.request_limits as request_limits

    monkeypatch.setitem(request_limits.UPLOAD_BODY_LIMITS, "/api/documents", 4)
    sent = _run(
        _scope("/api/documents"),
        [{"type": "http.request", "body": b"1234", "more_body": False}],
        _consume_body,
    )

    assert sent[0]["status"] == 200


def test_malformed_content_length_returns_bad_request():
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    sent = _run(
        _scope("/api/documents", [(b"content-length", b"many")]),
        [],
        downstream,
    )

    assert not called
    assert sent[0]["status"] == 400
