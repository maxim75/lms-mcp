"""Properties every registered tool must satisfy."""

from __future__ import annotations

import pytest

from helpers import build_server
from lms_mcp.context import ServerContext

DESTRUCTIVE_TOOLS = {
    "lms_set_pref",
    "lms_wipe_cache",
    "lms_server_restart",
    "lms_server_stop",
    "lms_saved_playlist_delete",
    "lms_favorites_delete",
}


@pytest.fixture
async def tools(ctx: ServerContext):
    return await build_server(ctx).list_tools()


async def test_every_tool_is_prefixed_and_documented(tools):
    for tool in tools:
        assert tool.name.startswith("lms_"), tool.name
        assert tool.description, tool.name
        assert tool.annotations is not None, tool.name


async def test_tool_names_are_unique(tools):
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names))


async def test_every_tool_has_an_object_input_schema(tools):
    for tool in tools:
        assert tool.input_schema["type"] == "object", tool.name


async def test_every_tool_returns_structured_output(tools):
    for tool in tools:
        assert tool.output_schema is not None, tool.name


async def test_read_only_tools_are_marked(tools):
    by_name = {tool.name: tool for tool in tools}
    for name in ("lms_list_players", "lms_player_status", "lms_search", "lms_get_queue"):
        assert by_name[name].annotations.read_only_hint is True, name
    assert by_name["lms_play"].annotations.read_only_hint is False


async def test_destructive_tools_are_hidden_by_default(tools):
    assert DESTRUCTIVE_TOOLS.isdisjoint({tool.name for tool in tools})


async def test_destructive_tools_appear_when_enabled(make_ctx):
    ctx = make_ctx(default_player="Kitchen", enable_destructive=True)
    tools = await build_server(ctx).list_tools()
    names = {tool.name for tool in tools}

    assert DESTRUCTIVE_TOOLS <= names
    for name in DESTRUCTIVE_TOOLS:
        annotations = next(tool for tool in tools if tool.name == name).annotations
        assert annotations.destructive_hint is True, name


async def test_player_tools_accept_an_optional_player(tools):
    by_name = {tool.name: tool for tool in tools}
    for name in ("lms_play", "lms_set_volume", "lms_get_queue"):
        schema = by_name[name].input_schema
        assert "player" in schema["properties"], name
        assert "player" not in schema.get("required", []), name
