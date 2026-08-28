"""The Random Play plugin: endless mixes drawn from the library."""

from __future__ import annotations

from typing import Literal

from ..context import ServerContext
from ..models import NamePage, Ok, ScalarResult
from ..normalize import DEFAULT_COUNT, clamp_count, loop, page_fields
from ._common import first
from ._registry import Registrar

MixKind = Literal["tracks", "albums", "artists", "year"]
# The plugin calls the artist mix "contributors".
MIX_COMMANDS: dict[str, str] = {
    "tracks": "tracks",
    "albums": "albums",
    "artists": "contributors",
    "year": "year",
}


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("random_play", "Start a random mix")
    async def lms_random_play(kind: MixKind = "tracks", player: str | None = None) -> Ok:
        """Start an endless random mix of tracks, albums, artists or a random year."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["randomplay", MIX_COMMANDS[kind]])
        return Ok(detail=f"random {kind} mix started")

    @tool("random_stop", "Stop refilling the random mix", idempotent=True)
    async def lms_random_stop(player: str | None = None) -> Ok:
        """Stop adding new tracks to the mix. What is already queued still plays out."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["randomplay", "disable"])
        return Ok(detail="random mix will not be refilled")

    @tool("random_status", "Random mix status", read_only=True)
    async def lms_random_status(player: str | None = None) -> ScalarResult:
        """Return which kind of random mix is running, if any."""
        pid = await ctx.player_id(player)
        result = await ctx.client.request(pid, ["randomplayisactive"])
        return ScalarResult(value=first(result, "_randomplayisactive"))

    @tool("random_genres", "List random mix genres", read_only=True)
    async def lms_random_genres(start: int = 0, count: int = DEFAULT_COUNT) -> NamePage:
        """List genres and whether each one is included in random mixes."""
        limit = clamp_count(count)
        result = await ctx.client.request(None, ["randomplaygenrelist", start, limit])
        rows = loop(result, "item_loop", "loop_loop")
        items = []
        for row in rows:
            name = str(row.get("text") or row.get("name") or "")
            included = row.get("checkbox")
            items.append({"id": name, "name": f"{name} ({'on' if included in (1, '1') else 'off'})"})
        page = page_fields(result, start, items)
        return NamePage(items=items, **page)  # type: ignore[arg-type]

    @tool("random_choose_genre", "Include or exclude a genre", idempotent=True)
    async def lms_random_choose_genre(genre: str, include: bool, player: str | None = None) -> Ok:
        """Turn a genre on or off for random mixes."""
        pid = await ctx.player_id(player)
        await ctx.client.request(pid, ["randomplaychoosegenre", genre, 1 if include else 0])
        return Ok(detail=f"{genre} {'included in' if include else 'excluded from'} random mixes")
