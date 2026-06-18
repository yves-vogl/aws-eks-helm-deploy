# Requirements: aws-eks-helm-deploy v2.0

**Defined:** 2026-06-16
**Core Value:** A maintainer can ship a Bitbucket Pipelines deployment to AWS EKS from a clean repository in under five minutes — without committing static AWS credentials and without surprises at upgrade time.

Two consumer-side personas drive the requirements: **(M)** the maintainer of a downstream service who configures the pipe in their `bitbucket-pipelines.yml`, and **(D)** the developer of this Pipe (you) who maintains, tests, releases, and supports it. Most requirements are written from M's perspective; toolchain/CI/release requirements are written from D's.

## v1 Requirements

### Toolchain (TOOL) — developer experience

- [ ] **TOOL-01**: D can install all dev dependencies with `uv sync --all-extras` in under 10 seconds on a warm cache.
- [ ] **TOOL-02**: Source code lives under `src/aws_eks_helm_deploy/`; `pyproject.toml` declares the package, scripts, dependencies, and tool configs; `requirements.txt` is removed.
- [ ] **TOOL-03**: `ruff check` and `ruff format --check` pass with zero findings on the v2.0 source tree; CI fails on violations.
- [ ] **TOOL-04**: `mypy --strict src/` passes with zero errors; CI fails on regressions.
- [ ] **TOOL-05**: `pre-commit` runs `ruff`, `ruff format`, `mypy`, and `pytest -q --no-cov` on staged changes locally; identical checks run in CI.
- [ ] **TOOL-06**: `pytest --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` passes on every PR (no exceptions; `# pragma: no cover` reviewed in PR).
- [ ] **TOOL-07**: D can run a full integration test against a real Helm install on a local `kind` cluster with one command (`make integration-test` or `uv run pytest tests/integration`).
- [ ] **TOOL-08**: D can run the acceptance test suite by building the image and spawning it with `docker run` (parity with existing v1 acceptance pattern, ported to `pytest`).

### AWS Authentication (AUTH)

- [ ] **AUTH-01**: M can authenticate using static `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (parity with v1.x).
- [ ] **AUTH-02**: M can additionally assume an IAM role by setting `ROLE_ARN` (and optional `SESSION_NAME`), composable on top of any base credential source (parity with v1.x).
- [ ] **AUTH-03**: M can authenticate via Bitbucket Pipelines OIDC by setting only `OIDC_AUDIENCE` and `ROLE_ARN`; the pipe exchanges `BITBUCKET_STEP_OIDC_TOKEN` for STS credentials via `AssumeRoleWithWebIdentity`. **(Closes #3.)**
- [ ] **AUTH-04**: Strategy selection follows the boto3 / AWS CLI default credential resolver chain; when both static keys AND an OIDC token are present, **static keys win** — same behaviour as the AWS CLI itself. A one-time WARN log (`auth.precedence.static_keys_won_over_oidc`) surfaces the precedence so consumers who set both by accident can see why their OIDC token was ignored. **(Revised 2026-06-18 — original wording assumed OIDC precedence; superseded by D1 in `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md`.)**
- [ ] **AUTH-05**: The pipe ships a documented AWS IAM trust-policy template scoped to `BITBUCKET_WORKSPACE_UUID` and `BITBUCKET_REPO_UUID` so consumers cannot accidentally configure a permissive policy. **(Pitfall #1.)**
- [ ] **AUTH-06**: The pipe rejects misconfigurations explicitly (e.g. `ROLE_ARN` set without any base credentials, `OIDC_AUDIENCE` without `ROLE_ARN`) with a clear error message before contacting AWS.
- [ ] **AUTH-07**: The EKS token (`k8s-aws-v1.<base64url-presigned-STS-URL>`) is generated via `boto3` only; no `awscli` dependency in the runtime image.

### Helm Chart Sources (CHART)

- [ ] **CHART-01**: M can deploy a Helm chart from a local path (parity with v1.x).
- [x] **CHART-02**: M can deploy a chart from a Helm repository by setting `CHART=repo://<repo-name>/<chart>`, `REPO_URL=<url>`, optional `CHART_VERSION=<version>`. **(Closes #7.)**
- [x] **CHART-03**: M can deploy a chart from an OCI registry by setting `CHART=oci://<registry>/<chart>` with optional `CHART_VERSION` and optional `REGISTRY_USERNAME` + `REGISTRY_PASSWORD`.
- [ ] **CHART-04**: M can verify an OCI chart signature by setting `CHART_VERIFY=true` (Cosign verification of the chart artifact); failure aborts the upgrade.
- [ ] **CHART-05**: The pipe reports the resolved chart name + version in its success message so the consumer's logs are unambiguous.

