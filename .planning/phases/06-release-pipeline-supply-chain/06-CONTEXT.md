# Phase 6 CONTEXT — Release Pipeline & Supply Chain

**Source:** autonomous inline `discuss-phase` run on 2026-06-20 11:35 local (no interactive AskUserQuestion — Claude took the Recommended option at every gray area per standing 48h autonomy mandate; D1-D10 below are the locked decisions). Inputs: ROADMAP Phase 6 entry (uniquely detailed — most "what" is already locked there), REQUIREMENTS.md, Phase 4/5 CONTEXT carry-forwards (subprocess discipline, Dockerfile multi-stage pattern), `.github/workflows/` current state.

**Downstream:** `gsd-phase-researcher` reads to know WHAT to investigate; `gsd-planner` reads to know WHAT decisions are locked, what is deferred.

---

## Phase boundary (from ROADMAP)

**Goal:** Every push to `main` produces a release-please PR that, when merged, builds a multi-arch (`linux/amd64` + `linux/arm64`) image on native runners, signs it with Cosign keyless, attaches SBOM (SPDX + CycloneDX) and SLSA provenance, runs Trivy + pip-audit as required PR gates, and pushes to `ghcr.io/yves-vogl/aws-eks-helm-deploy` (Docker Hub frozen at v1.3.0 as v1.x archive). Dependabot, branch protection, GPG-signed commits, issue/PR templates, GH Project board, label taxonomy, security rescan, GitHub Private Vulnerability Reporting, and OpenSSF Scorecard all live.

**REQs in scope (23):** IMAGE-04, IMAGE-06, SEC-01..05, SEC-07, SEC-08, SEC-09, SEC-10, CI-01..07, CMN-01..04, MIG-01.

**Out of scope (Phase 7):** mkdocs-material site, README badge rendering polish, full migration guide POLISH.

**v2.1+ deferred:** Reusable GitHub Action wrapper (CI-NEXT-01).

---

## Canonical refs (MANDATORY for downstream agents)

| Ref | Path | Why |
|---|---|---|
| Roadmap (Phase 6 entry) | `.planning/ROADMAP.md` | Goal + 10 SCs + 6 risks — exceptionally detailed; treat as primary contract |
| Requirements catalog | `.planning/REQUIREMENTS.md` | All 23 REQ wordings normative |
| Project | `.planning/PROJECT.md` | Decisions table, deferred items |
| Phase 4 CONTEXT | `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md` | D8 cosign-fetch Dockerfile pattern — Phase 6 reuses cosign 2.6.3 pin for signing AND verification |
| Phase 5 CONTEXT | `.planning/phases/05-log-masking-diff-rollback-metadata-flip/05-CONTEXT.md` | D6 subprocess discipline (exactly 2 files); D2 helm-diff bundling pattern (analog for any future plugin bundles) |
| Phase 5 VERIFICATION | `.planning/phases/05-log-masking-diff-rollback-metadata-flip/05-VERIFICATION.md` | Shape Phase 6 verifier mirrors |
| Existing `.github/workflows/ci.yml` | `.github/workflows/ci.yml` | Current 2-job CI (lint+typecheck+unit+secrets + analyze-python via CodeQL) — Phase 6 expands |
| Existing `.github/workflows/codeql.yml` | `.github/workflows/codeql.yml` | Already pinned to digest; pattern reference |
| Existing `.github/workflows/scorecard.yml` | `.github/workflows/scorecard.yml` | Already exists per ls — Phase 6 verifies/extends, doesn't rewrite from scratch |
| Existing `Dockerfile` | `Dockerfile` | Multi-stage already established (helm-fetch, cosign-fetch, helm-diff-fetch, runtime). Phase 6 adds OCI annotations + pins base image by digest |
| Existing `pipe.yml` | `pipe.yml` | Bitbucket Pipe Marketplace metadata; updated by release-please on each release |
| Existing `pyproject.toml` | `pyproject.toml` | Version field driven by release-please; Phase 6 ensures release-please can read+write it |
| Existing `scripts/pip-audit-with-stale-check.sh` | `scripts/pip-audit-with-stale-check.sh` | Phase 4 established the two-pass stale-suppression pattern — Phase 6 CI calls this script |
| Existing `.pre-commit-config.yaml` | `.pre-commit-config.yaml` | pip-audit runs as pre-push hook locally; CI gate is in addition |
| `googleapis/release-please-action@v5` docs | https://github.com/googleapis/release-please-action | Source-of-truth for `.release-please-config.json` schema. **⚠ RESEARCH CORRECTION (C2): use v5.0.0 (SHA 45996ed1f6d02564a971a2fa1b5860e934307cf7), NOT v4** |
| `sigstore/cosign-installer` GitHub Action | https://github.com/sigstore/cosign-installer | Installs cosign in CI; pin to digest |
| `anchore/sbom-action` (Syft) | https://github.com/anchore/sbom-action | SBOM generation in SPDX + CycloneDX |
| `actions/attest-build-provenance` | https://github.com/actions/attest-build-provenance | SLSA provenance attestation. **⚠ RESEARCH CORRECTION (C1): latest is v4.1.0 (SHA `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`), NOT v1.** |
| `aquasecurity/trivy-action` | https://github.com/aquasecurity/trivy-action | Trivy scanner; SARIF upload to Code Scanning |
| `ossf/scorecard-action@v2` | https://github.com/ossf/scorecard-action | Scorecard evaluation |
| OpenSSF Scorecard public API | https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy/badge | README badge URL |

