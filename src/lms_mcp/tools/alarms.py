"""Player alarms."""

from __future__ import annotations

from ..context import ServerContext
from ..models import AlarmList, BrowsePage, Ok, ScalarResult
from ..normalize import DEFAULT_COUNT, alarm, as_int, browse_item, clamp_count, loop, page_fields
from ._registry import Registrar


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("alarms_list", "List alarms", read_only=True)
    async def lms_alarms_list(
        enabled_only: bool = False, start: int = 0, count: int = DEFAULT_COUNT, player: str | None = None
    ) -> AlarmList:
        """List the alarms set on a player. Times are seconds after midnight."""
        pid = await ctx.player_id(player)
        limit = clamp_count(count)
        result = await ctx.client.request(
            pid, ["alarms", start, limit], {"filter": "enabled" if enabled_only else "all"}
        )
        return AlarmList(
            alarms=[alarm(row) for row in loop(result, "alarms_loop")],
            total=as_int(result.get("count")),
        )

    @tool("alarm_add", "Add an alarm")
    async def lms_alarm_add(
        time_seconds: int,
        days: str = "0,1,2,3,4,5,6",
        enabled: bool = True,
        repeat: bool = True,
        volume: int | None = None,
        url: str | None = None,
        player: str | None = None,
    ) -> ScalarResult:
        """Create an alarm.

        time_seconds is seconds after midnight (07:30 is 27000). `days` is a
        comma-separated list where 0 is Sunday. `url` may be a track/playlist URL, or
        one of randomplay:track, randomplay:album, randomplay:contributor,
        randomplay:year; omit it to use the player's current playlist.
        """
        pid = await ctx.player_id(player)
        result = await ctx.client.request(
            pid,
            ["alarm", "add"],
            {
                "time": time_seconds,
                "dow": days,
                "enabled": 1 if enabled else 0,
                "repeat": 1 if repeat else 0,
                "volume": volume,
                "url": url,
            },
        )
        return ScalarResult(value=result.get("id"))

    @tool("alarm_update", "Update an alarm", idempotent=True)
    async def lms_alarm_update(
        alarm_id: str,
        time_seconds: int | None = None,
        days: str | None = None,
        enabled: bool | None = None,
        repeat: bool | None = None,
        volume: int | None = None,
        url: str | None = None,
        player: str | None = None,
    ) -> Ok:
        """Change one or more settings on an existing alarm."""
        pid = await ctx.player_id(player)
        await ctx.client.request(
            pid,
            ["alarm", "update"],
            {
                "id": alarm_id,
                "time": time_seconds,
                "dow": days,
                "enabled": None if enabled is None else (1 if enabled else 0),
                "repeat": None if repeat is None else (1 if repeat else 0),
                "volume": volume,
                "url": url,
            },
        )
        return Ok(detail=f"updated alarm {alarm_id}")

    @tool("alarm_delete", "Delete an alarm")
    async def lms_alarm_delete(alarm_id: str, player: str | None = None) -> Ok:
        """Delete an alarm from a player."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["alarm", "delete"], {"id": alarm_id})
        return Ok(detail=f"deleted alarm {alarm_id}")

    @tool("alarms_enable_all", "Enable all alarms", idempotent=True)
    async def lms_alarms_enable_all(player: str | None = None) -> Ok:
        """Enable every alarm on a player."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["alarm", "enableall"])
        return Ok(detail="all alarms enabled")

    @tool("alarms_disable_all", "Disable all alarms", idempotent=True)
    async def lms_alarms_disable_all(player: str | None = None) -> Ok:
        """Disable every alarm on a player without deleting them."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["alarm", "disableall"])
        return Ok(detail="all alarms disabled")

    @tool("alarm_playlists", "List alarm sounds", read_only=True)
    async def lms_alarm_playlists(start: int = 0, count: int = DEFAULT_COUNT) -> BrowsePage:
        """List the playlists, natural sounds and favorites an alarm can play.

        Use a returned `url` as the `url` argument of lms_alarm_add.
        """
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["alarm", "playlists", start, limit])
        rows = loop(result, "item_loop", "playlists_loop", "loop_loop")
        items = [browse_item({**row, "name": row.get("title"), "type": row.get("category")}) for row in rows]
        return BrowsePage(items=items, **page_fields(result, start, items))
