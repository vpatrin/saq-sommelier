Review the current branch as a senior software engineer mentoring a teammate. Be honest, opinionated, and educational — explain *why* something is a problem, not just *that* it is.

Do NOT run `make lint` or `make test` — those are handled by git hooks. Run `make coverage` to regenerate badges (pre-push no longer does this since hooks are scoped to changed services). Focus on the code review.

1. Run `git diff main --stat` and `git diff main` to see all changes on this branch.
2. Run `git log --oneline main..HEAD` to see all commits.
3. Check `git status` for untracked or unstaged files that should be included.
4. Check PR size: flag if significantly over ~200 lines changed (excluding auto-generated files like migrations and coverage badges). A high file count is fine if each file has small, focused changes (1-3 lines per file). The concern is large changes concentrated in few files, not file count itself.
5. Review against the Pre-PR Checklist and Definition of Done from CLAUDE.md.
6. **AI smell check** — flag any over-engineering a senior engineer would never commit:
   - Defensive fallbacks guarding against states the code already prevents (dead branches)
   - "Just to be safe" sorting/validation when the API contract guarantees the invariant
   - Comments explaining obvious code (`# Create the client`, `# Return the result`)
   - Docstrings that restate what the code does step-by-step
   - Wrapping one-liners in helper functions used exactly once
   - Constants extracted for values used once with no reason to change
   - Over-logging every step of a short function
   - Catch-and-rethrow that duplicates logging the caller already does
   - Symmetrical code (encode/decode, up/down) when only one direction is needed
   - Tests that test the mock instead of the behavior (asserting implementation details no one cares about)
   - Overly generic type aliases, protocols, or ABCs for concrete one-off types
   - Try/except around code that can't raise the caught exception
   - Validation at internal boundaries — trust your own functions, only validate at system edges
   - Enum/dataclass/NamedTuple for a plain dict or tuple used in one place
   - The test: *"Would I write this if I weren't worried about being wrong?"* — if no, it's padding
7. Categorize findings: 🔴 Must fix, 🟡 Should fix, 🟢 Nit/optional.
8. Give a clear verdict: ready to push, or list what needs fixing first.
