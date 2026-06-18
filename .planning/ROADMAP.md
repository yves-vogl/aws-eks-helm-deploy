# Roadmap: aws-eks-helm-deploy v2.0

## Overview

v2.0 is the state-of-the-art modernization of an existing, in-production Bitbucket Pipelines Pipe (v1.3.0 on Docker Hub, 9+ public consumers). The journey is brownfield: we keep v1.x frozen on Docker Hub forever and ship v2.0 as a clean break on **GitHub Container Registry (`ghcr.io/yves-vogl/aws-eks-helm-deploy`)** as the sole publish target. We bootstrap a modern Python toolchain first, then port the auth and helm layers behind typed Protocols (no behavior change), then layer the new v2 features (OIDC, OCI/repo charts, dry-run with PR comments, rollback, opt-in metadata) on top. Supply-chain modernization (multi-arch, Cosign keyless, SBOM, SLSA provenance, Trivy, pip-audit, release-please, GitHub Actions as the release source-of-truth) ships in one combined phase. A versioned `mkdocs-material` site with `mike` and a line-level v1→v2 migration guide is the final phase before tag-cut.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Toolchain & Spine** - `uv`/`ruff`/`mypy --strict`/`pytest`/`src/` layout, base Dockerfile, settings/logging/errors/pipe_io skeleton
- [x] **Phase 2: AWS Layer & Auth Foundation** - drop `awscli`, pure-`boto3` EKS token gen, `AuthStrategy` Protocol with static-keys + assume-role (v1 parity)
- [x] **Phase 3: Helm Core & Upgrade Action** - `HelmClient`, kubeconfig writer, `UpgradeAction`, local-path charts, `HISTORY_MAX`, v1-style metadata injection (v1 feature parity reached)
- [ ] **Phase 4: OIDC & Chart Source Extensions** - OIDC strategy + IAM trust template, `ChartSource` Protocol with repo + OCI sources + Cosign verify
- [ ] **Phase 5: Log Masking, Diff, Rollback & Metadata Flip** - `SEC-06` log redaction first, then `DiffAction` + PR-comment poster, `RollbackAction` + `SAFE_UPGRADE`, opt-in metadata default flip with v1 deprecation warning
- [ ] **Phase 6: Release Pipeline & Supply Chain** - GitHub Actions CI + release-please, multi-arch native-runner build, Cosign keyless, SBOM, SLSA provenance, Trivy + pip-audit at build, scheduled Trivy rescan + SARIF to Code Scanning, Dependabot with `fix(deps):` prefix for base-image patch releases, GitHub Private Vulnerability Reporting, branch protection, community ops
- [ ] **Phase 7: Documentation Site & Migration Guide** - `mkdocs-material` + `mike` v1/v2 spaces, ADRs, examples, `README` rewrite, line-level v1→v2 migration guide

## Phase Details

### Phase 1: Toolchain & Spine
**Goal**: A maintainer can clone the repo, run `uv sync --all-extras`, and get green `ruff`, `mypy --strict`, and `pytest` (with placeholder modules); the base Dockerfile builds for `linux/amd64` from `python:3.13-slim-bookworm` with OCI annotations and non-root user.
**Depends on**: Nothing (first phase)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, IMAGE-01, IMAGE-02, IMAGE-03, IMAGE-05, OBS-01, OBS-02
**Success Criteria** (what must be TRUE):
  1. `uv sync --all-extras` completes in under 10 seconds on a warm cache and produces a `.venv/` with all dev tools (TOOL-01).
  2. `ruff check`, `ruff format --check`, and `mypy --strict src/` exit 0 on the v2 source tree; `pre-commit run --all-files` runs the same checks locally (TOOL-03, TOOL-04, TOOL-05).
  3. `pytest --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` exits 0 on the placeholder skeleton; an integration target (`make integration-test` or `uv run pytest tests/integration`) provisions `kind` and runs at least one helm-on-cluster smoke test; the acceptance tier builds the image and runs `docker run` against it (TOOL-06, TOOL-07, TOOL-08).
  4. `docker build` produces a `linux/amd64` image from `python:3.13-slim-bookworm` with Helm 3.18.x + `helm-diff` 3.10.x bundled, running as `USER pipe` (uid ≥ 10000), with OCI annotations (`source`, `revision`, `version`, `licenses=Apache-2.0`, `title`, `description`) set via `buildx --annotation` (IMAGE-01, IMAGE-02, IMAGE-03, IMAGE-05).
  5. The pipe entrypoint emits human-readable logs by default and one JSON object per line on stderr when `LOG_FORMAT=json`, with stable field names (`action`, `cluster`, `release`, `namespace`, `chart_source`, `auth_strategy`, `duration_ms`); `DEBUG=true` raises verbosity to include resolved auth source and per-phase timings without leaking credentials (OBS-01, OBS-02).
