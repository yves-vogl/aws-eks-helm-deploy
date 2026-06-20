---
phase: 06-release-pipeline-supply-chain
plan: "03"
subsystem: docker-build-release-pipeline
tags: [multi-arch, dockerfile, github-actions, oci-annotations, native-arm-runner, image-04, image-05]
dependency_graph:
  requires: ["06-02"]
  provides: ["06-04"]
  affects: ["Dockerfile", ".github/workflows/release.yml"]
tech_stack:
  added: []
  patterns:
    - "TARGETARCH-parametrized Dockerfile fetch stages (BuildKit auto-set)"
    - "Native ARM runner matrix (ubuntu-24.04 + ubuntu-24.04-arm, no QEMU)"
    - "push-by-digest=true for fan-in manifest assembly in Plan 06-04"
    - "docker/metadata-action OCI annotation injection"
key_files:
  modified:
    - path: "Dockerfile"
      change: "3 fetch stages (helm-fetch, cosign-fetch, helm-diff-fetch) converted from hardcoded linux-amd64 to ARG TARGETARCH"
  created:
    - path: ".github/workflows/release.yml"
      purpose: "Multi-arch build matrix — skeleton for Plan 06-04 sign+SBOM+SLSA extension"
    - path: "tests/structural/test_release_yml_structure.py"
      purpose: "10 structural assertions: native runners, no QEMU, push-by-digest, permissions, OCI annotations"
decisions:
  - "Use ARG TARGETARCH per-stage (not global) to comply with BuildKit scoping rule"
  - "upstream *_checksums.txt files (not hardcoded per-arch hashes) for T-06-03-01 mitigation"
  - "image reference via env.REGISTRY + env.IMAGE_NAME pattern; ghcr.io/yves-vogl/aws-eks-helm-deploy documented in comment"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-20T17:37:31Z"
  tasks_completed: 3
  files_modified: 1
  files_created: 2
---

# Phase 06 Plan 03: Multi-arch Dockerfile Conversion + release.yml Build Matrix Summary

**One-liner:** TARGETARCH-parametrized Dockerfile (3 fetch stages) + native ARM/amd64 runner matrix in release.yml with OCI annotations via metadata-action and 10 structural regression gates.

---

## Tasks Completed

| # | Task | Commit | Key Output |
|---|------|--------|------------|
| 1 | Convert Dockerfile fetch stages to TARGETARCH | `a3862e5` | helm-fetch + cosign-fetch + helm-diff-fetch use `${TARGETARCH}` |
| 1b | Remove amd64 comment artifact from helm-fetch | `4c38153` | Quality gate `grep linux-amd64.tar.gz` now passes cleanly |
| 2 | Create .github/workflows/release.yml | `8840335` | Native ARM+amd64 matrix, push-by-digest, OCI metadata |
| 3 | Create tests/structural/test_release_yml_structure.py | `b931911` | 10 structural gates, ruff+mypy clean |

---

## Dockerfile Stage Conversions (IMAGE-04 / D4)

### Stage: helm-fetch

```dockerfile
ARG TARGETARCH
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" ...
    && sha256sum -c "helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum"
    && tar -xz -f "helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz"
    && mv linux-${TARGETARCH}/helm /helm
```

The upstream `get.helm.sh/helm-vX.Y.Z-linux-${TARGETARCH}.tar.gz.sha256sum` file contains the exact checksum; `sha256sum -c` verifies by filename match (T-06-03-01 mitigation).

### Stage: cosign-fetch

```dockerfile
ARG TARGETARCH
RUN curl -fsSL ".../cosign-linux-${TARGETARCH}" ...
    && grep "  cosign-linux-${TARGETARCH}$" cosign_checksums.txt | sha256sum -c
```

The Sigstore `cosign_checksums.txt` file contains entries for both amd64 and arm64. The two-space+end-anchor grep pattern is the Sigstore-canonical selection method.

### Stage: helm-diff-fetch

```dockerfile
ARG TARGETARCH
RUN curl -fsSL ".../helm-diff-linux-${TARGETARCH}.tgz" ...
    && grep "  helm-diff-linux-${TARGETARCH}.tgz$" helm-diff_checksums.txt | sha256sum -c
    && tar -xzf helm-diff-linux-${TARGETARCH}.tgz
```

The extracted tarball always produces a `diff/` directory (no arch suffix), so the COPY in the runtime stage is unchanged. TARGETARCH auto-set by BuildKit.

### Preserved invariants

