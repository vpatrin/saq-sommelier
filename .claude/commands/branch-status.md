Summarize the current branch status and what's left to do.

1. Run `git log --oneline main..HEAD` to see what's been committed.
2. Run `git diff main --stat` to see all changes on this branch vs main (committed + uncommitted).
3. Run `git status` for untracked or unstaged files.
4. Identify the goal of this branch from the branch name and related issue(s) (`gh issue list --state open`).
5. Compare current progress against the goal: what's done, what's in progress, what's missing.
6. List remaining tasks in suggested order of execution.
