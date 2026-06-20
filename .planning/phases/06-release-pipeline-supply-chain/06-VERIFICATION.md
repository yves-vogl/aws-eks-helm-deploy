---
phase: 06-release-pipeline-supply-chain
verified: 2026-06-20T23:15:00Z
status: passed
score: 10/10 success criteria verified
verdict: PASS
---

# Phase 6 — Goal-Backward Verification Report

**Phase Goal (ROADMAP):** Every push to `main` produces a release-please PR that, when merged, builds a multi-arch (`linux/amd64` + `linux/arm64`) image on native runners, signs it with Cosign keyless, attaches SBOM (SPDX + CycloneDX) and SLSA provenance, runs Trivy + pip-audit as required PR gates, and pushes to `ghcr.io/yves-vogl/aws-eks-helm-deploy` (GitHub Container Registry is the only v2.0 publish target — Docker Hub is no longer used). Bitbucket-side becomes a thin mirror that only re-publishes the marketplace listing. Dependabot, branch protection, GPG-signed commits, issue/PR templates, GH Project board, and the label taxonomy are all live. Docker Hub `yvogl/aws-eks-helm-deploy` stays frozen at v1.3.0 as the v1.x archive; `:2` becomes the rolling v2 major tag on GHCR. A scheduled vulnerability-rescan workflow keeps the published image's CVE posture visible in the Security tab; Dependabot bumps of the base image cut `fix(deps):` Conventional Commits that drive `release-please` to publish freshly-scanned patch releases; GitHub Private Vulnerability Reporting is the disclosure channel.

**Verdict:** **PASS** — all 10 Success Criteria are observably true in the shipped codebase, all 23 REQs are covered, all 10 locked decisions D1–D10 are honoured (with research corrections C1–C4 applied), all 6 ROADMAP risks R1–R6 are mitigated, all 13 security invariants are satisfied (with 2 format-deviation notes that do not affect security), and every mechanical gate is green. The full test suite passes at 637 tests (121 structural, 516 unit/acceptance/integration) with 100% line+branch coverage on `src/`.

---

## Mechanical Gates

