"""Browsing and searching the music library."""

from __future__ import annotations

from typing import Literal

from ..context import ServerContext
from ..models import AlbumPage, ArtistPage, BrowsePage, NamePage, SearchResults, Track, TrackPage
from ..normalize import (
    DEFAULT_COUNT,
    album,
    artist,
    as_int,
    as_str,
    browse_item,
    clamp_count,
    loop,
    named,
    page_fields,
    track,
)
from ._registry import Registrar
from .player import TRACK_TAGS

ALBUM_TAGS = "lyjaS"

AlbumSort = Literal[
    "album", "new", "changed", "lastplayed", "playcount", "artistalbum", "yearalbum", "random"
]


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("search", "Search the library", read_only=True)
    async def lms_search(term: str, count: int = 10) -> SearchResults:
        """Search artists, albums and tracks at once.

        Returns up to `count` of each kind. Use the ids with lms_play_item.
        """
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["search", 0, limit], {"term": term})
        artists = [
            artist({"id": row.get("artist_id"), "artist": row.get("artist")})
            for row in loop(result, "artists_loop")
        ]
        albums = [
            album({"id": row.get("album_id"), "album": row.get("album")}, ctx.client.base_url)
            for row in loop(result, "albums_loop")
        ]
        tracks = [
            Track(id=as_str(row.get("track_id")), title=as_str(row.get("track")))
            for row in loop(result, "tracks_loop")
        ]
        return SearchResults(artists=artists, albums=albums, tracks=tracks, total=as_int(result.get("count")))

    @tool("list_artists", "List artists", read_only=True)
    async def lms_list_artists(
        search: str | None = None,
        genre_id: str | None = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> ArtistPage:
        """List artists, optionally filtered by a search string or genre."""
        limit = clamp_count(count)
        result = await ctx.client.request(
            None, ["artists", start, limit], {"search": search, "genre_id": genre_id}
        )
        items = [artist(row) for row in loop(result, "artists_loop")]
        return ArtistPage(items=items, **page_fields(result, start, items))

    @tool("list_albums", "List albums", read_only=True)
    async def lms_list_albums(
        search: str | None = None,
        artist_id: str | None = None,
        genre_id: str | None = None,
        year: int | None = None,
        sort: AlbumSort = "album",
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> AlbumPage:
        """List albums with optional filters and sort order."""
        limit = clamp_count(count)
        result = await ctx.client.request(
            None,
            ["albums", start, limit],
            {
                "search": search,
                "artist_id": artist_id,
                "genre_id": genre_id,
                "year": year,
                "sort": sort,
                "tags": ALBUM_TAGS,
            },
        )
        items = [album(row, ctx.client.base_url) for row in loop(result, "albums_loop")]
        return AlbumPage(items=items, **page_fields(result, start, items))

    @tool("list_tracks", "List tracks", read_only=True)
    async def lms_list_tracks(
        search: str | None = None,
        album_id: str | None = None,
        artist_id: str | None = None,
        genre_id: str | None = None,
        year: int | None = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> TrackPage:
        """List tracks with optional filters. Ids returned here work with lms_play_item."""
        limit = clamp_count(count)
        result = await ctx.client.request(
            None,
            ["titles", start, limit],
            {
                "search": search,
                "album_id": album_id,
                "artist_id": artist_id,
                "genre_id": genre_id,
                "year": year,
                "tags": TRACK_TAGS,
            },
        )
        items = [track(row, ctx.client.base_url) for row in loop(result, "titles_loop")]
        return TrackPage(items=items, **page_fields(result, start, items))

    @tool("album_tracks", "Tracks on an album", read_only=True)
    async def lms_album_tracks(album_id: str, start: int = 0, count: int = DEFAULT_COUNT) -> TrackPage:
        """List an album's tracks in track-number order."""
        limit = clamp_count(count)
        result = await ctx.client.request(
            None, ["titles", start, limit], {"album_id": album_id, "sort": "tracknum", "tags": TRACK_TAGS}
        )
        items = [track(row, ctx.client.base_url) for row in loop(result, "titles_loop")]
        return TrackPage(items=items, **page_fields(result, start, items))

    @tool("artist_albums", "Albums by an artist", read_only=True)
    async def lms_artist_albums(artist_id: str, start: int = 0, count: int = DEFAULT_COUNT) -> AlbumPage:
        """List the albums credited to an artist."""
        limit = clamp_count(count)
        result = await ctx.client.request(
            None, ["albums", start, limit], {"artist_id": artist_id, "tags": ALBUM_TAGS, "sort": "yearalbum"}
        )
        items = [album(row, ctx.client.base_url) for row in loop(result, "albums_loop")]
        return AlbumPage(items=items, **page_fields(result, start, items))

    @tool("list_genres", "List genres", read_only=True)
    async def lms_list_genres(
        search: str | None = None, start: int = 0, count: int = DEFAULT_COUNT
    ) -> NamePage:
        """List genres known to the server."""
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["genres", start, limit], {"search": search})
        items = [named(row, "genre") for row in loop(result, "genres_loop")]
        return NamePage(items=items, **page_fields(result, start, items))

    @tool("list_years", "List years", read_only=True)
    async def lms_list_years(start: int = 0, count: int = DEFAULT_COUNT) -> NamePage:
        """List the years present in the library."""
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["years", start, limit], {"hasAlbums": 1})
        items = [named(row, "year") for row in loop(result, "years_loop")]
        return NamePage(items=items, **page_fields(result, start, items))

    @tool("list_libraries", "List virtual libraries", read_only=True)
    async def lms_list_libraries() -> NamePage:
        """List virtual library views configured on the server."""
        result = await ctx.client.request(None, ["libraries", 0, 999])
        items = [named(row, "name", "title") for row in loop(result, "folder_loop", "libraries_loop")]
        return NamePage(items=items, **page_fields(result, 0, items))

    @tool("list_new_music", "Recently added albums", read_only=True)
    async def lms_list_new_music(start: int = 0, count: int = DEFAULT_COUNT) -> AlbumPage:
        """List albums most recently added to the library."""
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["albums", start, limit], {"sort": "new", "tags": ALBUM_TAGS})
        items = [album(row, ctx.client.base_url) for row in loop(result, "albums_loop")]
        return AlbumPage(items=items, **page_fields(result, start, items))

    @tool("track_info", "Track details", read_only=True)
    async def lms_track_info(track_id: str) -> Track:
        """Full metadata for one track."""
        result = await ctx.client.request(None, ["songinfo", 0, 100], {"track_id": track_id})
        merged: dict[str, object] = {"id": track_id}
        for row in loop(result, "songinfo_loop"):
            merged.update(row)
        return track(merged, ctx.client.base_url)

    @tool("browse_music_folder", "Browse the music folder", read_only=True)
    async def lms_browse_music_folder(
        folder_id: str | None = None, start: int = 0, count: int = DEFAULT_COUNT
    ) -> BrowsePage:
        """Browse the music folder tree. Omit folder_id for the top level.

        Rows of type `folder` can be browsed again; rows of type `track` can be played
        with lms_play_item(kind="track"), and a folder with lms_play_item(kind="folder").
        """
        limit = clamp_count(count)
        result = await ctx.client.request(
            None, ["musicfolder", start, limit], {"folder_id": folder_id, "tags": "cdus"}
        )
        rows = loop(result, "folder_loop")
        items = [browse_item({**row, "name": row.get("filename") or row.get("title")}) for row in rows]
        return BrowsePage(items=items, **page_fields(result, start, items))
