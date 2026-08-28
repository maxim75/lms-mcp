from __future__ import annotations

from conftest import FakeLMS
from helpers import call
from lms_mcp.context import ServerContext


def tagged(command: list[str], name: str) -> str | None:
    for part in command:
        if part.startswith(f"{name}:"):
            return part.split(":", 1)[1]
    return None


async def test_search_splits_the_three_result_kinds(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "search",
        {
            "count": 4,
            "artists_loop": [{"artist_id": "2", "artist": "Alphaville"}],
            "albums_loop": [{"album_id": "10", "album": "Forever Young"}],
            "tracks_loop": [
                {"track_id": "11", "track": "Big in Japan"},
                {"track_id": "12", "track": "Sounds Like a Melody"},
            ],
        },
    )
    results = await call(ctx, "lms_search", term="alpha")

    assert lms.last[1][:3] == ["search", "0", "10"]
    assert "term:alpha" in lms.last[1]
    assert results["artists"][0] == {"id": "2", "name": "Alphaville"}
    assert results["albums"][0]["title"] == "Forever Young"
    assert [t["title"] for t in results["tracks"]] == ["Big in Japan", "Sounds Like a Melody"]
    assert results["total"] == 4


async def test_list_albums_applies_filters_and_tags(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "albums",
        {
            "count": 1,
            "albums_loop": [
                {
                    "id": "5",
                    "album": "Fallen",
                    "artist": "Evanescence",
                    "year": "2003",
                    "artwork_track_id": "77",
                }
            ],
        },
    )
    page = await call(ctx, "lms_list_albums", artist_id="4", sort="yearalbum", count=5)

    command = lms.last[1]
    assert command[:3] == ["albums", "0", "5"]
    assert tagged(command, "artist_id") == "4"
    assert tagged(command, "sort") == "yearalbum"
    assert tagged(command, "tags") == "lyjaS"
    album = page["items"][0]
    assert album == {
        "id": "5",
        "title": "Fallen",
        "artist": "Evanescence",
        "artist_id": None,
        "year": 2003,
        "artwork_url": "http://lyrion.local:9000/music/77/cover.jpg",
    }


async def test_omitted_filters_are_not_sent(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_list_artists")
    assert lms.last[1] == ["artists", "0", "50"]


async def test_album_tracks_sorts_by_track_number(ctx: ServerContext, lms: FakeLMS):
    lms.reply("titles", {"count": 1, "titles_loop": [{"id": "3", "title": "Bring Me to Life"}]})
    page = await call(ctx, "lms_album_tracks", album_id="5")

    command = lms.last[1]
    assert tagged(command, "album_id") == "5"
    assert tagged(command, "sort") == "tracknum"
    assert page["items"][0]["title"] == "Bring Me to Life"


async def test_track_info_merges_the_songinfo_loop(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "songinfo",
        {
            "count": 3,
            "songinfo_loop": [
                {"id": "2"},
                {"title": "If I Had You"},
                {"artist": "Diana Krall", "duration": "297.1"},
            ],
        },
    )
    track = await call(ctx, "lms_track_info", track_id="2")

    assert "track_id:2" in lms.last[1]
    assert track["title"] == "If I Had You"
    assert track["artist"] == "Diana Krall"
    assert track["duration"] == 297.1


async def test_list_new_music_sorts_by_addition_date(ctx: ServerContext, lms: FakeLMS):
    await call(ctx, "lms_list_new_music")
    assert tagged(lms.last[1], "sort") == "new"


async def test_browse_music_folder_labels_rows(ctx: ServerContext, lms: FakeLMS):
    lms.reply(
        "musicfolder",
        {
            "count": 2,
            "folder_loop": [
                {"id": "313", "filename": "A-Ha", "type": "folder"},
                {"id": "50", "filename": "Test.m3u", "type": "playlist"},
            ],
        },
    )
    page = await call(ctx, "lms_browse_music_folder", folder_id="313")

    assert tagged(lms.last[1], "folder_id") == "313"
    assert [item["name"] for item in page["items"]] == ["A-Ha", "Test.m3u"]
    assert page["items"][0]["type"] == "folder"


async def test_list_years_only_returns_years_with_albums(ctx: ServerContext, lms: FakeLMS):
    lms.reply("years", {"count": 2, "years_loop": [{"year": "1985"}, {"year": "2002"}]})
    page = await call(ctx, "lms_list_years")

    assert "hasAlbums:1" in lms.last[1]
    assert [item["id"] for item in page["items"]] == ["1985", "2002"]
