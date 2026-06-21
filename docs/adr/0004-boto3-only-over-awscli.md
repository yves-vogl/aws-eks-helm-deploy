---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: image consumers, EKS authentication maintainers
---

# `boto3`-only EKS token generation; drop bundled `awscli` from the runtime image

## Context and Problem Statement

v1 bundled `awscli` in the runtime image solely so it could call `aws eks get-token` to obtain a Kubernetes API token for EKS clusters via the IAM authenticator protocol. The bundled `awscli` adds ~120 MB to the image, slows cold start, and broadens the supply-chain attack surface (awscli pulls a large transitive Python dependency tree). The actual token-generation logic is ~40 lines: presign an STS `GetCallerIdentity` URL with the EKS cluster name in the `x-k8s-aws-id` header, base64url-encode it, prepend `k8s-aws-v1.`. `boto3` already ships in the v2 image for every other AWS call we make.

## Decision Drivers

* Image size budget (IMAGE-06 — sub-200 MB target).
* Cold start time on EKS-deploy invocations.
* Supply-chain narrowing — fewer transitive deps means fewer CVE-update obligations.
* No behavioral difference for consumers — the produced token is byte-identical to `aws eks get-token`'s output.
* Stays inside the D6 subprocess invariant — token generation runs as pure Python with boto3, no `subprocess.run("aws", ...)`.

## Considered Options

* Keep `awscli` bundled.
* `boto3`-only — implement the IAM-authenticator presigned-URL spec in ~40 lines of Python.
* Static-link a Go binary (e.g., `aws-iam-authenticator`).

## Decision Outcome

Chosen option: **"`boto3`-only"**, because the IAM-authenticator spec is small enough that re-implementing it in Python against `boto3.client('sts').generate_presigned_url('get_caller_identity')` is faster, smaller, and produces byte-identical output to `aws eks get-token`. The implementation lives at `src/aws_eks_helm_deploy/eks/token.py` and is covered by acceptance tests that compare the generated token to a known-good fixture.

### Consequences

* Good, because image weight drops by ~120 MB (awscli + its dependency tree).
* Good, because no `subprocess` invocation for the auth path — stays inside the D6 invariant.
* Good, because boto3 was already a runtime dependency for every other AWS call; no new dependency surface added.
* Bad, because if AWS ever changes the IAM-authenticator token format (extremely unlikely — it is a documented k8s-aws-v1 protocol), we maintain the code instead of awscli's maintainers.
* Bad, because users debugging the auth path lose the familiar `aws eks get-token` CLI as a comparison reference (mitigated by the acceptance test that compares both outputs).

## Pros and Cons of the Options

### Keep `awscli` bundled

* Good, because zero re-implementation cost.
* Bad, because ~120 MB image weight purely for one CLI call.
* Bad, because broad transitive dependency tree to keep CVE-current.
* Bad, because requires `subprocess` call to `aws`, contradicting the D6 invariant we are otherwise enforcing in v2.

### `boto3`-only

* Good, because tiny code surface (~40 lines + tests).
* Good, because re-uses boto3 already on the image.
* Good, because no subprocess; pure Python; deterministic.
* Neutral, because we accept maintenance responsibility for the spec compliance (small risk; protocol is stable).

### Static-link a Go binary

* Good, because Go binaries are small and self-contained.
* Bad, because adds a second runtime language to the project.
* Bad, because requires a separate CI step to produce + sign the binary.
* Bad, because is overkill for ~40 lines of Python.

## More Information

* Sources: [Phase 2 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/02-aws-layer-auth-foundation/02-CONTEXT.md), REQUIREMENTS.md AUTH-07 (boto3-only EKS token), IMAGE-06 (image weight budget).
* Cross-references: ADR-0009 (src-layout — `eks/token.py` lives under `src/`).
* NIH check: the IAM-authenticator protocol is a public, stable AWS spec; the Python implementation uses upstream `boto3` for the actual STS presigning. We are not inventing an auth scheme; we are using a 40-line adapter over an upstream library. Re-bundling awscli purely to avoid writing those 40 lines is the inverse anti-pattern.
