---
phase: 06-release-pipeline-supply-chain
plan: 11
subsystem: release-pipeline
tags: [bitbucket, benchmark, migration-guide, readme-badges, ci-04, image-06, mig-01]
dependency_graph:
  requires: [06-04, 06-09]
  provides: [bitbucket-thin-stub, benchmark-cold-start-script, mig-01-docs, readme-badges, benchmark-ci-job]
  affects: [bitbucket-pipelines.yml, scripts/benchmark-cold-start.sh, docs/guides/v1-to-v2.md, README.md, .github/workflows/release.yml]
tech_stack:
  added: []
  patterns: [bash-benchmark-script, structural-tests-pytest, yaml-workflow-append]
key_files:
  created:
    - scripts/benchmark-cold-start.sh
    - tests/structural/test_benchmark_cold_start.py
  modified:
    - bitbucket-pipelines.yml
    - docs/guides/v1-to-v2.md
    - README.md
    - .github/workflows/release.yml
decisions:
  - "A6 honoured: cold-start benchmark 10s target is documented, not a hard CI gate; only >30s catastrophic fails CI"
  - "D10 Docker Hub README content sealed in docs/guides/v1-to-v2.md Distribution-change section"
  - "benchmark-cold-start job permissions: contents: read only — no id-token:write or attestations:write"
  - "README badge row: 7 badges (License, Release, GHCR, CI, Coverage, Cosign, Scorecard) + cold-start link below"
  - "Bitbucket thin stub: replaced v1.x build+push pipeline with no-op that exits 0 (CI-04)"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-20T21:03:00Z"
  tasks: 5
  files_modified: 6
---

# Phase 06 Plan 11: Bitbucket Thin Stub + Cold-Start Benchmark + Distribution Docs + README Badges Summary

**One-liner:** Bitbucket thin Marketplace stub (CI-04), cold-start benchmark script + CI job (IMAGE-06), v1→v2 Distribution-change addendum with Docker Hub README verbatim content (MIG-01), 7-badge README row finalized.

---

## What Was Built

### Task 1: bitbucket-pipelines.yml — Thin Marketplace-only stub (CI-04) [commit: 0640b07]

Replaced the entire v1.x build+push pipeline (which used `bitbucket-pipe-release` with Docker Hub credentials) with a minimal no-op stub. The stub:
- Uses `python:3.13-slim-bookworm` as the image (satisfies Marketplace validator)
- Has a single `default:` pipeline with one step that echoes the GHCR image reference and exits 0
- Contains zero Docker Hub credential references (`DOCKERHUB_USERNAME`, `DOCKERHUB_PASSWORD`)
- Contains zero `docker build` or `docker push` commands
- Documents why the file exists (Marketplace validation) and where image builds happen (GitHub Actions)

**Threat T-06-11-01 mitigated:** Long-lived Docker Hub credentials removed from CI; no longer a secret attack surface.

### Task 2: scripts/benchmark-cold-start.sh — Cold-start benchmark (IMAGE-06) [commit: e203e9d]

New executable bash script (`chmod 755`) that:
- Pre-pulls the target image to exclude network time (IMAGE-06 spec)
- Runs `docker run --rm <image> --help` N times (default N=5)
- Computes median via `sort -n` + middle index
- Emits JSON output to a file (default `/tmp/cold-start-results.json`) with fields: `image`, `runs`, `times_ms`, `median_ms`, `target_ms`, `catastrophic_ms`, `pass`, `catastrophic`
- Warns at >10s (IMAGE-06 documented target) but does NOT fail CI
- Fails CI only at >30s catastrophic threshold (RESEARCH A6 — prevents runner jitter from flapping releases)
- Uses bash strict mode (`set -euo pipefail`); syntax-clean
- Already exempt from 100% coverage rule via `scripts/*` in `pyproject.toml` `[tool.coverage.run] omit`

### Task 3: docs/guides/v1-to-v2.md — Distribution-change addendum (MIG-01 / D10) [commit: 761a980]

Appended a new "Distribution change (Phase 6 / MIG-01)" section at the end of the Phase 5 draft. All existing Phase 5 content preserved. New section includes:
- v1.x consumers: Docker Hub `yvogl/aws-eks-helm-deploy` frozen at v1.3.0 forever
- v2.x consumers: GHCR pinning options (`:2.0.0` patch, `:2` rolling major, `:latest` not recommended)
- v1→v2 migration example: single-line image reference change
- Why GHCR-only: native OIDC, single trust domain (GitHub → Fulcio → Rekor → GHCR), multi-arch native runners
- Cosign keyless verify + SBOM verify-attestation + SLSA `gh attestation verify` commands
- Verbatim Docker Hub README content (D10) for maintainer one-shot paste per Plan 06-10 §7

