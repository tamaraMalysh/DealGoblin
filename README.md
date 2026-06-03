# DealGoblin

Async Telegram flea-market finder.

DealGoblin ingests posts from allowlisted Telegram chats, indexes them in SQLite/FTS5, and provides search + alerting through a Telegram bot.

The bot supports both saved watches for alerts and historical search across all indexed chats.

## Search Semantics

- Phrase queries match adjacent words in order.
- Russian word forms are normalized via lemmatization (for example, `стиральная машина` also matches `стиральную машину`).
- Minus-words exclude matches (for example, `стиральная машина -lg -samsung`).

## Requirements

- Python `3.13+`
- `uv`

## Quick Start

```bash
uv sync --extra dev
uv run python -m dealgoblin
```

Configure runtime secrets and IDs in `.env` (for example: Telegram API credentials, bot token, owner/source chat IDs).
Run only one DealGoblin instance per bot token when using long polling.

## Environment Variables

Copy `.env.example` to `.env` and fill in required values:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `BOT_TOKEN`
- `OWNER_CHAT_ID`
- `SOURCE_CHAT_IDS` (comma-separated Telegram chat IDs)
- `DB_BUSY_TIMEOUT_MS` (optional, default `15000`; SQLite lock wait timeout in milliseconds)
- `RUNTIME_LOCK_PATH` (optional, default `data/runtime.lock`; host-local single-instance lock file)
- `DUPLICATE_SUPPRESSION_DAYS` (optional, default `14`; suppresses cross-chat duplicate alerts per watch)

## Quality Checks

```bash
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run pytest -q
uv run bandit -q -r src/dealgoblin -ll -ii
uv export --frozen --format requirements.txt --extra dev --no-emit-project --output-file /tmp/requirements-deps.txt
uv run pip-audit --strict -r /tmp/requirements-deps.txt --no-deps
```

## Local-First Release Workflow

Validate changes locally before pushing, then deploy production only after GitHub CI passes on `main`.

1. Run the smallest relevant test or check first when the change is narrowly scoped.
2. Run the local gate before push:

```bash
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run pytest -q
```

3. If the change touches runtime, auth, deployment, or other security-sensitive code, also run:

```bash
uv run bandit -q -r src/dealgoblin -ll -ii
```

Local verification is automated only. Do not run live Telegram end-to-end checks against the production bot, and do not reuse the production Telethon session on your laptop.

If you need a local manual runtime, keep its state separate from production:

```env
DB_PATH=data/local/dealgoblin.sqlite3
SESSION_PATH=data/local/telethon.session
RUNTIME_LOCK_PATH=data/local/runtime.lock
```

Never copy the DigitalOcean production `data/dealgoblin.sqlite3` or `data/telethon.session` files onto your local machine.

Release sequence:

1. Develop on a feature branch.
2. Run the local gate.
3. Push the branch and merge to `main` after CI is green.
4. Trigger GitHub Actions workflow `Deploy` with `ref=main`.
5. If needed, verify production with `docker compose ps` and `docker compose logs -f --tail=200 dealgoblin`.

## CI

GitHub Actions workflow `CI` (`.github/workflows/ci.yml`) runs on pull requests and pushes to `main` and enforces the full quality gate.
Manual production deploy workflow `Deploy` (`.github/workflows/deploy.yml`) is triggered from GitHub Actions UI (`workflow_dispatch`).

## Docker (Local/Single Host)

```bash
docker compose build
docker compose up
```

### Rebuild and Restart Bot (Docker Compose)

Rebuild the bot image and recreate the running service:

```bash
docker compose up -d --build dealgoblin
```

Restart the bot service without rebuilding:

```bash
docker compose restart dealgoblin
```

For long-running production deployment on a VPS with persistent SQLite/session data, use:

- [VPS deployment guide](docs/deployment-vps.md)
- [systemd unit template](deploy/systemd/dealgoblin.service)

## Production Deploy (DigitalOcean)

This repository includes deployment automation for a single DigitalOcean VPS:

- `deploy/scripts/bootstrap_server.sh`: one-time host setup (Ubuntu checks, Docker install, service setup, `.env` validation).
- `deploy/scripts/deploy_server.sh`: idempotent app deploy with deploy lock (`flock`), `git pull --ff-only`, and `docker compose up -d --build dealgoblin`.
- `.github/workflows/deploy.yml`: manual GitHub deploy (`workflow_dispatch`) over SSH.

Production state on the VPS is not a local test fixture. Do not copy the production SQLite DB or Telethon session to your laptop, and do not run the production bot token locally while the VPS runtime is active.

### One-time host setup

On the VPS after cloning the repository:

```bash
chmod +x deploy/scripts/bootstrap_server.sh deploy/scripts/deploy_server.sh
./deploy/scripts/bootstrap_server.sh
```

If `data/telethon.session` does not exist yet:

```bash
docker compose run --rm dealgoblin
```

### Manual deploy from server shell

```bash
./deploy/scripts/deploy_server.sh main
```

### Manual deploy from GitHub Actions

Configure repository secrets:

- `DO_SSH_HOST`
- `DO_SSH_PORT` (optional, defaults to `22`)
- `DO_SSH_USER`
- `DO_SSH_PRIVATE_KEY`
- `DO_SSH_KNOWN_HOSTS`

Then run workflow `Deploy` in GitHub Actions and keep `ref=main` for production deploys.

## Troubleshooting

### `TelegramConflictError: terminated by other getUpdates request`

This means more than one bot runtime is polling Telegram with the same token.

1. Stop all duplicate local/container runtimes and keep only one instance.
2. Restart the remaining instance once to clear any stale polling loop state.
3. Confirm logs no longer show repeated `TelegramConflictError` lines.

### `sqlite3.DatabaseError: database disk image is malformed`

DealGoblin now attempts automatic recovery for SQLite corruption:

1. The corrupted database files are moved to timestamped quarantine files such as
   `dealgoblin.sqlite3.corrupt-YYYYMMDDTHHMMSSZ` (including `-wal` and `-shm` sidecars).
2. A fresh SQLite database is created at the configured `DB_PATH`.
3. Runtime components treat corruption as fatal so the supervisor restarts cleanly.

Quarantined `.corrupt-*` files are preserved for manual forensic recovery if you need to inspect or salvage data.
