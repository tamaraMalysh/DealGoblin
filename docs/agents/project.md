# Project Context

## Current State
- Repository bootstrapped with uv, ruff, and hatchling build system.
- Package structure: `src/dealgoblin/` with subpackages `bot/`, `ingest/`, `match/`, `storage/`.
- Tech stack: Python 3.13, Telethon, aiogram v3, aiosqlite, pydantic-settings.

## Goals
- Build DealGoblin: async Telegram flea-market finder.
- Ingest posts from allowlisted chats via Telethon, index with SQLite/FTS5.
- Provide search + instant alerts via aiogram bot.
- Keep agent instructions concise at root and detailed in scoped docs.
- Ensure repeatable setup, test, and quality-check commands.

## Non-Goals
- Defining full product requirements in this document.
- Duplicating command details that belong in `commands.md`.

## Assumptions
- Python is the primary language.
- uv is the package and environment manager.
- Agent instruction filename convention is `AGENTS.md` (plural).
- Default production target is a single VPS running Docker Compose with persistent `./data`.

## Change Policy
- If project stack or tooling changes, update:
  - `/AGENTS.md` quick command summary
  - `docs/agents/commands.md`
  - Any nested `AGENTS.md` files affected by the change
