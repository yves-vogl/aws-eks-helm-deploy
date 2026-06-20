---
phase: 06-release-pipeline-supply-chain
plan: "10"
subsystem: governance
tags: [github, issue-templates, pr-template, branch-protection, label-taxonomy, pvr, structural-tests]

requires:
  - phase: 06-01
    provides: "7-job CI fan-out with exact job name: strings needed for branch-protection required_status_checks.contexts"

provides:
  - "docs/admin/repo-settings.md — 8-section maintainer runbook with copy-pasteable gh API commands"
  - ".github/ISSUE_TEMPLATE/bug_report.yml — structured bug report form (CMN-01)"
  - ".github/ISSUE_TEMPLATE/feature_request.yml — structured feature request form (CMN-01)"
  - ".github/ISSUE_TEMPLATE/config.yml — blank_issues_enabled: false + PVR security redirect"
  - ".github/PULL_REQUEST_TEMPLATE.md — merge checklist with Conventional Commit + ADR + release-please guidance"
  - "tests/structural/test_governance_files.py — 31 structural assertions for all governance files"

affects:
  - "06-11 (MIG-01 Docker Hub README — cross-referenced in runbook §7)"
  - "Maintainer (post-merge manual steps documented in runbook)"

tech-stack:
  added: []
  patterns:
    - "Governance docs as code: repo-settings.md is the authoritative runbook for out-of-band admin actions"
    - "GitHub issue form YAML (body: + validations: required: true) for structured bug/feature intake"
    - "Structural test tier extended: test_governance_files.py asserts file existence + YAML validity + required field presence"

key-files:
  created:
    - docs/admin/repo-settings.md
    - .github/ISSUE_TEMPLATE/bug_report.yml
    - .github/ISSUE_TEMPLATE/feature_request.yml
    - .github/ISSUE_TEMPLATE/config.yml
    - .github/PULL_REQUEST_TEMPLATE.md
    - tests/structural/test_governance_files.py

key-decisions:
  - "All 6 files committed together (not per-task) because the pre-commit pytest hook enforces all unit-marked tests pass at commit time — same Rule 3 pattern as 06-01. The new structural tests reference the governance files; committing them separately would cause the hook to fail on the intermediate state."
  - "Branch-protection contexts array contains 8 entries: 7 ci.yml job name: strings from 06-01-SUMMARY.md + cosign-verify (latest GHCR release) from 06-05."
  - "bug_report.yml and feature_request.yml both auto-apply labels: [type/bug, area/triage] and [type/feature, area/triage] respectively — area/triage added (beyond plan minimum) to route new issues into the triage column of the project board."
  - "required_signatures endpoint is a POST (separate from the main branch protection PUT payload) — documented explicitly in runbook §3 to avoid Pitfall of merging the two calls."

requirements-completed: [CI-06, CI-07, CMN-01, CMN-02, CMN-03, CMN-04]

duration: ~20min
completed: 2026-06-20
---

# Phase 06 Plan 10: Governance Files Summary

Governance documentation + GitHub templates enabling CI-06/CI-07/CMN-01/CMN-02/CMN-03/CMN-04: maintainer runbook with copy-pasteable gh API commands for branch protection (8 contexts), GPG-signing, PVR, auto-merge, label taxonomy, and Project board, plus structured issue/PR templates with required fields and a 31-assertion structural test suite.

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-06-20
- **Tasks:** 3 (+ structural test file — scope constraint in objective)
- **Files created:** 6

## Accomplishments

- `docs/admin/repo-settings.md`: 8-section, 299-line runbook — every manual post-merge action for Phase 6 is documented with an exact `gh` command and an idempotent verify command
- Branch-protection command in §2 lists all 8 `required_status_checks.contexts` verbatim from `06-01-SUMMARY.md` (7 ci.yml `name:` strings) + cosign-verify job from Plan 06-05
- 3 issue templates + PR template + 31 structural assertions — all pass with 100% unit coverage maintained

## Branch-Protection Contexts (8 total)

These are the exact strings required in `required_status_checks.contexts` for the `gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection` PUT command:

| # | Context string | Source |
|---|----------------|--------|
| 1 | `lint-typecheck (ruff + mypy)` | 06-01 ci.yml `lint-typecheck` job |
| 2 | `unit-coverage (100% line+branch)` | 06-01 ci.yml `unit-coverage` job |
| 3 | `integration (kind + helm)` | 06-01 ci.yml `integration` job |
| 4 | `trivy-image` | 06-01 ci.yml `trivy-image` job |
| 5 | `trivy-dockerfile` | 06-01 ci.yml `trivy-dockerfile` job |
| 6 | `pip-audit` | 06-01 ci.yml `pip-audit` job |
| 7 | `acceptance (docker run image)` | 06-01 ci.yml `acceptance` job |
| 8 | `cosign-verify (latest GHCR release)` | 06-05 cosign-verify.yml |

## Task Commits

All 6 files committed together (pre-commit pytest hook Rule 3 — see Deviations):

1. **Tasks 1-3 + structural tests** — `a9a4538` (docs(06-10): add maintainer runbook docs/admin/repo-settings.md)

**Plan metadata commit:** see below

## Files Created