### Pipe Actions (PIPE)

- [ ] **PIPE-01**: `ACTION=upgrade` (default) runs `helm upgrade --install` with the resolved chart source and credentials.
- [ ] **PIPE-02**: `ACTION=diff` (or shortcut `DRY_RUN=true` on an upgrade) runs `helm diff upgrade` via the bundled `helm-diff` plugin and surfaces the diff to stdout without mutating the cluster.
- [ ] **PIPE-03**: When `ACTION=diff` runs in a Bitbucket Pull-Request build (`$BITBUCKET_PR_ID` set) and `POST_DIFF_AS_COMMENT=true`, the diff is posted as a PR comment via the Bitbucket REST API using `BITBUCKET_TOKEN`. **(Differentiator #3.)**
- [ ] **PIPE-04**: `ACTION=rollback` with `REVISION=<n>` runs `helm rollback <release> <revision>` against the cluster.
- [ ] **PIPE-05**: When `SAFE_UPGRADE=true`, the pipe passes both `--wait` and `--atomic` to `helm upgrade --install`, and pre-flight-checks `helm history <release>` before any rollback to detect revisions that were not `--wait`-ed. **(Pitfall #3.)**
- [ ] **PIPE-06**: Every action returns a non-zero exit code on failure with a human-readable failure message via the `bitbucket-pipes-toolkit` `fail()` channel.

### Helm Release History (HISTORY)

- [ ] **HISTORY-01**: M can set `HISTORY_MAX=<n>` (default unset, meaning Helm default of 10) to bound the release history retained by Helm. **(Closes #17.)**
- [ ] **HISTORY-02**: When `HISTORY_MAX` is set, the pipe passes `--history-max <n>` to `helm upgrade --install`.

### Bitbucket Metadata Injection (META)

- [ ] **META-01**: When `INJECT_BITBUCKET_METADATA=true`, the pipe injects `--set bitbucket.bitbucket_build_number=…`, `bitbucket.bitbucket_repo_slug=…`, `bitbucket.bitbucket_commit=…`, `bitbucket.bitbucket_tag=…`, `bitbucket.bitbucket_step_triggerer_uuid=…` (v1.x parity behavior).
- [ ] **META-02**: When `INJECT_BITBUCKET_METADATA` is unset or `false` (the v2.0 default), no `bitbucket.*` values are injected. **(Closes #16; breaking change vs v1.x.)**
- [ ] **META-03**: When the pipe detects that a chart's `values.yaml` references `.Values.bitbucket.*` and `INJECT_BITBUCKET_METADATA` is not explicitly set, it logs a loud one-time warning recommending the consumer set it explicitly. **(Pitfall #2 mitigation.)**

### Container Image (IMAGE)

- [ ] **IMAGE-01**: The image is built from `python:3.13-slim-bookworm` as the base; Alpine is not used.
- [ ] **IMAGE-02**: The image bundles Helm 3.18.x and the `helm-diff` 3.10.x plugin.
- [ ] **IMAGE-03**: The image runs as a non-root user (`USER pipe` with uid ≥ 10000).
- [ ] **IMAGE-04**: The image is built for both `linux/amd64` and `linux/arm64` and published as a single multi-arch manifest; native ARM runners are used (no QEMU). **(Pitfall #5.)**
- [ ] **IMAGE-05**: The image carries OCI annotations: `org.opencontainers.image.source`, `…revision`, `…version`, `…licenses` (`Apache-2.0`), `…title`, `…description`.
- [ ] **IMAGE-06**: A documented cold-start benchmark (image pull excluded) is published in the README; v2.0 target is under 10 seconds on a Bitbucket-Pipelines-equivalent runner.

### Supply-Chain Security (SEC)

- [ ] **SEC-01**: Every release image is **signed with Cosign keyless** via GitHub Actions OIDC → Fulcio → Rekor; the signature includes an offline bundle (`--bundle`). **(Pitfall #4.)**
- [ ] **SEC-02**: Each release image carries an **SBOM** generated by Syft in **both SPDX and CycloneDX** formats, attached as Cosign attestations.
- [ ] **SEC-03**: Each release image carries a **SLSA build provenance** attestation via `actions/attest-build-provenance@v1`.
- [ ] **SEC-04**: `trivy` scans the built image, Dockerfile, Helm chart fixtures, and secret-leak patterns on every PR; CI fails on `CRITICAL` or `HIGH` findings unless suppressed in `.trivyignore` with rationale.
- [ ] **SEC-05**: `pip-audit` runs on every PR; CI fails on any unsuppressed vulnerability.
- [ ] **SEC-06**: Helm output emitted by the pipe (logs, PR comments, debug dumps) **masks `kind: Secret` rendered manifests** — replacing the entire `data:`/`stringData:` payload with `<redacted>`. **(Pitfall TS-9 in PITFALLS.md; precondition for PIPE-03.)**
- [ ] **SEC-07**: A scheduled **continuous vulnerability scan** workflow (`.github/workflows/security-rescan.yml`, cron daily) runs `aquasecurity/trivy-action` against `ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` and against the `:2` rolling tag. On `CRITICAL` findings the workflow opens a GitHub issue with labels `area/security` + `priority/p0`; on `HIGH` findings a `priority/p1` issue. Findings already tracked in an open issue are de-duplicated by digest+CVE. Results are uploaded as SARIF to GitHub Code Scanning so the **Security** tab shows live CVE state.
- [ ] **SEC-08**: Dependabot updates that bump the **Dockerfile base-image digest** (`python:3.13-slim-bookworm`) use the commit prefix `fix(deps): bump base image …` (configured in `.github/dependabot.yml` via `commit-message: prefix: fix`). This makes `release-please` cut a `patch` release on merge, which triggers `.github/workflows/release.yml` and re-publishes a freshly-scanned image to GHCR. The same prefix is used for `helm` and `helm-diff` plugin bumps.
- [ ] **SEC-09**: **GitHub Private Vulnerability Reporting** is enabled on the repository (`Settings → Security → Private vulnerability reporting`); `SECURITY.md` (DOC-06) documents the disclosure flow and points to it. CVE responses are published as **GitHub Security Advisories** with CVE IDs requested via the GitHub Security Advisory workflow when applicable; advisories are linked from `CHANGELOG.md` patch entries.
- [ ] **SEC-10**: An **OpenSSF Scorecard** workflow (`.github/workflows/scorecard.yml` using `ossf/scorecard-action@v2`, weekly cron + on-push to `main`) evaluates the repository against the Scorecard checks (Dependency-Update-Tool, Signed-Releases, Pinned-Dependencies, Branch-Protection, Code-Review, Token-Permissions, SAST, SBOM, Maintained, …); SARIF results upload to GitHub Code Scanning. The README badge row links to the live score via `https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy/badge`. Target score: **≥ 8/10 by the v2.0 tag-cut**; a `.scorecard-exception.md` documents any deliberate sub-check failure with rationale and review date.

### CI / Release (CI)

- [ ] **CI-01**: A GitHub Actions workflow (`.github/workflows/ci.yml`) runs `ruff`, `mypy`, `pytest --cov`, `trivy`, and `pip-audit` on every PR; required status checks gate merge into `main`.
- [ ] **CI-02**: A GitHub Actions workflow (`.github/workflows/release.yml`) is driven by `release-please` (v4, `release-type: python`); a release-PR updates `pyproject.toml`, `CHANGELOG.md`, and `pipe.yml` image-tag in a single commit.
- [ ] **CI-03**: On `main` after a release-PR merge, the workflow builds the multi-arch image, signs it with Cosign, attaches SBOM + provenance, and pushes to `ghcr.io/yves-vogl/aws-eks-helm-deploy`. **GitHub Container Registry is the only v2.0 publish target**; Docker Hub is no longer used (rationale: native OIDC push from GitHub Actions eliminates `DOCKER_HUB_PAT` as a long-lived CI secret, and SLSA provenance + Cosign keyless run end-to-end inside a single trust domain).
- [ ] **CI-04**: A separate, minimal `bitbucket-pipelines.yml` continues to publish the Bitbucket Pipe Marketplace listing on tagged releases; GitHub Actions is the source-of-truth for image builds.
- [ ] **CI-05**: Dependabot (`.github/dependabot.yml`) is configured for `pip`, `docker`, and `github-actions`; auto-merge is enabled for all updates (including majors) once CI passes — tests are the gate.
- [ ] **CI-06**: Every commit on `main` is GPG-signed (verified on GitHub); branch protection enforces signed commits.
- [ ] **CI-07**: Branch protection on `main`: signed commits, required review (1+), required status checks, no direct pushes.

### Observability & Logging (OBS)

- [ ] **OBS-01**: The pipe emits **structured log lines** (one JSON object per line on stderr when `LOG_FORMAT=json`, otherwise human-readable) with stable field names: `action`, `cluster`, `release`, `namespace`, `chart_source`, `auth_strategy`, `duration_ms`.
- [ ] **OBS-02**: `DEBUG=true` (parity with v1.x) raises verbosity to include full helm argv, resolved credentials source (never the credentials themselves), and per-phase timings.

### Documentation (DOC)

- [ ] **DOC-01**: The `README.md` is the entry doc: badge row, 60-second quick-start, link to the docs site for everything else.
- [ ] **DOC-02**: An `mkdocs-material` site is published to GitHub Pages with `mike` providing `/v1/` (frozen v1.3.0 reference) and `/v2/` (current).
- [ ] **DOC-03**: A `Migration Guide v1 → v2` documents every breaking change: `INJECT_BITBUCKET_METADATA` default, removed/renamed env vars, image-tag pinning policy, recommended `latest` policy (pinned to v1.3.0 forever).
- [ ] **DOC-04**: ADRs live under `docs/adr/` (MADR template). At minimum: forge primacy (GitHub), v2.0 clean break, Cosign keyless over GPG, `boto3`-only over `awscli`, `release-please` over `semversioner`, OIDC default behavior, multi-arch via native runners.
- [ ] **DOC-05**: `CONTRIBUTING.md` documents the `uv sync` / `pre-commit` / `pytest` / `kind` development loop and the Conventional-Commits rule.
- [ ] **DOC-06**: `SECURITY.md` documents the private disclosure flow (email or GitHub security advisory) and the supported-version policy (v2.x current; v1.x receives security fixes for 6 months post-v2.0).
- [ ] **DOC-07**: `CODE_OF_CONDUCT.md` adopts the Contributor Covenant 2.1.
- [ ] **DOC-08**: An `examples/` directory ships ≥4 end-to-end `bitbucket-pipelines.yml` snippets: basic, OIDC-only, OCI chart from GHCR, multi-environment deploy with `helm-diff` PR comment.

### Community Ops (CMN)

- [ ] **CMN-01**: `.github/ISSUE_TEMPLATE/bug_report.yml` and `feature_request.yml` are present; both require pipe version, runtime context, and reproduction.
- [ ] **CMN-02**: `.github/PULL_REQUEST_TEMPLATE.md` lists the merge checklist: tests added, `CHANGELOG`/`release-please` entry, docs updated, ADR if architecturally relevant.
- [ ] **CMN-03**: A GitHub Project (board) tracks the v2.0 milestone in `Backlog → Ready → In Progress → In Review → Done` columns; auto-linked to the `v2.0.0` milestone.
- [ ] **CMN-04**: The label taxonomy (`area/*`, `type/*`, `priority/*`, `breaking-change`, `good first issue`, `help wanted`) is applied to every open issue and PR.

### Migration v1 → v2 (MIG)

- [ ] **MIG-01**: The Docker Hub `yvogl/aws-eks-helm-deploy` repository is **frozen at v1.3.0** as the final v1.x image (no v2 image is pushed there); a documented `:2` rolling tag is introduced on `ghcr.io/yves-vogl/aws-eks-helm-deploy` for v2 consumers who want major-version-pinned auto-updates. The Docker Hub README is updated with a deprecation note pointing to GHCR.
- [ ] **MIG-02**: The first v2.0 image emits a loud one-time deprecation warning at startup if it detects v1-only env-var names (`SET`/`VALUES` in the older positional format, or charts referencing `.Values.bitbucket.*` without `INJECT_BITBUCKET_METADATA=true`).
- [ ] **MIG-03**: An `examples/migration-v1-to-v2/` directory contains a before/after `bitbucket-pipelines.yml` diff with line-level explanations of every required change.

## v2 (Deferred) Requirements

These are acknowledged but explicitly **not in the v2.0 scope** — tracked for v2.1+:

### Auth (v2.1+)

- **AUTH-NEXT-01**: AWS Pod Identity support for self-hosted Bitbucket Pipelines runners on EKS.
- **AUTH-NEXT-02**: `aws-vault` integration for self-hosted Mac/Linux runners.

### Pipe Actions (v2.1+)

- **PIPE-NEXT-01**: `ACTION=uninstall` (`helm uninstall`) with `KEEP_HISTORY=true` opt-in.
- **PIPE-NEXT-02**: `ACTION=lint` (`helm lint`) for PR-time chart validation.

### Distribution (v2.1+)

- **CI-NEXT-01**: Reusable GitHub Action wrapper so the same pipe code can also be invoked from GitHub Actions (consumer convenience; the project remains Bitbucket-first).

### Documentation site (v2.1+)

- **DOC-NEXT-01**: Migrate from `mkdocs-material` to `Zensical` once stable (mkdocs-material entered maintenance mode in early 2026).

## Out of Scope

Explicit boundaries. Anti-features carry reasoning so re-adding requires explicit revisit.

| Feature | Reason |
|---------|--------|
| **First-party GitHub Actions invocation surface** | This is a Bitbucket Pipe. GH Actions consumers are pointed at `aws-actions/configure-aws-credentials` + a Helm action. Turning this into an Action is a different project. |
| **Multi-cluster atomic deploy in one pipe call** | Composability via multiple steps in `bitbucket-pipelines.yml` is sufficient. Adds reconciliation complexity (rollback semantics across clusters) without proportionate value. |
| **GitOps reconciliation (drift detection, sync loops)** | This is what Flux/ArgoCD are for. Our pipe owns the "best-in-class one-shot CI deploy" position, not "worse imitation of a GitOps controller". |
| **Helmfile-style multi-release manifest** | Composability via multiple pipe steps is sufficient and avoids inventing a second DSL on top of Helm. |
| **Templated chart generation** | The pipe deploys charts, it doesn't author them. Out of scope and out of intent. |
| **Web frontend / GUI** | This is a CI Pipe (a container with env vars). |
| **Self-hosting Helm chart of this pipe** | The pipe is a CLI-style container, not a long-running service. |
| **GPG signing of Docker images** | Replaced by Cosign keyless. GPG image signing is dead-tech in OCI distribution. |
| **`semversioner`-managed releases** | Replaced by `release-please` for tighter Conventional-Commits + GitHub-native release flow; eliminates `.changes/` ceremony. |
| **Continued `awscli` dependency** | Dropped in v2.0. `boto3`-only EKS token generation is ~40 lines and saves ~120 MB of image weight. Documented in the migration guide. |
| **Alpine base image** | `python:3.13-slim-bookworm` chosen. musl-libc breaks `boto3` wheel availability and slows builds. |
| **QEMU multi-arch build** | Native ARM runners only. QEMU silently produces broken `arm64` images that are invisible from Bitbucket's amd64-only acceptance tests. |
| **Long-lived AWS credentials in the image or pipe code** | OIDC keyless flow is the production path; static keys remain a fallback for legacy consumers only. |

## Traceability

Populated by `gsd-roadmapper` on 2026-06-16 — every v1 REQ mapped to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TOOL-01 | Phase 1 | Pending |
| TOOL-02 | Phase 1 | Pending |
| TOOL-03 | Phase 1 | Pending |
| TOOL-04 | Phase 1 | Pending |
| TOOL-05 | Phase 1 | Pending |
| TOOL-06 | Phase 1 | Pending |
| TOOL-07 | Phase 1 | Pending |
| TOOL-08 | Phase 1 | Pending |
| AUTH-01 | Phase 2 | Pending |
| AUTH-02 | Phase 2 | Pending |
| AUTH-03 | Phase 4 | Pending |
| AUTH-04 | Phase 4 | Pending |
| AUTH-05 | Phase 4 | Pending |
| AUTH-06 | Phase 4 | Pending |
| AUTH-07 | Phase 2 | Pending |
| CHART-01 | Phase 3 | Pending |
| CHART-02 | Phase 4 | Complete |
| CHART-03 | Phase 4 | Complete |
| CHART-04 | Phase 4 | Pending |
| CHART-05 | Phase 3 | Pending |
| PIPE-01 | Phase 3 | Pending |
| PIPE-02 | Phase 5 | Pending |
| PIPE-03 | Phase 5 | Pending |
| PIPE-04 | Phase 5 | Pending |
| PIPE-05 | Phase 5 | Pending |
| PIPE-06 | Phase 3 | Pending |
| HISTORY-01 | Phase 3 | Pending |
| HISTORY-02 | Phase 3 | Pending |
| META-01 | Phase 3 | Pending |
| META-02 | Phase 5 | Pending |
| META-03 | Phase 5 | Pending |
| IMAGE-01 | Phase 1 | Pending |
| IMAGE-02 | Phase 1 | Pending |
| IMAGE-03 | Phase 1 | Pending |
| IMAGE-04 | Phase 6 | Pending |
| IMAGE-05 | Phase 1 | Pending |
| IMAGE-06 | Phase 6 | Pending |
| SEC-01 | Phase 6 | Pending |
| SEC-02 | Phase 6 | Pending |
| SEC-03 | Phase 6 | Pending |
| SEC-04 | Phase 6 | Pending |
| SEC-05 | Phase 6 | Pending |
| SEC-06 | Phase 5 | Pending |
| SEC-07 | Phase 6 | Pending |
| SEC-08 | Phase 6 | Pending |
| SEC-09 | Phase 6 | Pending |
| SEC-10 | Phase 6 | Pending |
| CI-01 | Phase 6 | Pending |
| CI-02 | Phase 6 | Pending |
| CI-03 | Phase 6 | Pending |
| CI-04 | Phase 6 | Pending |
| CI-05 | Phase 6 | Pending |
| CI-06 | Phase 6 | Pending |
| CI-07 | Phase 6 | Pending |
| OBS-01 | Phase 1 | Pending |
| OBS-02 | Phase 1 | Pending |
| DOC-01 | Phase 7 | Pending |
| DOC-02 | Phase 7 | Pending |
| DOC-03 | Phase 7 | Pending |
| DOC-04 | Phase 7 | Pending |
| DOC-05 | Phase 7 | Pending |
| DOC-06 | Phase 7 | Pending |
| DOC-07 | Phase 7 | Pending |
| DOC-08 | Phase 7 | Pending |
| CMN-01 | Phase 6 | Pending |
| CMN-02 | Phase 6 | Pending |
| CMN-03 | Phase 6 | Pending |
| CMN-04 | Phase 6 | Pending |
| MIG-01 | Phase 6 | Pending |
| MIG-02 | Phase 5 | Pending |
| MIG-03 | Phase 7 | Pending |

**Coverage:**

- v1 requirements: **67** total (8 TOOL + 7 AUTH + 5 CHART + 6 PIPE + 2 HISTORY + 3 META + 6 IMAGE + 6 SEC + 7 CI + 2 OBS + 8 DOC + 4 CMN + 3 MIG)
- Mapped to phases: **67** (100%)
- Unmapped: **0** ✓

**Distribution per phase:**

- Phase 1 (Toolchain & Spine): 14 REQs — TOOL-01..08, IMAGE-01, IMAGE-02, IMAGE-03, IMAGE-05, OBS-01, OBS-02
- Phase 2 (AWS Layer & Auth Foundation): 3 REQs — AUTH-01, AUTH-02, AUTH-07
- Phase 3 (Helm Core & Upgrade Action): 7 REQs — CHART-01, CHART-05, PIPE-01, PIPE-06, HISTORY-01, HISTORY-02, META-01
- Phase 4 (OIDC & Chart Source Extensions): 7 REQs — AUTH-03, AUTH-04, AUTH-05, AUTH-06, CHART-02, CHART-03, CHART-04
- Phase 5 (Log Masking, Diff, Rollback & Metadata Flip): 8 REQs — SEC-06, PIPE-02, PIPE-03, PIPE-04, PIPE-05, META-02, META-03, MIG-02
- Phase 6 (Release Pipeline & Supply Chain): 23 REQs — IMAGE-04, IMAGE-06, SEC-01..05, SEC-07..10, CI-01..07, CMN-01..04, MIG-01
- Phase 7 (Documentation Site & Migration Guide): 9 REQs — DOC-01..08, MIG-03

Sum: 14 + 3 + 7 + 7 + 8 + 23 + 9 = 71 ✓

---
*Requirements defined: 2026-06-16*
*Last updated: 2026-06-16 — added SEC-07/08/09 (continuous image vulnerability monitoring) + SEC-10 (OpenSSF Scorecard)*
