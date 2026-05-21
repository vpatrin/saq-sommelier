# Session Log — <short title>

**Branch:** `type/short-description`
**Date:** YYYY-MM-DD
**PR:** #NNN (or "not yet")
**Issue:** #NNN (or "none")
**Spec snapshot:** see `.claude/scratchpad/<branch>/spec.md` while branch lives

## Why this work

One paragraph. The motivation, not the implementation. Tie to issue, ADR, or roadmap item.

## Decisions worth keeping

Non-obvious calls future-you will want to remember. NOT "we implemented X" — "we chose X over Y because Z." Typically 1-3 entries. If none: "no real tradeoffs — straightforward execution."

### <decision title>

- **Context:** what was on the table
- **Decision:** what we picked
- **Rejected:** Y, Z (one-line reason each)
- **ADR:** `docs/decisions/NNNN-<slug>.md` (or "no — too small")

(Repeat per decision.)

## Obstacles + lessons

Dead ends, env quirks, library bugs that ate time. Future-you reads this to skip the same trap. If none worth mentioning: "none — clean run."

## Final state

Self-contained summary so this log reads on its own without the PR or scratchpad:

- **Files changed:** N files (~M source lines, ~K test lines)
- **Tests:** A added, B updated, coverage X% → Y%
- **ADRs spawned:** list each with one-line summary, or "none"
- **Docs updated:** rules/X.md, README, etc. (or "none")
- **Migrations:** yes (with table) | no

## Links

- **PR:** #NNN
- **Per-agent pipeline trace:** `.claude/scratchpad/<branch>/log.md` (ephemeral — copy into PR description before deleting the branch if you want it preserved)
- **Related ADRs:** list (the ones referenced or built on, not just spawned)
- **Related session logs (same surface):** look up via [`INDEX.md`](./INDEX.md)
