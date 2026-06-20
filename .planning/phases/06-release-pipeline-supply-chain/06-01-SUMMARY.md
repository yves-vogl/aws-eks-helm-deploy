---
phase: 06-release-pipeline-supply-chain
plan: "01"
subsystem: ci-workflow
tags: [ci, github-actions, structural-tests, security, supply-chain]
dependency_graph:
  requires: []
  provides:
    - tests/structural/ test tier (consumed by all downstream Phase 6 plans)
    - .github/workflows/ci.yml 7-job fan-out (CI-01 gate for all PRs)
  affects:
    - .github/workflows/ci.yml (rewritten)
    - tests/structural/ (new tier)
    - pyproject.toml (unchanged — auto-discovery covers tests/structural via testpaths = ["tests"])
tech_stack:
  added:
    - helm/kind-action@99576bfa6ddf9a8e612d83b513da5a75875caced (v1.9.0) — kind cluster creation for integration job
    - aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 (v0.36.0) — image + config + secret scanning
    - github/codeql-action/upload-sarif@dd903d2e4f5405488e5ef1422510ee31c8b32357 (v3) — SARIF upload for Trivy findings
  patterns:
    - Structural pytest tier (tests/structural/) for YAML/JSON workflow assertions
    - 7-job parallel CI fan-out (D9 decision)
    - PyYAML YAML-1.1 boolean coercion guard (_get_on_block helper)
key_files:
  created:
    - tests/structural/__init__.py
    - tests/structural/test_workflow_digest_pins.py
    - tests/structural/test_ci_yml_structure.py
  modified:
    - .github/workflows/ci.yml (rewritten from 1-job pre-commit to 7-job fan-out)
decisions:
  - "Tasks 2 and 3 committed together (not separately) because the pre-commit pytest hook enforces all unit-marked tests pass before committing. test_ci_workflow_has_seven_required_jobs would fail unless ci.yml is already rewritten — Rule 3 auto-fix: merged into one commit."
  - "helm/kind-action@99576bfa6ddf9a8e612d83b513da5a75875caced (v1.9.0) chosen for integration job — SHA resolved via gh api repos/helm/kind-action/git/refs/tags/v1.9.0 on 2026-06-20."
  - "pyproject.toml unchanged — testpaths = ['tests'] already covers tests/structural; structural tests use pytestmark = pytest.mark.unit so they run in default test collection."
  - "Trivy trivyignores input points to .trivyignore which does not yet exist (created by Plan 06-09). Trivy treats a missing .trivyignore as 'no suppressions' by default — graceful-degrade confirmed."
metrics:
  duration: "~25 minutes"
  completed: "2026-06-20"
  tasks_completed: 4
  files_created: 3
  files_modified: 1
---

# Phase 06 Plan 01: CI Workflow Fan-Out + Structural Test Tier Summary

Rewrote `.github/workflows/ci.yml` from a 1-job pre-commit runner to a 7-job parallel fan-out and established the `tests/structural/` pytest tier for YAML/workflow assertions consumed by all downstream Phase 6 plans.

## What Was Built

### .github/workflows/ci.yml (7-job fan-out)

| Job key | `name:` field (branch-protection string) | Runner | Purpose |
|---------|------------------------------------------|--------|---------|
| `lint-typecheck` | `lint-typecheck (ruff + mypy)` | ubuntu-24.04 | ruff check + ruff format --check + mypy --strict |
| `unit-coverage` | `unit-coverage (100% line+branch)` | ubuntu-24.04 | pytest tests/unit tests/structural --cov 100% |
| `integration` | `integration (kind + helm)` | ubuntu-24.04 | pytest tests/integration via helm/kind-action kind cluster |
| `trivy-image` | `trivy-image` | ubuntu-24.04 | docker build + Trivy image scan → SARIF upload |
| `trivy-dockerfile` | `trivy-dockerfile` | ubuntu-24.04 | Trivy config scan + secret scan → SARIF upload |
| `pip-audit` | `pip-audit` | ubuntu-24.04 | scripts/pip-audit-with-stale-check.sh (Phase 4 two-pass pattern) |
| `acceptance` | `acceptance (docker run image)` | ubuntu-24.04 | docker build + pytest tests/acceptance |

**Plan 06-10 branch-protection payload** must use the `name:` strings in the second column above as the `required_status_checks.contexts` values.

### Action SHAs Used (from 06-RESEARCH.md)

| Action | SHA | Tag |
|--------|-----|-----|
| `actions/checkout` | `11bd71901bbe5b1630ceea73d27597364c9af683` | v4.2.2 (kept — C5 carry-forward) |
| `astral-sh/setup-uv` | `caf0cab7a618c569241d31dcd442f54681755d39` | v3.2.4 (kept — carry-forward) |
| `aquasecurity/trivy-action` | `ed142fd0673e97e23eac54620cfb913e5ce36c25` | v0.36.0 |
| `github/codeql-action/upload-sarif` | `dd903d2e4f5405488e5ef1422510ee31c8b32357` | v3 |
| `helm/kind-action` | `99576bfa6ddf9a8e612d83b513da5a75875caced` | v1.9.0 (resolved 2026-06-20) |

