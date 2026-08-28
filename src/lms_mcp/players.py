"""Resolve friendly player names to Lyrion player ids."""

from __future__ import annotations

import re
import time

from .client import LMSClient
from .config import Config
from .errors import LMSError
from .models import Player
from .normalize import loop
from .normalize import player as to_player

MAC_RE = re.compile(r"^(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.IGNORECASE)
CACHE_TTL = 10.0


class PlayerNotFound(LMSError):
    """The requested player could not be matched to a connected device."""


class PlayerRegistry:
    """Caches the player list and maps names/ids onto player ids."""

    def __init__(self, client: LMSClient, config: Config, ttl: float = CACHE_TTL) -> None:
        self._client = client
        self._config = config
        self._ttl = ttl
        self._players: list[Player] = []
        self._fetched_at = 0.0

    async def list_players(self, *, refresh: bool = False) -> list[Player]:
        now = time.monotonic()
        if refresh or not self._players or now - self._fetched_at > self._ttl:
            result = await self._client.request(None, ["serverstatus", 0, 999])
            self._players = [to_player(row) for row in loop(result, "players_loop")]
            self._fetched_at = now
        return self._players

    def invalidate(self) -> None:
        self._fetched_at = 0.0

    async def resolve(self, player: str | None) -> str:
        """Return a player id for a name, an id, or the configured default."""
        wanted = (player or "").strip() or self._config.default_player
        if not wanted:
            names = await self._names()
            raise PlayerNotFound(
                f"No player specified and LMS_DEFAULT_PLAYER is not set. Pass `player` as one of: {names}"
            )

        if MAC_RE.match(wanted):
            return wanted.lower()

        players = await self.list_players()
        for candidate in players:
            if candidate.id.lower() == wanted.lower():
                return candidate.id

        exact = [p for p in players if p.name.lower() == wanted.lower()]
        if len(exact) == 1:
            return exact[0].id
        if len(exact) > 1:
            raise PlayerNotFound(f"{wanted!r} matches more than one player; use the player id instead")

        partial = [p for p in players if wanted.lower() in p.name.lower()]
        if len(partial) == 1:
            return partial[0].id
        if len(partial) > 1:
            options = ", ".join(sorted(p.name for p in partial))
            raise PlayerNotFound(f"{wanted!r} is ambiguous; did you mean one of: {options}?")

        # Stale cache is the usual cause of a miss for a player that just connected.
        if self._fetched_at:
            self.invalidate()
            refreshed = await self.list_players()
            if any(p.name.lower() == wanted.lower() for p in refreshed):
                return next(p.id for p in refreshed if p.name.lower() == wanted.lower())

        raise PlayerNotFound(f"No player named {wanted!r}. Available players: {await self._names()}")

    async def _names(self) -> str:
        players = await self.list_players()
        if not players:
            return "(no players are connected to the Lyrion server)"
        return ", ".join(f"{p.name!r}" for p in players)
