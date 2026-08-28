"""Plugin apps and internet radio (TIDAL, Spotty, Qobuz, TuneIn, ...).

These are menu-driven: every app exposes a hierarchy of items, and each item is
either playable or browsable further. The `app` argument is the plugin's CLI name
as reported by lms_list_apps.
"""

from __future__ import annotations

from typing import Literal

from ..context import ServerContext
from ..models import BrowsePage, Ok
from ..normalize import DEFAULT_COUNT, browse_item, clamp_count, loop, page_fields
from ._registry import Registrar


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("list_apps", "List plugin apps", read_only=True, open_world=True)
    async def lms_list_apps() -> BrowsePage:
        """List the music service plugins installed on the server.

        The `id` of each row is the name to pass as `app` to the other app tools.
        """
        result = await ctx.client.request(None, ["apps", 0, 999])
        rows = loop(result, "appss_loop", "apps_loop", "loop_loop")
        items = [browse_item({**row, "id": row.get("cmd") or row.get("name")}) for row in rows]
        return BrowsePage(items=items, **page_fields(result, 0, items))

    @tool("app_browse", "Browse a plugin app", read_only=True, open_world=True)
    async def lms_app_browse(
        app: str,
        item_id: str | None = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
        player: str | None = None,
    ) -> BrowsePage:
        """Browse an app's menu. Omit item_id for the app's top level.

        Rows with has_items can be browsed again by passing their id back as item_id;
        rows with is_audio can be played with lms_app_play.
        """
        pid = await _optional_player(ctx, player)
        limit = clamp_count(count)
        result = await ctx.client.request(pid, [app, "items", start, limit], {"item_id": item_id})
        items = [browse_item(row) for row in loop(result, "loop_loop", "item_loop")]
        return BrowsePage(items=items, **page_fields(result, start, items))

    @tool("app_search", "Search inside a plugin app", read_only=True, open_world=True)
    async def lms_app_search(
        app: str,
        query: str,
        item_id: str | None = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
        player: str | None = None,
    ) -> BrowsePage:
        """Search within an app. Some apps only accept a search under a specific menu item_id."""
        pid = await _optional_player(ctx, player)
        limit = clamp_count(count)
        result = await ctx.client.request(
            pid, [app, "items", start, limit], {"search": query, "item_id": item_id}
        )
        items = [browse_item(row) for row in loop(result, "loop_loop", "item_loop")]
        return BrowsePage(items=items, **page_fields(result, start, items))

    @tool("app_play", "Play from a plugin app", open_world=True)
    async def lms_app_play(
        app: str,
        item_id: str,
        how: Literal["play", "add", "insert"] = "play",
        player: str | None = None,
    ) -> Ok:
        """Play an app item, or add it to the queue."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, [app, "playlist", how], {"item_id": item_id})
        return Ok(detail=f"{how} {app} item {item_id}")

    @tool("app_add", "Add an app item to the queue", open_world=True)
    async def lms_app_add(app: str, item_id: str, player: str | None = None) -> Ok:
        """Append an app item to the end of the queue."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, [app, "playlist", "add"], {"item_id": item_id})
        return Ok(detail=f"added {app} item {item_id}")

    @tool("list_radios", "List radio plugins", read_only=True, open_world=True)
    async def lms_list_radios() -> BrowsePage:
        """List the internet radio services available on the server."""
        result = await ctx.client.request(None, ["radios", 0, 999])
        rows = loop(result, "radioss_loop", "radios_loop", "loop_loop")
        items = [browse_item({**row, "id": row.get("cmd") or row.get("name")}) for row in rows]
        return BrowsePage(items=items, **page_fields(result, 0, items))

    @tool("radio_browse", "Browse a radio service", read_only=True, open_world=True)
    async def lms_radio_browse(
        service: str = "tunein",
        item_id: str | None = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
        player: str | None = None,
    ) -> BrowsePage:
        """Browse an internet radio service's menu, e.g. `tunein` for TuneIn.

        Play a station with lms_app_play using the same service name, or with
        lms_play_url if the row carries a direct stream URL.
        """
        pid = await _optional_player(ctx, player)
        limit = clamp_count(count)
        result = await ctx.client.request(pid, [service, "items", start, limit], {"item_id": item_id})
        items = [browse_item(row) for row in loop(result, "loop_loop", "item_loop")]
        return BrowsePage(items=items, **page_fields(result, start, items))


async def _optional_player(ctx: ServerContext, player: str | None) -> str | None:
    """Browsing works server-wide, but apps personalise menus when given a player."""
    if player is None and ctx.config.default_player is None:
        return None
    return await ctx.player_id(player)
