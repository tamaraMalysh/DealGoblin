# DealGoblin Agent Instructions

This file is the canonical instruction entrypoint for agent work in this repository.

## Purpose
- Keep root guidance short and deterministic.
- Route task-specific detail to docs in `docs/agents/`.
- Treat repository docs as the durable system of record.

These are default conventions for the current greenfield state and should be aligned with project config as files are added.

## Workflow Expectations
- Read this file first, then load only the most relevant doc from `docs/agents/`.
- Keep changes focused and minimal for the requested task.
- Update docs when behavior, commands, or workflows change.
- Do not introduce conflicting command variants across docs.
- Validate feature work locally with automated checks before pushing.
- Keep production SQLite and Telethon session state isolated from local development.
- Prefer production releases from `main` via the manual GitHub Actions deploy workflow after CI passes.
- Source ingestion allowlist is env-driven (`SOURCE_CHAT_IDS`), not runtime bot commands.

## Definition of Done
- Requested behavior is implemented.
- Relevant checks pass or any blockers are explicitly reported.
- Documentation is updated when instructions or behavior changed.

## Safety Boundaries
- Never commit secrets, tokens, credentials, or private keys.
- Flag destructive operations before running them unless explicitly requested.
- Avoid unrelated refactors while implementing scoped work.

## Context Routing
- Project context and scope: `docs/agents/project.md`
- Command canon: `docs/agents/commands.md`
- Engineering standards: `docs/agents/standards.md`
- Doc loading order by task: `docs/agents/README.md`

## Local Overrides
- As the repository grows, add nested `AGENTS.md` files in subdirectories that need specialized rules.
- Nested files only govern their own subtree and may narrow or extend these root instructions.
