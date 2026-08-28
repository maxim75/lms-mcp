"""The ASGI application: MCP over Streamable HTTP, plus an unauthenticated /health."""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from . import __version__
from .config import Config
from .context import ServerContext
from .errors import LMSError
from .tools import register_all

logger = logging.getLogger(__name__)

HEALTH_PATH = "/health"
HEALTH_CACHE_SECONDS = 5.0
HEALTH_TIMEOUT_SECONDS = 3.0

INSTRUCTIONS = """\
Controls a Lyrion Music Server (formerly Logitech Media Server) and the players
attached to it.

Most tools take an optional `player` argument accepting either a player name
("Kitchen") or a player id (a MAC address); when it is omitted the server's
configured default player is used. Call lms_list_players first if you are unsure
what exists.

To play something from the library: find it with lms_search or the lms_list_*
tools, then pass the id you got back to lms_play_item with the matching `kind`.
"""


class HealthProbe:
    """Caches the result of a cheap LMS ping so health checks cannot flood the server."""

    def __init__(self, ctx: ServerContext, ttl: float = HEALTH_CACHE_SECONDS) -> None:
        self._ctx = ctx
        self._ttl = ttl
        self._checked_at = 0.0
        self._payload: dict[str, Any] = {"reachable": False, "error": "not checked yet"}
        self._started = time.monotonic()

    @property
    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self._started, 1)

    async def check(self) -> dict[str, Any]:
        now = time.monotonic()
        if now - self._checked_at < self._ttl:
            return self._payload
        try:
            result = await self._ctx.client.request(None, ["version", "?"], timeout=HEALTH_TIMEOUT_SECONDS)
            version = result.get("_version") or next(iter(result.values()), None)
            self._payload = {"reachable": True, "version": version}
        except LMSError as exc:
            self._payload = {"reachable": False, "error": str(exc)}
        except Exception as exc:  # a bug here must not take the health endpoint down
            logger.exception("health probe failed")
            self._payload = {"reachable": False, "error": repr(exc)}
        self._checked_at = now
        return self._payload


class BearerAuthMiddleware:
    """Requires `Authorization: Bearer <token>` on everything except the exempt paths."""

    def __init__(self, app: Callable[..., Awaitable[None]], token: str | None, exempt: set[str]) -> None:
        self.app = app
        self.token = token
        self.exempt = exempt

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.token is None or scope.get("path") in self.exempt:
            await self.app(scope, receive, send)
            return

        if self._authorized(scope):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            {"error": "unauthorized", "detail": "Provide Authorization: Bearer <token>"},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="lms-mcp"'},
        )
        await response(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        for key, value in scope.get("headers") or []:
            if key.lower() != b"authorization":
                continue
            header = value.decode("latin-1")
            scheme, _, presented = header.partition(" ")
            if scheme.lower() != "bearer":
                return False
            return secrets.compare_digest(presented.strip(), self.token or "")
        return False


def create_server(ctx: ServerContext) -> MCPServer[None]:
    """Build the MCP server: every tool, plus the /health route."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[None]) -> AsyncIterator[None]:
        try:
            yield None
        finally:
            await ctx.aclose()

    server: MCPServer[None] = MCPServer(
        "lms-mcp",
        title="Lyrion Music Server",
        version=__version__,
        instructions=INSTRUCTIONS,
        log_level=ctx.config.log_level,  # type: ignore[arg-type]
        lifespan=lifespan,
    )
    register_all(server, ctx)

    probe = HealthProbe(ctx)

    @server.custom_route(HEALTH_PATH, methods=["GET"])
    async def health(_: Request) -> Response:
        lms = await probe.check()
        healthy = bool(lms.get("reachable"))
        return JSONResponse(
            {
                "status": "ok" if healthy else "degraded",
                "version": __version__,
                "uptime_s": probe.uptime_seconds,
                "lms": {"url": ctx.config.lms_base_url, **lms},
            },
            status_code=200 if healthy else 503,
        )

    return server


def create_app(config: Config | None = None, ctx: ServerContext | None = None) -> Starlette:
    """Build the ASGI application to hand to uvicorn."""
    cfg = config or (ctx.config if ctx else Config.from_env())
    context = ctx or ServerContext.create(cfg)
    server = create_server(context)

    security = (
        TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=cfg.allowed_hosts,
            allowed_origins=cfg.allowed_hosts,
        )
        if cfg.allowed_hosts
        else None
    )

    app = server.streamable_http_app(
        streamable_http_path=cfg.mcp_path,
        json_response=True,
        stateless_http=True,
        transport_security=security,
        host=cfg.mcp_host,
    )
    app.add_middleware(BearerAuthMiddleware, token=cfg.auth_token, exempt={HEALTH_PATH})
    return app
