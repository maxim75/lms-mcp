"""Server, player, mixer, favorites, alarms, randomplay and app tools."""

from __future__ import annotations

from conftest import FakeLMS
from helpers import call
from lms_mcp.context import ServerContext

KITCHEN = "aa:bb:cc:dd:ee:01"


async def test_server_status_summarises_the_library(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "serverstatus",
        {
            "version": "9.0.1",
            "player count": 2,
            "info total albums": "120",
            "info total songs": "2400",
            "lastscan": "1700000000",
            "players_loop": [{"playerid": KITCHEN, "name": "Kitchen"}],
        },
    )
    status = await call(ctx, "lms_server_status")

    assert status["version"] == "9.0.1"
    assert status["total_albums"] == 120
    assert status["players"][0]["name"] == "Kitchen"


async def test_library_totals_asks_for_each_count(ctx: ServerContext, lms: FakeLMS):
    lms.reply(("info", "total", "genres"), {"_genres": 12})
    lms.reply(("info", "total", "artists"), {"_artists": 34})
    lms.reply(("info", "total", "albums"), {"_albums": 56})
    lms.reply(("info", "total", "songs"), {"_songs": 78})

    totals = await call(ctx, "lms_library_totals")

    assert totals == {"genres": 12, "artists": 34, "albums": 56, "songs": 78}
    assert lms.commands[0] == ["info", "total", "genres", "?"]


