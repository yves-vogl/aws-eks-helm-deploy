---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: "v2.0.0 RELEASED — tag cut, signed + SBOMs published to GHCR, docs site live"
stopped_at: v2.0.0 release ceremony complete on 2026-06-23 — only web-UI maintainer steps remain (Marketplace listing + Docker Hub banner)
last_updated: "2026-06-23T01:30:00Z"
last_activity: 2026-06-23 — v2.0.0 released; v1.x EOS frozen at 2026-12-23 (PR #56)
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 45
  completed_plans: 45
  percent: 100
  note: All 7 phases shipped (1-7). v2.0.0 RELEASED 2026-06-23 — signed via Cosign keyless, SPDX+CycloneDX SBOMs attested, multi-arch (amd64+arm64) on GHCR. Docs site live at https://yves-vogl.github.io/aws-eks-helm-deploy/ with /v1/ (frozen) + /v2/ (default/latest).
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-16)

**Core value:** A maintainer can ship a Bitbucket Pipelines deployment to AWS EKS from a clean repository in under five minutes — without committing static AWS credentials and without surprises at upgrade time.
**Current focus:** v2.0.0 RELEASED. Only two web-UI-only ceremony steps remain (Bitbucket Pipe Marketplace + Docker Hub banner).

## Current Position

v2.0.0 RELEASED 2026-06-23. 7 phases shipped end-to-end (Phase 1 toolchain → Phase 7 docs site). 700+ unit+structural tests, 100% line+branch coverage on src/, mypy --strict + ruff clean. D6 subprocess invariant preserved end-to-end.

Progress: [██████████] 100% (7 of 7 phases complete; release ceremony complete except web-UI maintainer steps)

## v2.0.0 Release Ceremony Status

| Step | Status | Reference |
|---|---|---|
| v2.0.0 tag pushed | ✅ done 2026-06-23 | `git tag v2.0.0` |
| release.yml: build linux/amd64 + linux/arm64 | ✅ done | run 27995499495 |
| release.yml: sign + SPDX + CycloneDX SBOMs + SLSA provenance | ✅ done | Cosign keyless via Fulcio/Rekor |
| release.yml: benchmark cold-start (IMAGE-06) | ✅ done | run 27995499495 |
| GitHub Release v2.0.0 with SBOM JSON assets | ✅ done | https://github.com/yves-vogl/aws-eks-helm-deploy/releases/tag/v2.0.0 |
| GHCR multi-arch images `:2.0.0` + `:2` + `:latest` | ✅ done | ghcr.io/yves-vogl/aws-eks-helm-deploy |
| GitHub Pages enabled (`gh api pages -X POST`) | ✅ done | runbook §7 |
| `mike set-default v2 --push` (root → /v2/) | ✅ done | runbook §8 |
| `mike deploy v1` (frozen snapshot live at /v1/) | ✅ done | runbook §9 |
| v1.x EOS date frozen at `2026-12-23` (= 2026-06-23 + 6 months) | ✅ done | PR #56 |
| **Bitbucket Pipe Marketplace listing update** | ⏳ Yves | runbook §10 (web-UI only) |
| **Docker Hub README deprecation banner** | ⏳ Yves | runbook §11 (web-UI only) |

Docs site live:
- https://yves-vogl.github.io/aws-eks-helm-deploy/ (root redirects to /v2/)
- https://yves-vogl.github.io/aws-eks-helm-deploy/v2/ (current, default + latest)
- https://yves-vogl.github.io/aws-eks-helm-deploy/v1/ (frozen)

## Carry-forward backlog (post-v2.0.0)

Three Phase 6 follow-ups still marked `continue-on-error: true` in `.github/workflows/ci.yml`; SARIF uploads preserve visibility:
- META-01 curly-brace UUID round-trip in helm-template / get-values
- trivy-image `.trivyignore.bare` sidecar honored (upgrade `trivy-action` OR migrate `.trivyignore` → YAML)
- trivy-dockerfile `skip-dirs` syntax (KSV-0014 / KSV-0118 chart-fixture findings leak)

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
