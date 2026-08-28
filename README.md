# lms-mcp

An MCP server that controls [Lyrion Music Server](https://lyrion.org) (formerly Logitech
Media Server / Squeezebox Server) and the players attached to it.

It speaks **MCP Streamable HTTP** — JSON-RPC 2.0 over HTTP POST — so it runs as a
long-lived container behind a URL rather than as a local stdio process, and it exposes a
`/health` endpoint for Docker and Coolify health checks.

Under the hood every tool becomes a Lyrion CLI command issued over the server's
`/jsonrpc.js` endpoint.

## What it exposes

103 tools, all prefixed `lms_`, covering the Lyrion CLI:

| Area | Examples |
| --- | --- |
| Server | `lms_server_status`, `lms_library_totals`, `lms_rescan_start`, `lms_rescan_status` |
| Players | `lms_list_players`, `lms_player_status`, `lms_set_power`, `lms_sync`, `lms_sleep` |
| Playback | `lms_play`, `lms_pause`, `lms_next_track`, `lms_seek`, `lms_set_repeat`, `lms_set_shuffle` |
| Audio | `lms_set_volume`, `lms_mute`, `lms_set_bass`, `lms_get_audio_settings` |
| Queue | `lms_get_queue`, `lms_play_item`, `lms_add_item`, `lms_play_url`, `lms_queue_save` |
| Library | `lms_search`, `lms_list_artists`, `lms_list_albums`, `lms_album_tracks`, `lms_track_info` |
| Favorites | `lms_favorites_list`, `lms_favorites_play`, `lms_favorites_add_current` |
| Alarms | `lms_alarms_list`, `lms_alarm_add`, `lms_alarm_update` |
| Random mixes | `lms_random_play`, `lms_random_genres` |
| Apps & radio | `lms_list_apps`, `lms_app_browse`, `lms_app_search`, `lms_app_play`, `lms_radio_browse` |

Six further tools change or destroy server state — `lms_wipe_cache`, `lms_server_restart`,
`lms_server_stop`, `lms_set_pref`, `lms_saved_playlist_delete`, `lms_favorites_delete`.
They are **not registered** unless you set `LMS_ENABLE_DESTRUCTIVE=true`.

### Addressing players

Every player tool takes an optional `player` argument accepting either a friendly name
(`"Kitchen"`, case-insensitive, unique prefixes work) or a player id / MAC address. When
it is omitted, `LMS_DEFAULT_PLAYER` is used; if that is unset the tool fails with a message
listing the players that are connected.

### Playing something

Find an id with `lms_search` or a `lms_list_*` tool, then hand it to `lms_play_item` with
the matching `kind` (`track`, `album`, `artist`, `genre`, `year`, `playlist`, `folder`).
`lms_add_item` and `lms_insert_item` queue it instead. For streams and file paths, use
`lms_play_url`.

## Running it

### Docker Compose

```bash
cp .env.example .env    # then edit LMS_HOST and MCP_AUTH_TOKEN
```

```bash
docker compose up --build -d
```

```bash
curl -s localhost:9055/health
```

### Coolify

1. Create a new **Docker Compose** resource pointing at this repository. Coolify builds
   from the committed `Dockerfile`.
2. Set the environment variables from `.env.example` — at minimum `LMS_HOST` and
   `MCP_AUTH_TOKEN`. Generate the token with `openssl rand -hex 32`.
3. Map your domain to the service's port **9055**.
4. Point the health check at `/health`. It returns `200` while Lyrion is reachable and
   `503` when it is not, so a dead media server shows up as a degraded container rather
   than a silently broken endpoint.

Lyrion itself is not part of this compose file: the container talks to your existing
server over the network.

### Locally, without Docker

```bash
uv sync
```

```bash
LMS_HOST=192.168.1.10 MCP_AUTH_TOKEN=dev-token uv run lms-mcp
```

## Connecting a client

```bash
claude mcp add --transport http lms https://lms-mcp.example.com/mcp --header "Authorization: Bearer $MCP_AUTH_TOKEN"
```

Any MCP client that supports Streamable HTTP with a custom `Authorization` header works
the same way.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `LMS_HOST` | `localhost` | Lyrion host |
| `LMS_PORT` | `9000` | Lyrion HTTP port |
| `LMS_PROTOCOL` | `http` | `http` or `https` |
| `LMS_BASE_URL` | — | Full base URL; overrides the three above |
| `LMS_TIMEOUT` | `10` | Request timeout in seconds |
| `LMS_USERNAME` / `LMS_PASSWORD` | — | HTTP basic auth, if Lyrion requires it |
| `LMS_DEFAULT_PLAYER` | — | Player used when a tool omits `player` |
| `LMS_ENABLE_DESTRUCTIVE` | `false` | Register the six destructive tools |
| `MCP_AUTH_TOKEN` | — | **Required.** Bearer token clients must present |
| `MCP_ALLOW_ANONYMOUS` | `false` | Run with no authentication (the server refuses to start without one of these two) |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `9055` | Listener |
| `MCP_PATH` | `/mcp` | Path of the MCP endpoint |
| `MCP_ALLOWED_HOSTS` | — | Comma-separated `Host`/`Origin` allow-list; leave unset behind a proxy |
| `LOG_LEVEL` | `INFO` | Python log level |

## Security

The MCP endpoint requires `Authorization: Bearer <MCP_AUTH_TOKEN>` on every request; the
token is compared in constant time. `/health` is deliberately unauthenticated so orchestrators
can probe it, and it reveals only the configured Lyrion URL, its version and reachability.
The server refuses to start when neither `MCP_AUTH_TOKEN` nor `MCP_ALLOW_ANONYMOUS` is set,
so an internet-facing deployment cannot end up open by accident.

The transport runs stateless with JSON responses, so it survives proxy restarts and scales
horizontally without sticky sessions.

## Development

```bash
uv run pytest -q
```

```bash
uv run ruff check . && uv run ruff format --check .
```

The test suite is hermetic: `tests/conftest.py` mocks the Lyrion HTTP endpoint, records the
CLI command each tool emits, and replays canned results, so no music server is needed.

### Layout

```
src/lms_mcp/
  config.py     environment parsing and start-up validation
  client.py     slim.request framing over /jsonrpc.js
  players.py    name -> player id resolution with a short-lived cache
  normalize.py  Lyrion's *_loop payloads -> typed models
  models.py     pydantic results (structured tool output)
  http.py       ASGI app: bearer auth, /health, Streamable HTTP
  tools/        one module per Lyrion command family
```

Tools never touch HTTP directly: each one builds a CLI command array and hands it to
`LMSClient.request`, which is what makes them straightforward to test.

## Prior art

[shermozle/lms-mcp](https://github.com/shermozle/lms-mcp) is a JavaScript MCP server for
Lyrion that runs over stdio. This project covers the same ground in Python over Streamable
HTTP so it can be deployed as a networked service.
