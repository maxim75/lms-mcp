"""A fake Lyrion server: records the CLI commands issued and replays canned results."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest

from lms_mcp.client import LMSClient
from lms_mcp.config import Config
from lms_mcp.context import ServerContext

PLAYERS_RESULT = {
    "count": 2,
    "players_loop": [
        {
            "playerid": "aa:bb:cc:dd:ee:01",
            "name": "Kitchen",
            "modelname": "Squeezelite",
            "ip": "192.168.1.20:1234",
            "connected": 1,
            "power": 1,
            "isplayer": 1,
            "canpoweroff": 1,
        },
        {
            "playerid": "aa:bb:cc:dd:ee:02",
            "name": "Living Room",
            "modelname": "Radio",
            "ip": "192.168.1.21:1234",
            "connected": 1,
            "power": 0,
            "isplayer": 1,
            "canpoweroff": 1,
        },
    ],
}


class FakeLMS:
    """Captures requests and answers them from `responses`, keyed by command prefix."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.responses: dict[tuple[str, ...], dict[str, Any]] = {
            ("serverstatus",): dict(PLAYERS_RESULT),
            ("players",): dict(PLAYERS_RESULT),
        }
        self.status_code = 200
        self.error: str | None = None

    def reply(self, command: tuple[str, ...] | str, result: dict[str, Any]) -> None:
        key = (command,) if isinstance(command, str) else command
        self.responses[key] = result

    @property
    def last(self) -> tuple[str, list[str]]:
        assert self.calls, "no request was made"
        return self.calls[-1]

    @property
    def commands(self) -> list[list[str]]:
        return [command for _, command in self.calls]

    def _lookup(self, command: list[str]) -> dict[str, Any]:
        for length in range(min(3, len(command)), 0, -1):
            key = tuple(command[:length])
            if key in self.responses:
                return self.responses[key]
        return {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["method"] == "slim.request"
        player, command = payload["params"]
        self.calls.append((player, command))
        if self.status_code != 200:
            return httpx.Response(self.status_code, text="nope")
        if self.error is not None:
            return httpx.Response(200, json={"id": payload["id"], "error": self.error})
        return httpx.Response(
            200, json={"id": payload["id"], "method": "slim.request", "result": self._lookup(command)}
        )

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@pytest.fixture
def lms() -> FakeLMS:
    return FakeLMS()


@pytest.fixture
def config() -> Config:
    return Config.from_env({"MCP_AUTH_TOKEN": "secret-token", "LMS_HOST": "lyrion.local"})


@pytest.fixture
def make_ctx(lms: FakeLMS, config: Config) -> Callable[..., ServerContext]:
    def factory(**overrides: Any) -> ServerContext:
        cfg = config
        if overrides:
            cfg = Config(**{**config.__dict__, **overrides})
        return ServerContext.create(cfg, LMSClient(cfg, transport=lms.transport))

    return factory


@pytest.fixture
def ctx(make_ctx: Callable[..., ServerContext]) -> ServerContext:
    return make_ctx(default_player="Kitchen")
