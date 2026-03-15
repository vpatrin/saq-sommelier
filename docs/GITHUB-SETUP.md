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

```bash
gh api -X PATCH repos/$REPO \
  -F has_wiki=false \
  -F has_discussions=false \
  -F has_projects=true \
  -F has_issues=true \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=true \
  -F delete_branch_on_merge=true \
  -F allow_auto_merge=true \
  -F allow_update_branch=true \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=BLANK \
  -F web_commit_signoff_required=false
```

> **`-F` vs `-f`:** `-F` sends values as JSON types (booleans, numbers).
> `-f` sends strings. Booleans *must* use `-F` — otherwise `false` is sent
> as the string `"false"`, which is truthy in JSON.

- **Squash + rebase, no merge commits** — one clean commit per PR, linear `git log`
- **`PR_TITLE` + `BLANK`** — conventional commit title flows into squash; body lives on GitHub
- **`delete_branch_on_merge`** — auto-cleanup after merge
- **`allow_auto_merge`** — required for Dependabot auto-merge
- **Wiki off** — docs live in `docs/`, not a disconnected wiki

---

## 2. Actions Permissions

Both permission layers default to dangerously permissive. This is the
highest-impact security change you can make.

### Layer 1: Default token permissions

```bash
gh api -X PUT repos/$REPO/actions/permissions/workflow \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false
```

`GITHUB_TOKEN` defaults to **write** on everything. Setting `read` forces
every workflow to declare what it needs via `permissions:` blocks. A
compromised action can read your code but can't modify anything.

`can_approve_pull_request_reviews=false` prevents workflows from
auto-approving their own PRs.

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

`selected` mode with an explicit allowlist. `github_owned_allowed=true`
trusts `actions/*` as a baseline. `verified_allowed=false` because
"verified creator" is a Marketplace badge, not a security audit.

To build your allowlist, find all third-party actions:

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
          { "context": "security" },
          { "context": "gitleaks" }
        ]
      }
    }
  ]
}
EOF
```

What each rule does:

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
gh api -X PATCH repos/$REPO/code-scanning/default-setup \
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
are optional — skip them if you're the only deployer.

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

A typical production repo needs four workflows, each triggered differently:

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
      - uses: actions/checkout@v6
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
      - uses: actions/checkout@v6
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

### The summary gate pattern

The gate job at the bottom of the skeleton is the key pattern. Branch
protection requires named status checks, but path-filtered jobs get
*skipped* when irrelevant. GitHub treats "skipped" as neither pass nor
fail — so a frontend-only PR would be blocked forever waiting for
`lint-backend`.

Summary gates solve this: they run `if: always()`, list all related jobs
in `needs:`, and pass if every result is `success` or `skipped`. Branch
protection points at the gates, not individual jobs.

Always-run jobs (like Gitleaks) don't need a gate — make them a direct
required status check.

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
      - uses: actions/checkout@v6
      - uses: docker/login-action@v4
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
      - uses: actions/checkout@v6
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

Note: `environment: production` restricts this to `main` + `v*` tags
([section 5](#5-deployment-environments)). Image tags use the exact git
tag — never `latest`.

### CVE scan: weekly vigilance

Catches new CVEs in base images *between* releases:

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
      - uses: actions/checkout@v6
      - uses: ./.github/actions/build-and-scan
        with:
          service: ${{ matrix.service }}

  open-issue:
    needs: [scan]
    if: failure()
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - name: Create issue if none exists
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          EXISTING=$(gh issue list --label cve-scan --state open --json number --jq '.[0].number')
          if [ -z "$EXISTING" ]; then
            gh issue create \
              --title "CVE scan failure — $(date +%Y-%m-%d)" \
              --label cve-scan \
              --body "Workflow run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          fi
```

### Dependabot auto-merge

Auto-merges **patch-only** Dependabot PRs:

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
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

`--auto` waits for all checks to pass. `permissions: {}` at workflow level,
then per-job write — elevated permissions scoped to exactly one job.

---

## 8. Composite Actions

A composite action (`.github/actions/<name>/action.yml`) bundles steps into
a single `uses:` call. Extract when the same steps appear in 2+ jobs.

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
    - uses: actions/setup-python@v6
      with:
        python-version: ${{ inputs.python-version }}

    - name: Install Poetry
      run: pip install poetry==${{ inputs.poetry-version }}
      shell: bash

    - name: Cache venv
      uses: actions/cache@v5
      with:
        path: ${{ inputs.service }}/.venv
        key: venv-${{ inputs.service }}-${{ inputs.install-args || 'all' }}-${{ hashFiles(format('{0}/poetry.lock', inputs.service)) }}

    - name: Install dependencies
      run: cd ${{ inputs.service }} && poetry install ${{ inputs.install-args }} --no-interaction
      shell: bash
