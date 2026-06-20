---
phase: "06-release-pipeline-supply-chain"
plan: "06"
subsystem: "dependabot-config-auto-merge"
tags: ["dependabot", "auto-merge", "supply-chain", "github-actions", "ci"]
dependency_graph:
  requires: ["06-01"]
  provides: ["CI-05-dependabot-auto-merge", "SEC-08-docker-prefix-contract", "C3-pip-prefix-correction"]
  affects: [".github/dependabot.yml", ".github/workflows/dependabot-auto-merge.yml"]
tech_stack:
  added: []
  patterns:
    - "Dependabot grouping (D6): 3 ecosystems with explicit group blocks to reduce PR noise"
    - "C3 pip prefix correction: chore vs fix to avoid release-please patch spam"
    - "SEC-08 docker prefix contract: fix(deps): base-image bump → release-please → freshly-scanned image"
    - "Auto-merge workflow: gh pr checks --watch + gh pr merge --squash --auto pattern"
    - "Structural YAML tests asserting prefix invariants (prevent regressions)"
key_files:
  created:
    - ".github/workflows/dependabot-auto-merge.yml"
    - "tests/structural/test_dependabot_config.py"
  modified:
    - ".github/dependabot.yml"
decisions:
  - "C3 correction: pip ecosystem prefix changed from 'fix' to 'chore' — Python dep bumps must not trigger release-please patch releases"
  - "SEC-08 preserved: docker ecosystem prefix stays 'fix' — base-image bumps drive release-please patch → freshly-scanned GHCR image"
  - "No id-token:write in auto-merge workflow — pull_request trigger (not pull_request_target) per GitHub security best practice"
  - "gh pr checks --watch is the CI gate; gh pr merge --squash --auto is the merge call"
  - "Plan 06-10 note: maintainer must enable 'Allow auto-merge' in repo Settings (cannot be done via PR)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 1
---

# Phase 6 Plan 06: Dependabot Config + Auto-merge Workflow Summary

**One-liner:** Dependabot reconfigured with D6 grouping + C3 pip-prefix correction (chore) + SEC-08 docker-prefix contract (fix) + dependabot-auto-merge.yml that gates on CI before squash-merging.

---

## Objective

Reconfigure Dependabot to avoid release-please patch spam from Python dep bumps (C3 correction), preserve the SEC-08 contract that docker base-image bumps DO drive releases (freshly-scanned image republish), add D6 PR-noise grouping to all 3 ecosystems, and ship the CI-05 auto-merge workflow.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Reconfigure .github/dependabot.yml per D6 + C3 | `5321db1` | `.github/dependabot.yml` |
| 2 | Create dependabot-auto-merge.yml (CI-05) | `9a9bea6` | `.github/workflows/dependabot-auto-merge.yml` |
| 3 | Structural tests for dependabot.yml | `f0d2e6b` | `tests/structural/test_dependabot_config.py` |

---

## Key Changes

### C3 Correction: pip prefix `fix` → `chore`

The existing `.github/dependabot.yml` used `prefix: "fix"` for the pip ecosystem. This was a mistake identified in RESEARCH (C3): every weekly Python dep bump would produce a `fix(deps):` commit, which release-please interprets as a patch-worthy change and opens a Release PR. With `prefix: "chore"`, Python dep bumps are invisible to release-please — no spurious patch releases.

### SEC-08 Contract: docker prefix stays `fix`

The docker ecosystem retains `prefix: "fix"` because that IS the intended SEC-08 flow:
1. Dependabot bumps base image digest → `fix(deps): bump python ...`
2. release-please reads `fix` as patch → opens Release PR
3. Maintainer merges Release PR → tag push triggers release.yml
4. release.yml rebuilds multi-arch image + Cosign signs + SBOM attaches → freshly-scanned image in GHCR

This chain only works if the docker prefix is `fix`.

### D6 Grouping