**Plans**: TBD
**Risks**:
  - `uv` lockfile drift between local dev and CI (PITFALLS-style supply-chain risk). Mitigation: CI runs `uv sync --frozen` only; `uv.lock` must be committed and is gated by Dependabot.
  - `mypy --strict` plus `boto3-stubs` is famously noisy on first contact. Mitigation: scope strict mode to `src/` only on day one; defer `tests/` strictness to a follow-up plan inside Phase 1 if needed.
  - The `src/`-layout migration accidentally drops a v1 import path that a consumer's vendored fork relied on. Mitigation: v2.0 is a clean break — the migration guide (Phase 7) documents this explicitly; no compat shims.

### Phase 2: AWS Layer & Auth Foundation
**Goal**: The pipe authenticates to AWS using static keys and optional `ROLE_ARN` assumption through a typed `AuthStrategy` Protocol; EKS tokens are generated by pure `boto3` only; `awscli` is fully removed from the image. Functional parity with v1.x, new architecture.
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-07
**Success Criteria** (what must be TRUE):
  1. `src/aws_eks_helm_deploy/auth/base.py` defines the `AuthStrategy` Protocol and `AwsCredentials` value object; `static_keys.py` and `assume_role.py` are independent classes; `auth/__init__.py::select_strategy(settings)` composes `AssumeRoleStrategy` on top of any base strategy (AUTH-01, AUTH-02).
  2. `src/aws_eks_helm_deploy/aws/eks_token.py` generates a `k8s-aws-v1.<base64url-presigned-STS-URL>` token using only `boto3` (no `awscli`, no `awscli.customizations.eks.get_token` import); a golden unit test asserts the produced token equals `aws eks get-token` reference output byte-for-byte (AUTH-07).
  3. `pyproject.toml` declares `boto3` and removes `awscli`; `docker history` of the built image shows no `awscli` layer; runtime image size is measurably smaller than v1.x (target: > 100 MB reduction).
  4. Unit-test coverage is 100% line+branch for `auth/` and `aws/` modules (mocked via `moto` and `pytest-mock`); a `kind`-backed integration test proves `StaticKeysStrategy` + `AssumeRoleStrategy` produce a kubeconfig that `helm` accepts.
**Plans**: TBD
**Risks**:
  - EKS token format is undocumented as a stable contract; the presigned-URL 15-minute exclusive cluster-name header is easy to get wrong. Mitigation: golden test against `aws eks get-token` output on every PR; reference the `aws-iam-authenticator` repo header format.
  - `boto3` STS `assume_role` regional endpoint defaults differ from `awscli`. Mitigation: pin `AWS_STS_REGIONAL_ENDPOINTS=regional` explicitly in session config; document in CHANGELOG.
  - The `AuthStrategy` Protocol must accommodate OIDC in Phase 4 without refactor. Mitigation: design review at end of Phase 2 — write OIDC strategy *signature* (not impl) as a compile-only stub to prove the Protocol holds.

