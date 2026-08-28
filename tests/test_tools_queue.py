from __future__ import annotations

from conftest import FakeLMS
from helpers import call
from lms_mcp.context import ServerContext

KITCHEN = "aa:bb:cc:dd:ee:01"


async def test_get_queue_normalizes_the_playlist_loop(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "status",
        {
            "playlist_tracks": 3,
            "playlist_cur_index": "1",
            "playlist_name": "Evening",
            "playlist_loop": [
                {"playlist index": 0, "id": "1", "title": "One", "artist": "A", "duration": "100"},
                {"playlist index": 1, "id": "2", "title": "Two", "artist": "B", "duration": "200"},
            ],
        },
    )
    page = await call(ctx, "lms_get_queue", count=2)

    assert lms.last[1][:3] == ["status", "0", "2"]
    assert page["playlist_index"] == 1
    assert page["playlist_name"] == "Evening"
    assert [item["title"] for item in page["items"]] == ["One", "Two"]
    assert page["has_more"] is True


async def test_get_queue_caps_the_page_size(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_get_queue", count=10_000)
    assert lms.last[1][2] == "200"


async def test_play_item_uses_playlistcontrol(ctx: ServerContext, lms: FakeLMS):
    lms.reply("playlistcontrol", {"count": 12})
    result = await call(ctx, "lms_play_item", kind="album", item_id="22")

    player, command = lms.last
    assert player == KITCHEN
    assert command[0] == "playlistcontrol"
    assert set(command[1:]) == {"cmd:load", "album_id:22"}
    assert "12 track(s)" in result["detail"]


async def test_play_item_can_start_at_an_index(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_play_item", kind="playlist", item_id="7", start_at_index=3)
    assert set(lms.last[1][1:]) == {"cmd:load", "playlist_id:7", "play_index:3"}


async def test_add_and_insert_map_to_their_commands(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_add_item", kind="artist", item_id="5")
    assert set(lms.last[1][1:]) == {"cmd:add", "artist_id:5"}
    await call(ctx, "lms_insert_item", kind="track", item_id="9")
    assert set(lms.last[1][1:]) == {"cmd:insert", "track_id:9"}
    await call(ctx, "lms_remove_item", kind="genre", item_id="4")
    assert set(lms.last[1][1:]) == {"cmd:delete", "genre_id:4"}


async def test_play_url_passes_an_optional_title(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_play_url", url="http://stream/1", title="Radio One")
    assert lms.last == (KITCHEN, ["playlist", "play", "http://stream/1", "Radio One"])
    await call(ctx, "lms_add_url", url="http://stream/2")
    assert lms.last == (KITCHEN, ["playlist", "add", "http://stream/2"])


async def test_queue_editing_commands(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_queue_move", from_index=1, to_index=4)
    assert lms.last == (KITCHEN, ["playlist", "move", "1", "4"])
    await call(ctx, "lms_queue_delete_index", index=2)
    assert lms.last == (KITCHEN, ["playlist", "delete", "2"])
    await call(ctx, "lms_queue_clear")
    assert lms.last == (KITCHEN, ["playlist", "clear"])
    await call(ctx, "lms_queue_save", name="Evening")
    assert lms.last == (KITCHEN, ["playlist", "save", "Evening"])


async def test_saved_playlists_are_listed_server_wide(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "playlists",
        {
            "count": 2,
            "playlists_loop": [{"id": "37", "playlist": "Funky"}, {"id": "57", "playlist": "Super"}],
        },
    )
    page = await call(ctx, "lms_saved_playlists", search="u")

    assert lms.last[0] == ""
    assert "search:u" in lms.last[1]
    assert [item["name"] for item in page["items"]] == ["Funky", "Super"]


async def test_saved_playlist_tracks_requests_the_playlist_id(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        ("playlists", "tracks"),
        {"count": 1, "playlisttracks_loop": [{"id": "1", "title": "Track"}]},
    )
    page = await call(ctx, "lms_saved_playlist_tracks", playlist_id="37")

    assert lms.last[1][:2] == ["playlists", "tracks"]
    assert "playlist_id:37" in lms.last[1]
    assert page["items"][0]["title"] == "Track"


async def test_destructive_playlist_delete_is_gated(ctx: ServerContext, make_ctx):
    from helpers import build_server

    default_tools = {tool.name for tool in await build_server(ctx).list_tools()}
    assert "lms_saved_playlist_delete" not in default_tools

    opted_in = make_ctx(default_player="Kitchen", enable_destructive=True)
    enabled_tools = {tool.name for tool in await build_server(opted_in).list_tools()}
    assert "lms_saved_playlist_delete" in enabled_tools
