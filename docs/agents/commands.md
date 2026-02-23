# Command Canon (Python-first)

Use these as canonical commands unless repository configuration later defines alternatives.

## Setup
uv sync --extra dev

## Run
uv run python -m dealgoblin

## Test
uv run pytest

## Lint
uv run ruff check src/ tests/

## Format
uv run ruff format src/ tests/

## Notes
- Keep command definitions consistent with `/AGENTS.md`.
- If uv is replaced, update this file and `/AGENTS.md` in the same change.
