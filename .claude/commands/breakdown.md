Break down a task into small, focused GitHub issues.

Rules from CLAUDE.md:
- Each issue should touch maximum 2-3 files
- Each issue should be independently deployable
- One issue = one branch = one PR

Steps:
1. Analyze the task and identify logical units of work.
2. Order them by dependency — which issues must land before others?
3. For each unit, draft:
   - Title (conventional commits style)
   - Label (from existing labels: `api`, `scraper`, `frontend`, `infra`, `docs`, `bug`; suggest a new label if none fit)
   - Description
   - Acceptance criteria (include dependency on prior issue if applicable)
4. Present the numbered breakdown for Victor's approval before creating anything.
5. Once approved, create each issue with `gh issue create --label <label>` and immediately add it to the kanban:
```
   gh project item-add 1 --owner vpatrin --url <issue-url>
```
6. List all created issues with their numbers and URLs.