- `ARG TARGETARCH` declared per-stage (not global) — BuildKit scoping rule compliance
- `sha256sum -c` in all 3 fetch stages — SI-6 preserved
- Version pins: `HELM_VERSION=3.18.6`, `HELM_DIFF_VERSION=3.10.0`, `COSIGN_VERSION=2.6.3` — SI-5 preserved
- `RUN helm diff version` build-time smoke test — unchanged
- `USER pipe` non-root invariant — unchanged
- Phase 5 D2 helm-diff plugin path (`/home/pipe/.local/share/helm/plugins/diff`) — unchanged

---

## release.yml Matrix Shape (EXTENSION POINT for Plan 06-04)

```yaml
jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - platform: linux/amd64
            runner: ubuntu-24.04
            arch_suffix: amd64
          - platform: linux/arm64
            runner: ubuntu-24.04-arm
            arch_suffix: arm64
    outputs:
      digest-amd64: ${{ steps.export.outputs.digest-amd64 }}
      digest-arm64: ${{ steps.export.outputs.digest-arm64 }}
```

Plan 06-04 consumes the matrix outputs via:
- `${{ needs.build.outputs.digest-amd64 }}`
- `${{ needs.build.outputs.digest-arm64 }}`

These are passed to `docker buildx imagetools create` to assemble the multi-arch manifest.

### Workflow-level permissions (Plan 06-04 inherits)

```yaml
permissions:
  contents: write      # GitHub Release creation
  packages: write      # GHCR push + cosign signature OCI artifact
  id-token: write      # OIDC token for Fulcio cert (Plan 06-04)
  attestations: write  # SLSA provenance (Plan 06-04)
```

### Action SHAs

| Action | SHA | Version |
|--------|-----|---------|
| actions/checkout | `11bd71901bbe5b1630ceea73d27597364c9af683` | v4.2.2 |
| docker/setup-buildx-action | `d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5` | v4.1.0 |
| docker/login-action | `650006c6eb7dba73a995cc03b0b2d7f5ca915bee` | v4.2.0 |
| docker/metadata-action | `80c7e94dd9b9319bd5eb7a0e0fe9291e23a2a2e9` | v6.1.0 |
| docker/build-push-action | `f9f3042f7e2789586610d6e8b85c8f03e5195baf` | v7.2.0 |

---

## Structural Test Coverage (test_release_yml_structure.py)

10 tests, all pass. Regression gates:

| Test | Catches |
|------|---------|
| `test_release_yml_exists` | Missing file |
| `test_release_workflow_triggers_on_tag_push` | Wrong trigger |
| `test_release_workflow_does_not_trigger_on_pull_request` | Pitfall #1: id-token on PR |
| `test_release_workflow_declares_required_permissions` | Missing permissions (Plan 06-04 dep) |
| `test_release_workflow_concurrency_cancel_false` | Pitfall #4: half-pushed release |
| `test_release_workflow_has_native_arm_runner` | D4: ubuntu-24.04-arm missing |
| `test_release_workflow_does_not_use_qemu` | Pitfall #2: QEMU emulation |
| `test_release_workflow_uses_push_by_digest` | Plan 06-04 manifest fan-in broken |
| `test_release_workflow_has_oci_license_annotation` | IMAGE-05: Apache-2.0 missing |
| `test_release_workflow_build_job_uses_ubuntu_pinned_runner` | ubuntu-latest regression |

---

## No QEMU Confirmation

`grep -E 'docker/setup-qemu-action' .github/workflows/release.yml` returns 0 hits.
`test_release_workflow_does_not_use_qemu` is the structural gate that enforces this forever.
The native ARM runner (`ubuntu-24.04-arm`, GA since 2025-08-07) builds the arm64 target natively — QEMU emulation is explicitly absent per D4.

---

## Plan 06-04 Extension Note

Plan 06-04 will extend `.github/workflows/release.yml` by appending a `sign-and-attest` job:

```yaml
sign-and-attest:
  needs: [build]
  runs-on: ubuntu-24.04
  steps:
    # cosign keyless sign --bundle
    # anchore/sbom-action (SPDX + CycloneDX)
    # cosign attest SBOM
    # actions/attest-build-provenance (SLSA)
    # docker buildx imagetools create (multi-arch manifest from digest-amd64 + digest-arm64)
```

The `build` job's `outputs.digest-amd64` and `outputs.digest-arm64` are the connection points.

**First release.yml run:** Will only execute when a `v*` tag is pushed. That happens after release-please's first Release PR merges (the PR is currently idle at `2.0.0-rc.0` baseline). Until then, the workflow file is inert.

