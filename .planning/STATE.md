---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: "v2.0 FEATURE-COMPLETE — Phase 7 shipped (PR #45 merged); awaiting v2.0.0 tag-cut (maintainer manual)"
stopped_at: Phase 7 complete — verifier PASS, PR #45 merged on 2026-06-21
last_updated: "2026-06-21T17:45:00Z"
last_activity: 2026-06-21 — Phase 7 PR #45 merged; v2.0 feature-complete
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 45
  completed_plans: 45
  percent: 100
  note: All 7 phases shipped (1-7). v2.0 is feature-complete. v2.0.0 tag-cut is a maintainer-manual step (Yves runs `git tag v2.0.0 && git push --tags` — release.yml then signs + SBOMs + publishes to GHCR).
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-16)

**Core value:** A maintainer can ship a Bitbucket Pipelines deployment to AWS EKS from a clean repository in under five minutes — without committing static AWS credentials and without surprises at upgrade time.
**Current focus:** v2.0 is feature-complete. Next step is the v2.0.0 tag-cut ceremony (maintainer-manual).

## Current Position

Phase: 7 — SHIPPED (verifier PASS, PR #45 merged 2026-06-21)
Plans done in Phase 7: 7 of 7 (07-01..07-07 all on main)
Status: v2.0 FEATURE-COMPLETE. 7 phases shipped end-to-end (Phase 1 toolchain → Phase 7 docs site). 700+ unit+structural tests, 100% line+branch coverage on src/, mypy --strict + ruff clean. D6 subprocess invariant preserved end-to-end.
Last activity: 2026-06-21 — Phase 7 PR #45 merged

Progress: [██████████] 100% (7 of 7 phases complete)

## v2.0.0 tag-cut ceremony (PENDING — MAINTAINER MANUAL)

The branch is ready. **Yves runs these steps; Claude will NOT run them autonomously** (production touches per the standing confirmation guardrails):

1. `git checkout main && git pull && git tag v2.0.0 && git push --tags`
2. Verify `release.yml` ran: `gh run list --workflow=release.yml --limit 5`
3. Enable GitHub Pages — see `docs/admin/repo-settings.md` §7.
4. Set default mike alias — `docs/admin/repo-settings.md` §8.
5. Publish v1 frozen snapshot — `docs/admin/repo-settings.md` §9.
6. Update Bitbucket Pipe Marketplace listing — `docs/admin/repo-settings.md` §10.
7. Paste Docker Hub README deprecation banner — `docs/admin/repo-settings.md` §11.
8. Replace `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` placeholder in SECURITY.md + `docs/migration/v1-to-v2.md` with the absolute date (commit as `chore(security): freeze v1.x EOS date`).

PR #45 body has the same checklist; PR template carries it forward for future use.

## Today's Autonomous Run (2026-06-20)

Phase 5 completed end-to-end + Phase 6 planned across multiple cap windows:
- **06:00-06:30** — Phase 5 Discuss (6 locked decisions) → Research (3 corrections) → VALIDATION → Planner (7 plans) → Checker (PASS) → Wave 1 (05-01 + 05-02) → paused at 86% 5h-cap
- **10:15-11:30** — Resumed via CronCreate. PR #37 CodeQL fix + dep-bump (msgpack, pydantic-settings) + merge → Rebase phase/05 onto main → Wave 2 (05-03) → Wave 3 (05-04 + 05-05) → Wave 4 (05-06) → Wave 5 (05-07) → Verifier PASS (13/13) → PR #38 → merged
- **11:30-13:00** — Phase 6 Discuss (inline, 10 locked decisions D1-D10) → Research (Sonnet, 16 action digests resolved via gh api, 4 corrections C1-C4) → Planner (Opus, 11 plans across 6 waves, all 23 REQs covered) → Plan-Checker (Sonnet, 2 blockers + 2 warnings → all 4 fixes applied inline including 06-VALIDATION.md materialization) → paused for cap reset

## Phase 7 Resume Plan (next autonomous window)

**Phase 7 = Documentation Site & Migration Guide (final phase for v2.0).** Covers:
- mkdocs-material site at `docs/` with full content (currently scattered across `docs/guides/*.md`)
- Polish `docs/guides/v1-to-v2.md` (Phase 5 draft)
- Polish `docs/guides/oidc-setup.md` (Phase 4 draft) — IAM trust-policy + Bitbucket workspace setup
- Authoring guide for `repo://` + `oci://` charts
- Operations runbook (rollback / SAFE_UPGRADE / SECURITY.md disclosure flow)
- README badge polish + landing-page navigation
- v2.0.0 release notes + announcement
- v2.0.0 tag cut → release-please patches `pyproject.toml` + `pipe.yml` + CHANGELOG, release.yml signs+SBOMs+publishes to GHCR
- Docker Hub README banner update (manual maintainer step from docs/admin/repo-settings.md)
- Bitbucket Pipe Marketplace listing update

**Recommended next command:** `/gsd-discuss-phase 7` on a fresh `phase/07-documentation-site-and-migration` branch from main. Likely 5-7 plans, smaller than Phase 6 (mostly content + mkdocs config + release ceremony).

**Estimated cap:** ~600-900k subagent tokens for end-to-end (Phase 6 was 1.4M because it was infra-heavy with 11 plans; Phase 7 is content-heavy with fewer plans). Fresh 10:15 window should comfortably handle it.

---

## Historical Pause / Resume Plan (2026-06-20 11:30 → 2026-06-21 10:15)

*Below is the historical resume plan from yesterday's pause. Phase 6 was executed during the 2026-06-20 evening session under the "Mach jetzt autonom weiter" override and shipped before this scheduled window fired. Kept for audit trail.*

**At 10:15 tomorrow — autonomous resume tasks:**

1. **Pre-flight:** verify cap reset; read this STATE.md; `git log --oneline -10` confirms last commit is `e73ed59 docs(06): apply 4 plan-checker fixes + add VALIDATION.md` on `phase/06-release-pipeline-supply-chain`.

2. **Wave 1** (parallel-safe, dispatch sequentially): 06-01 (CI 7-job fan-out + Wave-0 tests/structural/ infrastructure) → 06-02 (release-please bootstrap config + manifest + driver workflow). Push after each.

3. **Wave 2:** 06-03 (Dockerfile TARGETARCH + release.yml build matrix native ARM, no QEMU per Pitfall #5).

4. **Wave 3:** 06-04 (release.yml sign-and-attest: Cosign keyless + Syft SBOM SPDX+CycloneDX + SLSA provenance attest-build-provenance@v4.1.0 + GHCR push). Push.

5. **Wave 4:** 06-05 (cosign-verify.yml PR gate — no `id-token: write`).

6. **Wave 5** (5 parallel-safe plans, dispatch sequentially): 06-06 (Dependabot) → 06-07 (security-rescan) → 06-08 (SECURITY.md) → 06-09 (.trivyignore + .scorecard-exception + ci.yml wiring per blocker-fix) → 06-10 (governance docs + templates).

7. **Wave 6:** 06-11 (Bitbucket stub + benchmark + MIG-01 docs + release.yml benchmark job append).

8. **Verify** via `gsd-verifier` (Sonnet) — Phase 6 verifier mirrors Phase 5 shape: 10 SCs + 23 REQs + 10 decisions + 6 risks + 13 security invariants + multi-arch real-arch sentinel.

9. **Ship**: open PR against main. PR body lists all 11 plans + the 4 research corrections + the maintainer-manual-step contract (Plan 06-10 ships `docs/admin/repo-settings.md`; Yves runs the `gh api` commands post-merge for branch protection, PVR enable, GPG-sign requirement, label creation, project board).

10. **Note for future-Claude:** Phase 6 PR will likely surface fresh CodeQL/pip-audit findings on the new structural test files and the new scripts; apply the same false-positive-fix pattern as PR #37 (refactor assertion to explicit element-match; add CVE expiry to `.trivyignore` per the D2 grammar this phase introduces).

**Cap budget for tomorrow:** estimated ~1.2-1.5M subagent tokens for full execution + verify + ship. Tomorrow's window is the right place; today's window has ~1.4M already spent.

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: 7-phase structure derived from SUMMARY.md §6 sequencing and ARCHITECTURE.md 10-phase build order, consolidated into 7 to match `granularity: standard`.
- Roadmap: Log-masking (SEC-06) sequenced before PIPE-03 (PR-comment helm-diff) as hard precondition.
- Roadmap: Release pipeline + Cosign + SBOM + Trivy + pip-audit + multi-arch consolidated into a single Phase 6 ("Release & Supply Chain") for plan-size economy.
- AUTH-04 (Phase 4): Strategy precedence mirrors botocore default chain — static keys win over OIDC when both present; one-time WARN log surfaces precedence. "OIDC wins deterministically" wording removed from ROADMAP + REQUIREMENTS (commit 6e28005).
- CHART-02 (Phase 4 Plan 04-06): HelmClient repo_add/repo_update/pull_repo raise ChartResolutionError (exit=4) not HelmExecutionError (exit=5) — chart-resolution failures semantically distinct from upgrade failures. RepoChart uses placeholder kubeconfig_path for HelmClient constructor (repo ops don't need a kubeconfig).

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Deferred Items

Items acknowledged and carried forward as v2.1+ (see REQUIREMENTS.md "v2 (Deferred) Requirements"):

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Auth | AUTH-NEXT-01 (AWS Pod Identity for self-hosted runners) | Deferred | 2026-06-16 |
| Auth | AUTH-NEXT-02 (`aws-vault` integration) | Deferred | 2026-06-16 |
| Pipe Actions | PIPE-NEXT-01 (`ACTION=uninstall`) | Deferred | 2026-06-16 |
| Pipe Actions | PIPE-NEXT-02 (`ACTION=lint`) | Deferred | 2026-06-16 |
| Distribution | CI-NEXT-01 (reusable GitHub Action wrapper) | Deferred | 2026-06-16 |
| Docs | DOC-NEXT-01 (mkdocs-material → Zensical migration) | Deferred | 2026-06-16 |

## Session Continuity

Last session: 2026-06-20T03:26:07.775Z
Stopped at: Phase 5 context gathered — 6 locked decisions, ready for /gsd-plan-phase 5
Resume file: .planning/phases/05-log-masking-diff-rollback-metadata-flip/05-CONTEXT.md
Next command: `/gsd-plan-phase 5` on branch `phase/05-log-masking-diff-rollback-metadata` — researcher reads 05-CONTEXT.md canonical refs, planner uses suggested 05-01..05-07 breakdown
