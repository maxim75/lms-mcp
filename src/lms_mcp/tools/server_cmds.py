"""Server-wide commands: status, version, library totals, scanning and preferences."""

from __future__ import annotations

from ..context import ServerContext
from ..models import LibraryTotals, Ok, ScalarResult, ScanStatus, ServerStatus, SyncGroup, SyncGroups
from ..normalize import library_totals, loop, scan_status, server_status
from ._common import first
from ._registry import Registrar


def register(tool: Registrar, ctx: ServerContext) -> None:
    @tool("server_status", "Server status", read_only=True)
    async def lms_server_status() -> ServerStatus:
        """Overview of the Lyrion server: version, library totals and connected players.

        Start here when you need to know which players exist.
        """
        result = await ctx.client.request(None, ["serverstatus", 0, 999])
        ctx.registry.invalidate()
        return server_status(result)

    @tool("server_version", "Server version", read_only=True)
    async def lms_server_version() -> ScalarResult:
        """Return the Lyrion Music Server version string."""
        result = await ctx.client.request(None, ["version", "?"])
        return ScalarResult(value=first(result, "_version"))

    @tool("library_totals", "Library totals", read_only=True)
    async def lms_library_totals() -> LibraryTotals:
        """Counts of genres, artists, albums and songs in the library."""
        values = {}
        for kind in ("genres", "artists", "albums", "songs"):
            result = await ctx.client.request(None, ["info", "total", kind, "?"])
            values[kind] = first(result, f"_{kind}")
        return library_totals(values)

    @tool("list_sync_groups", "List sync groups", read_only=True)
    async def lms_list_sync_groups() -> SyncGroups:
        """Return the players currently grouped together for synchronised playback."""
        result = await ctx.client.request(None, ["syncgroups", "?"])
        groups = []
        for row in loop(result, "syncgroups_loop"):
            members = str(row.get("sync_members") or "")
            names = str(row.get("sync_member_names") or "")
            groups.append(
                SyncGroup(
                    member_ids=[m for m in members.split(",") if m],
                    member_names=[n for n in names.split(",") if n],
                )
            )
        return SyncGroups(groups=groups)

    @tool("rescan_start", "Start library rescan")
    async def lms_rescan_start(mode: str = "new") -> Ok:
        """Start a library scan.

        mode is "new" for new and changed files (the default), "full" for a complete
        rescan of the music folders, or "playlists" to rescan playlists only.
        """
        command: list[str] = ["rescan"]
        if mode == "full":
            command.append("full")
        elif mode == "playlists":
            command.append("playlists")
        await ctx.client.request(None, command)
        return Ok(detail=f"{mode} scan started")

    @tool("rescan_status", "Rescan progress", read_only=True)
    async def lms_rescan_status() -> ScanStatus:
        """Report whether a scan is running and how far along each step is."""
        result = await ctx.client.request(None, ["rescanprogress"])
        return scan_status(result)

    @tool("rescan_abort", "Abort rescan")
    async def lms_rescan_abort() -> Ok:
        """Stop a library scan that is currently running."""
        await ctx.client.request(None, ["abortscan"])
        return Ok(detail="scan aborted")

    @tool("get_pref", "Read a server preference", read_only=True)
    async def lms_get_pref(name: str) -> ScalarResult:
        """Read a server preference. Prefix with a namespace for plugin prefs, e.g. `plugin.name:pref`."""
        result = await ctx.client.request(None, ["pref", name, "?"])
        return ScalarResult(value=first(result, "_p2", "_value"))

    @tool("get_string", "Look up a localized string", read_only=True)
    async def lms_get_string(token: str) -> ScalarResult:
        """Resolve a server string token into its localized text."""
        result = await ctx.client.request(None, ["getstring", token])
        return ScalarResult(value=first(result, token, "_" + token))

    @tool("set_pref", "Write a server preference", destructive=True)
    async def lms_set_pref(name: str, value: str) -> Ok:
        """Change a server preference. Wrong values can break the server's behaviour."""
        await ctx.client.request(None, ["pref", name, value])
        return Ok(detail=f"{name} set to {value}")

    @tool("wipe_cache", "Wipe library and rescan", destructive=True)
    async def lms_wipe_cache() -> Ok:
        """Delete the music library database and start a full rescan from scratch."""
        await ctx.client.request(None, ["wipecache"])
        return Ok(detail="cache wiped, full rescan started")

    @tool("server_restart", "Restart the server", destructive=True)
    async def lms_server_restart() -> Ok:
        """Restart Lyrion Music Server. Playback stops until it comes back up."""
        await ctx.client.request(None, ["restartserver"])
        return Ok(detail="restart requested")

    @tool("server_stop", "Shut down the server", destructive=True)
    async def lms_server_stop() -> Ok:
        """Shut down Lyrion Music Server. Nothing here can start it again."""
        await ctx.client.request(None, ["stopserver"])
        return Ok(detail="shutdown requested")
