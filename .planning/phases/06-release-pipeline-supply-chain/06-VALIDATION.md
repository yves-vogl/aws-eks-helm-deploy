---
phase: 6
slug: release-pipeline-supply-chain
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 6 has NO Python source changes — "tests" are structural assertions on YAML/JSON/script files plus the workflow runs themselves. Derived from 06-RESEARCH.md "Validation Architecture" + "Security Domain" sections.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 (already configured) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/structural -q --no-cov` |
| **Full suite command** | `uv run pytest tests/ -q --no-cov` |
| **Unit tier (Python-source coverage check, MUST stay at 100%)** | `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` |
| **Workflow smoke check** | Workflow run passes on the smoke PR (the Phase 6 PR itself) |
| **Estimated runtime** | ~5 s structural, ~60 s full + coverage |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/structural -q --no-cov` (structural assertions, < 5s)
- **After every wave merge:** `uv run pytest tests/ -q --no-cov` (full suite)
- **Before `/gsd-verify-work`:** Full suite green AND `uv run mypy --strict src/aws_eks_helm_deploy` clean AND `uv run ruff check src/ tests/ scripts/` clean
- **Phase gate:** Phase 6 PR's CI run passes on its own first invocation (the new workflows must be green when run against the PR that introduces them)
- **Max feedback latency:** ~10 s (structural test tier is fast)

---

## Per-Task Verification Map

