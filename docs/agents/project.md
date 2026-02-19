# Project Context (Greenfield)

## Current State
- Repository is in initial bootstrap state with no established application source tree yet.
- Tooling conventions are Python-first and Poetry-first until project manifests or team decisions override them.

## Goals
- Build DealGoblin with clear, maintainable architecture and deterministic workflows.
- Keep agent instructions concise at root and detailed in scoped docs.
- Ensure repeatable setup, test, and quality-check commands.

## Non-Goals
- Defining full product requirements in this document.
- Locking framework-level architecture before implementation context exists.
- Duplicating command details that belong in `commands.md`.

## Assumptions
- Python is the primary language for initial implementation.
- Poetry is the default package and environment manager.
- Agent instruction filename convention is `AGENTS.md` (plural).

## Change Policy
- If project stack or tooling changes, update:
  - `/AGENTS.md` quick command summary
  - `docs/agents/commands.md`
  - Any nested `AGENTS.md` files affected by the change
