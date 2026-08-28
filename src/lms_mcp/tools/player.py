"""Player discovery, power, naming, sync and status."""

from __future__ import annotations

from ..context import ServerContext
from ..models import Ok, Player, PlayerList, PlayerStatus, ScalarResult
from ..normalize import as_bool, as_int, player_status
from ..normalize import player as to_player
from ._common import first
from ._registry import Registrar

# artist, album, duration, album_id, artist_id, genre, tracknum, year, url,
# coverid, remote artwork, remote flag, remote title, artwork track id.
TRACK_TAGS = "aldesgtyucKxNJ"


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("list_players", "List players", read_only=True)
    async def lms_list_players() -> PlayerList:
        """List every player known to the server, with the ids and names other tools accept."""
        players = await ctx.registry.list_players(refresh=True)
        return PlayerList(players=players, default_player=ctx.config.default_player)

    @tool("player_status", "Player status", read_only=True)
    async def lms_player_status(player: str | None = None) -> PlayerStatus:
        """What a player is doing right now: mode, volume, current track and queue position."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["status", "-", 1], {"tags": TRACK_TAGS})
        return player_status(result, pid, ctx.client.base_url)

    @tool("player_info", "Player details", read_only=True)
    async def lms_player_info(player: str | None = None) -> Player:
        """Model, IP address and capabilities of a single player."""
        pid = await ctx.player_id(player)
        for candidate in await ctx.registry.list_players():
            if candidate.id == pid:
                return candidate
        result = await ctx.client.request(None, ["players", 0, 999])
        for row in result.get("players_loop") or []:
            if str(row.get("playerid")) == pid:
                return to_player(row)
        return Player(id=pid, name=pid)

    @tool("get_power", "Get power state", read_only=True)
    async def lms_get_power(player: str | None = None) -> ScalarResult:
        """Return whether the player is powered on."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["power", "?"])
        return ScalarResult(value=as_bool(first(result, "_power")))

    @tool("set_power", "Set power state", idempotent=True)
    async def lms_set_power(on: bool, player: str | None = None) -> Ok:
        """Turn a player on or off."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["power", 1 if on else 0])
        return Ok(detail=f"power {'on' if on else 'off'}")

    @tool("sleep", "Sleep timer", idempotent=True)
    async def lms_sleep(seconds: int, player: str | None = None) -> Ok:
        """Keep playing for this many seconds, then power the player off. Use 0 to cancel."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["sleep", seconds])
        return Ok(detail=f"sleeping in {seconds}s" if seconds else "sleep timer cancelled")

    @tool("sync", "Synchronise players")
    async def lms_sync(other_player: str, player: str | None = None) -> Ok:
        """Add `other_player` to `player`'s sync group so they play in step."""
        pid = await ctx.player_id(player)
        other = await ctx.player_id(other_player)
        await ctx.client.request(pid, ["sync", other])
        return Ok(detail=f"{other} synced to {pid}")

    @tool("unsync", "Remove from sync group", idempotent=True)
    async def lms_unsync(player: str | None = None) -> Ok:
        """Remove the player from whatever sync group it is in."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["sync", "-"])
        return Ok(detail=f"{pid} unsynced")

    @tool("rename_player", "Rename player", idempotent=True)
    async def lms_rename_player(name: str, player: str | None = None) -> Ok:
        """Change the display name of a player."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["name", name])
        ctx.registry.invalidate()
        return Ok(detail=f"renamed to {name}")

    @tool("signal_strength", "Wireless signal strength", read_only=True)
    async def lms_signal_strength(player: str | None = None) -> ScalarResult:
        """Wireless signal strength from 1 to 100, or 0 for a wired player."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["signalstrength", "?"])
        return ScalarResult(value=as_int(first(result, "_signalstrength")))

    @tool("show_message", "Show a message on the display")
    async def lms_show_message(
        line1: str,
        line2: str | None = None,
        duration: int = 3,
        player: str | None = None,
    ) -> Ok:
        """Display a short message on a player with a screen."""
        pid = await ctx.player_id(player)
        await ctx.client.request(
            pid,
            ["show"],
            {"line1": line1, "line2": line2, "duration": duration},
        )
        return Ok(detail="message shown")

    @tool("press_button", "Simulate a button press")
    async def lms_press_button(button: str, player: str | None = None) -> Ok:
        """Simulate a remote or front-panel button press.

        Button codes come from the player's Default.map, e.g. `volup`, `jump_fwd`,
        `pause`, `preset_1.single`.
        """
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["button", button])
        return Ok(detail=f"pressed {button}")
