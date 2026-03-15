# Hardening a GitHub Repository — From Zero to Production-Grade

Most GitHub repos ship with default settings: anyone can push to `main`,
workflows run with full write access, and there's no security scanning.
This guide walks you through locking all of that down — with `gh api`
commands you can copy-paste into any repo.

Everything here is generic. No project-specific code, no custom tooling.
Just GitHub features, why they matter, and how to turn them on.

> **Before you start:** set `export REPO=owner/repo` once. Every command
> below uses `$REPO`.

---

**What we'll cover:**

1. [Repository settings](#1-repository-settings) — merge strategy, branch cleanup
2. [Actions permissions](#2-actions-permissions) — least-privilege tokens, action allowlist
3. [Branch rulesets](#3-branch-rulesets) — protecting main, protecting tags
4. [Security scanning](#4-security-scanning) — secrets, CodeQL, CVEs, containers
5. [Deployment environments](#5-deployment-environments) — gating production access
6. [Secrets management](#6-secrets-management) — what goes where
7. [Workflow architecture](#7-workflow-architecture) — CI, CD, CVE scans, auto-merge
8. [Composite actions](#8-composite-actions) — DRY for your CI
9. [Dependabot](#9-dependabot) — automated dependency updates
10. [Git hooks](#10-git-hooks) — catching problems before they reach CI
11. [Repo files](#11-repo-files) — PR templates, trivyignore, file inventory
12. [Verification](#12-verification) — confirming it all works

---

## 1. Repository Settings

The first thing to configure on a new repo is the merge strategy. GitHub
defaults to allowing merge commits, squash merges, and rebases — all three.
That sounds flexible, but it means your `main` history is an unpredictable
mix of merge bubbles and individual commits.

Pick a strategy and enforce it:

```bash
gh api -X PATCH repos/$REPO -f \
  has_wiki=false \
  has_discussions=false \
  has_projects=true \
  has_issues=true \
  allow_squash_merge=true \
  allow_merge_commit=false \
  allow_rebase_merge=true \
  delete_branch_on_merge=true \
  allow_auto_merge=true \
  allow_update_branch=true \
  squash_merge_commit_title=PR_TITLE \
  squash_merge_commit_message=BLANK \
  web_commit_signoff_required=false
```

**Why squash + rebase, no merge commits?** Squash gives you one clean commit
per PR — the PR title becomes the commit message, so `git log --oneline`
reads like a changelog. Rebase is there for when a PR has carefully crafted
atomic commits worth preserving. Merge commits just add noise.

**Why `PR_TITLE` + `BLANK`?** The PR title follows conventional commit format
(`feat: add X`), which flows directly into the squash commit. The PR body
lives on GitHub — no need to duplicate it in the commit message.

**Why `delete_branch_on_merge`?** Merged branches are dead branches. Without
this, you accumulate stale branches that nobody cleans up.

**Why `allow_auto_merge`?** This is what makes Dependabot auto-merge work.
A PR marked for auto-merge will merge itself once all required checks pass.

**Why disable the wiki?** Docs should live in your repo (`docs/`), not in a
separate wiki that's disconnected from your code, PRs, and version history.

---

## 2. Actions Permissions

GitHub Actions has two permission layers, and both default to dangerously
permissive settings. This is the single highest-impact security change you
can make.

### Layer 1: Default token permissions

```bash
gh api -X PUT repos/$REPO/actions/permissions/workflow \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false
```

By default, `GITHUB_TOKEN` has **write** access to everything — code,
issues, PRs, packages, deployments. That means any action in any workflow
can push code, merge PRs, or delete branches.

Setting `default_workflow_permissions=read` flips this. Now every workflow
*must* explicitly declare what it needs via `permissions:` blocks. If a
workflow doesn't declare permissions, it gets read-only. A compromised
third-party action can read your code but can't modify anything.

`can_approve_pull_request_reviews=false` prevents workflows from approving
their own PRs — which would bypass human review entirely.

### Layer 2: Which actions can run

```bash
gh api -X PUT repos/$REPO/actions/permissions \
  -F enabled=true \
  -f allowed_actions=selected

gh api -X PUT repos/$REPO/actions/permissions/selected-actions \
  -F github_owned_allowed=true \
  -F verified_allowed=false \
  -f 'patterns_allowed[]=dorny/paths-filter@*' \
  -f 'patterns_allowed[]=aquasecurity/trivy-action@*' \
  # ... one line per third-party action you use
```

Anyone can publish a GitHub Action. With the default "allow all" policy,
a typo in a `uses:` line could pull arbitrary code into your CI runner.
`selected` mode means only actions you've explicitly approved can execute.

GitHub-owned actions (`actions/checkout`, `actions/setup-python`, etc.) are
safe to trust as a baseline. But "verified creator" is just a Marketplace
badge — it's not a security audit. Keep that off and maintain an explicit
allowlist instead.

To find which third-party actions your workflows currently use:

```bash
grep -rh 'uses:' .github/ | grep -v 'actions/' | grep -v './' | sort -u
```

---

## 3. Branch Rulesets

Rulesets are GitHub's modern replacement for the legacy "branch protection
rules" (which still work but are no longer recommended). Rulesets are more
powerful — they cover branches *and* tags, support multiple bypass actors,
and are fully API-configurable.

### Protecting main

```bash
gh api -X POST repos/$REPO/rulesets --input - <<'EOF'
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_type": "RepositoryRole",
      "actor_id": 5,
      "bypass_mode": "always"
    }
  ],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    { "type": "required_signatures" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          { "context": "lint" },
          { "context": "test" },
          { "context": "build" },
          { "context": "security" }
        ]
      }
    }
  ]
}
EOF
```

That's a lot of JSON. Here's what each rule is doing:

- **`deletion`** + **`non_fast_forward`** — nobody can delete `main` or
  force-push to it. History is immutable.
- **`required_linear_history`** — no merge commits. Keeps `git log` clean.
- **`required_signatures`** — every commit must be GPG or SSH signed.
- **`pull_request`** with 0 approvals — all changes go through a PR, but CI
  is the reviewer (solo dev). For teams, bump `required_approving_review_count`.
- **`required_review_thread_resolution`** — can't merge with unresolved
  review comments.
- **`required_status_checks`** — the PR can't merge until CI passes.
  `strict` mode means the branch must be up-to-date with `main` first,
  preventing "merge skew" where two PRs are individually green but break
  when combined.

**About bypass actors:** `actor_id: 5` with `RepositoryRole` = the Admin
role. This lets repo admins bypass when needed (e.g., emergency hotfixes).
If you want only a *specific user* to bypass:

```bash
gh api users/YOUR_USERNAME --jq .id
# Use: "actor_type": "User", "actor_id": YOUR_ID
```

**About status check names:** these must match your CI workflow job names
*exactly*. If you use path-filtered CI, you'll want the
[summary gate pattern](#the-summary-gate-pattern) — it's explained in
the workflow architecture section.

### Protecting tags

```bash
gh api -X POST repos/$REPO/rulesets --input - <<'EOF'
{
  "name": "tag-protection",
  "target": "tag",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/tags/v*"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_type": "RepositoryRole",
      "actor_id": 5,
      "bypass_mode": "always"
    }
  ],
  "rules": [
    { "type": "deletion" },
    { "type": "update" }
  ]
}
EOF
```

Version tags (`v1.2.3`) typically trigger your CD pipeline. If someone
deletes or overwrites a tag, they can re-trigger a deploy with different
code. Making tags immutable means your release history is trustworthy.

---

## 4. Security Scanning

A production repo needs multiple layers of security scanning. Each catches
different things, and none of them alone is sufficient.

| What | Tool | Catches | When |
| --- | --- | --- | --- |
| Secret detection | GitHub secret scanning | API keys, tokens in commits | Every push |
| Secret prevention | Push protection | Blocks secrets *before* they enter history | Pre-receive |
| Static analysis | CodeQL | SQLi, XSS, path traversal | Weekly + PRs |
| History scanning | Gitleaks | Secrets anywhere in git history | Every PR |
| Dependency CVEs | Dependabot alerts | Known CVEs in your dependencies | Continuous |
| Container CVEs | Trivy | OS + library CVEs in Docker images | PRs + weekly |

### Secret scanning + push protection

Go to **Settings > Code security and analysis** and enable:

- [x] **Secret scanning** — scans for 200+ patterns (AWS keys, GitHub tokens, etc.)
- [x] **Push protection** — blocks `git push` if secrets are detected

> No stable `gh api` endpoint yet — this one's UI-only. Free for public
> repos; private repos need GitHub Advanced Security.

### CodeQL

```bash
gh api -X PUT repos/$REPO/code-scanning/default-setup \
  --input - <<'EOF'
{
  "state": "configured",
  "query_suite": "default",
  "languages": ["python", "javascript-typescript", "actions"]
}
EOF
```

CodeQL runs weekly on your default branch and on every PR. The `default`
query suite covers OWASP Top 10 patterns. The `actions` language scans your
workflow files for injection vulnerabilities — like using
`${{ github.event.issue.title }}` unsanitized in a `run:` step.

Supported languages: `python`, `javascript-typescript`, `go`, `java-kotlin`,
`ruby`, `csharp`, `swift`, `actions`. Pick the ones matching your stack.

### Dependabot security updates

Enable in **Settings > Code security and analysis**:

- [x] **Dependabot security updates** — auto-opens PRs for dependencies with known CVEs

This is *reactive* (triggered by CVE advisories). Dependabot *version*
updates (proactive weekly bumps) are configured separately in
`.github/dependabot.yml` — covered in [section 9](#9-dependabot).

---

## 5. Deployment Environments

GitHub environments let you gate access to production secrets. Without this,
any branch can reference `environment: production` in a workflow and access
whatever secrets are stored there.

```bash
gh api -X PUT repos/$REPO/environments/production --input - <<'EOF'
{
  "deployment_branch_policy": {
    "protected_branches": false,
    "custom_branch_policies": true
  }
}
EOF

gh api -X POST repos/$REPO/environments/production/deployment-branch-policies \
  -f name=main -f type=branch

gh api -X POST repos/$REPO/environments/production/deployment-branch-policies \
  -f name='v*' -f type=tag
```

Now only `main` and `v*` tags can access the `production` environment. A
feature branch workflow can't accidentally (or maliciously) access production
credentials.

For teams, you can also add **required reviewers** (manual approval before
CD runs) or a **wait timer** (N-minute delay as an "oh no" window). Both
are usually overkill for solo devs.

---

## 6. Secrets Management

Most repos need surprisingly few secrets:

| Secret | Source | How it works |
| --- | --- | --- |
| `GITHUB_TOKEN` | Automatic | GitHub creates a fresh token per workflow run. Permissions are controlled by `permissions:` blocks in your workflow files. Never set this manually. |
| `CODECOV_TOKEN` | [codecov.io](https://codecov.io) | Required for coverage uploads. |

```bash
gh secret set CODECOV_TOKEN --body "your-token-here"
```

The key insight is that `GITHUB_TOKEN` handles more than people think. It
can push Docker images to GHCR (`packages: write`), create GitHub Releases
(`contents: write`), and merge PRs (`pull-requests: write`) — all without
a personal access token. You just need to declare the right `permissions:`
in each job.

For production credentials (deploy keys, API tokens), use
**environment-scoped secrets** tied to the `production` environment from
section 5. That way they're only accessible to workflows running on `main`
or `v*` tags.

---

## 7. Workflow Architecture

A well-structured repo has four workflows, each triggered differently:

```text
PR opened ────────► ci.yml
                      lint, test, audit, build, scan, gitleaks
                      │
                      ▼
                    summary gates ──► branch protection ──► merge

v* tag pushed ────► cd.yml
                      build, scan, push to registry, GitHub Release

Weekly cron ──────► cve-scan.yml
                      rebuild + Trivy scan all images
                      │ (on failure)
                      ▼
                    auto-opens GitHub issue

Dependabot PR ────► dependabot-auto-merge.yml
                      patch-only ──► gh pr merge --auto --squash
```

### CI: path-filtered jobs + summary gates

The CI workflow is the most complex. In a monorepo, you don't want to lint
and test *every* service on *every* PR — only the ones that changed.

The architecture looks like this:

```text
                    ┌─ lint-svc-a ────┐
changes ──► filter ─┼─ lint-svc-b ────┼──► lint (gate)
                    └─ lint-shared ──┘

                    ┌─ test-svc-a ───┐
            filter ─┼─ test-svc-b ───┼──► test (gate)
                    └─ test-svc-c ──┘

                    ┌─ audit-svc-a ──┐
            filter ─┼─ audit-svc-b ──┼──► security (gate)
                    └─ gitleaks ─────┘
```

Here's the skeleton:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  changes:
    runs-on: ubuntu-latest
    timeout-minutes: 2
    outputs:
      svc-a: ${{ steps.filter.outputs.svc-a }}
      svc-b: ${{ steps.filter.outputs.svc-b }}
      shared: ${{ steps.filter.outputs.shared }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            svc-a:
              - 'svc-a/**'
              - 'shared/**'    # shared changes cascade
            svc-b:
              - 'svc-b/**'
              - 'shared/**'

  lint-svc-a:
    needs: [changes]
    if: needs.changes.outputs.svc-a == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-lang    # composite action
        with:
          service: svc-a
      - run: make lint-svc-a

  # ... repeat for each service ...

  # Summary gate — branch protection points here
  lint:
    needs: [lint-svc-a, lint-svc-b, lint-shared]
    if: always()
    runs-on: ubuntu-latest
    permissions: {}
    steps:
      - run: |
          for result in \
            "${{ needs.lint-svc-a.result }}" \
            "${{ needs.lint-svc-b.result }}" \
            "${{ needs.lint-shared.result }}"
          do
            if [ "$result" != "success" ] && [ "$result" != "skipped" ]; then
              exit 1
            fi
          done
```

Key patterns to notice:

- **Top-level permissions:** `contents: read`, `pull-requests: read`. All
  jobs inherit this. Gate jobs explicitly set `permissions: {}` since they
  just evaluate results.
- **Concurrency:** `ci-${{ github.ref }}` with `cancel-in-progress: true`.
  Pushing to the same branch cancels the previous run — saves minutes.
- **Timeout:** every job has `timeout-minutes`. Runaway jobs can't burn
  unlimited CI minutes.
- **Path filtering:** the `changes` job detects which directories were
  modified. Downstream jobs check the output before running. Shared package
  changes cascade to all dependent services.
- **Coverage uploads:** test jobs can upload reports to Codecov with
  per-service flags for segmented tracking.

### The summary gate pattern

This is the most important CI pattern in this guide, and it's not well
documented anywhere. Here's the problem:

Branch protection requires specific status checks to pass before merging.
But with path filtering, jobs that aren't relevant get *skipped*. GitHub
treats "skipped" as neither pass nor fail — so if branch protection
requires `lint-backend`, a frontend-only PR is blocked forever because
`lint-backend` will never run.

The solution is **summary gate jobs**. Instead of requiring individual jobs,
branch protection requires gate jobs that aggregate results:

```yaml
lint:
  needs: [lint-svc-a, lint-svc-b, lint-shared, lint-frontend]
  if: always()
  runs-on: ubuntu-latest
  permissions: {}
  steps:
    - run: |
        for result in \
          "${{ needs.lint-svc-a.result }}" \
          "${{ needs.lint-svc-b.result }}" \
          # ... one per dependency
        do
          if [ "$result" != "success" ] && [ "$result" != "skipped" ]; then
            exit 1
          fi
        done
```

The gate runs `if: always()` (so it's never skipped), lists all related
jobs in `needs:`, and iterates over their results. It passes if everything
is either `success` or `skipped`. Branch protection points at the gates,
not the individual jobs.

A frontend-only PR? All backend lint jobs are skipped, the `lint` gate sees
all `skipped` results, passes, and the PR can merge.

Jobs that should *always* run (like Gitleaks — secrets can leak in any file)
don't need path filtering or a gate. Make them a direct required status
check.

### CD: tag-triggered builds

The CD workflow triggers on `v*` tag pushes. It builds Docker images in a
matrix (one per service), scans each with Trivy, pushes to GHCR, and then
creates a GitHub Release with notes extracted from `CHANGELOG.md`.

```yaml
name: CD

on:
  push:
    tags: ["v*"]

permissions:
  contents: read

concurrency:
  group: cd-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build-scan-push:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment: production
    permissions:
      contents: read
      packages: write
    strategy:
      matrix:
        service: [svc-a, svc-b]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: ./.github/actions/build-and-scan
        with:
          service: ${{ matrix.service }}
          push: "true"
          tags: ghcr.io/${{ github.repository }}-${{ matrix.service }}:${{ github.ref_name }}

  release:
    needs: [build-scan-push]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Extract changelog
        run: |
          TAG="${GITHUB_REF_NAME#v}"
          NOTES=$(awk "/^## \\[$TAG\\]/{found=1; next} /^## \\[/{if(found) exit} found{print}" CHANGELOG.md)
          [ -z "$NOTES" ] && NOTES="No changelog entry for v$TAG."
          echo "$NOTES" > /tmp/release-notes.md
      - name: Create GitHub Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "$GITHUB_REF_NAME" \
            --title "$GITHUB_REF_NAME" \
            --notes-file /tmp/release-notes.md
```

Key details:

- **`environment: production`** — only `main` and `v*` tags can access this
  (configured in [section 5](#5-deployment-environments))
- **`concurrency: cd-${{ github.ref }}`** — prevents parallel deploys
- **Image tags use the git tag** (`v1.2.3`), never `latest` — you always
  know exactly what's deployed
- **Release notes from CHANGELOG** — the `awk` script extracts the section
  matching the tag version

### CVE scan: weekly vigilance

A dependency you shipped last week can get a CVE advisory today. This
workflow runs on a weekly cron (plus manual `workflow_dispatch`), rebuilds
all Docker images, and scans them with Trivy.

```yaml
name: CVE Scan

on:
  schedule:
    - cron: "0 8 * * 1"    # every Monday at 8 AM UTC
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      fail-fast: false      # scan all images even if one fails
      matrix:
        service: [svc-a, svc-b]
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/build-and-scan
        with:
          service: ${{ matrix.service }}

  open-issue:
    needs: [scan]
    if: failure()
    runs-on: ubuntu-latest
    permissions:
      issues: write
    steps:
      - uses: actions/checkout@v4
      - name: Create issue if none exists
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          EXISTING=$(gh issue list --label security --state open --search "CVE scan failure" --json number --jq '.[0].number')
          if [ -z "$EXISTING" ]; then
            gh issue create \
              --title "CVE scan failure — $(date +%Y-%m-%d)" \
              --label security \
              --body "Workflow run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          fi
```

`fail-fast: false` ensures all services get scanned even if one fails.
The `open-issue` job checks for existing open issues to avoid duplicates.

### Dependabot auto-merge

Not all Dependabot PRs need manual review. This workflow auto-merges
**patch-only** updates:

```yaml
name: Dependabot Auto-Merge

on:
  pull_request:
    branches: [main]

permissions: {}              # deny all at workflow level

jobs:
  auto-merge:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: dependabot/fetch-metadata@v2
        id: meta
      - if: steps.meta.outputs.update-type == 'version-update:semver-patch'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: gh pr merge "${{ github.event.pull_request.number }}" --auto --squash
```

`--auto` means the merge waits for all required status checks to pass
first. Patch updates are bug fixes and security patches — low risk. Minor
and major updates get manual review.

Notice the **permission trick:** `permissions: {}` at the workflow level
(deny everything), then `contents: write` + `pull-requests: write` only on
the auto-merge job. Elevated permissions scoped to exactly one job.

---

## 8. Composite Actions

A composite action is a reusable YAML file that bundles multiple steps into
a single `uses:` call. Think of it as a function for your CI — you define
inputs, run steps, and call it from any workflow.

```yaml
# .github/actions/my-action/action.yml
name: My Action
inputs:
  service:
    required: true
runs:
  using: composite
  steps:
    - run: echo "Setting up ${{ inputs.service }}"
      shell: bash
```

```yaml
# In a workflow:
- uses: ./.github/actions/my-action
  with:
    service: backend
```

### Why bother?

When the same sequence of steps appears in multiple jobs — setting up
Python + Poetry + venv cache, or building a Docker image + running Trivy —
you're duplicating code. One day you update the Python version in three
jobs but forget the fourth. Composite actions fix this: one source of truth,
called everywhere.

**When to extract:** if the same steps appear in 2+ jobs. Don't extract a
one-off — the indirection isn't worth it for a single caller.

### Pattern 1: Language setup

Installs a runtime, a package manager, caches dependencies, and runs the
install command. Used by every lint and test job.

```yaml
# .github/actions/setup-python-service/action.yml
name: Setup Python Service
inputs:
  service:
    required: true
  python-version:
    required: true
    default: "3.12"
  poetry-version:
    required: true
    default: "2.3.2"
  install-args:
    required: false
    default: ""

runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}

    - name: Install Poetry
      run: pipx install poetry==${{ inputs.poetry-version }}
      shell: bash

    - name: Cache venv
      uses: actions/cache@v4
      with:
        path: ${{ inputs.service }}/.venv
        key: venv-${{ inputs.service }}-${{ inputs.install-args || 'all' }}-${{ hashFiles(format('{0}/poetry.lock', inputs.service)) }}

    - name: Install dependencies
      run: cd ${{ inputs.service }} && poetry install ${{ inputs.install-args }}
      shell: bash
```

The cache key includes `install-args` because `--only dev` produces a
different venv than a full install. Without this, lint jobs (dev-only) and
test jobs (full) thrash each other's caches.

### Pattern 2: Build and scan

Builds a Docker image with layer caching, scans it for CVEs, and optionally
pushes to a registry. Used by CI (scan only) and CD (scan + push).

```yaml
# .github/actions/build-and-scan/action.yml
name: Build and Scan
inputs:
  service:
    required: true
  trivy-severity:
    required: false
    default: "LOW,MEDIUM,HIGH,CRITICAL"
  push:
    required: false
    default: "false"
  tags:
    required: false
    default: ""

runs:
  using: composite
  steps:
    - uses: docker/setup-buildx-action@v3

    - name: Build image
      uses: docker/build-push-action@v6
      with:
        context: ./${{ inputs.service }}
        load: true
        tags: ${{ inputs.service }}:scan
        cache-from: type=gha,scope=${{ inputs.service }}
        cache-to: type=gha,mode=max,scope=${{ inputs.service }}

    - name: Trivy scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ inputs.service }}:scan
        exit-code: "1"
        ignore-unfixed: true
        severity: ${{ inputs.trivy-severity }}
        trivyignores: .trivyignore

    - name: Push image
      if: inputs.push == 'true'
      uses: docker/build-push-action@v6
      with:
        context: ./${{ inputs.service }}
        push: true
        tags: ${{ inputs.tags }}
        cache-from: type=gha,scope=${{ inputs.service }}
```

`cache-from` and `cache-to` use `type=gha` scoped per service — so
different services don't pollute each other's layer caches. Cache hits
reduce Docker builds from minutes to seconds.

### Gotchas

- Always set `shell: bash` on every `run:` step — composite actions don't
  inherit the calling workflow's shell default.
- Pin tool versions as inputs, not hardcoded values — upgrades become a
  one-line change.

---

## 9. Dependabot

Dependabot does two things: **security updates** (reactive, triggered by
CVE advisories — enabled in section 4) and **version updates** (proactive
weekly bumps — configured in `.github/dependabot.yml`).

For a monorepo, you need one entry per ecosystem per directory:

| Ecosystem | What it bumps | Typical scope |
| --- | --- | --- |
| `pip` | Python packages | One entry per Python service |
| `npm` | Node packages | One entry per frontend service |
| `docker` | Base image versions | One entry per Dockerfile |
| `github-actions` | Action versions | One entry at `/` |

Here's a complete example for a two-service Python + frontend monorepo:

```yaml
# .github/dependabot.yml
version: 2
updates:
  # Python services
  - package-ecosystem: pip
    directory: /svc-a
    schedule: { interval: weekly }
    groups:
      minor-and-patch:
        update-types: [minor, patch]

  - package-ecosystem: pip
    directory: /svc-b
    schedule: { interval: weekly }
    groups:
      minor-and-patch:
        update-types: [minor, patch]

  # Frontend
  - package-ecosystem: npm
    directory: /frontend
    schedule: { interval: weekly }
    groups:
      minor-and-patch:
        update-types: [minor, patch]

  # Dockerfiles — ignore language runtime major/minor bumps
  - package-ecosystem: docker
    directory: /svc-a
    schedule: { interval: weekly }
    ignore:
      - dependency-name: python
        update-types: ["version-update:semver-major", "version-update:semver-minor"]

  # GitHub Actions versions
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
    groups:
      minor-and-patch:
        update-types: [minor, patch]
```

### Design decisions

**Weekly, not daily.** Daily updates are too noisy for a small team. Weekly
batches everything into one review session.

**Grouping minor + patch** produces one PR per ecosystem-directory pair
instead of one PR per dependency. Without it, a monorepo gets dozens of
PRs per week.

**Ignoring Docker base image minor bumps** is important because language
runtime versions like `python:3.12-slim` → `python:3.13-slim` are breaking
changes. Only let Dependabot handle patch bumps for these.

---

## 10. Git Hooks

CI catches everything, but it's slow. Git hooks catch the easy stuff
*locally* — lint errors, lock file drift, missing migrations — before you
wait 5 minutes for CI to tell you the same thing.

The trick is committing hooks to the repo (in `.githooks/`) and activating
them with one command:

```bash
git config core.hooksPath .githooks
```

Put this in your project's setup command (e.g. `make install`). It's a
per-repo setting — no global git config changes.

### pre-commit: lint only what changed

Runs on `git commit`. Only lints services with staged changes:

```bash
#!/usr/bin/env bash
set -e

SERVICES=(svc-a svc-b shared)
changed_dirs=$(git diff --cached --name-only | cut -d/ -f1 | sort -u)

to_lint=()
shared_changed=false

for dir in $changed_dirs; do
  for svc in "${SERVICES[@]}"; do
    [ "$dir" = "$svc" ] && to_lint+=("$svc")
    [ "$svc" = "shared" ] && [ "$dir" = "shared" ] && shared_changed=true
  done
done

# Shared package changes cascade to all services
if $shared_changed; then
  to_lint=(svc-a svc-b shared)
fi

to_lint=($(printf '%s\n' "${to_lint[@]}" | sort -u))

if [ ${#to_lint[@]} -eq 0 ]; then
  echo "No service changes staged — skipping lint."
  exit 0
fi

echo "Linting: ${to_lint[*]}"
for svc in "${to_lint[@]}"; do
  make "lint-$svc"
done
```

Full lint across all services takes 15+ seconds. Path-scoped lint keeps
it under 3 seconds for typical commits.

### pre-push: tests + validation

Runs on `git push`. More thorough because pushes are less frequent:

```bash
#!/usr/bin/env bash
set -e

# 1. Lock file integrity
echo "Checking lock files..."
(cd svc-a && poetry check --lock)
(cd svc-b && poetry check --lock)

# 2. Migration coverage
MODELS_CHANGED=$(git log main..HEAD -1 --format="%H" -- 'shared/models*.py')
MIGRATION_PRESENT=$(git log main..HEAD -1 --format="%H" -- 'shared/migrations/')

if [ -n "$MODELS_CHANGED" ] && [ -z "$MIGRATION_PRESENT" ]; then
  echo "Model changes without migration! Run: make revision msg=\"description\""
  exit 1
fi

# 3. Test changed services (same path-scoping as pre-commit)
changed_dirs=$(git diff --name-only main..HEAD | cut -d/ -f1 | sort -u)
# ... same cascade logic as pre-commit, then:
for svc in "${to_test[@]}"; do
  make "test-$svc"
done
```

Uses `git diff main..HEAD` (full branch diff, not just the latest commit)
to catch issues across the entire branch.

### Setting up hooks in a new repo

1. Create `.githooks/pre-commit` and `.githooks/pre-push`
2. Make them executable: `chmod +x .githooks/*`
3. Add `git config core.hooksPath .githooks` to your setup command
4. Update service directory names and file paths to match your project

---

## 11. Repo Files

A few files round out the setup:

### PR template

**File:** `.github/pull_request_template.md`

GitHub auto-fills this when creating a PR. Four sections are enough:

```markdown
## Summary        — what changed and why
## Related issue  — Closes #XX
## Changes        — bullet list
## How to test    — commands or steps to verify
```

Every PR answers the same questions. `Closes #XX` auto-closes the linked
issue on merge.

### .trivyignore

Suppresses known CVEs that can't be fixed yet (e.g. no upstream patch).
Every entry needs a comment — *why* it's suppressed, *when* it was added,
and a link to the advisory:

```text
# glibc overflow — no fix in Debian yet (2026-03-14)
# https://avd.aquasec.com/nvd/cve-YYYY-NNNNN
CVE-YYYY-NNNNN
```

Review this file on every base image bump and remove entries that now have
fixes.

### File inventory

When you're done, your `.github/` directory should look something like this:

| File | Purpose |
| --- | --- |
| `workflows/ci.yml` | Path-filtered lint, test, audit, build, scan + summary gates |
| `workflows/cd.yml` | Tag-triggered build + scan + push + GitHub Release |
| `workflows/cve-scan.yml` | Weekly Trivy scan with auto-issue on failure |
| `workflows/dependabot-auto-merge.yml` | Auto-merge patch-only Dependabot PRs |
| `dependabot.yml` | Version update config: ecosystems, grouping, ignore rules |
| `actions/build-and-scan/action.yml` | Composite: Docker build + cache + Trivy |
| `actions/setup-lang/action.yml` | Composite: runtime + package manager + cache |
| `pull_request_template.md` | Auto-filled PR description template |

Plus at the repo root: `.githooks/pre-commit`, `.githooks/pre-push`,
`.trivyignore`.

---

## 12. Verification

After running everything above, verify it works:

### Checklist

- [ ] Direct push to `main` is rejected
- [ ] PR to `main` requires all gate checks to pass
- [ ] Unsigned commits to `main` are rejected
- [ ] Tags matching `v*` can't be deleted or force-updated
- [ ] CD triggers on `v*` tag push and uses `production` environment
- [ ] Only `main` and `v*` can deploy to `production`
- [ ] Dependabot opens grouped PRs weekly
- [ ] Patch-only Dependabot PRs auto-merge after CI passes
- [ ] Secret scanning alerts appear under the Security tab
- [ ] CodeQL results appear under Security > Code scanning
- [ ] Third-party actions are restricted to the allowlist
- [ ] Default workflow permissions are `read`
- [ ] `git config core.hooksPath` returns `.githooks`
- [ ] `git commit` with lint errors is blocked
- [ ] `git push` with failing tests is blocked

### Verification commands

```bash
# Repo settings
gh api repos/$REPO --jq '{
  squash: .allow_squash_merge,
  merge: .allow_merge_commit,
  rebase: .allow_rebase_merge,
  auto_merge: .allow_auto_merge,
  delete_branch: .delete_branch_on_merge
}'

# Rulesets
gh api repos/$REPO/rulesets --jq '.[] | {name, enforcement, target}'

# Ruleset details (replace ID from output above)
gh api repos/$REPO/rulesets/RULESET_ID \
  --jq '{rules: [.rules[].type], bypass: .bypass_actors}'

# Actions permissions
gh api repos/$REPO/actions/permissions --jq '{enabled, allowed_actions}'
gh api repos/$REPO/actions/permissions/selected-actions --jq '.patterns_allowed'
gh api repos/$REPO/actions/permissions/workflow

# Environments
gh api repos/$REPO/environments \
  --jq '.environments[] | {name, deployment_branch_policy}'
gh api repos/$REPO/environments/production/deployment-branch-policies

# Security
gh api repos/$REPO/code-scanning/default-setup --jq '{state, languages}'
gh api repos/$REPO --jq '.security_and_analysis'

# Git hooks
git config core.hooksPath
ls -la .githooks/
```
