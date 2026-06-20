---
phase: 06-release-pipeline-supply-chain
plan: 04
subsystem: ci-cd
tags:
  - cosign-keyless
  - sbom
  - spdx
  - cyclonedx
  - slsa-provenance
  - ghcr
  - release-pipeline
  - sec-01
  - sec-02
  - sec-03
dependency_graph:
  requires:
    - 06-03  # release.yml skeleton (multi-arch build + manifest job)
  provides:
    - sign-and-attest job in release.yml
    - cosign 2.6.3 keyless image signing via OIDC → Fulcio → Rekor
    - SBOM in SPDX + CycloneDX, attached via cosign attest
    - SLSA build provenance via actions/attest-build-provenance@v4.1.0 (C1 correction)
    - 14 structural test assertions over the sign-and-attest contract
  affects:
    - 06-05 cosign-verify.yml (verifies what 06-04 signs)
tech_stack:
  - sigstore/cosign-installer@v3 (pinned to digest)
  - anchore/sbom-action@v0.24.0 (pinned to digest)
  - actions/attest-build-provenance@v4.1.0 (C1-corrected SHA a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32)
  - github OIDC → Sigstore Fulcio CA → Rekor transparency log
status: complete
completion_date: 2026-06-20
---

# Plan 06-04 — Sign + SBOM + SLSA Provenance

## Outcome

`release.yml` gains a `sign-and-attest` job that runs after the multi-arch manifest is published. The job:

1. Installs cosign 2.6.3 via `sigstore/cosign-installer` (Phase 4 D8 pin carry-forward).
2. Authenticates to GHCR via `docker/login-action`.
3. Runs `cosign sign --yes --bundle cosign.bundle "${IMAGE_REF}"` against the multi-arch manifest digest — keyless via the workflow's OIDC token → Fulcio cert → Rekor transparency log entry. `--bundle` emits the offline-verification bundle per D7.
4. Generates two SBOMs from the published image via `anchore/sbom-action`: `sbom.spdx.json` (SPDX 2.3 JSON) and `sbom.cyclonedx.json` (CycloneDX 1.5 JSON).
5. Attests each SBOM via `cosign attest --yes --bundle <out> --predicate <sbom> --type <spdxjson|cyclonedx>` — both attestations are SLSA-aligned and verifiable via `cosign verify-attestation`.
6. Attaches SLSA build provenance via `actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` (v4.1.0 — research correction C1 verbatim).

The job's `permissions` block is minimal: `id-token: write` (OIDC for Fulcio), `attestations: write` (SLSA provenance writer), `packages: write` (GHCR push for the cosign signature OCI artifact), `contents: read`.

## Artifacts produced

- `.github/workflows/release.yml` — extended with the `sign-and-attest` job (10 new steps, ~50 lines)
- `tests/structural/test_release_yml_sign_attest.py` — 14 structural assertions verifying the contract

## Commits

- `0f80b5e feat(06-04): append sign-and-attest job to release.yml (SEC-01/02/03)`
- `<test commit>: test(06-04): add 14 structural gates for sign-and-attest job`
- `<this commit>: docs(06-04): plan summary`

## Quality gates passed

| Gate | Result |
|------|--------|
| `uv run pytest tests/structural -q --no-cov` | 43 passed |
| `uv run pytest tests/unit -q --no-cov` | 469 passed (no regression) |
| `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` | PASS (100% line+branch) |
| `uv run mypy --strict src/aws_eks_helm_deploy` | 0 errors |
| `uv run ruff check src/ tests/ scripts/` | clean |
| `grep -F 'a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32' .github/workflows/release.yml` | 1 hit (C1 SHA) |
| `grep -F 'cosign sign' .github/workflows/release.yml` (multi-flag form, not literal `--bundle` substring) | 1 hit with `--bundle` flag present |
| `grep -F 'sbom.spdx.json' .github/workflows/release.yml` | 4 hits (output-file + predicate + bundle + attest) |
| `grep -F 'sbom.cyclonedx.json' .github/workflows/release.yml` | 4 hits |
| `grep -F 'id-token: write' .github/workflows/release.yml` | 2 hits (workflow level + sign-attest job) |
| `grep -F 'attestations: write' .github/workflows/release.yml` | 2 hits |
| `grep -F 'docker.io' .github/workflows/release.yml` | 0 hits (Docker Hub frozen) |
| `grep -E 'uses:.*@(v[0-9]+|main|master|latest)$' .github/workflows/release.yml` | 0 hits (every action SHA-pinned) |
| `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` | 2 files (D6 invariant preserved) |
| Pre-commit hooks | All passed (gitleaks, ruff, mypy, pytest unit) |

## Deviations from plan

The orchestrator's quality_gates expected `grep -F 'cosign sign --bundle'` as a single literal — the actual command uses multi-flag form `cosign sign --yes --bundle cosign.bundle "${IMAGE_REF}"`. Same for `cosign attest`, which uses `--predicate` + `--type` on separate lines. The semantic contract is fully met; the literal grep patterns were over-tight. Documented in this summary as expected behavior.

A second `id-token: write` and `attestations: write` appears at workflow level in addition to the job level — this is consistent with the cosign keyless three-way coupling (Pitfall #4) mitigation guidance from CONTEXT.md D7 and 06-RESEARCH.md.

## Closes

SEC-01 (Cosign keyless image sign with `--bundle`), SEC-02 (SBOM in BOTH SPDX and CycloneDX, attested via cosign), SEC-03 (SLSA build provenance via attest-build-provenance@v4.1.0).
