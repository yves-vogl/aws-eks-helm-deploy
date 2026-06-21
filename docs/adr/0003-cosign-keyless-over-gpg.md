---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: downstream image consumers, supply-chain auditors
---

# Cosign keyless (OIDC → Fulcio → Rekor) over GPG image signing

## Context and Problem Statement

The v2 image must ship with verifiable provenance to satisfy SEC-01 (signed images) and the supply-chain expectations of consumers running EKS deploys from a third-party image. v1 used GPG signing for source releases, but no image-level signing was in place. We need an image-signing strategy that is verifiable offline by consumers, requires no long-lived signing keys, and integrates with the wider SLSA story.

## Decision Drivers

* GitHub Actions OIDC eliminates the need for long-lived signing keys — the signing identity is the workflow identity, ephemeral per run.
* Rekor transparency log provides public, append-only proof that a specific image digest was signed by a specific workflow at a specific time.
* SLSA Build-Level-3 attestation aligns with the wider supply-chain story (Cosign + `actions/attest-build-provenance` are designed to compose).
* Offline verification via `cosign verify --bundle <bundle.json>` is supported, so consumers do not need a live Rekor connection at verify time.
* Cosign verify with certificate identity constraints (`--certificate-identity`, `--certificate-oidc-issuer`) lets consumers pin acceptable signers to the project's own GitHub workflow URL.

## Considered Options

* GPG sign the image manifest with a project-owned key.
* Cosign keyless (OIDC → Fulcio short-lived certificate → Rekor log).
* Cosign with a long-lived signing key stored in GitHub Secrets.

## Decision Outcome

Chosen option: **"Cosign keyless"**, because it removes the long-lived key custody problem entirely, integrates natively with the GitHub Actions OIDC issuer that Fulcio trusts, and produces a transparency-log entry that consumers can verify with constrained certificate identities. The signing bundle is published as a workflow artifact and as an OCI referrer, so offline verify works.

### Consequences

* Good, because there is no signing key to rotate, store, leak, or revoke.
* Good, because Rekor transparency log entries are public audit evidence for SLSA / supply-chain reviews.
* Good, because consumers verify with constrained certificate identity (`--certificate-identity-regexp ^https://github.com/yves-vogl/aws-eks-helm-deploy/.+`).
* Bad, because verification depends on the Sigstore PKI roots — consumers must trust Fulcio's root CA (mitigated by Rekor's transparency log).
* Bad, because keyless signing requires an OIDC-aware CI; consumers running their own forks need GitHub Actions OIDC (or accept unsigned forks).

## Pros and Cons of the Options

### GPG sign

* Good, because GPG is the most familiar signing format for Linux distros.
* Bad, because requires permanent key custody (HSM or encrypted secret) — a known source of supply-chain breaches.
* Bad, because no transparency log; revocation is informal.
* Bad, because does not compose with SLSA attestation tooling.

### Cosign keyless

* Good, because no long-lived keys; identity is the workflow.
* Good, because Rekor transparency log + `cosign verify --bundle` supports offline verify.
* Good, because composes with `actions/attest-build-provenance` for the full SLSA story.
* Neutral, because consumers must learn the cosign verification CLI (mitigated by the migration guide and `examples/cosign-verify/`).

### Cosign with a stored long-lived key

* Good, because no dependency on OIDC PKI.
* Bad, because reintroduces the long-lived key custody problem cosign keyless was designed to solve.
* Bad, because no transparency log unless explicitly opted-in.

## More Information

* Sources: [Phase 6 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/06-release-pipeline-supply-chain/06-CONTEXT.md) (cosign decision), 07-RESEARCH.md (Phase 6 Cosign integration), REQUIREMENTS.md SEC-01 (signed images), SEC-02 (transparency log presence).
* Cross-references: ADR-0001 (forge primacy — GitHub OIDC is the trust anchor), ADR-0007 (multi-arch native runners — each per-arch image is independently signed).
* NIH check: we use upstream Sigstore (`sigstore/cosign-installer`, Fulcio, Rekor) and Sigstore's published trust roots, not a hand-rolled signing scheme. Hand-rolled signing is a documented supply-chain anti-pattern.
* Verification posture: the documentation describes how to verify the signature (`examples/cosign-verify/README.md`). It does not include exploit walkthroughs for what an attacker could do if verification were skipped — that is intentionally out of scope for the ADR.
