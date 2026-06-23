# Security Policy

## Supported versions

| Version | Supported              |
|---------|------------------------|
| 2.x     | Yes (active development on `main`) |
| 1.x     | Security fixes for 6 months from the v2.0.0 release date — ending `2026-12-23` (v2.0.0 released 2026-06-23 + 6 months). Frozen at v1.3.0 on Docker Hub. |

## Reporting a vulnerability

**Please do not open a public issue for security findings.** GitHub Private Vulnerability Reporting is the canonical disclosure channel for this repository.

To report a vulnerability:

1. Go to the [Security tab](https://github.com/yves-vogl/aws-eks-helm-deploy/security) of this repository.
2. Click **Report a vulnerability** (direct link: [Report a vulnerability](https://github.com/yves-vogl/aws-eks-helm-deploy/security/advisories/new)).
3. Provide the details (affected version, reproduction steps, impact assessment, proposed mitigation if known).

The maintainer will acknowledge receipt within 5 working days and provide an initial assessment within 14 days.

## Disclosure timeline

We follow a coordinated disclosure model:

- **Day 0:** report received, acknowledgement sent.
- **Day 0–14:** triage, severity assessment, reproducer confirmation.
- **Day 14–60:** patch development and testing in a private branch.
- **Day 60–90:** coordinated disclosure window. Reporter is informed of the fix timeline and credited (unless they request otherwise).
- **Day 90 (max):** public disclosure via [GitHub Security Advisory](https://github.com/yves-vogl/aws-eks-helm-deploy/security/advisories), CHANGELOG.md entry, and patch release.

If the issue is being actively exploited in the wild, the disclosure window collapses to "as fast as a fix can be safely shipped."

## Scope

In scope:

- The Pipe runtime image published to GHCR (`ghcr.io/yves-vogl/aws-eks-helm-deploy`) for v2.x.
- The source code in `src/aws_eks_helm_deploy/`, the `Dockerfile`, and CI/CD workflows under `.github/workflows/`.
- Documented configuration interfaces (environment variables, `pipe.yml`).
- The build supply chain (`pyproject.toml`, `uv.lock`, `Dockerfile` base-image pins, helm/helm-diff version pins).

Out of scope:

- The v1.x image on Docker Hub (frozen; report v1 issues against the corresponding Bitbucket repository).
- Vulnerabilities in upstream Helm, Kubernetes, or AWS services themselves (please report to their respective security teams).
- Consumer misconfiguration (e.g. overly permissive IAM policies on the consumer side).
- Findings that require physical access to a developer's machine.

## What we do automatically

This repository runs several automated security gates that may catch issues before a manual report is needed:

- **gitleaks** as a pre-commit hook (every commit + every CI run).
- **pip-audit** on every PR via `scripts/pip-audit-with-stale-check.sh` (Python dependency CVE scan with stale-ignore detection).
- **CodeQL** static analysis on every PR + weekly on `main` (Security tab → Code scanning alerts).
- **OpenSSF Scorecard** weekly (Security tab; live badge on the README).
- **Trivy** image scanning on every PR (image filesystem + Dockerfile + chart fixtures + secret-leak patterns) AND on a daily scheduled rescan against the published GHCR image (`ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` and `:2`); findings upload to GitHub Code Scanning and CRITICAL/HIGH findings open auto-deduplicated GitHub Issues.
- **Cosign** keyless signing of the released image (Sigstore / Fulcio / Rekor) AND Cosign attestation of two SBOMs (SPDX + CycloneDX) AND SLSA build provenance via `actions/attest-build-provenance` — every release is verifiable via `cosign verify ghcr.io/yves-vogl/aws-eks-helm-deploy:<tag>` and `gh attestation verify`.
- **Cosign verify** as a PR gate (`.github/workflows/cosign-verify.yml`) — every PR runs `cosign verify` against the most recent published image to catch sign-chain regressions.
- **Dependabot** for `pip`, `docker`, and `github-actions` ecosystems with weekly grouping; auto-merge once required checks pass.

If your finding is something one of these tools should have caught and didn't, please mention that in the report — it helps us improve the gate.

## Acknowledgements

Security researchers who report valid issues will be credited in the GitHub Security Advisory and the CHANGELOG.md patch entry (unless they request anonymity).
