"""The current play queue and saved playlists."""

from __future__ import annotations

from typing import Literal

from ..context import ServerContext
from ..models import NamePage, Ok, QueuePage, ScalarResult, TrackPage
from ..normalize import DEFAULT_COUNT, as_int, clamp_count, loop, named, page_fields, track
from ._common import first
from ._registry import Registrar
from .player import TRACK_TAGS

ItemKind = Literal["track", "album", "artist", "genre", "year", "playlist", "folder"]
ID_TAGS: dict[str, str] = {
    "track": "track_id",
    "album": "album_id",
    "artist": "artist_id",
    "genre": "genre_id",
    "year": "year",
    "playlist": "playlist_id",
    "folder": "folder_id",
}


def register(tool: Registrar, ctx: ServerContext) -> None:
    async def _control(cmd: str, kind: ItemKind, item_id: str, player: str | None, **extra: object) -> int:
        pid = await ctx.player_id(player)
        tags: dict[str, object] = {"cmd": cmd, ID_TAGS[kind]: item_id}
        tags.update({k: v for k, v in extra.items() if v is not None})
        result = await ctx.client.request(pid, ["playlistcontrol"], tags)  # type: ignore[arg-type]
        return as_int(result.get("count")) or 0

    @tool("get_queue", "Show the play queue", read_only=True)
    async def lms_get_queue(
        start: int = 0, count: int = DEFAULT_COUNT, player: str | None = None
    ) -> QueuePage:
        """List the tracks currently queued on a player, newest window first."""
        pid = await ctx.player_id(player)
        limit = clamp_count(count)
        result = await ctx.client.request(pid, ["status", start, limit], {"tags": TRACK_TAGS})
        rows = loop(result, "playlist_loop")
        items = [track(row, ctx.client.base_url) for row in rows]
        return QueuePage(
            items=items,
            playlist_index=as_int(result.get("playlist_cur_index")),
            playlist_name=result.get("playlist_name") or None,
            **page_fields(result, start, items, "playlist_tracks"),
        )

    @tool("queue_clear", "Clear the queue")
    async def lms_queue_clear(player: str | None = None) -> Ok:
        """Remove everything from the play queue and stop playback."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "clear"])
        return Ok(detail="queue cleared")

    @tool("play_item", "Play a library item")
    async def lms_play_item(
        kind: ItemKind, item_id: str, player: str | None = None, start_at_index: int | None = None
    ) -> Ok:
        """Replace the queue with a library item and start playing it.

        `kind` says what the id refers to; ids come from the library tools
        (lms_search, lms_list_albums, lms_album_tracks, lms_saved_playlists, ...).
        """
        count = await _control("load", kind, item_id, player, play_index=start_at_index)
        return Ok(detail=f"playing {count} track(s) from {kind} {item_id}")

    @tool("add_item", "Add a library item to the queue")
    async def lms_add_item(kind: ItemKind, item_id: str, player: str | None = None) -> Ok:
        """Append a library item to the end of the queue without interrupting playback."""
        count = await _control("add", kind, item_id, player)
        return Ok(detail=f"added {count} track(s) from {kind} {item_id}")

    @tool("insert_item", "Play a library item next")
    async def lms_insert_item(kind: ItemKind, item_id: str, player: str | None = None) -> Ok:
        """Queue a library item to play immediately after the current track."""
        count = await _control("insert", kind, item_id, player)
        return Ok(detail=f"inserted {count} track(s) from {kind} {item_id}")

    @tool("remove_item", "Remove a library item from the queue")
    async def lms_remove_item(kind: ItemKind, item_id: str, player: str | None = None) -> Ok:
        """Remove every queue entry belonging to a library item."""
        count = await _control("delete", kind, item_id, player)
        return Ok(detail=f"removed up to {count} track(s) for {kind} {item_id}")

    @tool("play_url", "Play a URL or file")
    async def lms_play_url(url: str, title: str | None = None, player: str | None = None) -> Ok:
        """Replace the queue with a stream URL, file path or playlist file, and play it."""
        pid = await ctx.player_id(player)
        command: list[str] = ["playlist", "play", url]
        if title:
            command.append(title)
        await ctx.client.request(pid, command)
        return Ok(detail=f"playing {url}")

    @tool("add_url", "Add a URL or file to the queue")
    async def lms_add_url(url: str, title: str | None = None, player: str | None = None) -> Ok:
        """Append a stream URL, file path or playlist file to the queue."""
        pid = await ctx.player_id(player)
        command: list[str] = ["playlist", "add", url]
        if title:
            command.append(title)
        await ctx.client.request(pid, command)
        return Ok(detail=f"added {url}")

    @tool("queue_move", "Move a queue entry")
    async def lms_queue_move(from_index: int, to_index: int, player: str | None = None) -> Ok:
        """Move a track from one position in the queue to another (both 0-based)."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "move", from_index, to_index])
        return Ok(detail=f"moved {from_index} to {to_index}")

    @tool("queue_delete_index", "Remove a queue entry")
    async def lms_queue_delete_index(index: int, player: str | None = None) -> Ok:
        """Remove the track at a given 0-based position in the queue."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "delete", index])
        return Ok(detail=f"removed queue position {index}")

    @tool("queue_save", "Save the queue as a playlist", idempotent=True)
    async def lms_queue_save(name: str, player: str | None = None) -> Ok:
        """Save the current queue as a named saved playlist (no .m3u suffix)."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "save", name])
        return Ok(detail=f"saved as {name}")

    @tool("queue_current_index", "Current queue position", read_only=True)
    async def lms_queue_current_index(player: str | None = None) -> ScalarResult:
        """Return the 0-based position of the track playing now."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["playlist", "index", "?"])
        return ScalarResult(value=as_int(first(result, "_index")))

    @tool("queue_track_count", "Queue length", read_only=True)
    async def lms_queue_track_count(player: str | None = None) -> ScalarResult:
        """Return how many tracks are in the queue."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["playlist", "tracks", "?"])
        return ScalarResult(value=as_int(first(result, "_tracks")))

    @tool("saved_playlists", "List saved playlists", read_only=True)
    async def lms_saved_playlists(
        search: str | None = None, start: int = 0, count: int = DEFAULT_COUNT
    ) -> NamePage:
        """List saved playlists. Use the returned id with lms_play_item(kind="playlist")."""
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["playlists", start, limit], {"search": search})
        rows = loop(result, "playlists_loop")
        items = [named(row, "playlist", "name", "title") for row in rows]
        return NamePage(items=items, **page_fields(result, start, items))

    @tool("saved_playlist_tracks", "List playlist tracks", read_only=True)
    async def lms_saved_playlist_tracks(
        playlist_id: str, start: int = 0, count: int = DEFAULT_COUNT
    ) -> TrackPage:
        """List the tracks inside a saved playlist."""
        limit = clamp_count(count)
        result = await ctx.client.request(
            None, ["playlists", "tracks", start, limit], {"playlist_id": playlist_id, "tags": TRACK_TAGS}
        )
        rows = loop(result, "playlisttracks_loop", "titles_loop")
        items = [track(row, ctx.client.base_url) for row in rows]
        return TrackPage(items=items, **page_fields(result, start, items))

    @tool("saved_playlist_rename", "Rename a saved playlist", idempotent=True)
    async def lms_saved_playlist_rename(playlist_id: str, new_name: str) -> Ok:
        """Rename a saved playlist (no .m3u suffix)."""
        await ctx.client.request(
            None, ["playlists", "rename"], {"playlist_id": playlist_id, "newname": new_name}
        )
        return Ok(detail=f"renamed playlist {playlist_id} to {new_name}")

    @tool("saved_playlist_delete", "Delete a saved playlist", destructive=True)
    async def lms_saved_playlist_delete(playlist_id: str) -> Ok:
        """Permanently delete a saved playlist."""
        await ctx.client.request(None, ["playlists", "delete"], {"playlist_id": playlist_id})
        return Ok(detail=f"deleted playlist {playlist_id}")
