from __future__ import annotations

import pytest

from conftest import FakeLMS
from helpers import call
from lms_mcp.context import ServerContext

KITCHEN = "aa:bb:cc:dd:ee:01"


async def test_play_targets_the_default_player(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_play")
    assert lms.last == (KITCHEN, ["play"])


async def test_play_accepts_a_fade(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_play", fade_seconds=3)
    assert lms.last == (KITCHEN, ["play", "3"])


async def test_pause_forces_the_paused_state(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_pause")
    assert lms.last == (KITCHEN, ["pause", "1"])


async def test_toggle_pause_sends_a_bare_pause(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_toggle_pause")
    assert lms.last == (KITCHEN, ["pause"])


async def test_track_skipping_uses_relative_indexes(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_next_track")
    assert lms.last == (KITCHEN, ["playlist", "index", "+1"])
    await call(ctx, "lms_previous_track")
    assert lms.last == (KITCHEN, ["playlist", "index", "-1"])


@pytest.mark.parametrize(
    ("relative", "seconds", "expected"),
    [(False, 30, "30.0"), (True, 30, "+30.0"), (True, -15, "-15.0")],
)
async def test_seek_builds_absolute_and_relative_positions(
    ctx: ServerContext, lms: FakeLMS, relative: bool, seconds: float, expected: str
):
    await call(ctx, "lms_seek", seconds=seconds, relative=relative)
    assert lms.last == (KITCHEN, ["time", expected])


async def test_get_mode_reads_the_underscore_key(ctx: ServerContext, lms: FakeLMS):
    lms.reply("mode", {"_mode": "pause"})
    assert (await call(ctx, "lms_get_mode"))["value"] == "pause"


async def test_repeat_maps_names_to_lyrion_numbers(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_set_repeat", mode="playlist")
    assert lms.last == (KITCHEN, ["playlist", "repeat", "2"])
    lms.reply(("playlist", "repeat"), {"_repeat": 1})
    assert (await call(ctx, "lms_get_repeat"))["value"] == "song"


async def test_shuffle_maps_names_to_lyrion_numbers(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_set_shuffle", mode="albums")
    assert lms.last == (KITCHEN, ["playlist", "shuffle", "2"])
    lms.reply(("playlist", "shuffle"), {"_shuffle": 0})
    assert (await call(ctx, "lms_get_shuffle"))["value"] == "off"


async def test_a_named_player_overrides_the_default(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_stop", player="Living Room")
    assert lms.last == ("aa:bb:cc:dd:ee:02", ["stop"])