- `docs/admin/repo-settings.md` — 8-section maintainer runbook (SEC-09 / CI-06 / CI-07 / CI-05 / CMN-03 / CMN-04 / MIG-01)
- `.github/ISSUE_TEMPLATE/bug_report.yml` — requires pipe-version, runtime context (dropdown), reproduction steps, expected + actual behaviour (CMN-01)
- `.github/ISSUE_TEMPLATE/feature_request.yml` — requires use-case, motivation, breaking-or-not dropdown (CMN-01)
- `.github/ISSUE_TEMPLATE/config.yml` — `blank_issues_enabled: false` + PVR security redirect contact_link (SEC-09)
- `.github/PULL_REQUEST_TEMPLATE.md` — merge checklist: Conventional Commit, tests, mypy/ruff, docs, ADR, release-please, no --no-verify, no AI attribution, digest-pin reminder (Pitfall #5) (CMN-02)
- `tests/structural/test_governance_files.py` — 31 assertions (pytestmark = pytest.mark.unit)

## Decisions Made

1. **All 6 files committed together** — same pre-commit pytest-hook Rule 3 pattern as 06-01. The structural tests reference the governance files; any intermediate commit would fail the hook.
2. **`area/triage` added to issue template labels** — beyond the plan minimum (`type/bug`/`type/feature` only). Needed to route new issues into the triage column of the CMN-03 Project board.
3. **required_signatures is a POST to a separate endpoint** — documented explicitly in runbook §3. The main branch protection PUT payload does NOT include it; confusing them is a common maintainer error.
4. **Docker Hub step (§7) is a cross-reference to Plan 06-11** — MIG-01 content (the deprecation banner text) will be delivered in `docs/guides/v1-to-v2.md`. The runbook acknowledges this dependency.

## Deviations from Plan

### [Rule 3 - Blocking] All tasks committed together

**Found during:** Task 1 commit attempt

**Issue:** The pre-commit hook runs `pytest (unit, no-cov)` which includes `tests/structural/`. The new `test_governance_files.py` assertions reference the governance files. Committing the test file before the governance files (or vice versa) would cause 31 tests to fail, blocking the commit.

**Fix:** Committed all 6 files (`docs/admin/repo-settings.md`, 3 issue templates, PR template, structural test) together in a single `docs(06-10):` commit. Pre-commit passed cleanly.

**Files modified:** all 6 listed above

**Commit:** `a9a4538`

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking)
**Impact on plan:** No scope creep. Task ordering is irrelevant since all files must exist simultaneously for the pre-commit hook to pass. Same pattern documented in 06-01-SUMMARY.md.

## Issues Encountered

None beyond the commit-ordering Rule 3 deviation.

## Notes for Phase 6 Verifier

- The verifier can confirm docs/admin/repo-settings.md exists and is comprehensive — but CANNOT verify the maintainer ran the commands.
- The structural tests (`tests/structural/test_governance_files.py`) provide the automated assertion layer.
- Plan 06-11's `docs/guides/v1-to-v2.md` "Distribution change" section is the content for runbook §7 (Docker Hub README).

## Known Stubs

None — all files are fully wired. `docs/admin/repo-settings.md` §7 (Docker Hub update) is intentionally a forward-reference to Plan 06-11 and is documented as such.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. The `config.yml` security redirect closes T-06-10-01 (security report as public issue). The PR template Pitfall #5 reminder closes T-06-10-03 (unpinned action ref).

## Quality Gates — All Passed

- `pytest tests/structural -q --no-cov` — 107 passed (31 new governance assertions)
- `pytest tests/unit -q --no-cov` — 516 passed
- `mypy --strict src/aws_eks_helm_deploy` — 0 errors
- `ruff check src/ tests/ scripts/` — clean
- `test -f docs/admin/repo-settings.md` — FOUND (299 lines)
- `grep -F 'private-vulnerability-reporting' docs/admin/repo-settings.md` — 3 hits
- `grep -F 'allow_auto_merge' docs/admin/repo-settings.md` — 4 hits
- `grep -F 'required_signatures' docs/admin/repo-settings.md` — 4 hits
- `grep -F 'gh label create' docs/admin/repo-settings.md` — 10 hits
- `python3 yaml.safe_load bug_report.yml` — valid
- `python3 yaml.safe_load feature_request.yml` — valid
- `python3 yaml.safe_load config.yml` — valid
- `blank_issues_enabled: false` in config.yml — FOUND
- pre-commit (yaml + gitleaks + ruff) — PASSED

## Self-Check: PASSED

Files created:
- `docs/admin/repo-settings.md` — FOUND
- `.github/ISSUE_TEMPLATE/bug_report.yml` — FOUND
- `.github/ISSUE_TEMPLATE/feature_request.yml` — FOUND
- `.github/ISSUE_TEMPLATE/config.yml` — FOUND
- `.github/PULL_REQUEST_TEMPLATE.md` — FOUND
- `tests/structural/test_governance_files.py` — FOUND

Commits:
- `a9a4538` — docs(06-10): add maintainer runbook docs/admin/repo-settings.md — FOUND

---
*Phase: 06-release-pipeline-supply-chain*
*Completed: 2026-06-20*
