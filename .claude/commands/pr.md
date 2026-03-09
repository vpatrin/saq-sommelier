Create a PR for the current branch. Follow the Pre-PR Checklist from CLAUDE.md:

This assumes /review has already been run and passed.

1. Run `git log --oneline main..HEAD` to understand all commits on this branch.
2. Run `git diff main` to see the full diff.
3. Verify the branch has been pushed to remote (`git branch -vv`). If not, stop and ask Victor to push first.
4. Determine which issue(s) this branch closes from the commit history and branch name.
5. Check if this work completes a capability tracked in `docs/roadmaps/` — if so, mark it `[x]` with the issue ref (e.g., `(#50)`). Only add new items if they represent a meaningful capability, not every issue needs a roadmap entry.
6. If the PR changes deployed behavior (would a user notice?), add one line under `[Unreleased]` in `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. Skip for internal-only changes (CI, refactors, tests, docs, dependabot).
7. Create the PR using `gh pr create` with:
   - Title in conventional commits format: `type: description (#issue)`
   - Body following `.github/pull_request_template.md` (Summary, Related issue(s), Changes, How to test if applicable)
   - Use `Closes #XX` in the Related issue(s) section for each issue
   - If "How to test" includes curl commands, use port 8001 (backend runs on 8001, not 8000)
8. Return the PR URL.
