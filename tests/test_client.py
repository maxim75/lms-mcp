from __future__ import annotations

import pytest

from conftest import FakeLMS
from lms_mcp.client import LMSClient, encode_command
from lms_mcp.config import Config
from lms_mcp.errors import LMSCommandError, LMSConnectionError


def test_encode_command_stringifies_and_appends_tags():
    assert encode_command(["status", 0, 50], {"tags": "al", "search": None, "want_url": True}) == [
        "status",
        "0",
        "50",
        "tags:al",
        "want_url:1",
    ]


async def test_request_frames_a_slim_request(lms: FakeLMS, config: Config):
    client = LMSClient(config, transport=lms.transport)
    lms.reply("mixer", {"_volume": 42})

    result = await client.request("aa:bb:cc:dd:ee:01", ["mixer", "volume", "?"])

    assert result == {"_volume": 42}
    assert lms.last == ("aa:bb:cc:dd:ee:01", ["mixer", "volume", "?"])


async def test_server_commands_send_an_empty_player(lms: FakeLMS, config: Config):
    client = LMSClient(config, transport=lms.transport)
    await client.request(None, ["version", "?"])
    assert lms.last[0] == ""


async def test_http_error_becomes_a_connection_error(lms: FakeLMS, config: Config):
    lms.status_code = 500
    client = LMSClient(config, transport=lms.transport)
    with pytest.raises(LMSConnectionError, match="HTTP 500"):
        await client.request(None, ["version", "?"])


async def test_jsonrpc_error_becomes_a_command_error(lms: FakeLMS, config: Config):
    lms.error = "unknown command"
    client = LMSClient(config, transport=lms.transport)
    with pytest.raises(LMSCommandError, match="unknown command"):
        await client.request(None, ["bogus"])


async def test_unreachable_server_becomes_a_connection_error(config: Config):
    import httpx2 as httpx

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    client = LMSClient(config, transport=httpx.MockTransport(boom))
    with pytest.raises(LMSConnectionError, match="cannot reach Lyrion server"):
        await client.request(None, ["version", "?"])


async def test_basic_auth_header_is_sent(lms: FakeLMS):
    config = Config.from_env({"MCP_AUTH_TOKEN": "t", "LMS_USERNAME": "user", "LMS_PASSWORD": "pw"})
    seen: list[str | None] = []

    import httpx2 as httpx

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return lms.handler(request)

    client = LMSClient(config, transport=httpx.MockTransport(handler))
    await client.request(None, ["version", "?"])
    assert seen[0] is not None and seen[0].startswith("Basic ")