async def test_rescan_modes(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_rescan_start")
    assert lms.last[1] == ["rescan"]
    await call(ctx, "lms_rescan_start", mode="full")
    assert lms.last[1] == ["rescan", "full"]
    await call(ctx, "lms_rescan_start", mode="playlists")
    assert lms.last[1] == ["rescan", "playlists"]


async def test_sync_groups_are_split_into_members(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "syncgroups",
        {
            "syncgroups_loop": [
                {"sync_members": f"{KITCHEN},aa:bb:cc:dd:ee:02", "sync_member_names": "Kitchen,Living Room"}
            ]
        },
    )
    groups = await call(ctx, "lms_list_sync_groups")

    assert groups["groups"][0]["member_names"] == ["Kitchen", "Living Room"]


async def test_list_players_reports_the_default(ctx: ServerContext):
    listing = await call(ctx, "lms_list_players")
    assert listing["default_player"] == "Kitchen"
    assert [p["name"] for p in listing["players"]] == ["Kitchen", "Living Room"]
    assert listing["players"][0]["model"] == "Squeezelite"


async def test_player_status_uses_the_current_track_window(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "status",
        {
            "player_name": "Kitchen",
            "mode": "play",
            "mixer volume": "40",
            "playlist_loop": [{"id": "1", "title": "Song", "artist": "Band"}],
        },
    )
    status = await call(ctx, "lms_player_status")

    assert lms.last[1][:3] == ["status", "-", "1"]
    assert status["current_track"]["artist"] == "Band"
    assert status["volume"] == 40


async def test_power_and_sleep(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_set_power", on=True)
    assert lms.last == (KITCHEN, ["power", "1"])
    await call(ctx, "lms_sleep", seconds=0)
    assert lms.last == (KITCHEN, ["sleep", "0"])


async def test_sync_resolves_both_players(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_sync", other_player="Living Room")
    assert lms.last == (KITCHEN, ["sync", "aa:bb:cc:dd:ee:02"])
    await call(ctx, "lms_unsync")
    assert lms.last == (KITCHEN, ["sync", "-"])


async def test_show_message_uses_tagged_parameters(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_show_message", line1="Hello", duration=5)
    assert lms.last == (KITCHEN, ["show", "line1:Hello", "duration:5"])


async def test_volume_absolute_and_relative(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_set_volume", volume=35)
    assert lms.last == (KITCHEN, ["mixer", "volume", "35"])
    await call(ctx, "lms_set_volume", volume=10, relative=True)
    assert lms.last == (KITCHEN, ["mixer", "volume", "+10"])
    await call(ctx, "lms_set_volume", volume=-10, relative=True)
    assert lms.last == (KITCHEN, ["mixer", "volume", "-10"])


async def test_audio_settings_are_read_in_one_call(ctx: ServerContext, lms: FakeLMS):
    lms.reply("mixer", {"_volume": 30, "_muting": 0, "_bass": 50, "_treble": 50, "_pitch": 100})
    settings = await call(ctx, "lms_get_audio_settings")
    assert settings["player_id"] == KITCHEN
    assert settings["volume"] == 30


async def test_favorites_browse_requests_urls(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "favorites",
        {
            "count": 1,
            "loop_loop": [{"id": "1.2", "name": "Radio Swiss Jazz", "isaudio": 1, "hasitems": 0}],
        },
    )
    page = await call(ctx, "lms_favorites_list")

    assert lms.last[1][:2] == ["favorites", "items"]
    assert "want_url:1" in lms.last[1]
    assert page["items"][0]["is_audio"] is True


async def test_favorites_play_targets_a_player(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_favorites_play", item_id="1.2", how="add")
    assert lms.last == (KITCHEN, ["favorites", "playlist", "add", "item_id:1.2"])


async def test_favorites_add_current_reads_the_playing_track(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "status",
        {"playlist_loop": [{"title": "Now", "url": "http://stream/x"}]},
    )
    result = await call(ctx, "lms_favorites_add_current")

    assert result["ok"] is True
    assert lms.last[1][:2] == ["favorites", "add"]
    assert "url:http://stream/x" in lms.last[1]


async def test_favorites_add_current_reports_an_idle_player(ctx: ServerContext, lms: FakeLMS):
    lms.reply("status", {"playlist_loop": []})
    result = await call(ctx, "lms_favorites_add_current")
    assert result["ok"] is False


async def test_alarm_add_encodes_days_and_flags(ctx: ServerContext, lms: FakeLMS):
    lms.reply("alarm", {"id": "eaf39"})
    result = await call(ctx, "lms_alarm_add", time_seconds=27000, days="1,2,3,4,5", volume=40)

    player, command = lms.last
    assert player == KITCHEN
    assert command[:2] == ["alarm", "add"]
    assert set(command[2:]) == {"time:27000", "dow:1,2,3,4,5", "enabled:1", "repeat:1", "volume:40"}
    assert result["value"] == "eaf39"


async def test_alarm_update_only_sends_what_changed(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_alarm_update", alarm_id="eaf39", enabled=False)
    assert set(lms.last[1][2:]) == {"id:eaf39", "enabled:0"}


async def test_alarms_list_filters_and_normalizes(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "alarms",
        {"count": 1, "alarms_loop": [{"id": "a1", "time": "3600", "enabled": 1, "dow": "1,2"}]},
    )
    listing = await call(ctx, "lms_alarms_list", enabled_only=True)

    assert "filter:enabled" in lms.last[1]
    assert listing["alarms"][0] == {
        "id": "a1",
        "time": 3600,
        "enabled": True,
        "repeat": None,
        "days": "1,2",
        "volume": None,
        "url": None,
    }


async def test_random_play_maps_artists_to_contributors(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_random_play", kind="artists")
    assert lms.last == (KITCHEN, ["randomplay", "contributors"])
    await call(ctx, "lms_random_stop")
    assert lms.last == (KITCHEN, ["randomplay", "disable"])


async def test_app_browse_passes_the_item_id(ctx: ServerContext, lms: FakeLMS):
    lms.reply("tidal", {"count": 1, "loop_loop": [{"id": "x", "name": "Playlists", "hasitems": 2}]})
    page = await call(ctx, "lms_app_browse", app="tidal", item_id="root")

    assert lms.last[1][:2] == ["tidal", "items"]
    assert "item_id:root" in lms.last[1]
    assert page["items"][0]["has_items"] is True


async def test_app_browse_without_a_default_player_is_server_wide(make_ctx, lms: FakeLMS):
    ctx = make_ctx()
    await call(ctx, "lms_app_browse", app="tidal")
    assert lms.last[0] == ""


async def test_app_play_requires_a_player(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_app_play", app="spotty", item_id="track:1")
    assert lms.last == (KITCHEN, ["spotty", "playlist", "play", "item_id:track:1"])
