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

## Security
uv run bandit -q -r src/dealgoblin -ll -ii
uv export --frozen --format requirements.txt --extra dev --no-emit-project --output-file /tmp/requirements-deps.txt
uv run pip-audit --strict -r /tmp/requirements-deps.txt --no-deps

## CI Quality Gates (GitHub Actions)
Workflow: `.github/workflows/ci.yml` (`CI` / `quality`)

Gate order:
1. uv sync --frozen --extra dev
2. uv run ruff format --check src/ tests/
3. uv run ruff check src/ tests/
4. uv run pytest -q
5. uv run bandit -q -r src/dealgoblin -ll -ii
6. uv export --frozen --format requirements.txt --extra dev --no-emit-project --output-file /tmp/requirements-deps.txt
7. uv run pip-audit --strict -r /tmp/requirements-deps.txt --no-deps

## Docker (optional)
docker compose build

## Run (Docker)
docker compose up -d

## First Telethon Login (Docker)
docker compose run --rm dealgoblin

## Resolve Source ID (Docker)
docker compose run --rm dealgoblin \
  uv run python -m dealgoblin.tools.resolve_source https://t.me/<username>

## Notes
- Keep command definitions consistent with `/AGENTS.md`.
- If uv is replaced, update this file and `/AGENTS.md` in the same change.
- Sources are configured via `.env` using `SOURCE_CHAT_IDS` (comma-separated canonical IDs).
- Start from `.env.example` when creating `.env`.
- Docker runtime expects `.env` for secrets/config and mounts `./data` to persist SQLite + Telethon session files.
- First Telethon user-auth flow in Docker should be completed with `docker compose run --rm dealgoblin`; session files persist in `./data`.
- Never run `docker compose run --rm dealgoblin` concurrently with `docker compose up -d`; long-polling bots must run as a single active instance per token.
- Optional startup backfill depth is `SOURCE_BACKFILL_LIMIT` (default `100`).
- Optional raw forwarding of every ingested message is `FORWARD_ALL_INGESTED=true` (to `OWNER_CHAT_ID`).
- SQLite lock wait timeout is configurable via `.env`:
  - `DB_BUSY_TIMEOUT_MS` (default `15000`)
- Telethon startup connect retry policy is configurable via `.env`:
  - `TELETHON_CONNECTION_RETRIES` (default `-1`, effectively infinite)
  - `TELETHON_RETRY_DELAY_SECONDS` (default `1.0`)
- Runtime reconnect recovery is handled by the supervisor restart loop.
- SQLite corruption is treated as fatal at runtime, which triggers supervisor restart;
  startup then quarantines corrupted DB files (`.corrupt-*`) and rebuilds a fresh DB.
- Runtime supervisor restart backoff is configurable via `.env`:
  - `RUNTIME_RESTART_BASE_DELAY_SECONDS` (default `3.0`)
  - `RUNTIME_RESTART_MAX_DELAY_SECONDS` (default `30.0`)
- Runtime single-instance lock path is configurable via `.env`:
  - `RUNTIME_LOCK_PATH` (default `data/runtime.lock`)
- Bot API health watchdog is configurable via `.env`:
  - `BOT_HEALTHCHECK_INTERVAL_SECONDS` (default `15.0`)
  - `BOT_HEALTHCHECK_FAILURE_THRESHOLD` (default `8`)
- Match alert duplicate suppression window is configurable via `.env`:
  - `DUPLICATE_SUPPRESSION_DAYS` (default `14`)