*Populated by planner using suggested skeleton. Workflow YAML modifications use grep-based acceptance_criteria; Python helpers (`scripts/_trivyignore_parser.py`, `scripts/scorecard-exception-check.py`) use pytest assertions.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|----------|-----------|-------------------|-------------|--------|
| 06-01-* | 01 | 1 | CI-01 (D9) | T-06-W14 | `ci.yml` has 7 named jobs with correct fan-out | structural | `uv run pytest tests/structural/test_ci_yml_structure.py -x` | ❌ W0 | ⬜ pending |
| 06-01-* | 01 | 1 | CI-01 + SEC-04 | T-06-W10 | All workflows pin actions to 40-char SHA digest | structural | `uv run pytest tests/structural/test_workflow_digest_pins.py -x` | ❌ W0 | ⬜ pending |
| 06-02-* | 02 | 1 | CI-02 | — | `.release-please-config.json` valid + required fields | structural | `uv run pytest tests/structural/test_release_please_config.py -x` | ❌ W0 | ⬜ pending |
| 06-03-* | 03 | 2 | IMAGE-04 | T-06-V14 (no QEMU) | release.yml has 2-arch matrix on native runners | structural | `uv run pytest tests/structural/test_release_yml_matrix.py -x` | ❌ W0 | ⬜ pending |
| 06-03-* | 03 | 2 | IMAGE-04 | — | Multi-arch manifest has both arches (post-release smoke) | manual | `docker buildx imagetools inspect ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` | manual | ⬜ pending |
| 06-04-* | 04 | 3 | SEC-01 | T-06-V6 | release.yml has cosign sign step with `id-token: write` | structural | `uv run pytest tests/structural/test_release_yml_sign.py -x` | ❌ W0 | ⬜ pending |
| 06-04-* | 04 | 3 | SEC-01 | T-06-V6 | Released image verifies (post-release smoke) | manual | `cosign verify ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` | manual | ⬜ pending |
| 06-04-* | 04 | 3 | SEC-02 | — | release.yml attaches sbom.spdx.json + sbom.cyclonedx.json via cosign attest | structural | `grep -F 'sbom.spdx.json' .github/workflows/release.yml`, `grep -F 'sbom.cyclonedx.json' .github/workflows/release.yml` | ❌ W0 | ⬜ pending |
| 06-04-* | 04 | 3 | SEC-03 | — | release.yml uses actions/attest-build-provenance@v4.1.0 SHA | structural | `grep -F 'attest-build-provenance@a2bbfa2' .github/workflows/release.yml` (the C1-correct SHA) | ❌ W0 | ⬜ pending |
| 06-05-* | 05 | 4 | SEC-01 (verify path) | — | cosign-verify.yml has correct cert constraints + NO `id-token: write` | structural | `uv run pytest tests/structural/test_cosign_verify_yml.py -x` | ❌ W0 | ⬜ pending |
| 06-06-* | 06 | 5 | CI-05 | — | dependabot.yml has 3 ecosystems + groups + correct prefixes (pip=chore, docker=fix per C3) | structural | `uv run pytest tests/structural/test_dependabot_yml.py -x` | ❌ W0 | ⬜ pending |
| 06-06-* | 06 | 5 | SEC-08 | — | dependabot.yml docker ecosystem uses `commit-message.prefix: fix` | structural | `uv run pytest tests/structural/test_dependabot_yml.py::test_docker_prefix_is_fix -x` | ❌ W0 | ⬜ pending |
| 06-07-* | 07 | 5 | SEC-07 | — | security-rescan.yml has daily cron + Trivy + auto-issue dedup | structural | `uv run pytest tests/structural/test_security_rescan_yml.py -x` | ❌ W0 | ⬜ pending |
| 06-08-* | 08 | 5 | SEC-09 | — | SECURITY.md has GH PVR section + disclosure flow | grep | `grep -F 'Private Vulnerability Reporting' SECURITY.md` ≥ 1 | (extend) | ⬜ pending |
| 06-09-* | 09 | 5 | SEC-10 | — | scorecard.yml + README badge + .scorecard-exception.md grammar enforced | unit + structural | `uv run pytest tests/unit/test_scorecard_exception_check.py tests/structural/test_scorecard_yml.py -x` | ❌ W0 | ⬜ pending |
| 06-09-* | 09 | 5 | SEC-04 (D2 grammar) | — | `.trivyignore` grammar enforced; stale entries fail CI | unit | `uv run pytest tests/unit/test_trivyignore_check.py -x` | ❌ W0 | ⬜ pending |
| 06-09-* | 09 | 5 | SEC-04 (CI wiring) | — | ci.yml's trivy-image job invokes scripts/trivyignore-check.sh before trivy-action | structural | `grep -F 'trivyignore-check.sh' .github/workflows/ci.yml` ≥ 1 | (extend ci.yml) | ⬜ pending |
| 06-10-* | 10 | 5 | CI-06 + CI-07 + CMN-01..04 | — | docs/admin/repo-settings.md + 2 issue templates + PR template ship | grep | files exist + `grep -F` for required strings | ❌ W0 | ⬜ pending |
| 06-11-* | 11 | 6 | CI-04 | — | bitbucket-pipelines.yml is minimal stub (no docker push) | structural | `uv run pytest tests/structural/test_bitbucket_pipelines_yml.py -x` | ❌ W0 | ⬜ pending |
| 06-11-* | 11 | 6 | MIG-01 | — | docs/guides/v1-to-v2.md has "Distribution change" section | grep | `grep -F 'Distribution change' docs/guides/v1-to-v2.md` ≥ 1 | (extend) | ⬜ pending |
| 06-11-* | 11 | 6 | IMAGE-06 | — | scripts/benchmark-cold-start.sh + README badge + release.yml benchmark job | structural + manual | tests/structural/test_benchmark_cold_start.py + manual badge inspection | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Phase 6 introduces a new test tier `tests/structural/` for YAML/JSON workflow assertions. Wave 0 files to create:

