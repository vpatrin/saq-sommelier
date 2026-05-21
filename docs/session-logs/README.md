# Session Logs

Durable record of non-trivial sessions: what was decided, what was tried and rejected, what got in the way.

## When to write one

- Multi-decision sessions where the rationale would otherwise vanish in commit messages
- Sessions that spin up an ADR (link to it from here)
- Refactors or migrations that future-you will want to retrace
- Sessions that hit obstacles worth flagging (failed approach, env issue, library quirk)

## When to skip

- Routine bug fixes
- Dependabot bumps
- Single-commit chores
- Documentation-only PRs

## Format

Copy [`_template.md`](./_template.md) to `YYYY-MM-DD-<slug>.md`. Keep it tight — under 100 lines is the target.

## Lifecycle

Written during the session, finalized at PR time, never deleted. Old logs accumulate as project archaeology.