### tests/structural/ Tier

- `tests/structural/__init__.py` — empty package marker
- `tests/structural/test_workflow_digest_pins.py` — 4 tests: directory exists, all `uses:` pinned to 40-char SHA, no `@v{N}` tags, no `@main`/`@master`/`@HEAD` refs
- `tests/structural/test_ci_yml_structure.py` — 7 tests: ci.yml exists, 7 required jobs, `permissions: contents: read`, concurrency block, no `id-token: write`, `pull_request` trigger, no `pull_request_target`

Both files: `pytestmark = pytest.mark.unit`, `mypy --strict` clean, `ruff` clean.

## Deviations from Plan

### [Rule 3 - Blocking] Tasks 2 and 3 committed together

**Found during:** Task 2 commit attempt

**Issue:** The pre-commit hook runs `pytest (unit, no-cov)` which includes `tests/structural/`. `test_ci_workflow_has_seven_required_jobs` intentionally fails against the old ci.yml (expected red state per plan). The pre-commit hook does not allow a failing test to commit.

**Fix:** Committed `test_ci_yml_structure.py` and the rewritten `ci.yml` together in a single `feat(06-01):` commit so all tests pass at commit time.

**Files modified:** `tests/structural/test_ci_yml_structure.py`, `.github/workflows/ci.yml`

**Commit:** `7cf666a`

### pyproject.toml — no changes needed (plan anticipated possible edit)

**Found during:** Task 4

**Issue:** Plan said to verify and potentially edit `testpaths`. Current `testpaths = ["tests"]` already covers `tests/structural/` via parent-path inclusion. Structural tests are marked `pytest.mark.unit` and auto-discovered.

**Fix:** No edit made. Documented as expected in Task 4 plan ("If `testpaths` already covers `tests/structural` implicitly via a parent path, leave it untouched and document that in the SUMMARY").

### helm/kind-action SHA resolved at execution time

**Found during:** Task 3

**Issue:** Plan noted "planner did not pre-resolve this digest — Task executor MUST run `gh api` to resolve".

**Fix:** Resolved `helm/kind-action@v1.9.0` → `99576bfa6ddf9a8e612d83b513da5a75875caced` via `gh api repos/helm/kind-action/git/refs/tags/v1.9.0` on 2026-06-20. Used this SHA verbatim in ci.yml. No inline `kind create cluster` substitution needed — the action exists and resolves cleanly.

## .trivyignore Integration Note

The `trivy-image` and `trivy-dockerfile` jobs reference `trivyignores: .trivyignore`. This file does not yet exist (Plan 06-09 ships it). Trivy treats a missing `.trivyignore` as "no suppressions" by default — the jobs will run and fail only if real CRITICAL/HIGH findings exist. This is the intended graceful-degrade behavior documented in the plan.

## Known Stubs

None — ci.yml is a complete 7-job implementation. The `tests/structural/` files are complete structural assertions. No placeholder values or TODO stubs exist.

## Threat Flags

None — no new security-relevant surface introduced beyond what is documented in the plan's threat model. ci.yml has:
- Zero `id-token: write` references (T-06-V4-OIDC mitigated)
- Zero `pull_request_target` triggers (T-06-V4-PT mitigated)
- All `uses:` pinned to 40-char SHA (T-06-V10 mitigated)
- Workflow-level `permissions: contents: read` (V4 Access Control)
- `security-events: write` granted only at job level for `trivy-image` and `trivy-dockerfile`

## Quality Gates — All Passed

- `uv run pytest tests/structural -q --no-cov` — 11 passed
- `uv run pytest tests/unit -q --no-cov` — 469 passed
- `uv run pytest tests/unit tests/structural --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` — 100% coverage, 480 passed
- `uv run mypy --strict src/aws_eks_helm_deploy` — 0 errors
- `uv run ruff check src/ tests/ scripts/` — clean
- `grep -rE '^import subprocess' src/aws_eks_helm_deploy/ | wc -l` — 2 files (Phase 5 D6 invariant preserved)
- `grep -E 'uses:.*@(v[0-9]+|main|master|latest)$' .github/workflows/ci.yml` — 0 hits
- `grep -F 'pull_request_target' .github/workflows/ci.yml` — 0 hits
- `grep -F 'id-token: write' .github/workflows/ci.yml` — 0 hits
- 7-job YAML parse assertion — passed

## Self-Check: PASSED

Files exist:
- `tests/structural/__init__.py` — FOUND
- `tests/structural/test_workflow_digest_pins.py` — FOUND
- `tests/structural/test_ci_yml_structure.py` — FOUND
- `.github/workflows/ci.yml` — FOUND (7 jobs)

Commits exist:
- `67981c2` — test(06-01): add tests/structural root + test_workflow_digest_pins — FOUND
- `7cf666a` — feat(06-01): rewrite ci.yml as 7-job fan-out + add test_ci_yml_structure.py — FOUND
