# DealGoblin

Async Telegram flea-market finder.

DealGoblin ingests posts from allowlisted Telegram chats, indexes them in SQLite/FTS5, and provides search + alerting through a Telegram bot.

## Requirements

- Python `3.13+`
- `uv`

## Quick Start

```bash
uv sync --extra dev
uv run python -m dealgoblin
```

Configure runtime secrets and IDs in `.env` (for example: Telegram API credentials, bot token, owner/source chat IDs).

## Environment Variables

Copy `.env.example` to `.env` and fill in required values:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `BOT_TOKEN`
- `OWNER_CHAT_ID`
- `SOURCE_CHAT_IDS` (comma-separated Telegram chat IDs)

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

For long-running production deployment on a VPS with persistent SQLite/session data, use:

- [VPS deployment guide](docs/deployment-vps.md)
- [systemd unit template](deploy/systemd/dealgoblin.service)