**No external ADRs outside `.planning/` for Phase 6.** The 10 locked decisions below ARE the canonical record.

---

## Locked decisions

### D1 — release-please flow: maintainer-merge, no auto-merge on release-PR

**Decision:** `release-please-action@v4` (pinned to digest) opens a release-PR each time the changelog accumulates qualifying commits. **The release-PR does NOT auto-merge** — maintainer (Yves) reviews and merges manually. Branch protection still requires CI green + 1 review (self-review OK for solo project).

**Why:** Solo maintainer; release-PRs are the single point where image+SBOM+sign+publish all happen; cheap human eyeball catches release-note typos or accidental breaking commits flagged as `feat:` that should be `feat!:`. Release cadence is not so frequent that manual merge is friction.

**Concrete config:** `.release-please-config.json` with `"release-type": "python"`, `"package-name": "aws-eks-helm-deploy"`, files block lists `pyproject.toml` (version), `CHANGELOG.md`, `pipe.yml` (image tag). `.release-please-manifest.json` seeded at `"."` → `"2.0.0-rc.0"` (or current pre-release tag).

**Tests / verification:** dry-run the release-please action locally with `release-please --token <token> --repo-url=. --release-type=python --dry-run` to confirm parsing.

**Locks:** CI-02, CI-03.

---

### D2 — `.trivyignore` rationale + expiry format

**Decision:** Each suppression in `.trivyignore` is a single line with the inline comment grammar `<CVE-ID>  # expires=YYYY-MM-DD rationale="…" reviewer=<github-handle>`. Document in `CONTRIBUTING.md`. A small parsing script `scripts/trivyignore-check.sh` validates the grammar in CI and fails on entries without expiry, OR with expiry > 180 days, OR with expiry already past.

**Why:** Trivy itself only honours the CVE ID on each line — the format extension is for human review hygiene. Hard 180-day cap + maintainer-handle requirement is the standard "no stale CVE suppressions" pattern (also matches the existing `scripts/pip-audit-with-stale-check.sh` philosophy from Phase 4).

**Tests:** unit test `tests/unit/test_trivyignore_check.py` (Bash-via-pytest is awkward; instead test the parsing logic in a Python helper called from the script). Acceptance: a deliberately stale entry causes CI failure.

**Locks:** SEC-04 (rationale & expiry surface).

---

### D3 — `.scorecard-exception.md` YAML frontmatter table

**Decision:** Single file at repo root with YAML frontmatter listing each Scorecard check that is deliberately allowed to fail. Schema:

```yaml
---
exceptions:
  - check: Token-Permissions
    reason: "GHA workflow X requires write-all for action Y; isolated to job Z."
    review_date: 2026-12-20
    owner: yves-vogl
---
```

Body is human-readable prose describing the overall stance. CI workflow `.github/workflows/scorecard.yml` parses this frontmatter and refuses to merge if any `review_date` is past.

**Why:** Scorecard score is a public credential — drift detection matters. YAML is parseable + diff-friendly. Refusal-on-stale matches the `.trivyignore` pattern.

**Locks:** SEC-10.

---

### D4 — amd64 native runner = `ubuntu-24.04` (pinned)

**Decision:** Both runner labels are pinned: `ubuntu-24.04` for amd64 and `ubuntu-24.04-arm` for arm64 (per ROADMAP wording). NOT `ubuntu-latest` for either, even on amd64.

