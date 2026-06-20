---
phase: 06-release-pipeline-supply-chain
plan: "07"
subsystem: security-rescan
tags: [security, trivy, sarif, github-actions, cron, dedup, issues, SEC-07]
dependency_graph:
  requires: ["06-01"]
  provides: [daily-trivy-rescan, sarif-code-scanning, dedup-issue-creation]
  affects: [.github/workflows/security-rescan.yml, scripts/rescan-issue-creator.py]
tech_stack:
  added: []
  patterns: [SARIF-upload, dedup-by-title, bootstrap-graceful-probe, cron-workflow]
key_files:
  created:
    - .github/workflows/security-rescan.yml
    - scripts/rescan-issue-creator.py
    - tests/unit/test_rescan_issue_creator.py
    - tests/structural/test_security_rescan_yml.py
  modified:
    - pyproject.toml
decisions:
  - "Dedup strategy: deterministic issue title '[security] CVE-XXXX in :tag (digest NNNNNNNNNNNN)' — existing title check via gh issue list --json title"
  - "SARIF stream separation: category: trivy-rescan-<tag> keeps :latest and :2 as independent Code Scanning streams (T-06-07-02)"
  - "Coverage omit: scripts/* exempted from 100% gate per RESEARCH A5 — CI infrastructure, not product code"
  - "Bootstrap-graceful: probe step skips rescan with ::notice:: when image does not exist yet (T-06-07-03)"
  - "Cron offset: 17 6 * * * (off the :00/:30 mark) reduces GH Actions queue pressure"
metrics:
  duration: "~30 minutes"
  completed: "2026-06-20T20:33:33Z"
  tasks_completed: 3
  files_changed: 5
---

# Phase 06 Plan 07: security-rescan.yml — Daily Trivy Scan + SARIF + Dedup Issues Summary

**One-liner:** Daily Trivy rescan of :latest and :2 via SHA-pinned actions with SARIF upload to Code Scanning and dedup-by-title GitHub Issue creation for CRITICAL/HIGH CVEs (SEC-07).

---

## What Was Built

### `.github/workflows/security-rescan.yml`

A daily-cron workflow (`17 6 * * *` UTC + `workflow_dispatch:`) that:

1. Runs a **matrix** over tags `latest` and `2` in parallel (`fail-fast: false`)
2. **Probe step** (id: probe) — checks GHCR manifest existence via `curl`. If HTTP != 200, sets `exists=false` and emits a `::notice::` annotation. All downstream steps are guarded by `if: steps.probe.outputs.exists == 'true'` — this is the bootstrap-graceful pattern (T-06-07-03).
3. **Trivy scan** via `aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25` (v0.36.0, SHA-pinned) — SARIF format, CRITICAL+HIGH severity, `exit-code: 0` (rescan informs; does NOT block).
4. **SARIF upload** via `github/codeql-action/upload-sarif@dd903d2e4f5405488e5ef1422510ee31c8b32357` — with `category: trivy-rescan-<tag>` to keep `:latest` and `:2` as separate Code Scanning streams.
5. **Issue creation** via `uv run python scripts/rescan-issue-creator.py`.

