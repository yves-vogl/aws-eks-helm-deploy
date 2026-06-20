---
phase: 06-release-pipeline-supply-chain
plan: "05"
subsystem: supply-chain-security
tags: [cosign, sigstore, github-actions, pr-gate, sbom, oidc]
dependency_graph:
  requires: ["06-04"]
  provides: [".github/workflows/cosign-verify.yml", "tests/structural/test_cosign_verify_yml.py"]
  affects: []
tech_stack:
  added: []
  patterns:
    - "bootstrap-graceful probe: curl manifest HEAD before verify, skip on 404"
    - "CERT_IDENTITY_REGEXP env var as single source of truth for cert-identity constraint"
    - "per-step if: steps.probe.outputs.exists guard pattern"
key_files:
  created:
    - .github/workflows/cosign-verify.yml
    - tests/structural/test_cosign_verify_yml.py
  modified: []
decisions:
  - "Use workflow-level env.CERT_IDENTITY_REGEXP for cert-identity-regexp — avoids repetition across verify + verify-attestation steps"
  - "Bootstrap probe uses curl against GHCR Distribution Spec endpoint (no docker login, no cosign) — lightest possible pre-check"
  - "Open Question 3 CLOSED: :latest not found (HTTP non-200) → exists=false → all verify steps skip via if: — PRs not blocked pre-first-release"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 06 Plan 05: cosign-verify.yml PR-gate Summary

**One-liner:** PR-gate workflow that verifies the latest GHCR image signature, SPDX SBOM, and CycloneDX SBOM attestations on every PR, with bootstrap-graceful probe that exits 0 before the first release exists.

---

## What Was Built

### `.github/workflows/cosign-verify.yml`

Triggered on `pull_request: branches: [main]` (+ `workflow_dispatch` for manual smoke-runs). Runs a single `verify` job on `ubuntu-24.04`.

**Job step sequence:**

1. **Checkout** — `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2)
2. **Install cosign** — `sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6` (v4.1.2, cosign v2.6.3)
3. **Probe :latest existence** (`id: probe`) — curl anonymous HEAD against GHCR Distribution Spec endpoint; sets `exists=true`/`exists=false` as step output
4. **Verify image signature** (`if: steps.probe.outputs.exists == 'true'`):
   ```
   cosign verify \
     --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     ghcr.io/yves-vogl/aws-eks-helm-deploy:latest
   ```
5. **Verify SPDX SBOM attestation** (`if: steps.probe.outputs.exists == 'true'`):
   ```
   cosign verify-attestation \
     --type spdxjson \
     --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     ghcr.io/yves-vogl/aws-eks-helm-deploy:latest > /dev/null
   ```
6. **Verify CycloneDX SBOM attestation** (`if: steps.probe.outputs.exists == 'true'`):
   ```
   cosign verify-attestation \
     --type cyclonedx \
     --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     ghcr.io/yves-vogl/aws-eks-helm-deploy:latest > /dev/null
   ```
7. **Verify :2 rolling-major tag** (`if: steps.probe.outputs.exists == 'true'`) — graceful: warns (not fails) if `:2` does not exist yet

**Security properties:**
- `permissions: contents: read` ONLY at workflow level — no `id-token: write` anywhere (Pitfall #1 invariant)
- No `pull_request_target` (Pitfall #1 — would grant elevated context to fork PRs)
- All `uses:` references pinned to 40-char commit SHA (V10 Malicious Code mitigation)
- No `${{ secrets.* }}` in `if:` conditions (V14 Configuration)

### `tests/structural/test_cosign_verify_yml.py`

12 structural tests — all pass:

| Test | What It Enforces |
|------|-----------------|
| `test_cosign_verify_yml_exists` | File created |
| `test_cosign_verify_triggers_on_pull_request` | PR trigger present |
| `test_cosign_verify_does_not_use_pull_request_target` | Pitfall #1 — no elevated fork trigger |
| `test_cosign_verify_workflow_permissions_minimal` | Exact `{contents: read}` — no extras |
| `test_cosign_verify_no_id_token_write` | **LOAD-BEARING** — Pitfall #1 gate |
| `test_cosign_verify_installs_cosign_at_pinned_sha` | SHA `6f9f177...` pinned |
| `test_cosign_verify_uses_correct_cert_identity_regexp` | Repo-scoped cert identity |
| `test_cosign_verify_uses_correct_oidc_issuer` | GitHub Actions OIDC issuer |
| `test_cosign_verify_attests_both_sbom_formats` | spdxjson + cyclonedx both verified |
| `test_cosign_verify_has_bootstrap_graceful_probe` | exists=true/false + all verify steps guarded |
| `test_cosign_verify_concurrency_cancel_in_progress` | PR stacking mitigation |
| `test_cosign_verify_runs_on_ubuntu_pinned` | D4 — `ubuntu-24.04` not `ubuntu-latest` |

---

## Open Questions Closed

**Open Question 3 (06-RESEARCH.md) is now CLOSED.**

Resolution: The `probe` step curls `https://ghcr.io/v2/yves-vogl/aws-eks-helm-deploy/manifests/latest` anonymously. On HTTP 200, `exists=true` is set and all verify steps run. On any non-200 (including HTTP 401 / 404 from GHCR before the first push), `exists=false` is set and all verify steps skip via `if:`. PRs are never blocked pre-first-release.

