"""Entrypoint: serve MCP over Streamable HTTP with uvicorn."""

from __future__ import annotations

import logging
import sys

import uvicorn

from .config import Config, ConfigError
from .http import create_app

logger = logging.getLogger("lms_mcp")


def main() -> None:
    try:
        config = Config.from_env()
    except (ConfigError, ValueError) as exc:
        print(f"lms-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if config.allow_anonymous:
        logger.warning("MCP_ALLOW_ANONYMOUS is set: the MCP endpoint is unauthenticated")
    logger.info(
        "serving MCP at http://%s:%s%s for Lyrion at %s",
        config.mcp_host,
        config.mcp_port,
        config.mcp_path,
        config.lms_base_url,
    )

    uvicorn.run(
        create_app(config),
        host=config.mcp_host,
        port=config.mcp_port,
        log_level=config.log_level.lower(),
        access_log=config.log_level == "DEBUG",
    )


if __name__ == "__main__":
    main()
