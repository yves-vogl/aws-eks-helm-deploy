---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: downstream consumers, Bitbucket Pipe Marketplace users
---

# GitHub is the primary forge; Bitbucket Pipe Marketplace stays as a compat target

## Context and Problem Statement

The pipe was developed historically on Bitbucket as a Bitbucket Pipe published to the Pipe Marketplace. v2 modernization (OIDC keyless cosign signing, multi-arch native runners, release-please-driven semantic versioning, SLSA build provenance) depends on features that are first-party on GitHub Actions and either absent or substantially weaker on Bitbucket Pipelines. We need to pick one primary forge for v2.0 development and define how the historic Bitbucket distribution channel continues to work.

## Decision Drivers

* OIDC keyless cosign signing requires an OIDC provider that Fulcio trusts — GitHub Actions OIDC is the canonical example; Bitbucket Pipelines OIDC integration with Fulcio is not first-class.
* release-please-action v4 is GitHub-native and assumes Conventional Commits + GitHub Releases.
* Native ARM64 runners (`ubuntu-24.04-arm`) are GitHub-hosted; Bitbucket Pipelines has no equivalent without self-hosted infra.
* `actions/attest-build-provenance` (SLSA v1.0) only ships on GitHub Actions.
* GHCR is the native registry for GitHub OIDC tokens; pushing to Docker Hub from Bitbucket Pipelines requires long-lived credentials.
* The existing Bitbucket Pipe Marketplace listing has discoverability we must preserve for v1.x users.

## Considered Options

* Stay Bitbucket-primary; backport modern features.
* Move primary to GitHub; keep Bitbucket Pipe Marketplace listing for v1.x compat (Docker Hub frozen at v1.3.0).
* Move primary to GitLab.

## Decision Outcome

Chosen option: **"Move primary to GitHub; keep Bitbucket Pipe Marketplace listing for v1.x compat"**, because every v2 supply-chain requirement (cosign keyless, multi-arch native, SLSA attestation, release-please) lands cleanly on GitHub Actions and would require expensive workarounds on Bitbucket. The Bitbucket Pipe Marketplace listing is retained via a minimal `bitbucket-pipelines.yml` that points to the frozen v1.3.0 Docker Hub image — existing pipelines keep working, new development happens on GitHub.

### Consequences

* Good, because the v2 supply-chain story (cosign + SLSA + GHCR) becomes the documented happy path without forge-specific workarounds.
* Good, because release-please + Conventional Commits eliminate manual versioning ceremony.
* Bad, because contributors who only know Bitbucket need to learn the GitHub Actions workflow.
* Bad, because the dual-publish surface (GHCR for v2, Docker Hub for v1 frozen) is permanently load-bearing for migration users.

## Pros and Cons of the Options

### Stay Bitbucket-primary

* Good, because no migration cost for the existing user base.
* Bad, because Bitbucket Pipelines OIDC + Fulcio is not a documented happy path — cosign keyless would require self-managed certificates.
* Bad, because there is no native ARM64 runner on Bitbucket Pipelines.
* Bad, because release-please-action is GitHub-only.

### Move primary to GitHub; keep Bitbucket Marketplace listing

* Good, because every v2 supply-chain requirement is first-class.
* Good, because preserves the v1.x Bitbucket Marketplace discoverability.
* Neutral, because dual-channel publishing (GHCR for v2, Docker Hub frozen for v1) is part of the migration narrative.
* Bad, because contributors need a GitHub account.

### Move primary to GitLab

* Good, because GitLab CI has native OIDC + SLSA support.
* Bad, because abandons both the Bitbucket and (potential) GitHub user base.
* Bad, because the Pipe Marketplace listing has no GitLab analog.

## More Information

* Sources: [Phase 6 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/06-release-pipeline-supply-chain/06-CONTEXT.md), REQUIREMENTS.md MIG-01 (v1.3.0 frozen on Docker Hub, v2.0 on GHCR).
* Cross-references: ADR-0002 (clean break — explains why v1 stays frozen rather than receiving v2 features), ADR-0003 (cosign keyless — the security-critical driver), ADR-0007 (multi-arch native runners — depends on GitHub-hosted ARM64).
* NIH check: we use upstream GitHub Actions (`actions/attest-build-provenance`, `sigstore/cosign-installer`, `googleapis/release-please-action`) rather than hand-rolling. Bitbucket-specific reimplementations of these would be NIH.
