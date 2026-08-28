"""Async client for the Lyrion Music Server JSON-RPC endpoint."""

from __future__ import annotations

import logging
from typing import Any

import httpx2 as httpx

from .config import Config
from .errors import LMSCommandError, LMSConnectionError

logger = logging.getLogger(__name__)

Arg = str | int | float | bool


def encode_command(command: list[Arg], tags: dict[str, Arg | None] | None = None) -> list[str]:
    """Render a CLI command as the string array LMS expects.

    Positional args are stringified; `tags` become `name:value` entries, skipping
    None values so callers can pass optional filters unconditionally.
    """
    parts = [_stringify(arg) for arg in command]
    for name, value in (tags or {}).items():
        if value is None:
            continue
        parts.append(f"{name}:{_stringify(value)}")
    return parts


def _stringify(value: Arg) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


class LMSClient:
    """Issues `slim.request` calls against `/jsonrpc.js`."""

    def __init__(self, config: Config, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        auth = None
        if config.lms_username is not None:
            auth = httpx.BasicAuth(config.lms_username, config.lms_password or "")
        self._client = httpx.AsyncClient(
            timeout=config.lms_timeout,
            auth=auth,
            transport=transport,
            headers={"Content-Type": "application/json"},
        )
        self._request_id = 0

    @property
    def base_url(self) -> str:
        return self._config.lms_base_url

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        player: str | None,
        command: list[Arg],
        tags: dict[str, Arg | None] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Run one CLI command and return its `result` object.

        `player` is the player id (MAC); pass None for server-wide commands.
        """
        encoded = encode_command(command, tags)
        self._request_id += 1
        payload = {
            "id": self._request_id,
            "method": "slim.request",
            "params": [player or "", encoded],
        }

        try:
            response = await self._client.post(
                self._config.jsonrpc_url,
                json=payload,
                timeout=timeout if timeout is not None else self._config.lms_timeout,
            )
        except httpx.TransportError as exc:
            # Timeouts stringify to nothing useful, so name the class as well.
            detail = str(exc) or type(exc).__name__
            raise LMSConnectionError(
                f"cannot reach Lyrion server at {self._config.lms_base_url}: {detail}"
            ) from exc

        if response.status_code >= 400:
            raise LMSConnectionError(
                f"Lyrion server returned HTTP {response.status_code} for command {' '.join(encoded)}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise LMSCommandError(
                f"Lyrion server returned a non-JSON response to {' '.join(encoded)}"
            ) from exc

        if not isinstance(body, dict):
            raise LMSCommandError(f"unexpected response shape for {' '.join(encoded)}: {body!r}")

        error = body.get("error")
        if error:
            raise LMSCommandError(f"command {' '.join(encoded)} failed: {error}")

        result = body.get("result")
        if result is None:
            raise LMSCommandError(f"command {' '.join(encoded)} returned no result")
        if not isinstance(result, dict):
            return {"value": result}
        return result
