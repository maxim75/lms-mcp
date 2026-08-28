"""Test helpers: build a server with every tool registered and call tools directly."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from lms_mcp.context import ServerContext
from lms_mcp.tools import register_all


def build_server(ctx: ServerContext) -> MCPServer[None]:
    server: MCPServer[None] = MCPServer("lms-mcp-test")
    register_all(server, ctx)
    return server


async def call(ctx: ServerContext, tool_name: str, /, **arguments: Any) -> Any:
    """Invoke a tool through the MCP layer and return its structured result."""
    result = await build_server(ctx).call_tool(tool_name, arguments)
    return getattr(result, "structured_content", None) or result