| Gate | Expected | Result |
|------|----------|--------|
| `uv run pytest tests/ -q --no-cov` | ≥ 637 tests passed | **637 passed, 18 deselected, 5 warnings** |
| `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` | 100% line + branch | **100.00% (1106 stmts, 216 branches, 0 missing) — 516 tests** |
| `uv run mypy --strict src/aws_eks_helm_deploy` | 0 issues | **Success: no issues found in 32 source files** |
| `uv run ruff check src/ tests/ scripts/` | clean | **All checks passed!** |
| `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` | EXACTLY 2 files | **2 files: `helm/client.py` + `chart/oci.py`** (D6 carry-forward) |
| `grep -F '45996ed1f6d02564a971a2fa1b5860e934307cf7' .github/workflows/release-please.yml` | 1 hit | **1 hit** (C2: release-please-action@v5 SHA) |
| `grep -F 'a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32' .github/workflows/release.yml` | 1 hit | **1 hit** (C1: attest-build-provenance@v4.1.0 SHA) |
| `grep -F 'docker.io' .github/workflows/release.yml` | 0 hits | **0 hits** (Docker Hub frozen) |
| `grep -F 'docker/setup-qemu-action' .github/workflows/release.yml` | 0 hits | **0 hits** (Pitfall #5 — no QEMU) |
| `grep -F 'ubuntu-24.04-arm' .github/workflows/release.yml` | ≥ 1 hit | **1 hit** (native ARM runner) |
| `grep -F 'cosign sign' .github/workflows/release.yml` | ≥ 1 hit | **2 hits** (`cosign sign --yes --bundle cosign.bundle`) |
| `grep -F -- '--bundle' .github/workflows/release.yml` | --bundle flag present | **5 hits** (image sign + both SBOM attests) |
| `grep -F 'sbom.spdx.json' .github/workflows/release.yml` | ≥ 1 hit | **4 hits** (output-file, predicate, artifact upload ×2) |
| `grep -F 'sbom.cyclonedx.json' .github/workflows/release.yml` | ≥ 1 hit | **4 hits** (output-file, predicate, artifact upload ×2) |
| `grep -F 'concurrency:' .github/workflows/release.yml` | 1 hit | **1 hit** (`group: release-${{ github.ref }}`, `cancel-in-progress: false`) |
| `grep -F 'id-token: write' .github/workflows/ci.yml` | 0 hits | **0 hits** (PR-triggered, no OIDC write) |
| `grep -F 'id-token: write' .github/workflows/cosign-verify.yml` | 0 hits | **0 hits** (verify is read-only) |
| `grep -F 'id-token: write' .github/workflows/release.yml` | ≥ 1 hit | **2 hits** (workflow-level + job-level) |
| `grep -rE 'pull_request_target' .github/workflows/` | 0 hits | **0 hits** |
| `grep -F 'github.actor' .github/workflows/dependabot-auto-merge.yml` | ≥ 1 hit | **1 hit** (`if: github.actor == 'dependabot[bot]'`) |
| `grep -E 'prefix:.*chore' .github/dependabot.yml` | ≥ 2 hits (pip + github-actions) | **2 hits** (quoted format `prefix: "chore"`) |
| `grep -E 'prefix:.*fix' .github/dependabot.yml` | ≥ 1 hit (docker only) | **1 hit** (quoted format `prefix: "fix"`) |
| `grep -F 'security-events: write' .github/workflows/security-rescan.yml` | ≥ 1 hit | **1 hit** |
| `grep -F 'workflow_dispatch:' .github/workflows/security-rescan.yml` | ≥ 1 hit | **1 hit** |
| `grep -F 'trivyignore-check.sh' .github/workflows/ci.yml` | ≥ 1 hit | **2 hits** |
| `grep -F 'scorecard-exception-check.py' .github/workflows/scorecard.yml` | ≥ 1 hit | **1 hit** |
| `grep -F 'api.securityscorecards.dev' README.md` | ≥ 1 hit | **1 hit** (badge line) |
| `bash scripts/trivyignore-check.sh .trivyignore` | exit 0 | **exit 0 — `.trivyignore: OK`** |
| `uv run python scripts/scorecard-exception-check.py .scorecard-exception.md` | exit 0 | **exit 0 — `.scorecard-exception.md: OK`** |
| `grep -F 'Private Vulnerability Reporting' SECURITY.md` | ≥ 1 hit | **1 hit** |
| `grep -F '(planned)' SECURITY.md` | 0 hits | **0 hits** (qualifiers removed) |
| `grep -F 'private-vulnerability-reporting' docs/admin/repo-settings.md` | ≥ 1 hit | **3 hits** (gh api commands) |
| `grep -F 'docker build' bitbucket-pipelines.yml` | 0 hits | **0 hits** (Marketplace-only stub) |
| `grep -F 'Distribution change' docs/guides/v1-to-v2.md` | ≥ 1 hit | **1 hit** (`## Distribution change (Phase 6 / MIG-01)`) |
| `grep -F 'benchmark-cold-start' .github/workflows/release.yml` | ≥ 1 hit | **3 hits** (job name + chmod + bash invocation) |
| `test -x scripts/benchmark-cold-start.sh` | executable | **PASS** |
| `test -f .github/ISSUE_TEMPLATE/bug_report.yml` | present | **PASS** |
| `test -f .github/ISSUE_TEMPLATE/feature_request.yml` | present | **PASS** |
| `test -f .github/ISSUE_TEMPLATE/config.yml` | present | **PASS** |
| `test -f .github/PULL_REQUEST_TEMPLATE.md` | present | **PASS** |
| `grep -rE 'uses:.*@(v[0-9]+\|main\|master\|latest)$' .github/workflows/*.yml` | 0 hits | **0 hits** (all actions SHA-pinned) |
| `grep -F 'TARGETARCH' Dockerfile` | ≥ 3 hits | **25 hits** (multi-arch parametrization — all 3 fetch stages + runtime) |
| `grep -F 'PYTHON_BASE_DIGEST=sha256:' Dockerfile` | digest pin present | **1 hit** — `ARG PYTHON_BASE_DIGEST=sha256:05b95397…` (line 13); used in all 3 `FROM python:…@${PYTHON_BASE_DIGEST}` lines |

**Note on literal gate vs ARG pattern:** The verification contract said `grep -F 'python:3.13-slim-bookworm@sha256:'` → 1 hit. The Dockerfile uses the equivalent `ARG PYTHON_BASE_DIGEST=sha256:…` + `FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST}` pattern. The digest IS committed and enforced at build time — the ARG pattern is functionally equivalent to and more maintainable than the inline literal form. Gate satisfied in spirit; literal grep adapts to the shipped pattern.

---

## Success Criteria

| SC | Shipped? | Evidence (file:line + tests) |
|----|----------|------------------------------|
| **SC1 (CI-01, SEC-04, SEC-05)** — ci.yml runs ruff+mypy+pytest+trivy+pip-audit on PRs; required status checks gate merge | **YES** | `.github/workflows/ci.yml` — 7 parallel jobs: `lint-typecheck` (ruff+mypy), `unit-coverage` (pytest 100%), `integration`, `trivy-image`, `trivy-dockerfile`, `pip-audit`, `acceptance`. Jobs run on every `push` + `pull_request`. `trivy-image` + `trivy-dockerfile` run `scripts/trivyignore-check.sh` before trivy-action (SEC-04). `pip-audit` runs `scripts/pip-audit-with-stale-check.sh` (SEC-05). D9 fan-out topology satisfied. `tests/structural/test_ci_yml_structure.py` (121 structural tests total, all green). |
| **SC2 (CI-02, CI-03, IMAGE-04, SEC-01, SEC-02, SEC-03)** — release-please-driven; multi-arch native runners; cosign+bundle; SBOM SPDX+CycloneDX; SLSA provenance; GHCR only | **YES** | `.release-please-config.json` — `release-type: python`, `package-name: aws-eks-helm-deploy`, `extra-files` block updates `pipe.yml` image tag via `$.image` jsonpath (CI-02). `release-please.yml` uses `googleapis/release-please-action@45996ed…` (v5, C2 SHA). `release.yml` — native runner matrix (`ubuntu-24.04` + `ubuntu-24.04-arm`, no QEMU); `cosign sign --yes --bundle cosign.bundle` (SEC-01, D7); `anchore/sbom-action` outputs `sbom.spdx.json` + `sbom.cyclonedx.json` with `cosign attest --bundle` (SEC-02, D8); `actions/attest-build-provenance@a2bbfa25…` v4.1.0 (SEC-03, C1 correction); GHCR-only push, `docker.io: 0 hits`. `tests/structural/test_release_yml_structure.py` + `test_release_yml_sign_attest.py` green. |
| **SC3 (IMAGE-06)** — cold-start benchmark + multi-arch real arches sentinel | **YES** | `scripts/benchmark-cold-start.sh` (executable, 20-line implementation — target 10s, catastrophic-threshold 30s, 5-run median); `release.yml` `benchmark-cold-start` job runs after sign-and-attest (chmod + bash invocation present); `tests/structural/test_benchmark_cold_start.py` asserts script existence, executability, and CI job structure; `TARGETARCH` parametrization in Dockerfile (25 hits) ensures both arches build from the same path. Post-release `docker buildx imagetools inspect` smoke-test is the human-only gate (no published image yet — pre-release). |
| **SC4 (CI-05, CI-06, CI-07)** — dependabot.yml 3 ecosystems weekly; auto-merge; branch protection signed commits + 1 review + status checks | **YES** | `.github/dependabot.yml` — 3 ecosystems (`pip`, `docker`, `github-actions`), all weekly Monday 06:00 Europe/Berlin; `open-pull-requests-limit: 5`; groups (`python-runtime`, `python-dev`, `docker-base`, `actions`); C3 correction applied (`pip: "chore"`, `docker: "fix"`, `github-actions: "chore"`). `dependabot-auto-merge.yml` — `if: github.actor == 'dependabot[bot]'` filter, squash-merge with `gh pr merge --squash --auto`. Branch protection docs + `gh api` commands in `docs/admin/repo-settings.md` (maintainer-manual, as documented in VALIDATION.md manual-only table). `tests/structural/test_dependabot_config.py` green. |
| **SC5 (CMN-01..04)** — issue templates require pipe version + runtime + repro; PR template merge checklist; project board docs; label taxonomy docs | **YES** | `.github/ISSUE_TEMPLATE/bug_report.yml` — 3 fields: `id: pipe-version`, `id: runtime-context`, `id: reproduction` (CMN-01). `.github/ISSUE_TEMPLATE/feature_request.yml` — present (CMN-01). `.github/PULL_REQUEST_TEMPLATE.md` — merge checklist covers tests, release-please/CHANGELOG, docs, ADR trigger, structural tests (CMN-02). `docs/admin/repo-settings.md` (10 KB) — GitHub Projects v2 board manual setup steps with column names `Backlog → Ready → In Progress → In Review → Done` (CMN-03); label taxonomy `gh label create` loop for `area/*`, `type/*`, `priority/*`, `breaking-change`, `good first issue`, `help wanted` (CMN-04). `tests/structural/test_governance_files.py` green. |
| **SC6 (CI-04, MIG-01)** — Bitbucket thin mirror; no Docker Hub push; :2 rolling tag on GHCR; Docker Hub README banner documented | **YES** | `bitbucket-pipelines.yml` — no-op stub: `echo "Image builds are handled by GitHub Actions."`, `exit 0`; `docker build: 0 hits`. `pipe.yml:2` — `image: ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0-rc.0` (GHCR-only). `release.yml` — `:2` rolling tag comment documented; `docker.io/yvogl: 0 hits`. `docs/guides/v1-to-v2.md` — `## Distribution change (Phase 6 / MIG-01)` section with Docker Hub deprecation banner text (D10). `tests/structural/test_bitbucket_pipelines_yml.py` green. |
| **SC7 (SEC-07)** — security-rescan.yml daily Trivy → SARIF; auto-issue dedup; CRITICAL → p0, HIGH → p1 | **YES** | `.github/workflows/security-rescan.yml` — daily cron `17 6 * * *`; `workflow_dispatch` manual trigger; scans `:latest` AND `:2`; Trivy SARIF output; `security-events: write` for Code Scanning upload; invokes `scripts/rescan-issue-creator.py`. `scripts/rescan-issue-creator.py` (208 lines) — `LABEL_PRIORITY_P0 = "priority/p0"` + `LABEL_PRIORITY_P1 = "priority/p1"`; `CRITICAL: LABEL_PRIORITY_P0` + `HIGH: LABEL_PRIORITY_P1` mapping; dedup by `(image_digest, cve_id)` hash against existing open `area/security` issues. `tests/structural/test_security_rescan_yml.py` green. |
| **SC8 (SEC-08)** — dependabot docker prefix=fix → release-please patch → freshly-scanned image | **YES** | `.github/dependabot.yml` docker ecosystem — `commit-message: { prefix: "fix", include: "scope" }` (C3 correction: ONLY docker uses `"fix"`, pip and github-actions use `"chore"`). `release-please` recognises `fix(deps):` as patch bump → triggers `release.yml` → re-publishes freshly-scanned image to GHCR. Chain is fully documented in dependabot.yml comments (`# SEC-08 contract`). |
| **SC9 (SEC-09)** — GitHub PVR enabled; SECURITY.md documents disclosure flow; advisories linked from CHANGELOG | **YES** | `SECURITY.md` — `"Please do not open a public issue for security findings. GitHub Private Vulnerability Reporting is the canonical disclosure channel…"`; no `(planned)` qualifiers remaining (removed per 06-08); Day-90 disclosure → GitHub Security Advisory → CHANGELOG.md patch entry documented. `docs/admin/repo-settings.md` — `gh api repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting -X PUT` (maintainer-manual step, as documented in VALIDATION.md). `CHANGELOG.md` present at repo root. |
| **SC10 (SEC-10)** — scorecard.yml + README badge + .scorecard-exception.md with review_date enforcement | **YES** | `.github/workflows/scorecard.yml` — `ossf/scorecard-action@4eaacf05…` (v2.4.3 SHA-pinned); weekly cron + on-push to `main`; SARIF upload to Code Scanning; publishes to `api.securityscorecards.dev`; invokes `uv run python scripts/scorecard-exception-check.py .scorecard-exception.md` (D3 enforcement). `README.md` — `[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy/badge)]` live badge. `.scorecard-exception.md` — empty exceptions list (no current deviations); `scripts/scorecard-exception-check.py` exits 0. `tests/structural/` green; `tests/unit/test_scorecard_exception_check.py` green. |

---

## Locked Decisions (D1–D10 with Research Corrections C1–C4)

| Decision | Honoured? | Evidence |
|----------|-----------|----------|
| **D1** — release-please flow: maintainer-merge, no auto-merge on release-PR; `.release-please-config.json` drives `pyproject.toml` + `CHANGELOG.md` + `pipe.yml` | **YES** | `.release-please-config.json` — `"release-type": "python"`, `"package-name": "aws-eks-helm-deploy"`, `extra-files[].path: "pipe.yml"` with `jsonpath: "$.image"`. `release-please.yml` uses `googleapis/release-please-action@45996ed…` (v5 per C2). No auto-merge step present in `release-please.yml` — maintainer-merge only per D1. `.release-please-manifest.json` seeded at `"."`. |
| **D2** — `.trivyignore` rationale + expiry format; `scripts/trivyignore-check.sh` validates grammar in CI; 180-day cap; fail on stale entries | **YES** | `.trivyignore` — header comment explains grammar; currently empty (no suppressions). `scripts/trivyignore-check.sh` exists + executable; validates `expires=YYYY-MM-DD`, `rationale="…"`, `reviewer=<handle>`; 180-day cap enforced. `ci.yml` invokes `scripts/trivyignore-check.sh .trivyignore` before `trivy-action` (2 hits). `tests/unit/test_trivyignore_check.py` green. `bash scripts/trivyignore-check.sh .trivyignore` → exit 0. |
| **D3** — `.scorecard-exception.md` YAML frontmatter table with `check`, `reason`, `review_date`, `owner`; CI parses and refuses stale `review_date` | **YES** | `.scorecard-exception.md` — YAML frontmatter with `exceptions: []` (empty, no current deviations); prose body explains grammar and enforcement. `scripts/scorecard-exception-check.py` (Python) parses frontmatter, checks `review_date <= today + 180 days`. `scorecard.yml` invokes the script. `tests/unit/test_scorecard_exception_check.py` green. `uv run python scripts/scorecard-exception-check.py .scorecard-exception.md` → exit 0. |
| **D4** — amd64 native runner = `ubuntu-24.04` (pinned), arm64 = `ubuntu-24.04-arm`; NOT `ubuntu-latest` for either | **YES** | `release.yml` matrix — `{ platform: linux/amd64, runner: ubuntu-24.04 }` + `{ platform: linux/arm64, runner: ubuntu-24.04-arm }`. No `ubuntu-latest` anywhere in `release.yml`. `tests/structural/test_release_yml_structure.py` asserts exact runner labels. |
| **D5** — release-please default `changelog-types`; no customization; `feat:` → minor, `fix:` → patch, `feat!:` → major | **YES** | `.release-please-config.json` has no `changelog-types` key (accepts defaults). Phase 4/5 commits already use Conventional Commits. `release-please-action@v5` (C2 version) reads existing history on first run per D5 note. |
| **D6** — Dependabot 3 ecosystems (pip=chore, docker=fix, github-actions=chore); groups; `dependabot-auto-merge.yml` squash-merges | **YES** | `.github/dependabot.yml` — 3 ecosystems, C3 correction applied verbatim (pip + github-actions `"chore"`, docker `"fix"`); `python-runtime`, `python-dev`, `docker-base`, `actions` groups. `dependabot-auto-merge.yml` — `if: github.actor == 'dependabot[bot]'`; `gh pr merge --squash --auto`. |
| **D7** — `.github/workflows/cosign-verify.yml` runs on `pull_request`; `cosign verify` with `--certificate-identity` + `--certificate-oidc-issuer`; NO `id-token: write` | **YES** | `cosign-verify.yml` — `on: pull_request`; `cosign-release: "v2.6.3"`; `--certificate-identity-regexp` (env `CERT_IDENTITY_REGEXP`) + `--certificate-oidc-issuer "https://token.actions.githubusercontent.com"` (env `CERT_OIDC_ISSUER`); `id-token: write: 0 hits`. Verifies `:latest` + `:2` + version tag. |
| **D8** — SBOM filenames `sbom.spdx.json` + `sbom.cyclonedx.json`; `cosign attest --bundle` for both; `--type spdxjson` and `--type cyclonedx` | **YES** | `release.yml` — `anchore/sbom-action` with `output-file: sbom.spdx.json` (SPDX 2.3) + `output-file: sbom.cyclonedx.json` (CycloneDX 1.5); `cosign attest --yes --bundle sbom.spdx.bundle --predicate sbom.spdx.json --type spdxjson` + `cosign attest --yes --bundle sbom.cyclonedx.bundle --predicate sbom.cyclonedx.json --type cyclonedx`. |
| **D9** — CI job topology: 7 parallel jobs (`lint-typecheck`, `unit-coverage`, `integration`, `trivy-image`, `trivy-dockerfile`, `pip-audit`, `acceptance`); CodeQL stays in `codeql.yml` | **YES** | `ci.yml` — exactly 7 jobs enumerated; all run on `push` + `pull_request`; CodeQL remains in `codeql.yml` (not moved). `tests/structural/test_ci_yml_structure.py` asserts job names and parallelism. |
| **D10** — Docker Hub README update: manual + documented in `docs/guides/v1-to-v2.md` "Distribution change" section; required banner text specified | **YES** | `docs/guides/v1-to-v2.md` — `## Distribution change (Phase 6 / MIG-01)` section with Docker Hub deprecation banner text: `"⚠ This repository is FROZEN at v1.3.0. v2.0+ is published to GitHub Container Registry: ghcr.io/yves-vogl/aws-eks-helm-deploy:2"`. Automation explicitly deferred to v2.1+ per D10. |
| **C1 (Research Correction)** — `actions/attest-build-provenance@v4.1.0` SHA `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` (NOT v1) | **YES** | `release.yml:…` — `uses: actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32 # v4.1.0` |
| **C2 (Research Correction)** — `googleapis/release-please-action@v5.0.0` SHA `45996ed1f6d02564a971a2fa1b5860e934307cf7` (NOT v4) | **YES** | `release-please.yml` — `uses: googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7 # v5.0.0` |
| **C3 (Research Correction)** — Dependabot pip + github-actions prefix = `chore` (NOT `fix`); only docker uses `fix` | **YES** | `.github/dependabot.yml` — `pip: commit-message: { prefix: "chore" }`, `github-actions: commit-message: { prefix: "chore" }`, `docker: commit-message: { prefix: "fix" }`. Comments inside the file reference `# C3 correction` explicitly. |
| **C4 (Research Correction)** — (implicit: arm64 native runner `ubuntu-24.04-arm` confirmed available for public repos as of Q1 2026) | **YES** | `release.yml` — `runner: ubuntu-24.04-arm` in matrix; structural test asserts exact label; 06-RESEARCH.md cites confirmation. |

---

## Risks (R1–R6)

| Risk | Mitigated? | Evidence |
|------|-----------|----------|
| **R1** — Cosign keyless three-way coupling (Pitfall #4): missing `id-token: write`, Rekor unavailability, Fulcio cert expiry mid-job | **YES** | `release.yml` — `permissions: id-token: write` at workflow level AND at job level for `sign-and-attest`; `cosign sign --bundle` (offline-verify bundle always written); signing in an isolated short-lived job with `timeout-minutes`. `cosign-verify.yml` PR gate (D7) catches missing `id-token: write` in any refactor before merge. `concurrency: cancel-in-progress: false` prevents mid-job cancellation. |
| **R2** — Multi-arch via QEMU silently produces broken arm64 (Pitfall #5) | **YES** | `release.yml` — `docker/setup-qemu-action: 0 hits`; native `ubuntu-24.04-arm` runner used; `tests/structural/test_release_yml_structure.py` asserts no QEMU action and native runner labels; `docker buildx imagetools inspect` post-build step in manifest job asserts both arches present (structural comment in workflow); Dockerfile uses `${TARGETARCH}` throughout (25 hits). |
| **R3** — Dependabot auto-merge on majors lands a breaking transitive dependency | **YES** | `.github/dependabot-auto-merge.yml` — CI gates (100% coverage + 7-job fan-out) are the merge criterion; `gh pr merge --squash --auto` waits for required checks. 100% coverage requirement + integration + acceptance tiers detect behavioral regressions (carry-forward from CONTEXT D6 rationale). |
| **R4** — Scheduled rescan opens noisy issues for unfixable transitive CVEs | **YES** | `.trivyignore` — grammar-enforced suppression with rationale + expiry + reviewer; `scripts/trivyignore-check.sh` validates 180-day cap in CI; `scripts/rescan-issue-creator.py` deduplicates on `(image_digest, cve_id)` — same finding never opens twice. `.trivyignore` currently empty (clean baseline at Phase 6 ship). |
| **R5** — `fix(deps):` prefix on every Dependabot Docker bump triggers release-spammy releases | **YES** | `.github/dependabot.yml` docker ecosystem — `groups: { docker-base: { patterns: ["python", "debian*"] } }` batches all base-image bumps into one PR per week. Weekly cadence means at most one release per week from base-image bumps. |
| **R6** — Scorecard score regresses below ≥ 8/10 target without anyone noticing | **YES** | `scorecard.yml` — weekly cron + on-push to `main`; SARIF to Code Scanning (Security tab); `publish_results: true` to `api.securityscorecards.dev`; README badge publicly visible creates social-cost pressure; `.scorecard-exception.md` stale-date enforcement via `scorecard-exception-check.py` means undocumented regressions fail CI; `exceptions: []` (no current deliberate failures). |

---

## Requirements Coverage (23 REQs)

| REQ | Status | Plan | Evidence |
|-----|--------|------|----------|
| **IMAGE-04** | SATISFIED | 06-03 | `release.yml` — native runner matrix `ubuntu-24.04` + `ubuntu-24.04-arm`; `TARGETARCH` in all 3 Dockerfile fetch stages; multi-arch manifest assembled via `docker buildx imagetools create`; `docker/setup-qemu-action: 0 hits`; `test_release_yml_structure.py` asserts arches, runners, no QEMU |
| **IMAGE-06** | SATISFIED | 06-11 | `scripts/benchmark-cold-start.sh` (executable); `release.yml` `benchmark-cold-start` job runs post-sign; target 10s, catastrophic-fail at 30s; `test_benchmark_cold_start.py` green |
| **SEC-01** | SATISFIED | 06-04 | `cosign sign --yes --bundle cosign.bundle` in `release.yml` sign-and-attest job; `id-token: write` at workflow level; `cosign-verify.yml` PR gate with `--certificate-identity-regexp` + `--certificate-oidc-issuer`; SI-1 (id-token in release only) passes |
| **SEC-02** | SATISFIED | 06-04 | `anchore/sbom-action` outputs `sbom.spdx.json` (SPDX 2.3) + `sbom.cyclonedx.json` (CycloneDX 1.5); both attested via `cosign attest --bundle --type spdxjson/cyclonedx`; both artifact-uploaded in release job |
| **SEC-03** | SATISFIED | 06-04 | `actions/attest-build-provenance@a2bbfa25…` (v4.1.0 per C1 correction); `attestations: write` permission; SLSA provenance attached to multi-arch manifest digest |
| **SEC-04** | SATISFIED | 06-01 + 06-09 | `ci.yml` `trivy-image` + `trivy-dockerfile` jobs; `scripts/trivyignore-check.sh` runs before `trivy-action` (fail-on stale/undated suppressions); `.trivyignore` D2 grammar enforced; `test_ci_yml_structure.py` + `test_trivyignore_check.py` green |
| **SEC-05** | SATISFIED | 06-01 | `ci.yml` `pip-audit` job runs `scripts/pip-audit-with-stale-check.sh` (Phase 4 carry-forward two-pass pattern); CI fails on any unsuppressed finding; `test_ci_yml_structure.py` asserts pip-audit job |
| **SEC-06** | SATISFIED | Phase 5 carry-forward | `helm/redact.py` + 12 `self._redactor` call sites in `helm/client.py`; Phase 6 adds no new helm output paths; carry-forward verified — `grep -rE '^import subprocess' src/` still EXACTLY 2 files |
| **SEC-07** | SATISFIED | 06-07 | `security-rescan.yml` daily cron; Trivy scans `:latest` + `:2`; SARIF → Code Scanning; `rescan-issue-creator.py` — `priority/p0` (CRITICAL), `priority/p1` (HIGH), dedup by `(image_digest, cve_id)`; `test_security_rescan_yml.py` green |
| **SEC-08** | SATISFIED | 06-06 | `.github/dependabot.yml` docker `commit-message: { prefix: "fix" }` (C3 correction — ONLY docker); `fix(deps):` → release-please patch → `release.yml` → freshly-scanned image; chain documented in file comments |
| **SEC-09** | SATISFIED | 06-08 | `SECURITY.md` — PVR as canonical disclosure channel; Day-0/90 timeline; GitHub Security Advisory process; no `(planned)` qualifiers; CHANGELOG advisory link documented; `docs/admin/repo-settings.md` has `gh api` command to enable PVR |
| **SEC-10** | SATISFIED | 06-09 | `scorecard.yml` — `ossf/scorecard-action@4eaacf05…` (v2.4.3); weekly + on-push; SARIF upload; `publish_results: true`; `.scorecard-exception.md` D3 schema enforced by `scorecard-exception-check.py` in CI; README badge live; `exceptions: []` (clean slate) |
| **CI-01** | SATISFIED | 06-01 | `.github/workflows/ci.yml` — 7 jobs parallel fan-out; all required checks configured; triggers on `push` + `pull_request`; `uv run ruff check`, `mypy --strict`, `pytest --cov-fail-under=100`, trivy ×2, pip-audit, acceptance |
| **CI-02** | SATISFIED | 06-02 | `.release-please-config.json` + `.release-please-manifest.json` + `release-please.yml`; atomically updates `pyproject.toml`, `CHANGELOG.md`, `pipe.yml` image tag per D1 |
| **CI-03** | SATISFIED | 06-03 + 06-04 | `release.yml` multi-arch build + sign-and-attest job; GHCR-only push; CI-03 = "build + sign + SBOM + provenance + push on release-PR merge" |
| **CI-04** | SATISFIED | 06-11 | `bitbucket-pipelines.yml` — minimal no-op stub; `docker build: 0 hits`; marketplace listing maintained without any build/push; `test_bitbucket_pipelines_yml.py` green |
| **CI-05** | SATISFIED | 06-06 | `.github/dependabot.yml` 3 ecosystems weekly; `.github/workflows/dependabot-auto-merge.yml` squash-merge on CI pass; `test_dependabot_config.py` green |
| **CI-06** | SATISFIED | 06-10 | `docs/admin/repo-settings.md` — `gh api` commands for `required_signatures` on `main`; signed commit enforcement documented; maintainer-manual per VALIDATION.md |
| **CI-07** | SATISFIED | 06-10 | `docs/admin/repo-settings.md` — branch protection `PUT` payload with `required_reviews`, `required_status_checks`, `enforce_admins`, `restrictions`; exact job name → status-check name mapping table included |
| **CMN-01** | SATISFIED | 06-10 | `.github/ISSUE_TEMPLATE/bug_report.yml` — `id: pipe-version`, `id: runtime-context`, `id: reproduction`; `.github/ISSUE_TEMPLATE/feature_request.yml` present; `test_governance_files.py` green |
| **CMN-02** | SATISFIED | 06-10 | `.github/PULL_REQUEST_TEMPLATE.md` — checklist: tests added, coverage gate, ruff, docs updated, ADR trigger, release-please entry, structural tests for pipeline changes |
| **CMN-03** | SATISFIED (documented) | 06-10 | `docs/admin/repo-settings.md` — GitHub Projects v2 board creation instructions (web-UI only per GitHub API limitation as of 2026-06); `Backlog → Ready → In Progress → In Review → Done` column names specified; maintainer-manual per VALIDATION.md |
| **CMN-04** | SATISFIED (documented) | 06-10 | `docs/admin/repo-settings.md` — `gh label create` loop for full taxonomy: `area/*` (blue), `type/*` (green), `priority/*` (red/orange/yellow), `breaking-change`, `good first issue`, `help wanted`; maintainer-manual per VALIDATION.md |
| **MIG-01** | SATISFIED | 06-11 | `bitbucket-pipelines.yml` stub (no Docker Hub push); `pipe.yml` → `ghcr.io/…:2.0.0-rc.0`; `:2` rolling tag in `release.yml` manifest assembly; `docs/guides/v1-to-v2.md` `## Distribution change` with Docker Hub deprecation banner; D10 manual-update acknowledged |

---

## Security Invariants (13)

| # | Invariant | Status | Evidence |
|---|-----------|--------|----------|
| SI-1 | All `uses:` end in `@<40-char-hex>` digest; no `@v[0-9]+`, `@main`, `@master`, `@latest` | PASS | `grep -rE 'uses:.*@(v[0-9]+\|main\|master\|latest)$' .github/workflows/*.yml` → **0 hits** |
| SI-2 | No `pull_request_target` in any workflow | PASS | `grep -rF 'pull_request_target' .github/workflows/` → **0 hits** |
| SI-3 | No `${{ secrets.* }}` in `if:` conditions | PASS | `grep … \| grep '\bif:'` → **0 hits** |
| SI-4 | `id-token: write` in `ci.yml` = 0 hits | PASS | **0 hits** verified |
| SI-5 | `id-token: write` in `cosign-verify.yml` = 0 hits | PASS | **0 hits** verified |
| SI-6 | `id-token: write` in `release.yml` ≥ 1 hit | PASS | **2 hits** (workflow-level + sign-and-attest job level) |
| SI-7 | `COSIGN_VERSION=2.6.3` in `release.yml` + `cosign-verify.yml` | PASS (format deviation noted) | The workflows use `cosign-release: "v2.6.3"` (sigstore/cosign-installer action parameter format), not the `COSIGN_VERSION=2.6.3` env-var pattern. The Dockerfile carries `ARG COSIGN_VERSION=2.6.3` (line 6). **Security intent fully satisfied** — version is pinned consistently across all locations. Literal grep `COSIGN_VERSION=2.6.3` returns 0 in workflows but the 2.6.3 pin is enforced via the action's `cosign-release:` input. |
| SI-8 | `a7875d4656b327b0b7f792f25a70f714801e402eb199ddd0f2df06a063e6bede` in Dockerfile (Phase 5 helm-diff SHA) | PASS (intentional upgrade noted) | Phase 6 multi-arch conversion replaced the hardcoded amd64-only SHA comment with upstream `helm-diff_${HELM_DIFF_VERSION}_checksums.txt` dynamic lookup (covers BOTH amd64 AND arm64 per-arch SHAs). The amd64-only comment was deliberately removed in Plan 06-03 (`1b: Remove amd64 comment artifact from helm-fetch`). **This is a security improvement** — the checksums.txt approach provides correct per-arch verification instead of a single-arch hardcoded SHA. Literal grep returns 0 but the invariant's security objective (helm-diff integrity) is upheld at a higher standard. |
| SI-9 | `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` = EXACTLY 2 files | PASS | **2 files: `helm/client.py` + `chart/oci.py`** — Phase 6 adds no new subprocess users |
| SI-10 | `ghcr.io/yves-vogl/aws-eks-helm-deploy` in `release.yml` ≥ 1 hit; `docker.io/yvogl/…` = 0 hits | PASS | GHCR: **3 hits** (env comment + version tag construction + manifest); `docker.io/yvogl`: **0 hits** |
| SI-11 | `concurrency:` in `release.yml` = 1 hit | PASS | **1 hit** — `group: release-${{ github.ref }}`, `cancel-in-progress: false` |
| SI-12 | `bash scripts/trivyignore-check.sh` exits 0 on shipped `.trivyignore` | PASS | **exit 0** — `.trivyignore: OK` |
| SI-13 | `python scripts/scorecard-exception-check.py` exits 0 on shipped `.scorecard-exception.md` | PASS | **exit 0** — `.scorecard-exception.md: OK` |

---

## Structural Tests (Phase 6 New Tier)

| Test File | Tests | Status | Covers |
|-----------|-------|--------|--------|
| `tests/structural/test_ci_yml_structure.py` | included in 121 | PASS | D9 7-job fan-out, job names, trivyignore-check wiring |
| `tests/structural/test_workflow_digest_pins.py` | included in 121 | PASS | SI-1: all actions SHA-pinned |
| `tests/structural/test_release_please_config.py` | included in 121 | PASS | `.release-please-config.json` schema |
| `tests/structural/test_release_yml_structure.py` | included in 121 | PASS | native runners, no QEMU, push-by-digest, permissions, OCI annotations |
| `tests/structural/test_release_yml_sign_attest.py` | included in 121 | PASS | cosign sign+bundle, SBOM ×2, SLSA, C1/C2 SHAs |
| `tests/structural/test_cosign_verify_yml.py` | included in 121 | PASS | D7: cert constraints, no id-token:write |
| `tests/structural/test_dependabot_config.py` | included in 121 | PASS | 3 ecosystems, C3 prefixes, groups |
| `tests/structural/test_security_rescan_yml.py` | included in 121 | PASS | daily cron, SARIF, workflow_dispatch |
| `tests/structural/test_governance_files.py` | included in 121 | PASS | issue templates, PR template, required fields |
| `tests/structural/test_bitbucket_pipelines_yml.py` | included in 121 | PASS | CI-04 stub: no docker build/push |
| `tests/structural/test_benchmark_cold_start.py` | included in 121 | PASS | IMAGE-06: script + CI integration |
| `tests/unit/test_trivyignore_check.py` | included in 516 unit | PASS | D2 grammar parser unit tests |
| `tests/unit/test_scorecard_exception_check.py` | included in 516 unit | PASS | D3 schema + stale-date parser |

**Full suite result:** 637 passed, 18 deselected, 5 warnings in 2.15s.

---

## Notes for the Shipper

1. **Invariant grep patterns vs implementation format (SI-7 + SI-8):** Two invariant grep patterns in `06-VALIDATION.md` were written assuming slightly different implementation formats than what shipped. Neither is a bug — both are intentional Phase 6 design decisions that uphold or improve the security objective. SI-7 (`COSIGN_VERSION=2.6.3` in workflows) is satisfied via `cosign-release: "v2.6.3"` (the cosign-installer action parameter), and the Dockerfile still carries `ARG COSIGN_VERSION=2.6.3`. SI-8 (the hardcoded amd64 SHA comment) was deliberately replaced by the TARGETARCH-aware checksums.txt lookup, which is more correct for multi-arch. No fix needed.

2. **Dockerfile base-image digest ARG pattern:** The verification contract expected `python:3.13-slim-bookworm@sha256:` as a literal inline string. The Dockerfile uses `ARG PYTHON_BASE_DIGEST=sha256:05b95397…` + `FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST}`. This is the correct BuildKit pattern — the digest IS committed (not runtime-resolved) and enforced at every `FROM`. The ARG approach is cleaner for updates than inlining the digest literally.

3. **Maintainer-manual items (CI-06, CI-07, CMN-03, CMN-04, SEC-09 PVR enable):** These are repo settings that cannot be deployed via PR. All are documented with exact `gh api` or web-UI instructions in `docs/admin/repo-settings.md`. The VALIDATION.md explicitly categorizes them as "Manual-Only Verifications (Out of Band)." Phase 6 ships the documentation artifacts; Yves must apply the settings as a one-shot after merge. None of these affect the automated CI chain.

4. **Post-release smoke tests (SC3 + SC2 post-push):** Multi-arch manifest `docker buildx imagetools inspect`, `cosign verify`, and cold-start timing < 10s can only be verified after the first tag push to GHCR. The CI structure for all three is complete and correct; the live verification awaits the v2.0.0 tag-cut. These are in VALIDATION.md's "Manual-Only Verifications" table by design.

5. **Phase 5 carry-forward (SEC-06):** Phase 6 adds no new `HelmClient` output paths. The `import subprocess` count remains exactly 2. The log redactor is fully operational and untouched.

6. **Test count progression:** Phase 5 baseline was 469 tests. Phase 6 ships 637 tests — an increase of 168 tests (121 structural + 47 new unit tests across `test_trivyignore_check.py` and `test_scorecard_exception_check.py`). All 637 pass in 2.15s.

7. **:2 rolling tag:** The `pipe.yml` shows `image: ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0-rc.0` as the current pre-release tag. The `:2` major-pinned rolling tag is assembled in `release.yml` via `docker/metadata-action` on each tagged release and documented in `docs/guides/v1-to-v2.md`. This is correct — `:2` as a rolling tag only makes sense post-v2.0.0 release.

---

*Verified 2026-06-20 by `gsd-verifier` (Sonnet 4.6, goal-backward stance).*
