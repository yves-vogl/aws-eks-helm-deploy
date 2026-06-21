---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: image consumers running ARM64 (Graviton, Apple Silicon CI)
---

# Multi-arch via native runners (`ubuntu-24.04` + `ubuntu-24.04-arm`); never QEMU

## Context and Problem Statement

The v2 runtime image must publish both `linux/amd64` and `linux/arm64` variants so EKS Graviton node pools and Apple Silicon CI runners can pull a native image. Two strategies exist: (a) build both arches on a single amd64 runner under QEMU emulation, or (b) build each arch on a runner of that arch and assemble a multi-arch manifest by digest. Path (a) is the classic `docker buildx --platform linux/amd64,linux/arm64` flow; path (b) is the GitHub-native multi-arch flow introduced once `ubuntu-24.04-arm` runners became generally available.

QEMU emulation of ARM64 from an amd64 runner is known to silently produce broken arm64 binaries in subtle cases (segfaults under specific instruction patterns, mis-compiled native extensions, broken `helm` binary downloads when the arch-detection in install scripts is fooled by the userland namespace). These breakages would not be caught by the Bitbucket Pipeline Marketplace acceptance tests because they run on amd64 only.

## Decision Drivers

* Correctness — no silent broken-arm64 builds; every architecture is tested on its own arch.
* Build time — native ARM64 build on `ubuntu-24.04-arm` finishes in real time; QEMU-emulated ARM64 build on amd64 takes 5-10× longer.
* Native test execution — every architecture runs its acceptance tests on its native arch, so `helm template`, `helm install --dry-run`, and the `kubectl apply` smoke tests use the real per-arch binaries.
* `actions/attest-build-provenance` produces correct SLSA attestation per architecture only when each build runs on its own runner.
* `docker buildx imagetools create` cleanly assembles multi-arch manifests from per-arch digests.

## Considered Options

* QEMU emulation on a single runner — `docker buildx build --platform linux/amd64,linux/arm64`.
* Two native runners with per-arch image push by digest + a third "fan-in" job that runs `docker buildx imagetools create` to assemble the multi-arch manifest.
* Ship amd64 only and let consumers cross-build.

## Decision Outcome

Chosen option: **"Two native runners with per-arch push + manifest fan-in"**, because native ARM64 runners (`ubuntu-24.04-arm`) are GA on GitHub-hosted infrastructure, native builds eliminate the silent-QEMU-breakage class of bugs entirely, per-arch SLSA attestation is correct by construction, and the manifest fan-in step is a single `docker buildx imagetools create` invocation. Each per-arch image is independently cosign-signed; the multi-arch manifest is the entry consumers pull by tag.

### Consequences

* Good, because correctness — no QEMU-emulation breakage class.
* Good, because per-arch acceptance tests run on the actual target arch.
* Good, because per-arch cosign signing + SLSA attestation are natively correct.
* Good, because build time drops compared to amd64-with-QEMU-arm64.
* Bad, because the workflow has three jobs (build-amd64, build-arm64, manifest-fan-in) instead of one — slightly more YAML.
* Bad, because if `ubuntu-24.04-arm` runners ever go offline, the ARM64 build is blocked (mitigated: graceful failure surfaces clearly; no silent fallback to QEMU).

## Pros and Cons of the Options

### QEMU emulation on a single runner

* Good, because single job, simplest YAML.
* Bad, because **silently broken ARM64 outputs** under known instruction patterns (07-RESEARCH.md Pitfall #5).
* Bad, because 5-10× slower for the ARM64 leg.
* Bad, because per-arch acceptance tests cannot run natively.

### Native runners + manifest fan-in

* Good, because **correct ARM64 builds, every time**.
* Good, because per-arch testing on the actual target arch.
* Good, because composes cleanly with per-arch cosign sign + SLSA attestation.
* Neutral, because slightly more YAML (three jobs).

### Ship amd64 only

* Good, because simplest possible workflow.
* Bad, because consumers running ARM64 (Graviton, Apple Silicon) must cross-build, defeating the supply-chain story.
* Bad, because the image is no longer "deploy to any EKS cluster" — it is "deploy to amd64 EKS clusters only".

## More Information

* Sources: [Phase 6 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/06-release-pipeline-supply-chain/06-CONTEXT.md) (multi-arch decision), 07-RESEARCH.md Pitfall #5 (silent QEMU breakage), REQUIREMENTS.md IMAGE-04 (multi-arch).
* Cross-references: ADR-0001 (forge primacy — `ubuntu-24.04-arm` is GitHub-hosted only), ADR-0003 (cosign — each per-arch image signs independently).
* NIH check: we use upstream `docker buildx imagetools create` to assemble the multi-arch manifest; we do not hand-roll manifest assembly.
