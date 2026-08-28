"""Shared objects handed to every tool module."""

from __future__ import annotations

from dataclasses import dataclass

from .client import LMSClient
from .config import Config
from .players import PlayerRegistry


@dataclass
class ServerContext:
    config: Config
    client: LMSClient
    registry: PlayerRegistry

    @classmethod
    def create(cls, config: Config, client: LMSClient | None = None) -> ServerContext:
        lms = client or LMSClient(config)
        return cls(config=config, client=lms, registry=PlayerRegistry(lms, config))

    async def player_id(self, player: str | None) -> str:
        return await self.registry.resolve(player)

    async def aclose(self) -> None:
        await self.client.aclose()
