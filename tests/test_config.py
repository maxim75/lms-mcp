from __future__ import annotations

import pytest

from lms_mcp.config import Config, ConfigError


def test_defaults_build_a_local_lms_url():
    config = Config.from_env({"MCP_ALLOW_ANONYMOUS": "true"})
    assert config.lms_base_url == "http://localhost:9000"
    assert config.jsonrpc_url == "http://localhost:9000/jsonrpc.js"
    assert config.mcp_path == "/mcp"
    assert config.auth_token is None


def test_host_port_and_protocol_are_combined():
    config = Config.from_env(
        {"MCP_AUTH_TOKEN": "t", "LMS_HOST": "nas", "LMS_PORT": "9002", "LMS_PROTOCOL": "https"}
    )
    assert config.lms_base_url == "https://nas:9002"


def test_base_url_overrides_host_and_port_and_loses_trailing_slash():
    config = Config.from_env(
        {"MCP_AUTH_TOKEN": "t", "LMS_HOST": "ignored", "LMS_BASE_URL": "https://music.example.com/lms/"}
    )
    assert config.lms_base_url == "https://music.example.com/lms"


def test_missing_token_refuses_to_start():
    with pytest.raises(ConfigError, match="MCP_AUTH_TOKEN"):
        Config.from_env({})


def test_anonymous_must_be_explicit():
    assert Config.from_env({"MCP_ALLOW_ANONYMOUS": "yes"}).allow_anonymous is True


def test_path_is_normalised():
    assert Config.from_env({"MCP_AUTH_TOKEN": "t", "MCP_PATH": "rpc/"}).mcp_path == "/rpc"


def test_allowed_hosts_are_split():
    config = Config.from_env({"MCP_AUTH_TOKEN": "t", "MCP_ALLOWED_HOSTS": "a.example, b.example"})
    assert config.allowed_hosts == ["a.example", "b.example"]


def test_bad_integer_is_reported():
    with pytest.raises(ValueError, match="expected an integer"):
        Config.from_env({"MCP_AUTH_TOKEN": "t", "LMS_PORT": "nine thousand"})