**Why:** Reproducibility — `ubuntu-latest` rolls forward and can break cache hits or reveal hidden tool-version assumptions. Pinning matches the discipline already applied to base image (`python:3.13-slim-bookworm` digest-pinned), cosign (2.6.3), helm-diff (3.10.0).

**Locks:** IMAGE-04 (multi-arch native, no QEMU).

---

### D5 — release-please default `changelog-types` (no customization)

**Decision:** Accept release-please default Conventional Commits → CHANGELOG.md mapping. `feat:` → minor + "Features" section; `fix:` → patch + "Bug Fixes" section; `docs:` → patch (if release-affecting, e.g. SECURITY.md changes) + "Documentation"; `chore:` → no release. Breaking changes via `feat!:` or `BREAKING CHANGE:` footer → major bump.

**Why:** Defaults are battle-tested and what other consumers of the changelog expect. Customization invites bikeshedding and divergence from public expectation.

**Note for executors:** Phase 4/5 commits already use Conventional Commits — release-please will read them on first run. The v1.x history pre-release-please is not in scope for the changelog.

**Locks:** part of CI-02.

---

### D6 — Dependabot grouping

**Decision:** `.github/dependabot.yml` configures three ecosystems with explicit groups:

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule: { interval: weekly, day: monday, time: "06:00", timezone: Europe/Berlin }
    groups:
      python:
        patterns: [boto3*, botocore*, mypy*, ruff*, pytest*, structlog, pydantic*, pyyaml, requests]
    commit-message: { prefix: chore, prefix-development: chore }
    open-pull-requests-limit: 5
    # ⚠ RESEARCH CORRECTION (C3): existing dependabot.yml uses `prefix: fix` for pip;
    # change to `chore` so Python-only patch bumps do NOT trigger release-please patch
    # releases. ONLY docker ecosystem keeps `prefix: fix` (SEC-08 contract — base-image
    # bump → release-please patch → re-published freshly-scanned image).

  - package-ecosystem: docker
    directory: "/"
    schedule: { interval: weekly, day: monday, time: "06:00", timezone: Europe/Berlin }
    groups:
      docker-base:
        patterns: ["python", "debian*"]
    commit-message: { prefix: fix }  # base-image digest bump → fix(deps): → release-please patch

  - package-ecosystem: github-actions
    directory: "/"
    schedule: { interval: weekly, day: monday, time: "06:00", timezone: Europe/Berlin }
    groups:
      actions:
        patterns: ["*"]
    commit-message: { prefix: chore }
```

Auto-merge workflow `.github/workflows/dependabot-auto-merge.yml` watches for `dependabot[bot]` PRs and merges them once required checks pass (squash).

**Why:** ROADMAP risk mitigation; reduces PR noise via grouping; weekly cadence matches Phase 4 conventions; `commit-message.prefix: fix` for docker ecosystem is the SEC-08 contract (drives release-please patch on base-image bump).

**Locks:** CI-05, SEC-08.

---

### D7 — Cosign verify gate in a separate PR workflow

**Decision:** `.github/workflows/cosign-verify.yml` runs on `pull_request` against `main`. Invokes `cosign verify` against the most recent `ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` digest with `--certificate-identity` constrained to the project's release workflow path and `--certificate-oidc-issuer https://token.actions.githubusercontent.com`. Failure blocks merge.

**Why:** Risk mitigation for Pitfall #4 (cosign keyless three-way coupling). Catches: missing `id-token: write` permission in a refactor; Rekor unavailability not caught at release time; an accidental re-tag without re-sign. Cheap defensive gate.

**Locks:** SEC-01 (sign + offline-verify guarantee).

---

### D8 — SBOM filenames + attestation type

**Decision:** Two SBOM files per release: `sbom.spdx.json` and `sbom.cyclonedx.json`. Both generated via `anchore/sbom-action@v0.x.x` (pinned digest). Both attached via `cosign attest --predicate <path> --type spdxjson` (and `cyclonedx`) — this signs the SBOM atomically via the same keyless flow used for image signing. No separate `cosign sign` of the SBOM file is needed.

**Why:** Single signing flow → fewer ceremony failure modes. `cosign attest --type spdxjson` is the standard SLSA-aligned pattern. Verifiers can fetch with `cosign verify-attestation --type spdxjson`.

**Locks:** SEC-02.

---

### D9 — CI job topology: parallel fan-out

**Decision:** `.github/workflows/ci.yml` after Phase 6 has these jobs, all in parallel where possible:

| Job | Tier | Time budget | Required? |
|---|---|---|---|
| `lint-typecheck` | ruff check + ruff format --check + mypy --strict | ~30s | yes |
| `unit-coverage` | pytest tests/unit --cov 100% line+branch | ~60s | yes |
| `integration` | pytest tests/integration -m integration (Docker + helm) | ~3min | yes |
| `trivy-image` | Trivy scan image filesystem | ~1min | yes |
| `trivy-dockerfile` | Trivy scan Dockerfile + chart fixtures + secret-leak | ~30s | yes |
| `pip-audit` | scripts/pip-audit-with-stale-check.sh | ~30s | yes |
| `acceptance` (Docker-gated) | pytest tests/acceptance | ~1min | yes |

Existing `analyze-python` (CodeQL) remains in `.github/workflows/codeql.yml`, NOT moved into `ci.yml`. The 7+ jobs in ci.yml run as a single workflow → status check name is the workflow name (`ci`) for branch protection simplicity, OR per-job names — researcher determines which is the GitHub-required-check granularity.

**Why:** Parallelism within budget — entire CI completes in under 3 minutes wall-clock; failure surfaces the specific bad job.

**Locks:** CI-01, SEC-04, SEC-05.

---

### D10 — MIG-01 Docker Hub README update: manual + documented

**Decision:** Docker Hub README update is a maintainer one-shot via Docker Hub's web UI. Documented in `docs/guides/v1-to-v2.md` "Distribution change" section. Required README content:

```
⚠ This repository is FROZEN at v1.3.0.
v2.0+ is published to GitHub Container Registry:
  ghcr.io/yves-vogl/aws-eks-helm-deploy:2

See https://github.com/yves-vogl/aws-eks-helm-deploy for migration.
```

Automation deferred to v2.1+ (Docker Hub has no first-class README API; community wrappers are unmaintained).

**Locks:** MIG-01.

---

## Deferred ideas (out of scope for Phase 6)

- **Reusable GitHub Action wrapper** (CI-NEXT-01) — would let consumers use `uses: yves-vogl/aws-eks-helm-deploy@v2` in their workflows. Deferred to v2.1+.
- **Docker Hub README automation** — see D10. v2.1+ if community wrapper matures.
- **In-cluster verify policy** (Sigstore policy controller / Connaisseur) — outside the pipe's scope; consumer infrastructure choice.
- **`cosign verify-blob` integration tests against published images** — Phase 6 verifies in PR via D7, not as a separate test suite.
- **Custom Scorecard checks** — accept upstream Scorecard rule set; bikeshedding deferred.

---

## Scope creep redirects

None — Phase 6 scope is exhaustively defined in ROADMAP (10 SCs + 23 REQs).

---

## Settings / env-var additions

None — Phase 6 is CI/CD/release infrastructure, not runtime code. The pipe itself ships unchanged behavior; only the build/distribute layer changes.

---

## Out of scope

- Documentation site polish (Phase 7)
- Migration guide POLISH (Phase 7; v1-to-v2.md draft already shipped in Phase 5)
- IAM trust-policy doc polish (Phase 7)

---

## Notes for the researcher

1. **Resolve action digests** for every GitHub Action that will be pinned: `googleapis/release-please-action`, `sigstore/cosign-installer`, `anchore/sbom-action`, `actions/attest-build-provenance`, `aquasecurity/trivy-action`, `ossf/scorecard-action`, `docker/buildx-action`, `docker/login-action`. Use `gh api repos/<owner>/<repo>/git/refs/tags/<tag>` to get the SHA.
2. **Verify ARM runner availability** — `ubuntu-24.04-arm` is currently available on GitHub-hosted runners (free for public repos as of Q1 2026); confirm by checking https://github.blog/changelog/ for any deprecation. Researcher cites the announcement date.
3. **Cosign + GHCR keyless flow** — research the EXACT permissions block needed at workflow level (`id-token: write`, `packages: write`, `contents: read`) and whether the release workflow needs separate `packages: write` for the GHCR push.
4. **Syft SBOM action output paths** — confirm `anchore/sbom-action@v0` writes to a known path or requires explicit `output-file` config.
5. **release-please file-block behavior** — confirm release-please-config.json `extra-files` syntax for updating `pipe.yml` (which has a `image:` field that needs the new tag). Sample config from prior Python projects helpful.
6. **Bitbucket-side `bitbucket-pipelines.yml`** — what is the minimal CI a Bitbucket Pipe Marketplace listing needs? Read `pipe.yml` to understand. Probably zero — Pipe Marketplace is a manifest registry.
7. **Cold-start benchmark script** — what tools? Probably `time docker run --rm <image> --help` averaged over 5 runs after warm pull. Define the exact methodology.
8. **Repo settings that need MANUAL maintainer action** (cannot be set via PR):
   - Enable GitHub Private Vulnerability Reporting
   - Configure branch protection rules
   - Enable GPG signature verification requirement
   - Set up GH Project board v2
   - Define label taxonomy
   - Each of these can be documented in `docs/admin/repo-settings.md` and applied by Yves directly, but cannot land in the PR itself.