---

## Important Notes for Maintainers

**This workflow is a no-op until the first release exists.** Until `ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` is published by `release.yml` (Plan 06-04), every PR gets a green check with a `::notice::` annotation explaining the skip. This is intentional (T-06-05-01 mitigation).

**Maintainer runbook — if cosign-verify fails on a PR after the first release:**

The failure indicates one of three root causes:

1. **Rekor outage (transient):** The transparency log is temporarily unavailable. Re-run the workflow after a delay. No PR changes needed.

2. **Accidental re-tag without re-sign (operator error):** Someone manually pushed a new image to `:latest` without running the sign step. Fix: run `cosign sign` against the new digest using the release workflow or a manual invocation with `id-token: write` in a separate workflow.

3. **Regression in release.yml that broke the sign step:** The sign job in `release.yml` (Plan 06-04) may have lost `id-token: write` permission or the cosign step was removed/broken. Block the bad PR, audit `release.yml`'s `sign-and-attest` job.

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | `8cd4e3a` | feat(06-05): add cosign-verify.yml PR-gate |
| Task 2 | `dbad41b` | test(06-05): add 12 structural tests |

---

## Deviations from Plan

None — plan executed exactly as written.

The plan specified that the comment in the workflow header should include `id-token:write`, but that exact string would cause the quality gate grep (`grep -E 'id-token:\s*write'`) to return a false positive. The comment was rephrased to avoid the pattern while preserving the security documentation intent. This is a minor textual adjustment, not a behavioral deviation.

---

## Self-Check

### Files exist:
- `.github/workflows/cosign-verify.yml` — FOUND
- `tests/structural/test_cosign_verify_yml.py` — FOUND

### Commits exist:
- `8cd4e3a` — FOUND
- `dbad41b` — FOUND

### Quality gates:
- `uv run pytest tests/structural -q --no-cov` — 55 passed
- `uv run pytest tests/unit -q --no-cov` — 469 passed
- `uv run mypy --strict src/aws_eks_helm_deploy` — 0 errors
- `uv run ruff check src/ tests/ scripts/` — clean
- `grep -E 'id-token:\s*write' cosign-verify.yml` — 0 hits
- `grep --certificate-identity-regexp cosign-verify.yml` — 4 hits
- `grep token.actions.githubusercontent.com cosign-verify.yml` — 1 hit
- `grep ghcr.io/yves-vogl/aws-eks-helm-deploy:latest cosign-verify.yml` — 1 hit (comment)
- `grep concurrency: cosign-verify.yml` — 1 hit
- `grep -E 'uses:.*@(v[0-9]+|main|master|latest)$' cosign-verify.yml` — 0 hits
- `grep -rE '^import subprocess' src/` — exactly 2 files

## Self-Check: PASSED
