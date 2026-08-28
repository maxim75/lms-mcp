"""Helper for registering tools with consistent naming and annotations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from ..context import ServerContext

F = TypeVar("F", bound=Callable[..., Any])

TOOL_PREFIX = "lms_"


class Registrar:
    """Registers tools on the server, applying the `lms_` prefix and annotations.

    Tools flagged `destructive=True` are only registered when the deployment opted
    in with `LMS_ENABLE_DESTRUCTIVE=true`.
    """

    def __init__(self, server: MCPServer[Any], ctx: ServerContext) -> None:
        self.server = server
        self.ctx = ctx

    def __call__(
        self,
        name: str,
        title: str,
        *,
        read_only: bool = False,
        destructive: bool = False,
        idempotent: bool | None = None,
        open_world: bool = False,
    ) -> Callable[[F], F]:
        def decorator(fn: F) -> F:
            if destructive and not self.ctx.config.enable_destructive:
                return fn
            tool_name = name if name.startswith(TOOL_PREFIX) else TOOL_PREFIX + name
            self.server.add_tool(
                fn,
                name=tool_name,
                title=title,
                description=(fn.__doc__ or title).strip(),
                annotations=ToolAnnotations(
                    title=title,
                    readOnlyHint=read_only,
                    destructiveHint=destructive,
                    idempotentHint=idempotent if idempotent is not None else read_only,
                    openWorldHint=open_world,
                ),
            )
            return fn

        return decorator
