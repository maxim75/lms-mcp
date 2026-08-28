"""Transport controls: play, pause, seek, track skipping, repeat and shuffle."""

from __future__ import annotations

from typing import Literal

from ..context import ServerContext
from ..models import Ok, ScalarResult
from ..normalize import REPEAT_MODES, SHUFFLE_MODES, as_float, as_int
from ._common import first
from ._registry import Registrar

REPEAT_VALUES = {"off": 0, "song": 1, "playlist": 2}
SHUFFLE_VALUES = {"off": 0, "songs": 1, "albums": 2}


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("play", "Play", idempotent=True)
    async def lms_play(player: str | None = None, fade_seconds: int | None = None) -> Ok:
        """Start (or resume) playback of the player's current queue."""
        pid = await ctx.player_id(player)
        command: list[str | int] = ["play"]
        if fade_seconds is not None:
            command.append(fade_seconds)
        await ctx.client.request(pid, command)
        return Ok(detail="playing")

    @tool("pause", "Pause", idempotent=True)
    async def lms_pause(player: str | None = None) -> Ok:
        """Pause playback. Use lms_play to resume, or lms_toggle_pause to flip the state."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["pause", 1])
        return Ok(detail="paused")

    @tool("toggle_pause", "Toggle pause")
    async def lms_toggle_pause(player: str | None = None) -> Ok:
        """Toggle between playing and paused."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["pause"])
        return Ok(detail="toggled")

    @tool("stop", "Stop", idempotent=True)
    async def lms_stop(player: str | None = None) -> Ok:
        """Stop playback and reset the position to the start of the current track."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["stop"])
        return Ok(detail="stopped")

    @tool("get_mode", "Get playback mode", read_only=True)
    async def lms_get_mode(player: str | None = None) -> ScalarResult:
        """Return whether the player is currently playing, paused or stopped."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["mode", "?"])
        return ScalarResult(value=first(result, "_mode"))

    @tool("next_track", "Next track")
    async def lms_next_track(player: str | None = None) -> Ok:
        """Skip to the next track in the queue."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "index", "+1"])
        return Ok(detail="skipped forward")

    @tool("previous_track", "Previous track")
    async def lms_previous_track(player: str | None = None) -> Ok:
        """Go back to the previous track in the queue."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "index", "-1"])
        return Ok(detail="skipped back")

    @tool("play_index", "Play queue position", idempotent=True)
    async def lms_play_index(index: int, player: str | None = None) -> Ok:
        """Jump to a specific position in the current queue (0-based) and play it."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "index", index])
        return Ok(detail=f"playing queue position {index}")

    @tool("seek", "Seek", idempotent=True)
    async def lms_seek(seconds: float, relative: bool = False, player: str | None = None) -> Ok:
        """Seek within the current track.

        With relative=False, seconds is an absolute position from the start of the
        track. With relative=True, it is an offset from the current position and may
        be negative.
        """
        pid = await ctx.player_id(player)
        value: str | float = seconds
        if relative:
            value = f"+{seconds}" if seconds >= 0 else str(seconds)
        await ctx.client.request(pid, ["time", value])
        return Ok(detail=f"seek {'by' if relative else 'to'} {seconds}s")

    @tool("get_time", "Get elapsed time", read_only=True)
    async def lms_get_time(player: str | None = None) -> ScalarResult:
        """Return the elapsed seconds of the currently playing track."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["time", "?"])
        return ScalarResult(value=as_float(first(result, "_time")))

    @tool("set_repeat", "Set repeat mode", idempotent=True)
    async def lms_set_repeat(mode: Literal["off", "song", "playlist"], player: str | None = None) -> Ok:
        """Set the repeat mode."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "repeat", REPEAT_VALUES[mode]])
        return Ok(detail=f"repeat {mode}")

    @tool("get_repeat", "Get repeat mode", read_only=True)
    async def lms_get_repeat(player: str | None = None) -> ScalarResult:
        """Return the current repeat mode (off, song or playlist)."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["playlist", "repeat", "?"])
        return ScalarResult(value=REPEAT_MODES.get(as_int(first(result, "_repeat")) or 0))

    @tool("set_shuffle", "Set shuffle mode", idempotent=True)
    async def lms_set_shuffle(mode: Literal["off", "songs", "albums"], player: str | None = None) -> Ok:
        """Set the shuffle mode."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["playlist", "shuffle", SHUFFLE_VALUES[mode]])
        return Ok(detail=f"shuffle {mode}")

    @tool("get_shuffle", "Get shuffle mode", read_only=True)
    async def lms_get_shuffle(player: str | None = None) -> ScalarResult:
        """Return the current shuffle mode (off, songs or albums)."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["playlist", "shuffle", "?"])
        return ScalarResult(value=SHUFFLE_MODES.get(as_int(first(result, "_shuffle")) or 0))