### Phase 3: Helm Core & Upgrade Action
**Goal**: `ACTION=upgrade` (default) deploys a local-path Helm chart to a real EKS cluster end-to-end via the new typed `HelmClient`, honouring `HISTORY_MAX` and v1-style Bitbucket metadata injection. v1.x functional parity is reached on the new architecture. Closes issue #17.
**Depends on**: Phase 2
**Requirements**: CHART-01, CHART-05, PIPE-01, PIPE-06, HISTORY-01, HISTORY-02, META-01
**Success Criteria** (what must be TRUE):
  1. `src/aws_eks_helm_deploy/kube/kubeconfig.py` writes a tempfile kubeconfig (context-managed, deleted on exit) from a `ClusterAccess` + `EksAuthToken`; `helm/client.py` is the only module that calls `subprocess.run` and exposes one typed method per helm subcommand (`upgrade_install`, `history`); `actions/upgrade.py` is < 50 lines and calls exactly one `HelmClient` method (CHART-01, PIPE-01).
  2. An integration test against `kind` deploys a minimal chart from a local path, asserts the success message contains the resolved chart name + version (CHART-05), and the exit code is 0; an induced helm failure surfaces via `bitbucket-pipes-toolkit.fail()` with a non-zero exit code and human-readable message (PIPE-06).
  3. When `HISTORY_MAX=5` is set, `helm history <release>` in the cluster returns at most 5 revisions after 6 upgrade rounds; when unset, default-10 behavior holds (HISTORY-01, HISTORY-02). Closes #17.
  4. When `INJECT_BITBUCKET_METADATA=true` and `BITBUCKET_BUILD_NUMBER`/etc. are set, the rendered chart receives `--set bitbucket.bitbucket_build_number=…` for all five documented keys; assertion via `helm get values <release>` in an integration test (META-01).
**Plans**: TBD
**Risks**:
  - `subprocess.run` timeouts and Helm Go-duration parsing have v1.x edge cases that the new typed wrapper might re-introduce. Mitigation: snapshot tests with `syrupy` on argv generation; preserve the existing v1 timeout-handling regression cases as integration fixtures.
  - `kind` cluster startup in CI is flaky on cold runners. Mitigation: cache `kind` node image; retry cluster creation up to 3 times; mark flake patterns explicitly with `pytest-rerunfailures`.
  - Helm release-history coupling with future rollback (Phase 5) — pruning too aggressively breaks rollback. Mitigation: document `HISTORY_MAX` ≥ rollback-target depth in the variable reference; warn in Phase 5 when `HISTORY_MAX < REVISION + 1`.

### Phase 4: OIDC & Chart Source Extensions
**Goal**: Consumers can authenticate via Bitbucket Pipelines OIDC (zero static keys) and pull charts from Helm repos or OCI registries with optional Cosign signature verification. Closes issues #3 and #7.
**Depends on**: Phase 3
**Requirements**: AUTH-03, AUTH-04, AUTH-05, AUTH-06, CHART-02, CHART-03, CHART-04
**Success Criteria** (what must be TRUE):
  1. `src/aws_eks_helm_deploy/auth/oidc.py` adds `OidcWebIdentityStrategy`; when ONLY `BITBUCKET_STEP_OIDC_TOKEN` + `OIDC_AUDIENCE` + `ROLE_ARN` are set (no static keys), the pipe exchanges the token for STS credentials via `AssumeRoleWithWebIdentity` (AUTH-03); when BOTH static keys AND an OIDC token are present, **static keys win** — mirrors the boto3 / AWS CLI default credential resolver chain (env-var provider precedes web-identity provider in `botocore.credentials.create_credential_resolver`); a one-time WARN log (`auth.precedence.static_keys_won_over_oidc`) surfaces this precedence (AUTH-04); misconfigurations (`ROLE_ARN` without base creds, `OIDC_AUDIENCE` without `ROLE_ARN`, `BITBUCKET_STEP_OIDC_TOKEN` without `ROLE_ARN`) raise `ConfigurationError` with a clear message before any AWS API call (AUTH-06).
  > 2026-06-18 revision: AUTH-04 wording superseded — see `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md` D1 for full rationale (boto3 default chain mirror; principle-of-least-surprise for AWS engineers).
  2. `docs/guides/oidc-setup.md` (drafted here, polished in Phase 7) ships an IAM trust-policy template that constrains `aud` and `sub` to `BITBUCKET_WORKSPACE_UUID:{uuid}` and `BITBUCKET_REPO_UUID:{uuid}`; a unit test asserts the template is valid JSON and references both UUIDs (AUTH-05).
  3. `src/aws_eks_helm_deploy/chart/base.py` defines `ChartSource` Protocol + `ResolvedChart` dataclass; `local.py`, `repo.py`, and `oci.py` are independent; `CHART=repo://name/chart` + `REPO_URL` + `CHART_VERSION` runs `helm repo add` before upgrade (CHART-02); `CHART=oci://registry/chart` + optional `REGISTRY_USERNAME`/`PASSWORD` + `CHART_VERSION` pulls via `helm pull oci://…` (CHART-03).
  4. `CHART_VERIFY=true` invokes Cosign verification of the OCI chart artifact; a failed signature aborts the upgrade with `ChartResolutionError` exit code (CHART-04); integration test uses a local `registry:2` container and a signed test chart.
