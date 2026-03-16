Prepare a release tag and update the changelog. You handle the bookkeeping so Victor can focus on the deploy.

**Pre-tag check:** consider running `/roadmap-status` first to verify everything planned for this release is actually done.

## Steps

1. Run `git tag --sort=-version:refname | head -5` to see recent tags.
2. Run `git log --oneline <last-tag>..HEAD` to see what's shipped since last tag.
3. If there are no commits since the last tag, stop and say "Nothing to release."
4. Determine the next version: PATCH if only fixes/security, MINOR if new user-facing capability.
5. Check `CHANGELOG.md` — verify `[Unreleased]` has entries.
   - If empty but there are commits: warn Victor that shipped work is missing from the changelog. List the commits and suggest changelog entries before proceeding.
   - If entries exist only for internal changes (CI, refactors, tests, docs): warn that this would be a release with no user-visible changes. Ask Victor if that's intentional.
6. In `CHANGELOG.md`:
   - Rename `[Unreleased]` → `[x.y.z] - YYYY-MM-DD` (today's date)
   - Add fresh `## [Unreleased]` section at the top
   - Update comparison links at the bottom: `[Unreleased]: .../compare/vX.Y.Z...HEAD` and add `[x.y.z]: .../compare/vPREV...vX.Y.Z`
7. Stop. Print the commands for Victor to run:

```bash
git add CHANGELOG.md && git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

## Rules

- Do NOT run `git tag` or `git push` — only print the commands for Victor to run
- Do NOT modify any file other than `CHANGELOG.md`
- If `[Unreleased]` is empty, do NOT proceed — warn Victor and stop
