from __future__ import annotations

from collections.abc import Callable

import pytest

from conftest import FakeLMS
from lms_mcp.context import ServerContext
from lms_mcp.players import PlayerNotFound

KITCHEN = "aa:bb:cc:dd:ee:01"
LIVING = "aa:bb:cc:dd:ee:02"


async def test_resolves_a_name_case_insensitively(make_ctx: Callable[..., ServerContext]):
    ctx = make_ctx()
    assert await ctx.player_id("kitchen") == KITCHEN


async def test_resolves_a_player_id_without_querying(make_ctx: Callable[..., ServerContext], lms: FakeLMS):
    ctx = make_ctx()
    assert await ctx.player_id(LIVING) == LIVING
    assert lms.calls == []


async def test_falls_back_to_the_default_player(make_ctx: Callable[..., ServerContext]):
    ctx = make_ctx(default_player="Living Room")
    assert await ctx.player_id(None) == LIVING


async def test_unique_partial_names_match(make_ctx: Callable[..., ServerContext]):
    ctx = make_ctx()
    assert await ctx.player_id("living") == LIVING


async def test_missing_player_lists_the_options(make_ctx: Callable[..., ServerContext]):
    ctx = make_ctx()
    with pytest.raises(PlayerNotFound, match="Kitchen"):
        await ctx.player_id(None)


async def test_unknown_name_lists_the_options(make_ctx: Callable[..., ServerContext]):
    ctx = make_ctx()
    with pytest.raises(PlayerNotFound, match="No player named 'Study'"):
        await ctx.player_id("Study")


async def test_ambiguous_partial_name_is_rejected(make_ctx: Callable[..., ServerContext], lms: FakeLMS):
    lms.reply(
        "serverstatus",
        {
            "players_loop": [
                {"playerid": "aa:bb:cc:dd:ee:03", "name": "Office Left"},
                {"playerid": "aa:bb:cc:dd:ee:04", "name": "Office Right"},
            ]
        },
    )
    ctx = make_ctx()
    with pytest.raises(PlayerNotFound, match="ambiguous"):
        await ctx.player_id("Office")


async def test_the_player_list_is_cached(make_ctx: Callable[..., ServerContext], lms: FakeLMS):
    ctx = make_ctx()
    await ctx.player_id("Kitchen")
    await ctx.player_id("Living Room")
    assert len(lms.calls) == 1


async def test_a_stale_cache_is_refreshed_for_an_unknown_name(
    make_ctx: Callable[..., ServerContext], lms: FakeLMS
):
    ctx = make_ctx()
    await ctx.player_id("Kitchen")
    lms.reply("serverstatus", {"players_loop": [{"playerid": "aa:bb:cc:dd:ee:09", "name": "Study"}]})
    assert await ctx.player_id("Study") == "aa:bb:cc:dd:ee:09"
