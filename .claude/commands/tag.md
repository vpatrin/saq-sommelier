Tag a release and update the changelog.

1. Run `git log --oneline <last-tag>..HEAD` to see what's shipped since last tag.
2. Run `git tag --sort=-version:refname | head -5` to see recent tags.
3. Determine the next version: PATCH if only fixes/security, MINOR if new user-facing capability.
4. Check `CHANGELOG.md` — verify `[Unreleased]` has entries. If empty, warn Victor and stop.
5. In `CHANGELOG.md`:
   - Rename `[Unreleased]` → `[x.y.z] - YYYY-MM-DD` (today's date)
   - Add fresh `## [Unreleased]` section at the top
   - Update comparison links at the bottom: `[Unreleased]: .../compare/vX.Y.Z...HEAD` and add `[x.y.z]: .../compare/vPREV...vX.Y.Z`
6. Stop. Print the commands for Victor to run:
   ```
   git add CHANGELOG.md && git commit -m "chore: release vX.Y.Z"
   git tag vX.Y.Z
   git push && git push --tags
   ```
