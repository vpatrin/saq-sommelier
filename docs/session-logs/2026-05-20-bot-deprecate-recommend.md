# Session Log — Bot /recommend deprecation

**Branch:** `feat/bot-deprecate-recommend`
**Date:** 2026-05-20
**PR:** TBD
**Issue:** none
**Spec snapshot:** `docs/specs/_drafts/2026-05-20-bot-deprecate-recommend.md` (deleted post-ship — see TELEGRAM_BOT.md for bot architecture)

## Why this work

The bot's `/recommend` command ran the full RAG pipeline inline. As the web app (`coupette.club/chat`) matured into the primary recommendation surface with session history and richer interactions, the bot recommendation path became redundant and harder to maintain in parallel. The goal was to consolidate recommendations in the web app and reduce the bot to its core value: proactive stock alerts. Users who type `/recommend` now receive a short, friendly deprecation message linking them to the web app.

## Decisions worth keeping

### Inline stub in `app.py` instead of own handler file

- **Context:** the original handler lived in `bot/bot/handlers/recommend.py`; convention is one file per handler
- **Decision:** deleted the file and inlined a 7-line stub directly in `app.py`
- **Rejected:** keeping `handlers/recommend.py` — it would be a 7-line file with no real logic and a misleading module name; overkill for a message that reads "use the web app"
- **ADR:** no — too small

### Remove `🤖 Recommend` from `MAIN_MENU` entirely (no soft-redirect button)

- **Context:** spec open question — keep button as soft redirect vs. remove cleanly
- **Decision:** removed from keyboard; `/recommend` command still works as a redirect path
- **Rejected:** keeping the button as a soft redirect — it signals a still-supported feature, clutters the menu, and the deprecation is reachable via the command
- **ADR:** no — simple UX call with clear rationale

### Delete `BackendClient.recommend()` and `format_recommendations()` from bot

- **Context:** spec open question — delete dead bot client code vs. leave it since backend still uses the same payload shape
- **Decision:** deleted from `bot/` (method + formatter + all tests)
- **Rejected:** keeping dead code in `bot/` — the backend has its own contract tests; the bot carrying an unused client method creates false signal that it's called somewhere
- **ADR:** no — obvious dead-code removal

## Obstacles + lessons

None worth noting — clean run. The reviewer flagged a minor symmetry issue: `CommandHandler("recommend", …)` uses a string literal in `app.py` instead of a `CMD_RECOMMEND` constant in `config.py` (which is the convention for other command handlers). Not blocking, but worth addressing if a second stub handler appears.

## Final state

- **Files changed:** 8 files (handlers/recommend.py deleted; app.py, handlers/start.py, keyboards.py, config.py updated; api_client.py, formatters.py cleaned; tests rewritten)
- **Tests:** 146 passing, coverage 91.28% (threshold 85%)
- **ADRs spawned:** none
- **Docs updated:** CHANGELOG.md (Deprecated entry), ROADMAP.md (item marked done), docs/session-logs/ (this file)
- **Migrations:** no

## Links

- **PR:** TBD
- **Per-agent pipeline trace:** `.scratchpad.md` in worktree (ephemeral)
- **Related ADRs:** none
- **Related session logs (same surface):** none — first session log for `bot` surface
