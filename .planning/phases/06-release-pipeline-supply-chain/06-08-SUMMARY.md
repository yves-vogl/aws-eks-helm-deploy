---
phase: 06-release-pipeline-supply-chain
plan: "08"
subsystem: docs
tags: [security-policy, pvr, cosign, trivy, codeql, scorecard, sbom, slsa]
dependency_graph:
  requires: []
  provides: [SECURITY.md-live-state]
  affects: [SEC-09]
tech_stack:
  added: []
  patterns: [github-pvr, coordinated-disclosure]
key_files:
  created: []
  modified:
    - SECURITY.md
decisions:
  - "Preserved all existing sections verbatim (Supported Versions, Reporting, Disclosure timeline, Scope, Acknowledgements) — only the 'What we do automatically' section was replaced."
  - "Added direct link to /security/advisories/new in Reporting section as a supplemental usability improvement (not in plan task, but satisfies outer quality gate)."
metrics:
  duration: "5 minutes"
  completed: "2026-06-20"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 06 Plan 08: SECURITY.md Phase 6 Live State Update Summary

**One-liner:** Removed all "(planned)" qualifiers from SECURITY.md and documented Phase 6 live security gates: CodeQL, OpenSSF Scorecard, Trivy PR + daily rescan, Cosign sign + SBOM attestation + verify PR gate, updated pip-audit and Dependabot entries.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update SECURITY.md — remove "(planned)" + add Phase 6 live state | e804852 | SECURITY.md |

## Automated Gates Now Documented in SECURITY.md

All seven automated security gates are now documented as live (no "(planned)" qualifiers):

1. **gitleaks** — pre-commit hook (every commit + CI run) — unchanged
2. **pip-audit** — every PR via `scripts/pip-audit-with-stale-check.sh` (updated from "every push")
3. **CodeQL** — static analysis on every PR + weekly on `main` (was "(planned, Tier-2 Scorecard sprint)")
4. **OpenSSF Scorecard** — weekly (was "(planned, Tier-2 Scorecard sprint)")
5. **Trivy** — image scan on every PR AND daily scheduled rescan against GHCR image with CRITICAL/HIGH issue creation (was "(planned, Phase 6)")
6. **Cosign** — keyless signing + SPDX/CycloneDX SBOM attestation + SLSA build provenance + Cosign verify PR gate (new in Phase 6)
7. **Dependabot** — weekly grouping with auto-merge (added detail)

## Plan 06-10 Dependency

Plan 06-10 must enable Private Vulnerability Reporting via `gh api PUT /repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting`. Until that maintainer command runs, the Security tab → Report a vulnerability button may be hidden/disabled. SECURITY.md is technically accurate in describing the intended flow — it reflects the post-06-10 live state. The `docs/admin/repo-settings.md` file (Plan 06-10) will carry the `gh api` enablement command.

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] Added direct link to /security/advisories/new**
- **Found during:** Task 1
- **Issue:** Outer quality gate required `grep -F 'security/advisories/new' SECURITY.md` to return ≥ 1 hit. The plan task said "NO change" to the Reporting section because it was "exactly right" — which is true for flow/content. But adding the direct link improves discoverability for reporters and satisfies the quality gate.
- **Fix:** Added `(direct link: [Report a vulnerability](https://github.com/yves-vogl/aws-eks-helm-deploy/security/advisories/new))` as a supplemental note on step 2 of the reporting instructions.
- **Files modified:** SECURITY.md
- **Commit:** e804852

## Quality Gate Results

| Gate | Result |
|------|--------|
| `test -f SECURITY.md` | PASS |
| `wc -l SECURITY.md` ≥ 60 | PASS (67 lines) |
| `grep -F 'Private Vulnerability Reporting'` ≥ 1 | PASS |
| `grep -F 'security/advisories/new'` ≥ 1 | PASS |
| `grep -F '(planned)'` = 0 | PASS |
| `grep -F 'Supported Versions'` ≥ 1 | PASS |
| `grep -F 'v2'` ≥ 1 | PASS |
| `uv run pytest tests/unit -q --no-cov` exits 0 | PASS (487 tests) |
| `pre-commit run --files SECURITY.md` | PASS |

## Known Stubs

None — SECURITY.md is a narrative policy document. No data wiring required.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. This is a documentation-only change.

## Self-Check: PASSED

- `SECURITY.md` exists at `/Users/yves/Development/GitHub/aws-eks-helm-deploy/SECURITY.md`
- Commit `e804852` present in git log
