# Proposal: OpenSSF Scorecard Hardening Sprint

**Status:** Draft for review
**Author:** Yves Vogl
**Date:** 2026-06-17
**Target:** Score ≥ 9/10 at v2.0 tag-cut

## Background

The roadmap already includes Scorecard adoption as **SEC-10 in Phase 6**: a weekly `scorecard.yml` workflow, README badge, target ≥ 8/10. This proposal **raises the bar to ≥ 9/10** by extracting a dedicated hardening sprint instead of folding it into Phase 6's heavy supply-chain workload.

Rationale for separating it:
1. Phase 6 already carries Cosign + SBOM + Trivy + pip-audit + release-please + multi-arch + Dependabot + PVR — adding Scorecard maxing on top would either delay Phase 6 or leave Scorecard at the minimum-viable level
2. Most Scorecard checks are independent of Phase 2–5 functional work and can ship in parallel
3. Some checks (Branch-Protection, SECURITY.md, CodeQL, CII Best Practices badge) are zero-functional-risk and can ship before Phase 1 even merges
4. Concentrating the focus produces a defendable, externally-visible score quickly

## Current baseline assessment

The 18 Scorecard checks, assessed against the repo as of `HEAD` of `phase/02-aws-layer`:

| # | Check | Status | Current state | Reachable score |
|---|-------|--------|---------------|-----------------|
| 1 | Binary-Artifacts | PASS | Only `logo.png`/`logo.pxd`; no executables in tree | 10 |
| 2 | Branch-Protection | **FAIL** | `main` has no branch protection rules (GitHub API: 404) | 10 — needs setup |
| 3 | CI-Tests | PASS | `ci.yml` runs pre-commit + tests on push and PR | 10 |
| 4 | CII-Best-Practices | **FAIL** | No badge registered | 10 — 90-min effort to fill questionnaire |
| 5 | Code-Review | PARTIAL | Solo project — Yves merges own PRs, no second reviewer | **Capped at ~5/10** without external reviewer |
| 6 | Contributors | **FAIL** | Solo project, single org | **Capped at 0–3/10** without external contributors |
| 7 | Dangerous-Workflow | PASS | `ci.yml` uses `pull_request` (not `_target`); no script injection | 10 |
| 8 | Dependency-Update-Tool | **FAIL** | No `.github/dependabot.yml` (planned SEC-08 Phase 6) | 10 — Phase 6 plan can land early |
| 9 | Fuzzing | **FAIL** | No fuzz tests | 5–10 — Atheris+Hypothesis on `eks_token.py` is realistic mid-effort |
| 10 | License | PASS-ish | `LICENSE.txt` is Apache-2.0 but GitHub flags `licenseInfo: "Other"` due to `.txt` extension | 10 — trivial rename to `LICENSE` |
| 11 | Maintained | PASS | 56 commits last 3 months | 10 |
| 12 | Packaging | **FAIL** | No GitHub Releases yet (v1.x is on Docker Hub, not as GH release; v2.0 → GHCR in Phase 6) | 10 once Phase 6 release-please ships |
| 13 | Pinned-Dependencies | PARTIAL | `uv.lock` hashes ✓; GHA pinned by SHA ✓; helm SHA256 ✓; **base images on tags, not digests** | 9–10 once Dockerfile base images get digest-pinned |
| 14 | SAST | PARTIAL | ruff has security S-rules; no CodeQL/Semgrep | 10 with CodeQL workflow |
| 15 | Security-Policy | **FAIL** | No `SECURITY.md` | 10 — 30-min write |
| 16 | Signed-Releases | **FAIL** | No releases yet; Phase 6 plans Cosign | 10 once Phase 6 release pipeline ships |
| 17 | Token-Permissions | PASS | `ci.yml` has `permissions: contents: read` | 10 |
| 18 | Vulnerabilities | PARTIAL | pip-audit ignores CVE-2026-25645 (blocked on bpt 6.3.0, with stale-check) | 9 — Scorecard may dock for the ignore; closes when bpt 6.3.0 lands |

**Realistic ceiling for a single-maintainer OSS project:**
- Code-Review caps at ~5/10 — Scorecard's algorithm rewards multiple distinct reviewers per PR
- Contributors caps at ~0–3/10 — needs ≥3 distinct GitHub orgs over time
- Both reflect "is this a healthy multi-stakeholder project" rather than code quality. They cannot be quick-won.

