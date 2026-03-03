# DealGoblin

Async Telegram flea-market finder.

DealGoblin ingests posts from allowlisted Telegram chats, indexes them in SQLite/FTS5, and provides search + alerting through a Telegram bot.

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

## CI

GitHub Actions workflow `CI` (`.github/workflows/ci.yml`) runs on pull requests and pushes to `main` and enforces the full quality gate.

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

## Troubleshooting

### `TelegramConflictError: terminated by other getUpdates request`

This means more than one bot runtime is polling Telegram with the same token.

1. Stop all duplicate local/container runtimes and keep only one instance.
2. Restart the remaining instance once to clear any stale polling loop state.
3. Confirm logs no longer show repeated `TelegramConflictError` lines.
