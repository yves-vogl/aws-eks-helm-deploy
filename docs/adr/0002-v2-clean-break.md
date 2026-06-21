---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: v1.x users planning migration to v2
---

# v1.x → v2.x is a clean break; no compatibility shim layer

## Context and Problem Statement

v1.x is a shell-based Bitbucket Pipe (`pipe/` directory, bundled `awscli`, `kubectl`, `helm`, `gpg`). v2.x is a full Python rewrite (`src/aws_eks_helm_deploy/`, boto3-only EKS auth, OIDC-aware credential resolution, log masking, cosign signing). Maintaining runtime compatibility for the entire v1.x environment variable surface and behavior would require dual code paths in every action and would forever block deprecation of legacy behaviors (case-sensitive secret matching, shell-quoting bugs, opaque error messages).

## Decision Drivers

* Maintenance overhead — every dual-path branch is a permanent test matrix obligation.
* Security surface — keeping the legacy shell pipeline means keeping its known bugs and CVE exposure.
* Clarity for consumers — a clean break with a documented migration guide is easier to reason about than implicit compat layers.
* META-02 default flip (Phase 5) is the single biggest source of breaking change; it cannot be silently compat-shimmed because the changed default *is* the feature.

## Considered Options

* Compat shim layer — v2 entry point detects v1-style env vars and emulates v1 behavior.
* Clean break with migration guide — v1.x stays frozen on Docker Hub at v1.3.0; v2.x is a separate image on GHCR with a documented migration path.
* Versioned API — single image, runtime flag (`PIPE_COMPAT=v1|v2`) selects behavior.

## Decision Outcome

Chosen option: **"Clean break with migration guide"**, because v1.x has a maintained distribution channel (Docker Hub) that we keep on long-term security support per D10 (Phase 7 CONTEXT) and v2.x has new distribution channels (GHCR, Cosign-signed, SLSA-attested) that are not retrofittable to v1. Migration is documented in `docs/migration/v1-to-v2.md` covering every breaking change (META-02 default flip, removed env vars, image registry change, signing change).

### Consequences

* Good, because v2.x code paths are clean — no legacy branches to maintain or test.
* Good, because the migration story is explicit and testable rather than implicit and surprising.
* Good, because v1.x users who cannot migrate yet keep a security-supported image at Docker Hub v1.3.0 (6-month window per D10).
* Bad, because users running v1.x must consciously migrate; pinning to `:latest` will not bring them v2 automatically (intentional — v2 image is at a different registry).
* Bad, because we must permanently maintain two release surfaces for the 6-month support window.

## Pros and Cons of the Options

### Compat shim layer

* Good, because users can migrate without changing their pipeline configuration.
* Bad, because every v1 quirk becomes a v2 maintenance burden indefinitely.
* Bad, because META-02 (Bitbucket metadata injection) cannot be compat-shimmed — the default flip *is* the breaking change.
* Bad, because hidden compat layers are the canonical source of "works on my machine" support tickets.

### Clean break with migration guide

* Good, because v2 codebase stays clean and modern.
* Good, because the migration boundary is visible (different registry, different image, different version).
* Bad, because consumers must consciously read the migration guide.
* Neutral, because v1.x retains a security-supported path for 6 months (D10).

### Versioned API (runtime compat flag)

* Good, because single image to maintain.
* Bad, because the flag becomes a permanent footgun; users forget to set it correctly.
* Bad, because doubles the test matrix per release.
* Bad, because hides the semver intent of the major bump.

## More Information

* Sources: [Phase 6 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/06-release-pipeline-supply-chain/06-CONTEXT.md) (clean-break decision), [Phase 5 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/05-pipe-runtime-bash-parity/05-CONTEXT.md) (META-02 default flip — the biggest single breaking change), REQUIREMENTS.md MIG-01 + MIG-02 + MIG-03 (migration support window).
* Cross-references: ADR-0001 (forge primacy — GitHub is v2's home, Docker Hub stays for v1), ADR-0009 (src-layout, no compat shims — the package-level corollary of this decision).
* NIH check: we ship a written migration guide rather than a runtime emulation layer; emulation layers for breaking releases are a well-known anti-pattern documented across Rails, Django, Python 2→3 case studies.
