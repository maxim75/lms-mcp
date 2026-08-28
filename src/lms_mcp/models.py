"""Typed results returned by the tools (drive MCP structured output)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Ok(BaseModel):
    """Generic acknowledgement for commands with no interesting return value."""

    ok: bool = True
    detail: str | None = None


class Player(BaseModel):
    id: str = Field(description="Player id (MAC address), used as the `player` argument")
    name: str
    model: str | None = None
    ip: str | None = None
    connected: bool | None = None
    power: bool | None = None
    is_player: bool | None = None
    can_power_off: bool | None = None


class PlayerList(BaseModel):
    players: list[Player]
    default_player: str | None = None


class Track(BaseModel):
    id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_id: str | None = None
    artist_id: str | None = None
    duration: float | None = None
    tracknum: int | None = None
    year: int | None = None
    genre: str | None = None
    url: str | None = None
    artwork_url: str | None = None
    playlist_index: int | None = Field(default=None, description="Position in the current queue")


class Artist(BaseModel):
    id: str
    name: str


class Album(BaseModel):
    id: str
    title: str
    artist: str | None = None
    artist_id: str | None = None
    year: int | None = None
    artwork_url: str | None = None


class NamedItem(BaseModel):
    """A generic id/name row (genres, years, saved playlists, libraries)."""

    id: str
    name: str


class BrowseItem(BaseModel):
    """A row from a browsable menu (favorites, plugin apps, radio)."""

    id: str | None = None
    name: str | None = None
    type: str | None = None
    is_audio: bool | None = None
    has_items: bool | None = None
    url: str | None = None
    image: str | None = None


class _Page(BaseModel):
    start: int = 0
    count: int = 0
    total: int | None = None
    has_more: bool = False


class TrackPage(_Page):
    items: list[Track] = []


class ArtistPage(_Page):
    items: list[Artist] = []


class AlbumPage(_Page):
    items: list[Album] = []


class NamePage(_Page):
    items: list[NamedItem] = []


class BrowsePage(_Page):
    items: list[BrowseItem] = []


class SearchResults(BaseModel):
    artists: list[Artist] = []
    albums: list[Album] = []
    tracks: list[Track] = []
    total: int | None = None


class PlayerStatus(BaseModel):
    player_id: str
    name: str | None = None
    mode: str | None = Field(default=None, description="play, pause or stop")
    power: bool | None = None
    volume: int | None = None
    muted: bool | None = None
    time: float | None = Field(default=None, description="Elapsed seconds in the current track")
    duration: float | None = None
    playlist_index: int | None = None
    playlist_count: int | None = None
    repeat: str | None = Field(default=None, description="off, song or playlist")
    shuffle: str | None = Field(default=None, description="off, songs or albums")
    current_track: Track | None = None
    sync_master: str | None = None
    sync_slaves: list[str] = []


class QueuePage(_Page):
    items: list[Track] = []
    playlist_index: int | None = None
    playlist_name: str | None = None


class AudioSettings(BaseModel):
    player_id: str
    volume: int | None = None
    muted: bool | None = None
    bass: int | None = None
    treble: int | None = None
    pitch: int | None = None


class ScalarResult(BaseModel):
    """A single value read back from the server."""

    value: str | int | float | bool | None = None


class ServerStatus(BaseModel):
    version: str | None = None
    uuid: str | None = None
    player_count: int | None = None
    players: list[Player] = []
    total_albums: int | None = None
    total_artists: int | None = None
    total_songs: int | None = None
    total_genres: int | None = None
    last_scan: str | None = None
    scanning: bool | None = None


class SyncGroup(BaseModel):
    member_ids: list[str] = []
    member_names: list[str] = []


class SyncGroups(BaseModel):
    groups: list[SyncGroup] = []


class LibraryTotals(BaseModel):
    genres: int | None = None
    artists: int | None = None
    albums: int | None = None
    songs: int | None = None


class ScanStatus(BaseModel):
    scanning: bool
    steps: dict[str, str] = {}
    total_time: str | None = None


class Alarm(BaseModel):
    id: str
    time: int | None = Field(default=None, description="Seconds after midnight")
    enabled: bool | None = None
    repeat: bool | None = None
    days: str | None = Field(default=None, description="Comma-separated weekdays, 0=Sunday")
    volume: int | None = None
    url: str | None = None


class AlarmList(BaseModel):
    alarms: list[Alarm] = []
    total: int | None = None
