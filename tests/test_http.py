from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2 as httpx
from starlette.applications import Starlette

from conftest import FakeLMS
from lms_mcp.config import Config
from lms_mcp.context import ServerContext
from lms_mcp.http import create_app

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-06-18",
}


@asynccontextmanager
async def client_for(app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    """Serve the app in-process, running its lifespan so the session manager starts."""
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


@asynccontextmanager
async def serving(ctx: ServerContext) -> AsyncIterator[httpx.AsyncClient]:
    async with client_for(create_app(ctx=ctx)) as client:
        yield client


async def rpc(client: httpx.AsyncClient, method: str, params: Any = None, token: str | None = "secret-token"):
    headers = dict(MCP_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return await client.post("/mcp", json=body, headers=headers)


async def test_health_is_ok_when_lyrion_answers(ctx: ServerContext, lms: FakeLMS):
    async with serving(ctx) as client:
        lms.reply("version", {"_version": "9.0.1"})
        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["lms"] == {"url": "http://lyrion.local:9000", "reachable": True, "version": "9.0.1"}
        assert body["uptime_s"] >= 0


async def test_health_is_degraded_when_lyrion_is_down(config: Config):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    from lms_mcp.client import LMSClient

    ctx = ServerContext.create(config, LMSClient(config, transport=httpx.MockTransport(boom)))
    async with serving(ctx) as client:
        response = await client.get("/health")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
        assert "connection refused" in response.json()["lms"]["error"]


async def test_health_needs_no_token(ctx: ServerContext):
    async with serving(ctx) as client:
        assert (await client.get("/health")).status_code in (200, 503)


async def test_health_is_cached(ctx: ServerContext, lms: FakeLMS):
    async with serving(ctx) as client:
        await client.get("/health")
        await client.get("/health")
        assert lms.commands.count(["version", "?"]) == 1


async def test_mcp_requires_a_token(ctx: ServerContext):
    async with serving(ctx) as client:
        response = await rpc(client, "tools/list", token=None)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Bearer")


async def test_mcp_rejects_a_wrong_token(ctx: ServerContext):
    async with serving(ctx) as client:
        assert (await rpc(client, "tools/list", token="nope")).status_code == 401


async def test_initialize_reports_the_server(ctx: ServerContext):
    async with serving(ctx) as client:
        response = await rpc(
            client,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"},
            },
        )
        assert response.status_code == 200
        assert response.json()["result"]["serverInfo"]["name"] == "lms-mcp"


async def test_tools_list_returns_the_lms_tools(ctx: ServerContext):
    async with serving(ctx) as client:
        response = await rpc(client, "tools/list")
        tools = response.json()["result"]["tools"]

        assert len(tools) > 80
        assert all(tool["name"].startswith("lms_") for tool in tools)
        assert "lms_play" in {tool["name"] for tool in tools}


async def test_tools_call_reaches_lyrion(ctx: ServerContext, lms: FakeLMS):
    async with serving(ctx) as client:
        response = await rpc(client, "tools/call", {"name": "lms_set_volume", "arguments": {"volume": 25}})

        assert response.status_code == 200
        assert lms.last == ("aa:bb:cc:dd:ee:01", ["mixer", "volume", "25"])


async def test_a_lyrion_failure_is_reported_as_a_tool_error(ctx: ServerContext, lms: FakeLMS):
    async with serving(ctx) as client:
        lms.error = "unknown command"
        response = await rpc(client, "tools/call", {"name": "lms_play", "arguments": {}})

        result = response.json()["result"]
        assert result["isError"] is True
        assert "unknown command" in str(result["content"])


async def test_anonymous_mode_serves_without_a_token(config: Config, lms: FakeLMS):
    from lms_mcp.client import LMSClient

    anonymous = Config(**{**config.__dict__, "auth_token": None, "allow_anonymous": True})
    ctx = ServerContext.create(anonymous, LMSClient(anonymous, transport=lms.transport))
    async with serving(ctx) as client:
        assert (await rpc(client, "tools/list", token=None)).status_code == 200