```

The cache key includes `install-args` so lint jobs (`--only dev`) and test
jobs (full install) don't thrash each other's caches.

### Pattern 2: Build and scan

Builds, scans, and optionally pushes. Used by CI (no push) and CD (push).

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
    - uses: docker/setup-buildx-action@v4

    - name: Build image
      uses: docker/build-push-action@v7
      with:
        context: .
        file: ${{ inputs.service }}/Dockerfile
        load: true
        tags: ${{ inputs.service }}:scan
        cache-from: type=gha,scope=${{ inputs.service }}
        cache-to: type=gha,scope=${{ inputs.service }}

    - name: Trivy scan
      uses: aquasecurity/trivy-action@0.35.0
      with:
        image-ref: ${{ inputs.service }}:scan
        exit-code: "1"
        ignore-unfixed: true
        severity: ${{ inputs.trivy-severity }}
        trivyignores: .trivyignore

    - name: Push image
      if: inputs.push == 'true'
      shell: bash
      run: |
        docker tag ${{ inputs.service }}:scan ${{ inputs.tags }}
        docker push ${{ inputs.tags }}
```

**Tips:** always set `shell: bash` on `run:` steps (composites don't
inherit the workflow's shell). Pin tool versions as inputs.

---

## 9. Dependabot

One entry per ecosystem per directory. Example for a Python + frontend
monorepo:

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

**Weekly** — daily is too noisy. **Grouped** — one PR per ecosystem-directory
instead of per-dependency. **Docker ignores** — `python:3.12` → `3.13` is
breaking; only Dependabot patch bumps for base images.

---

## 10. Git Hooks

Commit hooks to `.githooks/` and activate per-repo:

```bash
git config core.hooksPath .githooks    # add to your make install
```

### pre-commit: lint staged services

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

### pre-push: tests + validation

```bash
#!/usr/bin/env bash
set -e

SERVICES=(svc-a svc-b shared)

# 1. Lock file integrity
echo "Checking lock files..."
(cd svc-a && poetry check --lock)
(cd svc-b && poetry check --lock)

# 2. Migration coverage
MODELS_CHANGED=$(git diff --name-only main..HEAD -- 'shared/models*.py')
MIGRATION_PRESENT=$(git diff --name-only main..HEAD -- 'shared/migrations/')

if [ -n "$MODELS_CHANGED" ] && [ -z "$MIGRATION_PRESENT" ]; then
  echo "Model changes without migration! Run: make revision msg=\"description\""
  exit 1
fi

# 3. Test changed services (same cascade logic as pre-commit)
changed_dirs=$(git diff --name-only main..HEAD | cut -d/ -f1 | sort -u)

to_test=()
shared_changed=false

for dir in $changed_dirs; do
  for svc in "${SERVICES[@]}"; do
    [ "$dir" = "$svc" ] && to_test+=("$svc")
    [ "$svc" = "shared" ] && [ "$dir" = "shared" ] && shared_changed=true
  done
done

if $shared_changed; then
  to_test=(svc-a svc-b shared)
fi

to_test=($(printf '%s\n' "${to_test[@]}" | sort -u))

for svc in "${to_test[@]}"; do
  make "test-$svc"
done
```

Uses `git diff main..HEAD` — full branch diff, not just the latest commit.

---

## 11. Repo Files

### PR template (`.github/pull_request_template.md`)

```markdown
## Summary        — what changed and why
## Related issue  — Closes #XX
## Changes        — bullet list
## How to test    — commands or steps to verify
```

### .trivyignore

CVE suppressions with mandatory comments:

```text
# glibc overflow — no fix in Debian yet (2026-03-14)
# https://avd.aquasec.com/nvd/cve-YYYY-NNNNN
CVE-YYYY-NNNNN
```

Review on every base image bump — remove entries that now have fixes.

### File inventory

| File | Purpose |
| --- | --- |
| `workflows/ci.yml` | Path-filtered lint, test, audit, build, scan + summary gates |
| `workflows/cd.yml` | Tag-triggered build + scan + push + GitHub Release |
| `workflows/cve-scan.yml` | Weekly Trivy scan with auto-issue on failure |
| `workflows/dependabot-auto-merge.yml` | Auto-merge patch-only Dependabot PRs |
| `dependabot.yml` | Version update config: ecosystems, grouping, ignore rules |
| `actions/build-and-scan/action.yml` | Composite: Docker build + cache + Trivy |
| `actions/setup-lang/action.yml` | Composite: runtime + package manager + cache |
| `pull_request_template.md` | PR description template |
| `.githooks/pre-commit` | Local lint gate |
| `.githooks/pre-push` | Local test + lockfile + migration gate |
| `.trivyignore` | CVE suppressions |

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