- [ ] `tests/structural/__init__.py` (empty marker)
- [ ] `tests/structural/test_ci_yml_structure.py` — ci.yml job names + fan-out
- [ ] `tests/structural/test_workflow_digest_pins.py` — all `uses:` strings end in `@<40-char-hex>`
- [ ] `tests/structural/test_release_please_config.py` — `.release-please-config.json` schema
- [ ] `tests/structural/test_release_yml_matrix.py` — release.yml has 2-arch matrix on native runners
- [ ] `tests/structural/test_release_yml_sign.py` — release.yml has cosign sign + SBOM + SLSA steps
- [ ] `tests/structural/test_cosign_verify_yml.py` — cosign-verify.yml correctness
- [ ] `tests/structural/test_dependabot_yml.py` — dependabot.yml ecosystem + group + prefix correctness
- [ ] `tests/structural/test_security_rescan_yml.py` — security-rescan.yml shape
- [ ] `tests/structural/test_scorecard_yml.py` — scorecard.yml extension
- [ ] `tests/structural/test_bitbucket_pipelines_yml.py` — Bitbucket stub minimal
- [ ] `tests/structural/test_benchmark_cold_start.py` — benchmark script + CI integration
- [ ] `tests/unit/test_trivyignore_check.py` — grammar parser unit tests (D2)
- [ ] `tests/unit/test_scorecard_exception_check.py` — schema + stale-date parser unit tests (D3)
- [ ] `scripts/_trivyignore_parser.py` — Python module called by trivyignore-check.sh
- [ ] `scripts/scorecard-exception-check.py` — Python module for D3
- [ ] `pyproject.toml` — add `[tool.coverage.run] omit` for the new `scripts/` files (they're CLI-glue, not library code)

---

## Manual-Only Verifications (Out of Band)

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-arch manifest published | IMAGE-04 | Requires actual release | `docker buildx imagetools inspect ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` after first release |
| Cosign signature verifies | SEC-01 | Requires released image | `cosign verify ghcr.io/yves-vogl/aws-eks-helm-deploy:latest --certificate-identity-regexp <pattern> --certificate-oidc-issuer https://token.actions.githubusercontent.com` |
| Cold-start under 10 s | IMAGE-06 | Real runtime measurement | Run `scripts/benchmark-cold-start.sh` on a GitHub-hosted runner; README badge auto-updates from CI artifact |
| Branch protection rules active | CI-06 | Maintainer-only repo setting | Yves runs `gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection -X PUT --input <payload.json>` |
| GPG-signed commits enforced | CI-07 | Maintainer-only repo setting | Web UI: Settings → Branches → main → Require signed commits |
| Private Vulnerability Reporting on | SEC-09 | Maintainer-only repo setting | `gh api repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting -X PUT` (204 = success) |
| GitHub Project board created | CMN-03 | Maintainer-only web UI | Yves creates v2.0.0 project, columns: Backlog → Ready → In Progress → In Review → Done |
| Label taxonomy created | CMN-04 | `gh label create` bash loop | Plan 06-10 ships the loop in docs/admin/repo-settings.md |
| Docker Hub README deprecation banner | MIG-01 | Docker Hub web UI | Yves pastes the banner from docs/guides/v1-to-v2.md "Distribution change" section into Docker Hub's repo README |
| Scorecard score ≥ 8/10 | SEC-10 | Public Scorecard API runs post-release | `curl https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy` shows score |

Plan 06-10 ships `docs/admin/repo-settings.md` with EXACT `gh` CLI commands for each maintainer-manual step.

---

## Security Domain (from 06-RESEARCH.md)

### Applicable ASVS Categories (ASVS Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | `permissions:` blocks at workflow level (least-privilege); `id-token: write` ONLY in release-triggered jobs |
| V5 Input Validation | yes | `.trivyignore` grammar check + `.scorecard-exception.md` schema enforcement scripts |
| V6 Cryptography | yes | Cosign keyless (Ed25519/ECDSA P-384 via Fulcio) — never hand-roll |
| V9 Communications | yes | All GitHub Action downloads over HTTPS; cosign certificate chain via Fulcio/Rekor |
| V10 Malicious Code | yes | All actions pinned to 40-char SHA digest; Dependabot keeps them current |
| V14 Configuration | yes | Secrets only via `secrets.*`; no `${{ secrets.* }}` in `if:` conditions |

### Known Threat Patterns

| Threat ID | Pattern | STRIDE | Standard Mitigation |
|-----------|---------|--------|---------------------|
| T-06-V10 | Compromised action via mutable tag | Tampering | All actions pinned to commit SHA digest; `test_workflow_digest_pins.py` enforces in CI |
| T-06-V4-PT | Malicious `pull_request_target` elevation | Elevation of Privilege | Never use `pull_request_target` anywhere; use `pull_request` only; structural test asserts |
| T-06-V4-OIDC | OIDC token exfiltration from PR | Information Disclosure | `id-token: write` ONLY in release-triggered jobs (release.yml + tag-triggered); NEVER in cosign-verify.yml or ci.yml |
| T-06-V5 | Stale CVE suppressions masking real vulnerabilities | Tampering | `.trivyignore` expiry enforcement via scripts/trivyignore-check.sh (180-day cap); `.scorecard-exception.md` review_date enforcement |
| T-06-V14-SECRETS | Secrets-in-if condition antipattern | Information Disclosure | Structural test: `grep -E '\\${{ ?secrets\\.' .github/workflows/*.yml | grep -E '\\bif:' ` returns 0 hits |
| T-06-V6 | Cosign keyless three-way coupling failure (Pitfall #4) | Repudiation / DoS | Risk mitigation per D1 (release-PR maintainer review) + D7 (verify gate per PR); workflow-level `id-token: write` + always `--bundle` |
| T-06-V14-QEMU | QEMU silently produces broken arm64 (Pitfall #5) | Tampering | Native runners only (ubuntu-24.04-arm); post-build `docker buildx imagetools inspect` asserts real arches; structural test asserts no QEMU action in release.yml |

### Security Invariants (plan-checker MUST enforce)

1. `grep -rE '@(v[0-9]+|main|master|latest)$' .github/workflows/*.yml` returns 0 hits (every `uses:` ends in `@<40-char-hex>` digest).
2. `grep -rF 'pull_request_target' .github/workflows/` returns 0 hits.
3. `grep -E '\\$\\{\\{ ?secrets\\.' .github/workflows/*.yml | grep -E '\\bif:'` returns 0 hits.
4. `grep -F 'id-token: write' .github/workflows/ci.yml` returns 0 hits (PR-triggered, must not have OIDC write).
5. `grep -F 'id-token: write' .github/workflows/cosign-verify.yml` returns 0 hits (verify is read-only).
6. `grep -F 'id-token: write' .github/workflows/release.yml` returns ≥ 1 hit (signing job needs it).
7. `grep -F 'COSIGN_VERSION=2.6.3' .github/workflows/release.yml .github/workflows/cosign-verify.yml` returns ≥ 1 hit per file (Phase 4 D8 carry-forward).
8. `grep -F 'a7875d4656b327b0b7f792f25a70f714801e402eb199ddd0f2df06a063e6bede' Dockerfile` returns 1 hit (Phase 5 D2 carry-forward — helm-diff SHA256).
9. `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` returns EXACTLY 2 files (Phase 4 D5 / Phase 5 D6 carry-forward; Phase 6 must not regress).
10. `grep -F 'ghcr.io/yves-vogl/aws-eks-helm-deploy' .github/workflows/release.yml` returns ≥ 1 hit; `grep -F 'docker.io/yvogl/aws-eks-helm-deploy' .github/workflows/release.yml` returns 0 hits (Docker Hub frozen; no v2 push there).
11. `grep -F 'concurrency:' .github/workflows/release.yml` returns 1 hit (prevents overlapping releases).
12. `bash scripts/trivyignore-check.sh` exits 0 on the shipped `.trivyignore` (no stale or future-undated entries).
13. `python scripts/scorecard-exception-check.py` exits 0 on shipped `.scorecard-exception.md` (all review_dates within 180-day cap).

---

## Verifier Bar (mirrors Phase 5 VERIFICATION shape)

Phase 6 verifier MUST assert:

- 10 Success Criteria observable in shipped code (per ROADMAP Phase 6 entry SC1-SC10)
- 23 REQs covered by source/workflow + green tests (IMAGE-04/06, SEC-01..05, SEC-07..10, CI-01..07, CMN-01..04, MIG-01)
- 10 locked decisions D1-D10 honoured (with 4 research-driven corrections C1-C4 applied)
- 6 ROADMAP risks R1-R6 mitigated
- 13 plan-checker security invariants enforced (grep gates above)
- Multi-arch manifest publishes both real arches (post-release smoke; OR sentinel structural test on workflow YAML pre-release)
- `tests/structural/` and new `tests/unit/test_trivyignore_check.py` + `test_scorecard_exception_check.py` all green
- Phase 6 PR's own CI run passes (the new workflows must work on the PR that introduces them)

---

*Skeleton authored 2026-06-20 by Claude autonomously per 48h mandate. Per-task rows post-execution-update.*
