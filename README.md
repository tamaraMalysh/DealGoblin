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

## Docker (Optional)

```bash
docker compose build
docker compose up
```