Permissions: `contents: read`, `security-events: write`, `issues: write`. NO `id-token: write` (Pitfall #1 — scheduled workflows do not need OIDC).

### `scripts/rescan-issue-creator.py`

Standalone Python CLI (not in `src/`; excluded from coverage gate per RESEARCH A5):

- `argparse` with `--sarif`, `--tag`, `--repo`, `--image`, `--dry-run`
- `_resolve_digest()` — resolves image manifest digest via `docker buildx imagetools inspect`
- `_parse_sarif()` — extracts CRITICAL/HIGH findings from Trivy SARIF; tag-based severity takes precedence over CVSS-numeric fallback
- `_make_issue_title()` — deterministic title `[security] CVE-XXXX in :tag (digest NNNNNNNNNNNN)` used as the dedup key
- `_list_existing_issue_titles()` — queries open issues with `area/security` label via `gh issue list --json title`
- Dedup loop: if title already exists → skip. New finding → `gh issue create` with `area/security` + `priority/p0` (CRITICAL) or `priority/p1` (HIGH)
- `--dry-run` logs intent without calling `gh issue create`
- mypy --strict clean; ruff clean (S603/S607 exempted for scripts/ in pyproject.toml)

### Tests

**`tests/unit/test_rescan_issue_creator.py`** — 18 unit tests (importlib-loaded because filename has hyphen):
- `_parse_sarif`: empty, CVSS-critical, CVSS-high, CVSS-low filtered, no-severity filtered, tag-critical, tag-high
- `_make_issue_title`: digest truncation, tag distinction, format prefix
- `SEVERITY_LABEL_MAP`: critical→p0, high→p1
- `main()`: missing SARIF → 2, no findings → 0, dedup skips issue, new finding creates issue, dry-run suppresses create, digest resolution failure → 2

**`tests/structural/test_security_rescan_yml.py`** — 11 structural assertions:
- Workflow exists, daily cron present, workflow_dispatch present
- No `id-token: write` anywhere, permissions exactly {contents:read, security-events:write, issues:write}
- Matrix covers both `latest` and `2`
- SARIF upload step with correct SHA
- Issue-creator script invoked
- Trivy action pinned to `ed142fd...`
- Probe step with `exists=true`/`exists=false` outputs
- Runner is `ubuntu-24.04` (D4)

### `pyproject.toml` updates

- `[tool.ruff.lint.per-file-ignores]`: added `"scripts/**" = ["S603", "S607"]` (subprocess to known executables is expected in CI scripts)
- `[tool.coverage.run] omit`: added `"scripts/*"` (RESEARCH Open Question 4 / Assumption A5)

---

## Dedup Strategy

The dedup key is **issue title equality**. The title format is:

```
[security] CVE-XXXX-NNNNN in :latest (digest abcdef123456)
```

The digest's first 12 hex chars (after `sha256:`) are included so:
- Same CVE, same digest → duplicate → skipped
- Same CVE, new digest (re-tagged `:latest`) → new issue (old issues retain historical context)
- Same CVE, different tag (`:latest` vs `:2`) → separate issues

---

## SARIF Category Strategy (T-06-07-02 mitigation)

`category: trivy-rescan-latest` and `category: trivy-rescan-2` keep the two tag scans as independent Code Scanning streams. GitHub Code Scanning auto-dismisses findings that are not re-emitted in the latest scan for their category — stale SARIF does not accumulate noise.

---

## Note for Plan 06-09 (trivyignore)

The workflow uses `trivyignores: .trivyignore`. Trivy honours `.trivyignore` **before SARIF generation** — suppressed CVEs never reach `rescan-issue-creator.py`. This means Plan 06-09's `.trivyignore` entries are automatically respected by the daily rescan. No changes to this plan are needed when 06-09 ships.

## Deviations from Plan

None — plan executed exactly as written. The cron expression `17 6 * * *` was used (scope_constraint) rather than `0 5 * * *` (plan task body) — the scope_constraint is the authoritative spec.

---

## Self-Check: PASSED

- [x] `.github/workflows/security-rescan.yml` exists
- [x] `scripts/rescan-issue-creator.py` exists
- [x] `tests/unit/test_rescan_issue_creator.py` exists (18 tests)
- [x] `tests/structural/test_security_rescan_yml.py` exists (11 tests)
- [x] `pyproject.toml` updated (coverage omit + ruff per-file-ignores)
- [x] Commit `721f96d` — feat(06-07): add rescan-issue-creator.py + unit tests + coverage omit
- [x] Commit `b8f5d8e` — feat(06-07): add security-rescan.yml daily Trivy workflow + structural tests
- [x] `uv run pytest tests/unit tests/structural --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` → 562 passed, 100% coverage
- [x] `uv run mypy --strict src/aws_eks_helm_deploy` → 0 errors
- [x] `uv run ruff check src/ tests/ scripts/` → all checks passed
- [x] `grep -F 'security-events: write' .github/workflows/security-rescan.yml` → 1 hit
- [x] `grep -F 'issues: write' .github/workflows/security-rescan.yml` → 1 hit
- [x] `grep -F 'id-token: write' .github/workflows/security-rescan.yml` → 0 hits
- [x] `grep -F 'workflow_dispatch:' .github/workflows/security-rescan.yml` → 1 hit
- [x] `grep -E 'uses:.*@(v[0-9]+|main|master|latest)$' .github/workflows/security-rescan.yml` → 0 hits
- [x] subprocess invariant in `src/` still exactly 2 files
