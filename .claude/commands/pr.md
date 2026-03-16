Create a PR for the current branch. Follow the Pre-PR Checklist from CLAUDE.md.

## Steps

1. Run `git log --oneline main..HEAD` to understand all commits on this branch.
2. Run `git diff main` to see the full diff.
3. Verify the branch has been pushed to remote (`git branch -vv`). If not, stop and ask Victor to push first.
4. Determine which issue(s) this branch closes from the commit history and branch name.
5. Verify CHANGELOG.md and ROADMAP.md are already updated (done in `/review`). If the PR changes deployed behavior and `[Unreleased]` has no matching entry, warn and stop.
6. Create the PR using `gh pr create` with:
   - Title in conventional commits format: `type: description (#issue)`
   - Body following `.github/pull_request_template.md` (Summary, Related issue(s), Changes, How to test if applicable)
   - Use `Closes #XX` in the Related issue(s) section for each issue
   - If "How to test" includes curl commands, use port 8001 (backend runs on 8001, not 8000)
7. Return the PR URL.

## Rules

- Do NOT push the branch — if it's not pushed, stop and ask Victor to push first
- Do NOT create the PR if CHANGELOG.md is missing an entry for user-visible changes — warn and stop
- Prerequisite: `/review` must have passed. If unsure, ask Victor before proceeding.
- **Scope note:** this command does not re-check code quality — that's `/review`'s job. It also does not check test coverage (`/qa`) or security (`/security`).