**Plans**: TBD
**Risks**:
  - Bitbucket OIDC trust policy under-constrained (Pitfall #1). Mitigation: ship the IAM template with explicit `aud`/`sub` UUIDs; add a `terraform` snippet; surface a warning in the pipe log if the IAM role's trust policy can be introspected and is found permissive (best-effort).
  - OCI auth state leaking into `~/.docker/config.json` past invocation. Mitigation: use `helm registry login` only with `HELM_REGISTRY_CONFIG` pointed at the tempfile dir; cleanup on exit.
  - Cosign chart-verify path expands the runtime image size and pulls a new binary. Mitigation: install `cosign` in the same multi-stage builder as `helm`; verify cold-start budget is still under 10s with an explicit benchmark in CI.

### Phase 5: Log Masking, Diff, Rollback & Metadata Flip
**Goal**: Helm output emitted by the pipe never leaks `Secret` payloads; consumers can preview changes via `ACTION=diff` (or `DRY_RUN=true`) and optionally post the diff as a Bitbucket PR comment; `ACTION=rollback` is safe by default; `INJECT_BITBUCKET_METADATA` defaults to `false` (breaking change) with a loud deprecation warning when v1-style chart usage is detected. Closes issue #16 and addresses Pitfalls #2 and #3.
**Depends on**: Phase 4
**Requirements**: SEC-06, PIPE-02, PIPE-03, PIPE-04, PIPE-05, META-02, META-03, MIG-02
**Success Criteria** (what must be TRUE):
  1. The log-masking subsystem replaces the entire `data:`/`stringData:` block of any rendered `kind: Secret` manifest with `<redacted>` before the bytes leave the pipe (logs, stdout, PR comments); a unit test feeds a chart that emits Secrets and asserts no secret bytes appear in any captured output stream; this lands before any PIPE-03 wiring (SEC-06).
  2. `ACTION=diff` (or `DRY_RUN=true` on upgrade) runs `helm diff upgrade` via the bundled `helm-diff` 3.10 plugin and prints a colored diff to stdout without mutating the cluster (PIPE-02); when `$BITBUCKET_PR_ID` is set and `POST_DIFF_AS_COMMENT=true`, the (masked) diff is posted as a PR comment via the Bitbucket REST API using `BITBUCKET_TOKEN`; integration test asserts the API was called with the masked payload (PIPE-03).
  3. `ACTION=rollback` + `REVISION=<n>` invokes `helm rollback <release> <n>` (PIPE-04); when `SAFE_UPGRADE=true`, both `--wait` and `--atomic` are passed to upgrade and a pre-flight `helm history` check fails the action if the target revision was not deployed with `--wait` (PIPE-05).
  4. With `INJECT_BITBUCKET_METADATA` unset, no `bitbucket.*` values are injected (META-02 — breaking change vs v1); when the pipe detects the chart's `values.yaml` references `.Values.bitbucket.*` without `INJECT_BITBUCKET_METADATA` set, it logs a loud one-time WARN recommending explicit opt-in (META-03); v1-only env-var names (`SET` / `VALUES` in positional format) trigger a one-time deprecation warning at startup (MIG-02). Closes #16.
**Plans**: TBD
**Risks**:
  - Log masking misses a non-stdlib Helm output channel (e.g., `helm get manifest` consumed by a future feature). Mitigation: centralize the redactor in `helm/redact.py`; every `HelmClient` method routes captured output through it; a fuzz test feeds randomised chart fixtures.
  - The PR-comment poster leaks credentials in error paths if Bitbucket API returns 4xx. Mitigation: error handler scrubs `BITBUCKET_TOKEN` from any logged response body; integration test asserts an injected 401 response surfaces no token bytes.
  - `--atomic` + `HISTORY_MAX` interaction (Pitfall #3): a `--wait`-less prior revision breaks rollback target. Mitigation: `SAFE_UPGRADE` couples both flags; pre-flight `helm history` rejects rollback to unsafe revisions; documented in migration guide.

### Phase 6: Release Pipeline & Supply Chain
**Goal**: Every push to `main` produces a release-please PR that, when merged, builds a multi-arch (`linux/amd64` + `linux/arm64`) image on native runners, signs it with Cosign keyless, attaches SBOM (SPDX + CycloneDX) and SLSA provenance, runs Trivy + pip-audit as required PR gates, and pushes to `ghcr.io/yves-vogl/aws-eks-helm-deploy` (GitHub Container Registry is the **only** v2.0 publish target — Docker Hub is no longer used). Bitbucket-side becomes a thin mirror that only re-publishes the marketplace listing. Dependabot, branch protection, GPG-signed commits, issue/PR templates, GH Project board, and the label taxonomy are all live. Docker Hub `yvogl/aws-eks-helm-deploy` stays frozen at v1.3.0 as the v1.x archive; `:2` becomes the rolling v2 major tag on GHCR. A scheduled vulnerability-rescan workflow keeps the published image's CVE posture visible in the **Security** tab; Dependabot bumps of the base image cut `fix(deps):` Conventional Commits that drive `release-please` to publish freshly-scanned patch releases; GitHub Private Vulnerability Reporting is the disclosure channel.
**Depends on**: Phase 5
**Requirements**: IMAGE-04, IMAGE-06, SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-07, SEC-08, SEC-09, SEC-10, CI-01, CI-02, CI-03, CI-04, CI-05, CI-06, CI-07, CMN-01, CMN-02, CMN-03, CMN-04, MIG-01
**Success Criteria** (what must be TRUE):
  1. `.github/workflows/ci.yml` runs `ruff`, `mypy`, `pytest --cov`, `trivy` (image + Dockerfile + chart fixtures + secret-leak), and `pip-audit` on every PR; required status checks gate merge into `main`; CI fails on Trivy `CRITICAL`/`HIGH` unless suppressed in `.trivyignore` with rationale; CI fails on any unsuppressed `pip-audit` finding (CI-01, SEC-04, SEC-05).
  2. `.github/workflows/release.yml` is driven by `googleapis/release-please-action@v4` (`release-type: python`); a release-PR atomically updates `pyproject.toml`, `CHANGELOG.md`, and `pipe.yml` image-tag; on release-PR merge the workflow builds a multi-arch manifest on a native-runner matrix (`ubuntu-24.04` for amd64, `ubuntu-24.04-arm` for arm64 — no QEMU), signs with `cosign sign --bundle` (keyless via GitHub OIDC → Fulcio → Rekor), attaches Syft SBOM in **both** SPDX and CycloneDX, attaches `actions/attest-build-provenance@v1` SLSA provenance, and pushes the manifest to `ghcr.io/yves-vogl/aws-eks-helm-deploy` only (CI-02, CI-03, IMAGE-04, SEC-01, SEC-02, SEC-03).
  3. A documented cold-start benchmark (`scripts/benchmark-cold-start.sh`, run in CI, results in README badge) reports under 10 seconds on a GitHub-hosted runner with the image pre-pulled (IMAGE-06); `docker buildx imagetools inspect` of the released manifest shows two real arches (no QEMU layers).
  4. `.github/dependabot.yml` configures `pip`, `docker`, and `github-actions` weekly; `dependabot-auto-merge.yml` workflow auto-merges PRs (including major bumps) once required checks pass (CI-05); branch protection on `main` requires signed commits, 1+ review, required status checks, and disallows direct pushes; all commits on `main` are GPG-verified (CI-06, CI-07).
  5. `.github/ISSUE_TEMPLATE/bug_report.yml` + `feature_request.yml` require pipe version + runtime context + repro; `PULL_REQUEST_TEMPLATE.md` lists the merge checklist (tests, release-please entry, docs, ADR); the v2.0.0 GitHub Project board has `Backlog → Ready → In Progress → In Review → Done` columns auto-linked to the milestone; every open issue and PR carries `area/*`, `type/*`, `priority/*`, `breaking-change`, `good first issue`, `help wanted` labels per taxonomy (CMN-01, CMN-02, CMN-03, CMN-04).
  6. A minimal `bitbucket-pipelines.yml` continues to publish the Bitbucket Pipe Marketplace listing on tagged releases without building or pushing images (CI-04); the Docker Hub `yvogl/aws-eks-helm-deploy` repository stays at v1.3.0 as the frozen v1.x archive (no v2 image pushed there); a documented `:2` rolling tag is introduced on `ghcr.io/yves-vogl/aws-eks-helm-deploy` for major-pinned v2 consumers; Docker Hub's README is updated with a deprecation note pointing to GHCR (MIG-01).
  7. `.github/workflows/security-rescan.yml` runs `aquasecurity/trivy-action` on a daily cron against `ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` and `:2`; SARIF results upload to GitHub Code Scanning so the Security tab shows live CVE state; `CRITICAL` findings open an `area/security` + `priority/p0` issue, `HIGH` findings a `priority/p1` issue (deduped per digest+CVE) (SEC-07).
  8. `.github/dependabot.yml` configures the Docker base-image ecosystem with `commit-message: prefix: fix` so a `python:3.13-slim-bookworm` digest bump lands as a `fix(deps): bump base image` Conventional Commit; `release-please` recognises it as a `patch` bump and the next release-PR triggers `.github/workflows/release.yml` to re-publish a freshly-scanned image (SEC-08).
  9. **GitHub Private Vulnerability Reporting** is enabled (`Settings → Security → Private vulnerability reporting`); `SECURITY.md` documents the disclosure flow; published CVE responses live as **GitHub Security Advisories**, linked from `CHANGELOG.md` patch entries (SEC-09).
  10. `.github/workflows/scorecard.yml` (`ossf/scorecard-action@v2`, weekly cron + on-push to `main`) evaluates the repo against the OpenSSF Scorecard checks (Dependency-Update-Tool, Signed-Releases, Pinned-Dependencies, Branch-Protection, Code-Review, Token-Permissions, SAST, SBOM, Maintained, …) and uploads SARIF to GitHub Code Scanning; the README badge row carries a live link to `https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy/badge`; the achieved score at v2.0 tag-cut is **≥ 8/10**; any deliberate sub-check failure is documented in `.scorecard-exception.md` with rationale and review date (SEC-10).
**Plans**: TBD
**Risks**:
  - Cosign keyless three-way coupling (Pitfall #4): missing `id-token: write` permission at job inheritance, Rekor unavailability at verify time, Fulcio cert expiry mid-job. Mitigation: declare `permissions: id-token: write` at workflow level; always `cosign sign --bundle`; isolate signing in a short-lived job; verify-on-PR step on every release-please PR.
  - Multi-arch via QEMU silently produces broken arm64 (Pitfall #5). Mitigation: native ARM runners only (`ubuntu-24.04-arm`); `docker buildx imagetools inspect` post-build smoke test asserts both arches are present as real platforms; base image pinned by digest.
  - Dependabot auto-merge on majors lands a breaking transitive dependency. Mitigation: test-gate is the merge criterion; the 100% coverage requirement + integration + acceptance tiers detect behavioral regressions; rollback via revert-and-pin path documented in `CONTRIBUTING.md`.
  - Scheduled rescan opens noisy issues for unfixable transitive CVEs in the base image. Mitigation: `.trivyignore` carries each suppression with rationale + expiry date; issue-creator dedup keys on `(digest, cve_id)` so the same finding never opens twice; quarterly review prunes `.trivyignore`.
  - `fix(deps):` prefix on every Dependabot Docker bump triggers a release on each base-image patch — could be release-spammy. Mitigation: Dependabot grouping (`groups: docker: patterns: [docker, helm, helm-diff]`) batches multiple bumps into one PR per week.
  - Scorecard score regresses below the ≥ 8/10 target without anyone noticing (e.g. a contributor lands an unpinned action). Mitigation: weekly Scorecard SARIF surfaces failed sub-checks in the Security tab; the README badge being publicly visible creates social-cost pressure; `.scorecard-exception.md` only accepts time-bound entries with a documented re-review date.

### Phase 7: Documentation Site & Migration Guide
**Goal**: A maintainer landing on the README finds a 60-second quickstart and a link to a versioned `mkdocs-material` site with `/v1/` (frozen v1.3.0 reference) and `/v2/` (current); the migration guide is the headline page and is supported by a line-level before/after `bitbucket-pipelines.yml` diff under `examples/migration-v1-to-v2/`. ADRs cover every architectural decision. This is the final phase before the v2.0.0 tag-cut.
**Depends on**: Phase 6
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07, DOC-08, MIG-03
**Success Criteria** (what must be TRUE):
  1. `README.md` is the entry doc: badge row (license, release, GHCR image, build, coverage, Cosign-verified, sponsors, stars, open issues), 60-second quickstart with one `bitbucket-pipelines.yml` snippet, and prominent links to the docs site, marketplace listing, and migration guide (DOC-01).
  2. `mkdocs-material` + `mike` site is deployed to GitHub Pages via `.github/workflows/docs.yml`; `mike list` shows both `v1` (frozen snapshot of v1.3.0 reference) and `v2` (default); the variable reference under `/v2/reference/variables.md` is auto-generated by `scripts/generate-variables-doc.py` from `settings.py` and CI fails if the committed output drifts from the generator (DOC-02).
  3. `docs/migration/v1-to-v2.md` documents every breaking change (`INJECT_BITBUCKET_METADATA` default flip, removed/renamed env vars, `NAMESPACE` default correction, image-tag pinning policy including the `:latest` freeze + `:2` rolling tag); `examples/migration-v1-to-v2/` contains a before/after `bitbucket-pipelines.yml` diff with line-level explanations (DOC-03, MIG-03).
  4. `docs/adr/` contains MADR-template ADRs covering at minimum: GitHub primary forge, v2.0 clean break, Cosign keyless over GPG, `boto3`-only over `awscli`, `release-please` over `semversioner`, OIDC default behavior, multi-arch via native runners (DOC-04).
  5. `CONTRIBUTING.md`, `SECURITY.md` (private disclosure flow + v1.x 6-month support window), and `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) are present at repo root and linked from the docs site (DOC-05, DOC-06, DOC-07); `examples/` ships at least four end-to-end `bitbucket-pipelines.yml` files: basic, OIDC-only, OCI chart from GHCR, multi-env deploy with `helm-diff` PR comment (DOC-08).
**Plans**: TBD
**UI hint**: yes
**Risks**:
  - `mkdocs-material` entered maintenance mode early 2026; choosing it now invites a future migration to `Zensical`. Mitigation: scoped as a known v2.1+ track (see REQUIREMENTS DOC-NEXT-01); the 12-18 month horizon is acceptable for v2.0.
  - Variable-reference generator drifts from `settings.py` if a contributor edits the generated file directly. Mitigation: CI step diffs generator output against committed file; PR check fails on drift; banner comment in the generated file warns against manual edits.
  - The migration guide misses a real-world breaking change discovered post-release. Mitigation: a follow-up "lessons learned" pass in the first 30 days post-v2.0.0 adds any consumer-reported breakage; tracked via the `breaking-change` label on the GH Project board.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Toolchain & Spine | 0/TBD | Not started | - |
| 2. AWS Layer & Auth Foundation | 0/TBD | Not started | - |
| 3. Helm Core & Upgrade Action | 0/TBD | Not started | - |
| 4. OIDC & Chart Source Extensions | 0/TBD | Not started | - |
| 5. Log Masking, Diff, Rollback & Metadata Flip | 0/TBD | Not started | - |
| 6. Release Pipeline & Supply Chain | 0/TBD | Not started | - |
| 7. Documentation Site & Migration Guide | 0/TBD | Not started | - |
