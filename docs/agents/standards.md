# Engineering Standards

## Coding Expectations
- Keep changes scoped to the user-requested outcome.
- Prefer clear, readable implementations over clever abstractions.
- Avoid unrelated renames or refactors in the same change.

## Testing Expectations
- Run the most targeted checks first, then broader checks as needed.
- Add or update tests when behavior changes and a test location exists.
- If checks cannot run, report the exact blocker and impact.

## Documentation Expectations
- Update `/AGENTS.md` and related docs when commands or workflow rules change.
- Keep root guidance short; put detail in `docs/agents/*`.
- Do not duplicate conflicting instructions across files.

## Security Expectations
- Never commit secrets, credentials, or private keys.
- Prefer environment variables for sensitive configuration.
- Surface any security-sensitive change explicitly in handoff notes.

## Change Quality Gate
- Implementation is complete for requested scope.
- Relevant checks were run or blockers documented.
- Instructions and docs remain internally consistent.
