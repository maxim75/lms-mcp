"""Server favorites: browse, play and manage."""

from __future__ import annotations

from typing import Literal

from ..context import ServerContext
from ..models import BrowsePage, Ok, ScalarResult
from ..normalize import DEFAULT_COUNT, as_bool, as_int, browse_item, clamp_count, loop, page_fields
from ._registry import Registrar


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("favorites_list", "List favorites", read_only=True)
    async def lms_favorites_list(
        item_id: str | None = None,
        search: str | None = None,
        start: int = 0,
        count: int = DEFAULT_COUNT,
    ) -> BrowsePage:
        """Browse favorites. Omit item_id for the top level.

        Favorite ids are hierarchical (e.g. `2.0.9`); pass one back as item_id to open
        a folder, or to lms_favorites_play to play it.
        """
        limit = clamp_count(count)
        result = await ctx.client.request(
            None,
            ["favorites", "items", start, limit],
            {"item_id": item_id, "search": search, "want_url": 1},
        )
        items = [browse_item(row) for row in loop(result, "loop_loop")]
        return BrowsePage(items=items, **page_fields(result, start, items))

    @tool("favorites_play", "Play a favorite")
    async def lms_favorites_play(
        item_id: str,
        how: Literal["play", "add", "insert"] = "play",
        player: str | None = None,
    ) -> Ok:
        """Play a favorite, or add it to the queue.

        A folder favorite plays all of its playable children.
        """
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["favorites", "playlist", how], {"item_id": item_id})
        return Ok(detail=f"{how} favorite {item_id}")

    @tool("favorites_add_url", "Add a favorite")
    async def lms_favorites_add_url(title: str, url: str, item_id: str | None = None) -> Ok:
        """Save a URL as a favorite. item_id optionally places it inside a folder."""
        await ctx.client.request(None, ["favorites", "add"], {"title": title, "url": url, "item_id": item_id})
        return Ok(detail=f"added favorite {title}")

    @tool("favorites_add_current", "Favorite the current track")
    async def lms_favorites_add_current(title: str | None = None, player: str | None = None) -> Ok:
        """Save whatever a player is playing right now as a favorite."""
        pid = await ctx.player_id(player)
        status = await ctx.client.request(pid, ["status", "-", 1], {"tags": "alu"})
        rows = loop(status, "playlist_loop")
        if not rows:
            return Ok(ok=False, detail="nothing is playing on this player")
        row = rows[0]
        url = row.get("url")
        if not url:
            return Ok(ok=False, detail="the current track has no URL to save")
        name = title or str(row.get("title") or url)
        await ctx.client.request(None, ["favorites", "add"], {"title": name, "url": url})
        return Ok(detail=f"added favorite {name}")

    @tool("favorites_rename", "Rename a favorite", idempotent=True)
    async def lms_favorites_rename(item_id: str, title: str) -> Ok:
        """Rename a favorite or a favorites folder."""
        await ctx.client.request(None, ["favorites", "rename"], {"item_id": item_id, "title": title})
        return Ok(detail=f"renamed {item_id} to {title}")

    @tool("favorites_move", "Move a favorite")
    async def lms_favorites_move(from_id: str, to_id: str) -> Ok:
        """Move a favorite or folder to another position in the hierarchy."""
        await ctx.client.request(None, ["favorites", "move"], {"from_id": from_id, "to_id": to_id})
        return Ok(detail=f"moved {from_id} to {to_id}")

    @tool("favorites_exists", "Check whether something is a favorite", read_only=True)
    async def lms_favorites_exists(url_or_id: str) -> ScalarResult:
        """Check whether a track id or URL is already saved as a favorite."""
        result = await ctx.client.request(None, ["favorites", "exists", url_or_id])
        exists = as_bool(result.get("exists"))
        index = as_int(result.get("index"))
        return ScalarResult(value=f"{bool(exists)}" if index is None else f"{bool(exists)} at index {index}")

    @tool("favorites_delete", "Delete a favorite", destructive=True)
    async def lms_favorites_delete(item_id: str) -> Ok:
        """Permanently delete a favorite or a favorites folder."""
        await ctx.client.request(None, ["favorites", "delete"], {"item_id": item_id})
        return Ok(detail=f"deleted favorite {item_id}")