---

## Notes for the planner

- **Plan-size guidance:** Phase 6 has 23 REQs — bigger than Phase 5. Expect 8–11 plans. Suggested breakdown:
  - 06-01: CI workflow refactor (lint/typecheck/unit/integration/trivy/pip-audit fan-out) — CI-01, SEC-04, SEC-05
  - 06-02: release-please config + bootstrap (.release-please-config.json + manifest) — CI-02
  - 06-03: release.yml multi-arch build (native runners, buildx, no QEMU) — IMAGE-04, IMAGE-05, IMAGE-06
  - 06-04: Cosign sign + SBOM + SLSA in release.yml — SEC-01, SEC-02, SEC-03
  - 06-05: Cosign verify PR gate workflow — risk R1 mitigation
  - 06-06: Dependabot + auto-merge workflow + grouping — CI-05, SEC-08
  - 06-07: Security rescan (daily cron Trivy → SARIF → auto-issue) — SEC-07
  - 06-08: SECURITY.md + Private Vulnerability Reporting docs — SEC-09
  - 06-09: Scorecard workflow extension + README badge + .scorecard-exception.md — SEC-10
  - 06-10: Governance: branch protection docs + GPG-sign requirement docs + issue/PR templates + label taxonomy + project board docs — CI-06, CI-07, CMN-01..04 (this is largely DOCUMENTING what the maintainer needs to set manually + shipping the templates that can be PR'd)
  - 06-11: Bitbucket thin mirror + MIG-01 Docker Hub deprecation docs + cold-start benchmark script — CI-04, MIG-01, IMAGE-06
- **Wave assignment guidance:**
  - Wave 1: 06-01 (CI refactor) — foundation; 06-02 (release-please bootstrap) — independent
  - Wave 2: 06-03 (multi-arch build) depends on 06-02 release.yml skeleton
  - Wave 3: 06-04 (sign+SBOM+SLSA) depends on 06-03 build artifacts
  - Wave 4: 06-05 (verify gate) depends on 06-04 (verifies what 04 signs)
  - Wave 5: 06-06 (Dependabot), 06-07 (rescan), 06-08 (SECURITY.md), 06-09 (Scorecard), 06-10 (governance), 06-11 (mirror + docs) — all largely independent of each other
- **Plan-checker invariants to enforce:**
  - All GitHub Actions pinned to digest (`@<sha>`, not `@v1`)
  - `permissions:` block declared at workflow level (least privilege)
  - `id-token: write` ONLY in jobs that need keyless signing
  - `concurrency:` declared to prevent overlapping releases
  - `.trivyignore` grammar enforced via `scripts/trivyignore-check.sh`
  - `.scorecard-exception.md` review_date enforced fresh (≤180 days)
  - No `${{ secrets.* }}` in `if:` conditions (security antipattern — see Scorecard Token-Permissions check)

---

## Discussion summary (for human audit)

10 gray areas surfaced; all resolved autonomously with Recommended options (no AskUserQuestion):
1. release-please flow → D1 manual merge
2. .trivyignore format → D2 expiry+rationale grammar
3. .scorecard-exception.md → D3 YAML frontmatter
4. amd64 runner pin → D4 ubuntu-24.04
5. release-please changelog-types → D5 defaults
6. Dependabot groups → D6 3-ecosystem + grouping
7. Cosign verify placement → D7 separate PR workflow
8. SBOM file naming + signing → D8 attest, both formats
9. CI job topology → D9 parallel fan-out
10. MIG-01 Docker Hub README → D10 manual + documented

**Implicit decisions taken (not surfaced as gray areas because they're mechanical):**
- All GitHub Actions pinned to digest (project convention from existing codeql.yml)
- ARM runner = `ubuntu-24.04-arm` (per ROADMAP wording)
- Cosign version = 2.6.3 (carry-forward Phase 4 D8)
- helm-diff version = 3.10.0 (carry-forward Phase 5 D2)
- Base image = `python:3.13-slim-bookworm` digest-pinned (existing project pattern)
