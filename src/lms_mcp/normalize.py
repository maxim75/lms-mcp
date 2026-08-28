"""Turn Lyrion's loose `*_loop` payloads into the typed models in `models.py`."""

from __future__ import annotations

from typing import Any

from .models import (
    Alarm,
    Album,
    Artist,
    BrowseItem,
    LibraryTotals,
    NamedItem,
    Player,
    PlayerStatus,
    ScanStatus,
    ServerStatus,
    Track,
)

MAX_COUNT = 200
DEFAULT_COUNT = 50


def clamp_count(count: int) -> int:
    """Keep list responses inside a token budget."""
    return max(1, min(int(count), MAX_COUNT))


def loop(result: dict[str, Any], *names: str) -> list[dict[str, Any]]:
    """Return the first present `*_loop` array, tolerating its absence."""
    for name in names:
        value = result.get(name)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def total_of(result: dict[str, Any], *names: str) -> int | None:
    for name in names:
        total = as_int(result.get(name))
        if total is not None:
            return total
    return None


def page_fields(result: dict[str, Any], start: int, items: list[Any], *total_keys: str) -> dict[str, Any]:
    total = total_of(result, *total_keys, "count")
    return {
        "start": start,
        "count": len(items),
        "total": total,
        "has_more": total is not None and start + len(items) < total,
    }


def artwork_url(base_url: str, row: dict[str, Any]) -> str | None:
    """Absolute cover URL for a track/album row, if the server has artwork for it."""
    remote = as_str(row.get("artwork_url"))
    if remote:
        # Online services return a ready-made absolute URL.
        return remote if remote.startswith("http") else f"{base_url}{remote}"
    cover_id = row.get("coverid") or row.get("artwork_track_id")
    if not cover_id:
        if not as_bool(row.get("coverart")):
            return None
        cover_id = row.get("id")
    if not cover_id:
        return None
    return f"{base_url}/music/{cover_id}/cover.jpg"


def track(row: dict[str, Any], base_url: str) -> Track:
    return Track(
        id=as_str(row.get("id") or row.get("track_id")),
        title=as_str(row.get("title") or row.get("track")),
        artist=as_str(row.get("artist") or row.get("trackartist") or row.get("albumartist")),
        album=as_str(row.get("album")),
        album_id=as_str(row.get("album_id")),
        artist_id=as_str(row.get("artist_id")),
        duration=as_float(row.get("duration")),
        tracknum=as_int(row.get("tracknum")),
        year=as_int(row.get("year")),
        genre=as_str(row.get("genre")),
        url=as_str(row.get("url")),
        artwork_url=artwork_url(base_url, row),
        playlist_index=as_int(row.get("playlist index")),
    )


def artist(row: dict[str, Any]) -> Artist:
    return Artist(id=as_str(row.get("id")) or "", name=as_str(row.get("artist")) or "")


def album(row: dict[str, Any], base_url: str) -> Album:
    return Album(
        id=as_str(row.get("id")) or "",
        title=as_str(row.get("album")) or "",
        artist=as_str(row.get("artist") or row.get("albumartist")),
        artist_id=as_str(row.get("artist_id")),
        year=as_int(row.get("year")),
        artwork_url=artwork_url(base_url, row),
    )


def named(row: dict[str, Any], *name_keys: str) -> NamedItem:
    name = ""
    for key in name_keys:
        value = as_str(row.get(key))
        if value:
            name = value
            break
    return NamedItem(id=as_str(row.get("id")) or name, name=name)


def browse_item(row: dict[str, Any]) -> BrowseItem:
    return BrowseItem(
        id=as_str(row.get("id") or row.get("item_id")),
        name=as_str(row.get("name") or row.get("title") or row.get("text")),
        type=as_str(row.get("type")),
        is_audio=as_bool(row.get("isaudio")),
        has_items=(as_int(row.get("hasitems")) or 0) > 0 if row.get("hasitems") is not None else None,
        url=as_str(row.get("url")),
        image=as_str(row.get("image") or row.get("icon")),
    )


def player(row: dict[str, Any]) -> Player:
    return Player(
        id=as_str(row.get("playerid") or row.get("playerindex")) or "",
        name=as_str(row.get("name")) or "",
        model=as_str(row.get("modelname") or row.get("model")),
        ip=as_str(row.get("ip")),
        connected=as_bool(row.get("connected")),
        power=as_bool(row.get("power")),
        is_player=as_bool(row.get("isplayer")),
        can_power_off=as_bool(row.get("canpoweroff")),
    )


def server_status(result: dict[str, Any]) -> ServerStatus:
    return ServerStatus(
        version=as_str(result.get("version")),
        uuid=as_str(result.get("uuid")),
        player_count=as_int(result.get("player count")),
        players=[player(row) for row in loop(result, "players_loop")],
        total_albums=as_int(result.get("info total albums")),
        total_artists=as_int(result.get("info total artists")),
        total_songs=as_int(result.get("info total songs")),
        total_genres=as_int(result.get("info total genres")),
        last_scan=as_str(result.get("lastscan")),
        scanning=as_bool(result.get("rescan")),
    )


def library_totals(values: dict[str, Any]) -> LibraryTotals:
    return LibraryTotals(
        genres=as_int(values.get("genres")),
        artists=as_int(values.get("artists")),
        albums=as_int(values.get("albums")),
        songs=as_int(values.get("songs")),
    )


def scan_status(result: dict[str, Any]) -> ScanStatus:
    steps = {
        str(key): str(value)
        for key, value in result.items()
        if key not in {"rescan", "totaltime", "_rescan"} and not isinstance(value, (list, dict))
    }
    return ScanStatus(
        scanning=bool(as_bool(result.get("rescan"))),
        steps=steps,
        total_time=as_str(result.get("totaltime")),
    )


REPEAT_MODES = {0: "off", 1: "song", 2: "playlist"}
SHUFFLE_MODES = {0: "off", 1: "songs", 2: "albums"}


def player_status(result: dict[str, Any], player_id: str, base_url: str) -> PlayerStatus:
    rows = loop(result, "playlist_loop")
    index = as_int(result.get("playlist_cur_index"))
    current: Track | None = None
    if rows:
        # `status` with a window starting at the current index puts it first.
        current = track(rows[0], base_url)
    volume = as_int(result.get("mixer volume"))
    muted = as_bool(result.get("mixer muting"))
    if volume is not None and volume < 0:
        # LMS reports a negative volume while muted.
        muted = True if muted is None else muted
        volume = abs(volume)
    slaves = as_str(result.get("sync_slaves"))
    return PlayerStatus(
        player_id=player_id,
        name=as_str(result.get("player_name")),
        mode=as_str(result.get("mode")),
        power=as_bool(result.get("power")),
        volume=volume,
        muted=muted,
        time=as_float(result.get("time")),
        duration=as_float(result.get("duration")),
        playlist_index=index,
        playlist_count=as_int(result.get("playlist_tracks")),
        repeat=REPEAT_MODES.get(as_int(result.get("playlist repeat")) or 0),
        shuffle=SHUFFLE_MODES.get(as_int(result.get("playlist shuffle")) or 0),
        current_track=current,
        sync_master=as_str(result.get("sync_master")),
        sync_slaves=slaves.split(",") if slaves else [],
    )


def alarm(row: dict[str, Any]) -> Alarm:
    return Alarm(
        id=as_str(row.get("id")) or "",
        time=as_int(row.get("time")),
        enabled=as_bool(row.get("enabled")),
        repeat=as_bool(row.get("repeat")),
        days=as_str(row.get("dow")),
        volume=as_int(row.get("volume")),
        url=as_str(row.get("url")),
    )
