"""Small ASGI middleware: safe errors, host checks and secret-free request logs."""
import logging
import time
from urllib.parse import urlsplit
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.api.exceptions import error_response

logger = logging.getLogger("hopfan.api")


class RequestBodyLimitMiddleware:
    """Bound JSON/image uploads before parsing; never logs request bodies."""
    def __init__(self, app: ASGIApp, limit: int = 12 * 1024 * 1024):
        self.app,self.limit=app,limit
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"]!="http" or scope["method"] not in {"POST","PATCH","PUT"}:
            return await self.app(scope,receive,send)
        headers=Headers(scope=scope)
        try:length=int(headers.get("content-length","0"))
        except ValueError:length=0
        if length>self.limit:
            return await error_response(413,"REQUEST_TOO_LARGE","The request exceeds the allowed size.")(scope,receive,send)
        chunks=[];total=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect":return
            body=message.get("body",b"");total+=len(body)
            if total>self.limit:
                return await error_response(413,"REQUEST_TOO_LARGE","The request exceeds the allowed size.")(scope,receive,send)
            chunks.append(body)
            if not message.get("more_body",False):break
        replayed=False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed=True
                return {"type":"http.request","body":b"".join(chunks),"more_body":False}
            return await receive()
        await self.app(scope,replay,send)


class SafeErrorMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_response(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception:
            # Never pass a raw exception to Uvicorn's traceback logger. A response
            # already sent cannot be replaced; report that failure without detail.
            scope.setdefault("state", {})["api_failed"] = True
            if not started:
                await error_response(500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred.")(
                    scope, receive, send
                )


class AllowedHostMiddleware:
    def __init__(self, app: ASGIApp, allowed_hosts: tuple[str, ...]) -> None:
        self.app = app
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            hosts = Headers(scope=scope).getlist("host")
            valid = False
            if len(hosts) == 1:
                try:
                    host = urlsplit("//" + hosts[0])
                    valid = (
                        host.hostname in self.allowed_hosts and host.port != 0
                        and not host.username and not host.password
                        and not host.path and not host.query and not host.fragment
                        and not any(char.isspace() for char in hosts[0])
                    )
                except ValueError:
                    pass
            if not valid:
                await error_response(400, "INVALID_HOST", "The request host is not allowed.")(scope, receive, send)
                return
        await self.app(scope, receive, send)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = time.perf_counter()
        status = 500

        async def send_response(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Frame-Options"] = "DENY"
                headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        finally:
            # Log the registered route template, never raw query/path parameters.
            # Unknown URLs can contain secrets, so their path is redacted.
            route_path = getattr(scope.get("route"), "path", "/<unmatched>")
            method = scope["method"] if scope["method"] in {
                "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"
            } else "OTHER"
            log = logger.error if scope["state"].get("api_failed") or status >= 500 else logger.info
            log("request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id, method, route_path, status,
                (time.perf_counter() - started_at) * 1000)
