# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An MCP server that controls Lyrion Music Server (LMS, formerly Logitech Media Server /
Squeezebox Server) and its players. It speaks **MCP Streamable HTTP** (JSON-RPC 2.0 over
HTTP POST at `/mcp`), not stdio, so it runs as a long-lived container behind a URL and
exposes `/health` for orchestrators. Every tool call is translated into an LMS CLI command
and POSTed to the server's `/jsonrpc.js` endpoint as `slim.request`.

The MCP SDK in use is **mcp 2.x**, where `FastMCP` was renamed `MCPServer`
(`from mcp.server.mcpserver import MCPServer`). `mcp.server.fastmcp` raises
`ModuleNotFoundError` on import in this version — don't reach for it or for v1-era API
names when reading SDK docs/examples.

## Commands

```bash
uv sync                                   # install deps
uv run pytest -q                          # full test suite (hermetic, no LMS needed)
uv run pytest tests/test_tools_queue.py -q -k play_item   # a single test
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run ruff format --check .              # format check only (what CI runs)
uv run lms-mcp                            # run the server (needs LMS_HOST/MCP_AUTH_TOKEN env)
docker compose up --build -d              # run as a container
```

Local dev needs `MCP_AUTH_TOKEN` set (or `MCP_ALLOW_ANONYMOUS=true`) or the process refuses
to start — see `.env.example` for the full variable list and `README.md` for the Coolify
deployment steps.

## Architecture

**Tools never touch HTTP.** Each tool in `src/lms_mcp/tools/*.py` builds an LMS CLI command
array (e.g. `["mixer", "volume", "25"]`) and hands it to `LMSClient.request()`
(`client.py`), which frames it as `{"id", "method": "slim.request", "params": [player, command]}`
and POSTs to `/jsonrpc.js`. This is what makes tools cheap to test: `tests/conftest.py`'s
`FakeLMS` mocks the HTTP transport and asserts on the exact command array a tool emitted,
without ever touching a real media server.

Request flow: `tools/*.py` → `LMSClient.request()` → `normalize.py` (turn LMS's `*_loop`
payloads into `models.py` pydantic types) → structured tool output.

Key modules in `src/lms_mcp/`:
- `config.py` — `Config.from_env()`. All environment parsing and startup validation lives
  here (e.g. refusing to boot without `MCP_AUTH_TOKEN` unless `MCP_ALLOW_ANONYMOUS=true`).
- `client.py` — `LMSClient`, the only thing that speaks HTTP to LMS. `encode_command()`
  stringifies positional args and renders tagged params as `name:value`, skipping `None`.
- `players.py` — `PlayerRegistry.resolve()` turns a name, MAC, or unique name-prefix into a
  player id, via a short-TTL cache of `serverstatus`. Falls back to `LMS_DEFAULT_PLAYER` when
  a tool call omits `player`; raises `PlayerNotFound` (a `ToolError`) listing available
  players otherwise.
- `normalize.py` — all the mapping from LMS's inconsistent `*_loop` / tagged-field responses
  into the typed models in `models.py`. `page_fields()` / `clamp_count()` standardize
  pagination across every list-returning tool (capped at `MAX_COUNT=200`).
- `errors.py` — `LMSError` subclasses `ToolError` directly, so a command failure surfaces to
  the model as a readable message instead of a generic crash, with no wrapper needed around
  tool bodies.
- `context.py` — `ServerContext` bundles `config` + `client` + `registry` and is passed into
  every `tools/*.register(tool, ctx)` call; no globals.
- `http.py` — builds the ASGI app: `BearerAuthMiddleware` (constant-time token compare,
  `/health` exempt), the cached `HealthProbe` (pings LMS `version`, 5s TTL), and
  `streamable_http_app(stateless_http=True, json_response=True)` — stateless by design so it
  survives proxy restarts and scales horizontally with no sticky sessions.
- `tools/_registry.py` — `Registrar` applies the `lms_` name prefix, sets `ToolAnnotations`
  (read-only/destructive/idempotent hints), and is where the `LMS_ENABLE_DESTRUCTIVE` gate
  lives: a tool registered with `destructive=True` is silently skipped unless that env var
  is set. `tools/__init__.py`'s `MODULES` tuple is the single place new tool modules get
  wired in.
- `tools/*.py` — one module per LMS command family (server, player, playback, mixer, queue,
  library, favorites, alarms, randomplay, apps). `tools/player.py`'s `TRACK_TAGS` constant
  (the LMS tag-letters requested on `status`/`titles` queries) is imported by several other
  modules — check there before adding a new track field.

## Testing conventions

- `tests/conftest.py`'s `FakeLMS` fixture records every `(player, command)` call and answers
  from a `responses` dict keyed by command prefix (`lms.reply(("info", "total", "genres"), {...})`);
  `lms.last` / `lms.commands` assert on what a tool actually sent.
- `tests/helpers.py`'s `call(ctx, "lms_tool_name", **args)` invokes a tool through the real
  MCP `call_tool()` path (not by calling the Python function directly), so schema validation
  and structured-output conversion are exercised too.
- `tests/test_registry.py` asserts cross-cutting properties over *every* registered tool at
  once (unique `lms_`-prefixed names, valid schemas, correct read-only/destructive
  annotations, destructive tools absent unless `LMS_ENABLE_DESTRUCTIVE=true`) — extend the
  relevant set there rather than writing a one-off test when adding a new destructive tool.
- `tests/test_http.py` exercises the full ASGI app in-process via `httpx.ASGITransport`,
  including bearer-auth rejection and the ASGI lifespan (needed for the SDK's session
  manager to start) — see its `serving()` context manager when adding endpoint-level tests.

## Adding a new LMS command as a tool

1. Confirm the exact CLI syntax against the Lyrion CLI reference
   (`https://lyrion.org/reference/cli/...`) — don't guess tag names or positional order.
2. Add the tool function to the relevant `tools/<family>.py` (or a new module registered in
   `tools/__init__.py`'s `MODULES`), decorated via the module's `Registrar` instance; mark
   `read_only=True` for queries and `destructive=True` for anything that deletes or mutates
   server-wide state.
3. Return one of the typed models in `models.py` (add a new one if needed) via a mapping
   function in `normalize.py`, not a raw dict.
4. Add a test in the matching `tests/test_tools_*.py` asserting the exact command array sent
   to `FakeLMS` and the normalized structured output.