### Task 4a: README.md — Completed badge row (SC1 / SC5) [commit: 896be39]

Replaced the previous badge row with the completed 7-badge layout:
1. License → `/github/license/yves-vogl/aws-eks-helm-deploy`
2. Release → `/github/v/release/yves-vogl/aws-eks-helm-deploy`
3. GHCR Image → static badge linking to GHCR packages page
4. CI → `ci.yml` workflow badge
5. Coverage → static `100%` badge (brightgreen)
6. Cosign verified → static badge linking to `cosign-verify.yml`
7. OpenSSF Scorecard → `api.securityscorecards.dev` live badge (Plan 06-09, preserved)

Below the badge row: a prose link to the latest `release.yml` workflow artifact for cold-start benchmark results (IMAGE-06 target: <10s; A6 note).

Note: a live cold-start badge URL is not added because it would require a hosted gist or shields.io endpoint that is not maintained in this phase. The link to the workflow artifact is the documented approach.

### Task 4b: .github/workflows/release.yml — benchmark-cold-start job appended [commit: 896be39]

Appended a new `benchmark-cold-start` job after `sign-and-attest`:
- `needs: [sign-and-attest]` — runs after the image is published to GHCR
- `runs-on: ubuntu-24.04`; `timeout-minutes: 10`
- `permissions: { contents: read }` — no `id-token: write`, no `attestations: write`
- Steps: Checkout → Run benchmark (invokes `scripts/benchmark-cold-start.sh` with the release tag) → Upload `cold-start-results.json` artifact (retention 90 days, `if: always()`)
- `actions/upload-artifact` pinned to `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1 per RESEARCH C4)

### Task 5: tests/structural/test_benchmark_cold_start.py — 14 structural tests [commit: e88bbd6]

New pytest structural test file (14 tests, all passing):
- `scripts/benchmark-cold-start.sh` exists and is executable (`stat.S_IXUSR`)
- Script encodes `TARGET_MS=10000` and `CATASTROPHIC_MS=30000`
- Script calls `docker pull` (IMAGE-06 pre-pull spec)
- `release.yml` has `benchmark-cold-start` job
- Job has `needs: [sign-and-attest]`
- Job permissions are minimal (`contents: read` only; no `id-token`, no `attestations`)
- Job invokes the script; job has upload-artifact step
- `bitbucket-pipelines.yml`: no `docker build`, no `docker push`, no `DOCKERHUB_USERNAME`/`DOCKERHUB_PASSWORD`/`DOCKERHUB_TOKEN`
- `bitbucket-pipelines.yml` is valid YAML with `pipelines:` key

---

## Verification Results

| Gate | Result |
|------|--------|
| `pytest tests/structural -q --no-cov` | 121 passed (107 prior + 14 new) |
| `pytest tests/unit -q --no-cov` | 516 passed |
| `pytest tests/unit --cov --cov-fail-under=100` | 100% coverage maintained |
| `mypy --strict src/` | 0 errors |
| `ruff check src/ tests/ scripts/` | All checks passed |
| `test -x scripts/benchmark-cold-start.sh` | PASS (executable bit set) |
| `grep -F 'docker build' bitbucket-pipelines.yml` | 0 hits |
| `grep -F 'docker push' bitbucket-pipelines.yml` | 0 hits |
| `grep -F 'DOCKERHUB' bitbucket-pipelines.yml` | 0 hits |
| `grep -F 'Distribution change' docs/guides/v1-to-v2.md` | FOUND |
| `grep -F 'ghcr.io/yves-vogl/aws-eks-helm-deploy' docs/guides/v1-to-v2.md` | FOUND |
| `grep -F 'benchmark-cold-start' .github/workflows/release.yml` | FOUND |
| `grep -F 'id-token: write' .github/workflows/release.yml` | FOUND (sign-and-attest job only; benchmark job clean) |
| YAML validity: bitbucket-pipelines.yml | PASS |
| YAML validity: release.yml | PASS |
| bash -n scripts/benchmark-cold-start.sh | PASS |
| pre-commit | PASS |

---

## Deviations from Plan

### Minor Auto-fix: bitbucket-pipelines.yml comment wording (Rule 1)

The plan's stub comment text included the literal string `DOCKERHUB_USERNAME/PASSWORD` (to document what was removed), but the quality gate requires `grep -F 'DOCKERHUB' bitbucket-pipelines.yml` to return 0 hits. The comment was reworded to say "Docker Hub credentials" instead, preserving the documentation intent without violating the quality gate.

Same for `bitbucket-pipe-release` — the comment was reworded to "Bitbucket pipe release helper" to satisfy `! grep -F 'bitbucket-pipe-release' bitbucket-pipelines.yml`.

### Minor: macOS chmod requires Python fallback (Rule 3)

On macOS, `git update-index --chmod=+x` sets the executable bit in the git index/tree but does NOT update the filesystem inode mode. The quality gate `test -x scripts/benchmark-cold-start.sh` checks the filesystem. Used `python3 -c "import os; os.chmod('scripts/benchmark-cold-start.sh', 0o755)"` to set the actual filesystem bit. The git index correctly shows `100755`.

### Not added: live cold-start badge in README

The plan's Task 4 says "Do NOT add a cold-start badge directly to README.md — the badge would require a hosted gist or shields.io endpoint that we don't maintain." This was followed exactly. A prose link to the workflow artifact was added below the badge row instead.

---

## A6 Resolution

The cold-start benchmark (IMAGE-06) uses a two-tier threshold:
- **10s (documented target):** Emits a WARNING to stderr but does NOT fail CI. Runner jitter at this boundary could flap releases on a legitimate <10s image.
- **30s (catastrophic):** Fails CI with exit code 1. Only a true regression (e.g., broken entry-point, massive dependency bloat) would trigger this.

This is explicit per RESEARCH A6: "Recommendation: emit the result as a workflow artifact + print to summary. Only gate if > 30s (catastrophic regression). At < 10s threshold, use a warning annotation."

---

## D10 Docker Hub README Content Sealed

The verbatim Docker Hub README content from CONTEXT D10 is now sealed in `docs/guides/v1-to-v2.md` under "Docker Hub README update (maintainer one-shot)". Plan 06-10 maintainer runbook §7 references this exact section. Yves pastes the fenced code block content into the Docker Hub web UI at https://hub.docker.com/repository/docker/yvogl/aws-eks-helm-deploy.

---

## Known Stubs

None. All deliverables are fully wired:
- Benchmark script invoked from release.yml with real image tag (`${{ github.ref_name }}`)
- Upload-artifact step uploads real JSON output
- Badge row links to real GitHub services
- v1-to-v2.md section contains verbatim D10 content (not placeholder)

---

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what was planned (removal of Docker Hub credentials = threat surface reduction).

---

## Phase 6 Completion

After this plan (06-11), all 11 plans in Phase 6 are complete:

| Plan | Requirement | Status |
|------|------------|--------|
| 06-01 | CI fan-out (D9) | Done |
| 06-02 | release-please bootstrap | Done |
| 06-03 | Multi-arch build (IMAGE-04) | Done |
| 06-04 | Sign + SBOM + SLSA (SEC-01/02/03) | Done |
| 06-05 | Cosign verify gate (D7) | Done |
| 06-06 | Dependabot + auto-merge (SEC-08/D6) | Done |
| 06-07 | Security rescan + pip-audit (SEC-04/05/07) | Done |
| 06-08 | Governance files (CMN-01/02/03/04) | Done |
| 06-09 | OpenSSF Scorecard (SEC-10/D3) | Done |
| 06-10 | Admin runbook (branch protection docs) | Done |
| **06-11** | **Bitbucket stub + benchmark + MIG-01 + badges** | **Done** |

## Self-Check

### Files exist:

- `bitbucket-pipelines.yml` — FOUND
- `scripts/benchmark-cold-start.sh` — FOUND, executable
- `docs/guides/v1-to-v2.md` — FOUND, Distribution-change section appended
- `README.md` — FOUND, 7-badge row + cold-start link
- `.github/workflows/release.yml` — FOUND, benchmark-cold-start job appended
- `tests/structural/test_benchmark_cold_start.py` — FOUND, 14 tests

### Commits exist:

- `0640b07` feat(06-11): replace bitbucket-pipelines.yml with thin Marketplace-only stub
- `e203e9d` feat(06-11): add scripts/benchmark-cold-start.sh cold-start benchmark
- `761a980` docs(06-11): add Phase 6 Distribution-change addendum to v1-to-v2.md
- `896be39` feat(06-11): complete README badge row + append benchmark-cold-start job to release.yml
- `e88bbd6` test(06-11): add structural tests for benchmark-cold-start and bitbucket stub

## Self-Check: PASSED