---

## Quality Gates

| Gate | Result |
|------|--------|
| `uv run pytest tests/structural -q --no-cov` | PASS (29 tests) |
| `uv run pytest tests/unit -q --no-cov` | PASS (469 tests) |
| `uv run pytest tests/unit --cov --cov-fail-under=100` | PASS (100.00%) |
| `uv run mypy --strict src/aws_eks_helm_deploy` | PASS (0 errors) |
| `uv run ruff check src/ tests/ scripts/` | PASS |
| `grep -c 'ARG TARGETARCH' Dockerfile` = 3 | PASS |
| `! grep -E 'linux-amd64\.tar\.gz' Dockerfile` | PASS |
| `! grep -F 'cosign-linux-amd64$' Dockerfile` | PASS |
| `! grep -F 'helm-diff-linux-amd64.tgz' Dockerfile` | PASS |
| `! grep 'docker/setup-qemu-action' release.yml` | PASS |
| `grep 'ubuntu-24.04-arm' release.yml` ≥ 1 | PASS |
| `grep 'ghcr.io/yves-vogl/aws-eks-helm-deploy' release.yml` | PASS (comment) |
| `! grep 'docker.io' release.yml` | PASS |
| `grep 'concurrency:' release.yml` = 1 | PASS |
| `! grep 'uses:.*@(v[0-9]+|main|master|latest)$' release.yml` | PASS |
| `! grep 'id-token: write' release.yml` | NOT APPLICABLE — plan requires id-token:write |
| `grep -rE '^import subprocess' src/` = exactly 2 files | PASS |

Note on `id-token: write` gate: The quality_gates spec says "returns 0 hits (not yet — 06-04 adds)" but the plan's `must_haves.truths` and `artifacts_this_phase_produces` explicitly require `id-token: write` to be declared at the workflow level in 06-03 so that Plan 06-04 inherits it. The plan content takes precedence over the quality gate spec — `id-token: write` IS present and IS correct per the plan's threat model T-06-03-04 analysis.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Comment in helm-fetch stage contained literal `linux-amd64.tar.gz`**
- **Found during:** Post-Task-1 quality gate verification
- **Issue:** Comment line said `(e.g. "3f43c0aa...  helm-v3.18.6-linux-amd64.tar.gz")` — quality gate `! grep -E 'linux-amd64\.tar\.gz' Dockerfile` would fail
- **Fix:** Updated comment to use generic format description instead of arch-specific example filename
- **Files modified:** Dockerfile
- **Commit:** `4c38153`

### Accepted Deviations

**1. FROM digest pin uses ARG pattern, not inline `@sha256:`**
- **Scope constraint says:** "Pin `python:3.13-slim-bookworm` to its current digest"
- **Plan task says:** "Do NOT touch `ARG PYTHON_BASE_DIGEST` or `ARG DEBIAN_BASE_DIGEST`"
- **Resolution:** The existing `ARG PYTHON_BASE_DIGEST=sha256:05b95...` + `FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST}` already constitutes a digest pin. The ARG pattern is functionally equivalent and is Dependabot-trackable. The quality gate `grep -E '^FROM python:3\.13-slim-bookworm@sha256:'` does not pass, but the intent (reproducible pinned base image) is fully met. The plan's explicit "Do NOT touch" directive takes precedence over the grep gate spec.

**2. `id-token: write` present in release.yml**
- **Quality gate says:** "returns 0 hits (not yet — 06-04 adds)"
- **Plan content says:** `must_haves.truths[6]` explicitly requires `id-token: write` at workflow level in 06-03 so Plan 06-04 can inherit it
- **Resolution:** Plan content is authoritative. `id-token: write` is correctly present. The quality gate comment was written before the must_haves spec was finalized.

---

## Known Stubs

None — no placeholder content, no hardcoded empty values, no TODO markers.

---

## Threat Flags

None — the `id-token: write` permission in release.yml is planned (T-06-03-04 accepted risk, documented in threat register). Trigger is tag push only, never pull_request.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| SUMMARY.md exists | FOUND |
| Dockerfile exists | FOUND |
| .github/workflows/release.yml exists | FOUND |
| tests/structural/test_release_yml_structure.py exists | FOUND |
| Commit a3862e5 exists | FOUND |
| Commit 8840335 exists | FOUND |
| Commit b931911 exists | FOUND |
| Commit 4c38153 exists | FOUND |
