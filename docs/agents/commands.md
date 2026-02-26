# Command Canon (Python-first)

Use these as canonical commands unless repository configuration later defines alternatives.

## Setup
uv sync --extra dev

## Run
uv run python -m dealgoblin

## Resolve Source ID
uv run python -m dealgoblin.tools.resolve_source https://t.me/<username>

Also supports:
- uv run python -m dealgoblin.tools.resolve_source https://t.me/addlist/<slug>

For addlist links, the resolver prints one `chat_id=...` line per resolved chat and a final
`SOURCE_CHAT_IDS=...` line suitable for `.env`.

## Test
uv run pytest

## Lint
uv run ruff check src/ tests/

## Format
uv run ruff format src/ tests/

## Notes
- Keep command definitions consistent with `/AGENTS.md`.
- If uv is replaced, update this file and `/AGENTS.md` in the same change.
- Sources are configured via `.env` using `SOURCE_CHAT_IDS` (comma-separated canonical IDs).
- Optional startup backfill depth is `SOURCE_BACKFILL_LIMIT` (default `100`).
- Optional raw forwarding of every ingested message is `FORWARD_ALL_INGESTED=true` (to `OWNER_CHAT_ID`).
- Telethon reconnect policy is configurable via `.env`:
  - `TELETHON_CONNECTION_RETRIES` (default `-1`, effectively infinite)
  - `TELETHON_RETRY_DELAY_SECONDS` (default `1.0`)
- Runtime supervisor restart backoff is configurable via `.env`:
  - `RUNTIME_RESTART_BASE_DELAY_SECONDS` (default `3.0`)
  - `RUNTIME_RESTART_MAX_DELAY_SECONDS` (default `60.0`)
- Bot API health watchdog is configurable via `.env`:
  - `BOT_HEALTHCHECK_INTERVAL_SECONDS` (default `15.0`)
  - `BOT_HEALTHCHECK_FAILURE_THRESHOLD` (default `8`)
