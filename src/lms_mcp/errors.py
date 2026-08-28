"""Errors raised by the LMS layer.

These subclass the SDK's `ToolError`, so a failure the tool anticipated (server
unreachable, unknown player, command rejected) reaches the model as a readable
message instead of a generic crash, with no wrapper around the tool functions.
"""

from __future__ import annotations

from mcp.server.mcpserver.exceptions import ToolError


class LMSError(ToolError):
    """Base error for anything that goes wrong talking to Lyrion Music Server."""


class LMSConnectionError(LMSError):
    """The server could not be reached, timed out, or returned a bad HTTP status."""


class LMSCommandError(LMSError):
    """LMS accepted the request but rejected or failed the command."""