All 3 ecosystems now have explicit `groups:` blocks:
- pip: `python-runtime` (production/minor+patch) + `python-dev` (development/minor+patch)
- docker: `docker-base` patterns `[python, debian*]` — batches all base-image bumps into one weekly PR
- github-actions: `actions` patterns `["*"]` — batches all action SHA bumps into one weekly PR

### Auto-merge Workflow (`dependabot-auto-merge.yml`)

- Trigger: `pull_request` to `main` (NOT `pull_request_target` — avoids OIDC token risk)
- Gate: `if: github.actor == 'dependabot[bot]'` — human PRs unaffected
- Permissions: `contents: write` + `pull-requests: write` only; NO `id-token: write`
- Flow: `gh pr checks --watch --interval 30` blocks until CI completes → `gh pr review --approve` + `gh pr merge --squash --auto`
- `--auto` flag queues merge; GitHub merges when all required branch-protection checks pass (defensive double-gate)
- `actions/checkout` pinned to `11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2)
- 60-minute timeout covers slow integration test runs

### Note for Plan 06-10

`gh pr merge --auto` requires "Allow auto-merge" to be enabled in repo Settings → General. This is a one-time maintainer action that CANNOT be done via PR. Plan 06-10 (governance docs) must include the manual step:

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy --method PATCH \
  --field allow_auto_merge=true
```

### Structural Tests (`test_dependabot_config.py`)

9 tests asserting:
1. `test_dependabot_yml_exists` — file exists
2. `test_dependabot_has_three_ecosystems` — exactly {pip, docker, github-actions}
3. `test_pip_ecosystem_uses_chore_prefix` — C3 gate
4. `test_docker_ecosystem_uses_fix_prefix` — SEC-08 gate
5. `test_github_actions_ecosystem_uses_chore_prefix` — chore only
6. `test_all_ecosystems_have_groups` — D6 contract
7. `test_docker_groups_match_base_patterns` — python + debian* in docker-base
8. `test_github_actions_group_matches_all` — patterns == ["*"]
9. `test_all_ecosystems_use_weekly_schedule` — weekly for all 3

---

## Deviations from Plan

**1. [Rule 1 - Bug] Comment text in auto-merge workflow matched quality gate grep pattern**
- **Found during:** Task 2 verification
- **Issue:** Comment `# Pitfall #1: pull_request-triggered workflow MUST NOT request id-token:write.` caused `grep -E 'id-token:\s*write'` to match the comment line (comment ends with the pattern literal)
- **Fix:** Rephrased comment to `...must not request the id-token permission.` — functionally identical, pattern-safe
- **Files modified:** `.github/workflows/dependabot-auto-merge.yml`
- **Auto-fixed inline:** yes

**2. [Rule 3 - Pre-commit] ruff-format reformatted test file**
- **Found during:** Task 3 first commit attempt
- **Issue:** Long string concatenations in assertions were reformatted by ruff-format
- **Fix:** Staged reformatted file and recommitted
- **Commit:** `f0d2e6b`

---

## Quality Gates

| Gate | Result |
|------|--------|
| `pytest tests/structural -q --no-cov` | 64 passed |
| `pytest tests/unit -q --no-cov` | 469 passed |
| `mypy --strict` | 0 errors |
| ruff clean | passed |
| pip prefix = chore (≥2 hits) | 2 hits |
| docker prefix = fix (≥1 hit) | 1 hit |
| `github.actor` in auto-merge workflow | 1 hit |
| NO `id-token: write` in auto-merge | 0 hits |
| NO unpinned action tags | 0 violations |
| pre-commit | passed |

---

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The auto-merge workflow only uses `GITHUB_TOKEN` (scoped to the repo). No new threat surface beyond what is documented in the plan's STRIDE register.

## Known Stubs

None.

---

## Self-Check: PASSED

- `.github/dependabot.yml` exists: FOUND
- `.github/workflows/dependabot-auto-merge.yml` exists: FOUND
- `tests/structural/test_dependabot_config.py` exists: FOUND
- Commits `5321db1`, `9a9bea6`, `f0d2e6b` exist: FOUND
