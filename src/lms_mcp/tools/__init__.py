"""Tool registration for every LMS command family."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..context import ServerContext
from . import (
    alarms,
    apps,
    favorites,
    library,
    mixer,
    playback,
    player,
    queue,
    randomplay,
    server_cmds,
)
from ._registry import Registrar

MODULES = (
    server_cmds,
    player,
    playback,
    mixer,
    queue,
    library,
    favorites,
    alarms,
    randomplay,
    apps,
)


def register_all(server: MCPServer[Any], ctx: ServerContext) -> None:
    tool = Registrar(server, ctx)
    for module in MODULES:
        module.register(tool, ctx)