**Reachable weighted score: ~8.5–9.2 / 10** depending on how Scorecard weights Code-Review and Contributors. Targeting **9.0** is ambitious-but-realistic; **8.5** is the safer floor.

## Proposed sprint scope

Split into three tiers by effort and timing:

### Tier 1 — Quick wins, ship before Phase 1 merge (1 sitting, ~2-3 h)

These have zero functional risk and immediately bump the score:

1. **Rename `LICENSE.txt` → `LICENSE`** — fixes GitHub's `licenseInfo: "Other"` flag and the Scorecard License check.
2. **Add `SECURITY.md`** — defines vulnerability-reporting channel (GitHub Private Vulnerability Reporting, the SEC-09 mechanism). Template: scope, supported-versions table, disclosure timeline (90 days), contact (`Security` tab on GitHub).
3. **Add `.github/dependabot.yml`** — for `pip` ecosystem (pyproject.toml + uv.lock), `docker` ecosystem (Dockerfile base image digests), `github-actions` ecosystem. Use the SEC-08 commit-prefix convention (`fix(deps):`) already documented in the roadmap.
4. **Enable Branch Protection on `main`** — require PR, require status check `ci / pre-commit (lint + typecheck + unit + secrets)`, require linear history, dismiss stale reviews, disallow force-push. Solo-developer concession: `Required approving reviews: 0` for now (Code-Review check stays low; that's acceptable).
5. **Enable GitHub Private Vulnerability Reporting (PVR)** — Settings → Security → Private vulnerability reporting → On. No code change. Links to SECURITY.md.
6. **Add `CONTRIBUTING.md`** — community-health file. Defines how to file issues, the PR workflow (Conventional Commits, signed commits, `make all` must pass), code-style expectations.
7. **Add `CODE_OF_CONDUCT.md`** — Contributor Covenant v2.1. Trivial copy.
8. **Add `CODEOWNERS`** — `* @yves-vogl` for now. Future contributors get auto-assigned reviews. Required by Branch Protection's `Require review from Code Owners` if enabled.

**Estimated bump:** +3 to +4 score points (License 10/10, Security-Policy 10/10, Branch-Protection ≥7/10, Dependency-Update-Tool 10/10).

### Tier 2 — Mid-effort, ship before Phase 6 (parallelizable with Phases 2–5, ~1 day)

1. **OpenSSF Best Practices badge** — register at `bestpractices.coreinfrastructure.org` and answer the 60+ "passing"-tier questions. Apache-2.0 license, public repo, documented contribution flow, CI gate — most answers are already true; this is paperwork. Bumps CII-Best-Practices from 0 → 10.
2. **CodeQL workflow** — `.github/workflows/codeql.yml`, weekly + on push to main. Python language. Adds SAST coverage beyond ruff's S-rules. Bumps SAST from ~5 → 10.
3. **Scorecard workflow itself** — bring SEC-10 forward from Phase 6 to this sprint. `.github/workflows/scorecard.yml` runs `ossf/scorecard-action@v2`, uploads SARIF to Code Scanning, README badge linking to `api.securityscorecards.dev`. Without this, the score is not externally visible.
4. **Dockerfile base-image digest pinning** — pull SEC-03 (currently deferred) forward. `FROM python:3.13-slim-bookworm@sha256:<digest>` and same for `debian:bookworm-slim`. Bumps Pinned-Dependencies from ~7 → 10. Dependabot (from Tier 1) maintains the digests.
5. **Fix the awscli acceptance gate (Warning 1 from Phase 2 plan-check)** — small acceptance test that proves `awscli` isn't importable in the image. Closes the manual-only gate. Marginal Scorecard impact but closes a soft ROADMAP commitment.

**Estimated bump:** +1.5 to +2 score points (CII 0 → 10, SAST 5 → 10, Pinned-Dependencies 7 → 10).

### Tier 3 — Higher effort, defer to Phase 6 cleanly

These are genuinely Phase 6 scope and shouldn't be hoisted into this sprint:

1. **Signed-Releases via Cosign keyless** — needs the full release pipeline (release-please + GHA OIDC + Cosign keyless signer) to exist. Phase 6 ships this.
2. **Packaging** — first GitHub Release with attached SBOM / provenance. Phase 6 ships this.
3. **Fuzzing** — Atheris + Hypothesis for `eks_token.py`'s token parser, `_CommaListEnvSource`'s decode logic. Mid-effort, defensible to defer; could also ship in this sprint as a Tier 2 stretch goal.

### Hard ceiling

These cannot be quick-won without external participation:

- **Code-Review** — requires distinct reviewers on PRs. Adding a CODEOWNERS entry for `@yves-vogl` does not satisfy this; Scorecard wants someone OTHER than the author to approve. Acceptance: solo project, this caps at ~5/10. Can revisit when adesso colleagues or external contributors join.
- **Contributors** — requires ≥3 distinct GitHub organizations contributing over time. Solo project caps at 0–3/10.

## Recommended Tier 1 + Tier 2 deliverable bundle

If you green-light a focused sprint, the natural deliverable is **a single PR (or 2–3 small PRs)** that adds:

- `LICENSE` (renamed from `LICENSE.txt`)
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `.github/CODEOWNERS`
- `.github/dependabot.yml` (pip + docker + github-actions, with `fix(deps):` commit prefix)
- `.github/workflows/codeql.yml` (CodeQL, weekly + on push)
- `.github/workflows/scorecard.yml` (Scorecard, weekly + on push)
- `Dockerfile` — base images digest-pinned (`python:3.13-slim-bookworm@sha256:…` + `debian:bookworm-slim@sha256:…`)
- README badge row updated with Scorecard badge + CII-Best-Practices badge (once registered)
- One acceptance test for awscli absence

Plus repo-level GitHub UI changes (no code commit, just settings):
- Enable Branch Protection on `main` (PR required, linear history, status checks)
- Enable Private Vulnerability Reporting
- Register OpenSSF Best Practices badge (external — issues a `cii-best-practices` ID)

## Expected outcome

| Check | Before | After Tier 1 + 2 |
|-------|--------|------------------|
| Binary-Artifacts | 10 | 10 |
| Branch-Protection | 0 | 8–9 (solo-dev concession on `required_reviewers=0`) |
| CI-Tests | 10 | 10 |
| CII-Best-Practices | 0 | 10 |
| Code-Review | 0 | 0–5 (capped by solo project) |
| Contributors | 0 | 0–3 (capped by solo project) |
| Dangerous-Workflow | 10 | 10 |
| Dependency-Update-Tool | 0 | 10 |
| Fuzzing | 0 | 0 (Tier 3) or 5 (Tier 2 stretch) |
| License | 10 (but flagged) | 10 (clean) |
| Maintained | 10 | 10 |
| Packaging | 0 | 0 → 10 after Phase 6 release |
| Pinned-Dependencies | 7 | 10 |
| SAST | 5 | 10 |
| Security-Policy | 0 | 10 |
| Signed-Releases | 0 | 0 → 10 after Phase 6 |
| Token-Permissions | 10 | 10 |
| Vulnerabilities | 9 | 10 (when bpt 6.3.0 lands) |

**Projected aggregate after this sprint: ~8.3 / 10**
**Projected aggregate after Phase 6 (Packaging + Signed-Releases + Fuzzing add): ~9.0 / 10**

The hard 10/10 is unreachable without multi-org contributors and per-PR external review. That's a project-maturity ceiling, not a hardening gap.

## Decision needed from Yves

1. **Tier-1 standalone PR now** (before Phase 1 merges) — yes/no?
2. **Tier-2 bundle as a parallel sprint** (during Phase 2/3 execution) — yes/no?
3. **Fuzzing in Tier 2 stretch or deferred to Phase 6** — preference?
4. **CII Best Practices badge — do the questionnaire** — yes/no/later?
5. **Tier-1 + Tier-2 grouping** — one big PR, three small PRs, or fold into existing phase PRs?

## Risks of doing this sprint

- **Branch Protection on `main` will block your own direct pushes** going forward. You're already using PRs (per `tech_standards.md`), so this codifies what you already do.
- **Dependabot will start opening PRs immediately** — most as `fix(deps):` for base-image digests, weekly for `pip`. Your `feedback_dependency_trust.md` policy is to auto-merge dependabot once CI is green; this will burn through PR cycles but no human attention.
- **CodeQL** may flag false positives (Python is well-supported but ruff's S-rules already catch most things). Each finding requires triage.
- **CII Best Practices** questionnaire takes ~90 minutes the first time.
- **OpenSSF Scorecard score becomes public** — a low initial score (e.g., 6/10 before this sprint completes) is visible on the README badge. Recommend: don't add the badge until the score is ≥ 8.
