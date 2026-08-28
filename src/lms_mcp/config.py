"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

TRUE_VALUES = {"1", "true", "yes", "on"}


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in TRUE_VALUES


def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"expected an integer, got {value!r}") from exc


def _float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"expected a number, got {value!r}") from exc


class ConfigError(Exception):
    """The process is misconfigured and must not start."""


@dataclass(frozen=True)
class Config:
    """Runtime settings, built from environment variables."""

    lms_base_url: str = "http://localhost:9000"
    lms_timeout: float = 10.0
    lms_username: str | None = None
    lms_password: str | None = None
    default_player: str | None = None
    enable_destructive: bool = False

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 9055
    mcp_path: str = "/mcp"
    auth_token: str | None = None
    allow_anonymous: bool = False
    allowed_hosts: list[str] = field(default_factory=list)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        src: Any = os.environ if env is None else env

        base_url = (src.get("LMS_BASE_URL") or "").strip()
        if not base_url:
            protocol = (src.get("LMS_PROTOCOL") or "http").strip()
            host = (src.get("LMS_HOST") or "localhost").strip()
            port = _int(src.get("LMS_PORT"), 9000)
            base_url = f"{protocol}://{host}:{port}"
        base_url = base_url.rstrip("/")

        path = (src.get("MCP_PATH") or "/mcp").strip()
        if not path.startswith("/"):
            path = "/" + path
        path = path.rstrip("/") or "/mcp"

        token = (src.get("MCP_AUTH_TOKEN") or "").strip() or None
        allow_anonymous = _bool(src.get("MCP_ALLOW_ANONYMOUS"))
        if token is None and not allow_anonymous:
            raise ConfigError(
                "MCP_AUTH_TOKEN is not set. Set it to a secret value, or set "
                "MCP_ALLOW_ANONYMOUS=true to deliberately run without authentication."
            )

        hosts = [h.strip() for h in (src.get("MCP_ALLOWED_HOSTS") or "").split(",") if h.strip()]

        return cls(
            lms_base_url=base_url,
            lms_timeout=_float(src.get("LMS_TIMEOUT"), 10.0),
            lms_username=(src.get("LMS_USERNAME") or "").strip() or None,
            lms_password=src.get("LMS_PASSWORD") or None,
            default_player=(src.get("LMS_DEFAULT_PLAYER") or "").strip() or None,
            enable_destructive=_bool(src.get("LMS_ENABLE_DESTRUCTIVE")),
            mcp_host=(src.get("MCP_HOST") or "0.0.0.0").strip(),
            mcp_port=_int(src.get("MCP_PORT"), 9055),
            mcp_path=path,
            auth_token=token,
            allow_anonymous=allow_anonymous,
            allowed_hosts=hosts,
            log_level=(src.get("LOG_LEVEL") or "INFO").strip().upper(),
        )

    @property
    def jsonrpc_url(self) -> str:
        return f"{self.lms_base_url}/jsonrpc.js"
