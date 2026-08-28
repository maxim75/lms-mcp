from __future__ import annotations

from lms_mcp import normalize

BASE = "http://lyrion.local:9000"


def test_loop_falls_back_through_candidate_keys():
    assert normalize.loop({"titles_loop": [{"id": 1}]}, "playlist_loop", "titles_loop") == [{"id": 1}]
    assert normalize.loop({}, "missing_loop") == []


def test_loop_ignores_non_dict_rows():
    assert normalize.loop({"x_loop": [{"id": 1}, "junk"]}, "x_loop") == [{"id": 1}]


def test_clamp_count_bounds_the_page_size():
    assert normalize.clamp_count(0) == 1
    assert normalize.clamp_count(50) == 50
    assert normalize.clamp_count(5000) == normalize.MAX_COUNT


def test_track_maps_lyrion_field_names():
    track = normalize.track(
        {
            "id": "12",
            "title": "Any How",
            "artist": "Llorca",
            "album": "New Comer",
            "album_id": "3",
            "duration": "340.29",
            "tracknum": "5",
            "year": "2001",
            "coverid": "abc",
            "playlist index": "2",
        },
        BASE,
    )
    assert track.id == "12"
    assert track.duration == 340.29
    assert track.tracknum == 5
    assert track.playlist_index == 2
    assert track.artwork_url == f"{BASE}/music/abc/cover.jpg"


def test_remote_artwork_url_is_used_as_is():
    track = normalize.track({"id": "1", "artwork_url": "https://cdn.example/art.jpg"}, BASE)
    assert track.artwork_url == "https://cdn.example/art.jpg"


def test_relative_artwork_url_is_made_absolute():
    track = normalize.track({"id": "1", "artwork_url": "/imageproxy/art.jpg"}, BASE)
    assert track.artwork_url == f"{BASE}/imageproxy/art.jpg"


def test_track_without_artwork_has_no_url():
    assert normalize.track({"id": "1", "title": "x"}, BASE).artwork_url is None


def test_page_fields_reports_more_results():
    fields = normalize.page_fields({"count": 120}, 0, [1] * 50)
    assert fields == {"start": 0, "count": 50, "total": 120, "has_more": True}
    assert normalize.page_fields({"count": 40}, 0, [1] * 40)["has_more"] is False


def test_player_status_reads_the_current_track_and_modes():
    status = normalize.player_status(
        {
            "player_name": "Kitchen",
            "mode": "play",
            "power": 1,
            "mixer volume": "-35",
            "time": "12.5",
            "duration": "200",
            "playlist_cur_index": "3",
            "playlist_tracks": "10",
            "playlist repeat": "2",
            "playlist shuffle": "1",
            "playlist_loop": [{"id": "9", "title": "Now playing"}],
        },
        "aa:bb:cc:dd:ee:01",
        BASE,
    )
    assert status.volume == 35
    assert status.muted is True
    assert status.repeat == "playlist"
    assert status.shuffle == "songs"
    assert status.current_track is not None
    assert status.current_track.title == "Now playing"


def test_scan_status_reports_progress_steps():
    status = normalize.scan_status({"rescan": 1, "totaltime": "00:01:20", "directory": "45%"})
    assert status.scanning is True
    assert status.steps["directory"] == "45%"
    assert status.total_time == "00:01:20"


def test_named_falls_back_across_key_names():
    assert normalize.named({"id": "3", "playlist": "Beats"}, "playlist", "name").name == "Beats"
    assert normalize.named({"year": "1999"}, "year").id == "1999"


def test_browse_item_flags():
    item = normalize.browse_item({"id": "1.2", "name": "Jazz", "hasitems": "3", "isaudio": "0"})
    assert item.has_items is True
    assert item.is_audio is False
