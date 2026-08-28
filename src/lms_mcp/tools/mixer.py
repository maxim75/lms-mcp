"""Volume, muting and tone controls."""

from __future__ import annotations

from ..context import ServerContext
from ..models import AudioSettings, Ok, ScalarResult
from ..normalize import as_bool, as_int
from ._common import first
from ._registry import Registrar


def register(tool: Registrar, ctx: ServerContext) -> None:
    async def _read(pid: str, setting: str) -> int | None:
        result = await ctx.client.request(pid, ["mixer", setting, "?"])
        return as_int(first(result, f"_{setting}"))

    @tool("get_volume", "Get volume", read_only=True)
    async def lms_get_volume(player: str | None = None) -> ScalarResult:
        """Current volume on a 0-100 scale. A negative value means the player is muted."""
        pid = await ctx.player_id(player)
        return ScalarResult(value=await _read(pid, "volume"))

    @tool("set_volume", "Set volume", idempotent=True)
    async def lms_set_volume(volume: int, relative: bool = False, player: str | None = None) -> Ok:
        """Set the volume on a 0-100 scale.

        With relative=True, `volume` is a change to apply (it may be negative) rather
        than an absolute level.
        """
        pid = await ctx.player_id(player)
        value: str | int = volume
        if relative:
            value = f"+{volume}" if volume >= 0 else str(volume)
        await ctx.client.request(pid, ["mixer", "volume", value])
        return Ok(detail=f"volume {'adjusted by' if relative else 'set to'} {volume}")

    @tool("mute", "Mute or unmute", idempotent=True)
    async def lms_mute(muted: bool = True, player: str | None = None) -> Ok:
        """Mute or unmute a player."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["mixer", "muting", 1 if muted else 0])
        return Ok(detail="muted" if muted else "unmuted")

    @tool("get_mute", "Get mute state", read_only=True)
    async def lms_get_mute(player: str | None = None) -> ScalarResult:
        """Return whether the player is muted."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["mixer", "muting", "?"])
        return ScalarResult(value=as_bool(first(result, "_muting")))

    @tool("set_bass", "Set bass", idempotent=True)
    async def lms_set_bass(level: int, player: str | None = None) -> Ok:
        """Set bass on a 0-100 scale. Only supported by SliMP3 and Squeezebox 1 hardware."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["mixer", "bass", level])
        return Ok(detail=f"bass {level}")

    @tool("set_treble", "Set treble", idempotent=True)
    async def lms_set_treble(level: int, player: str | None = None) -> Ok:
        """Set treble on a 0-100 scale. Only supported by SliMP3 and Squeezebox 1 hardware."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["mixer", "treble", level])
        return Ok(detail=f"treble {level}")

    @tool("set_pitch", "Set pitch", idempotent=True)
    async def lms_set_pitch(percent: int, player: str | None = None) -> Ok:
        """Set playback pitch from 80 to 120 percent. Only supported by Squeezebox 1 hardware."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["mixer", "pitch", percent])
        return Ok(detail=f"pitch {percent}")

    @tool("get_audio_settings", "Get audio settings", read_only=True)
    async def lms_get_audio_settings(player: str | None = None) -> AudioSettings:
        """Read volume, mute, bass, treble and pitch in one call."""
        pid = await ctx.player_id(player)
        muting = await ctx.client.request(pid, ["mixer", "muting", "?"])
        return AudioSettings(
            player_id=pid,
            volume=await _read(pid, "volume"),
            muted=as_bool(first(muting, "_muting")),
            bass=await _read(pid, "bass"),
            treble=await _read(pid, "treble"),
            pitch=await _read(pid, "pitch"),
        )
