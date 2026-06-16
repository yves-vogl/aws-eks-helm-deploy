# aws-eks-helm-deploy — v2.0 Modernization

## What This Is

`aws-eks-helm-deploy` is a Bitbucket Pipelines Pipe that deploys [Helm](https://helm.sh) charts to AWS Elastic Kubernetes Service (EKS) from a Bitbucket Pipeline. It wraps `helm upgrade --install` with on-the-fly EKS authentication (no `kubectl` install required in the consumer's pipeline image) and injects Bitbucket build metadata as Helm values. v1.3.0 is the current stable release on Docker Hub (`yvogl/aws-eks-helm-deploy`). This project tracks the **v2.0 modernization**: a state-of-the-art rewrite that moves development primary to GitHub, ships 100% test coverage, native AWS OIDC/IRSA, OCI/Helm-repo chart support, multi-arch signed images, and a fully automated GitHub Actions release pipeline.

## Core Value

**A maintainer can ship a Bitbucket Pipelines deployment to AWS EKS from a clean repository in under five minutes — without committing static AWS credentials and without surprises at upgrade time.** Every other concern (multi-arch, SBOM, OCI charts, rollback) is in service of that one promise. If that experience breaks, v2 has failed regardless of how clean the code is.

## Requirements

### Validated

<!-- Inherited from existing v1.x code — already shipped, in production use by 9+ public consumers. -->

- ✓ Deploys Helm charts to AWS EKS via `helm upgrade --install` — v1.x
- ✓ Authenticates to EKS using static AWS keys + optional `ROLE_ARN` STS assumption — v1.x
- ✓ Generates kubeconfig on the fly from `eks describe-cluster` + STS token — v1.x
- ✓ Supports `--namespace`, `--create-namespace`, `--set`, `--values`, `--wait`, `--timeout` (Go duration) — v1.x
- ✓ Injects Bitbucket build metadata (`bitbucket.bitbucket_build_number`, etc.) as Helm values — v1.x
- ✓ Apache-2.0 licensed, semversioner-managed CHANGELOG — v1.x
- ✓ Distributed as Docker Hub image `yvogl/aws-eks-helm-deploy` — v1.x

### Active

<!-- v2.0 scope. Hypotheses until shipped. -->

**Modernization baseline (functional parity + cleanup)**

- [ ] All Python source migrated to `src/` layout with `pyproject.toml`; `requirements.txt` removed
- [ ] Toolchain: `uv` for env/dependency management, `ruff` for lint+format, `mypy --strict` for typing, `pytest` for tests
- [ ] 100% unit-test line+branch coverage of `pipe/*` modules (mocked AWS, mocked Helm)
- [ ] Integration tests against a real local Kubernetes (`kind` or `k3d`) running real Helm
- [ ] Acceptance tests (Docker image invocation) retained and migrated to GitHub Actions
- [ ] `helm` invocation hardened: replace bare `subprocess.run` + `BaseException` with typed wrapper
- [ ] Replace `BaseException` subclasses with `Exception` subclasses; introduce a clear exception hierarchy
- [ ] Replace fragile `awscli.customizations.eks.get_token` internal import with `boto3`-only EKS token generation
- [ ] Drop the heavyweight `awscli` dependency in favor of `boto3` (already pulled in transitively)
- [ ] Fix `NAMESPACE` default inconsistency (README says `kube-public`, `pipe.yml` says `default`) → choose `default`, document in CHANGELOG
- [ ] OCI image labels (OCI annotations: source, revision, licenses, description)
- [ ] Multi-arch image build: `linux/amd64` + `linux/arm64`

**New features (v2.0 scope, on top of baseline)**

- [ ] **AWS OIDC / IRSA** as first-class authentication path — Bitbucket OIDC token → STS `AssumeRoleWithWebIdentity` → EKS token. Static keys remain as a fallback. (Closes Bitbucket Pipelines OIDC support gap — see #3.)
- [ ] **Helm repository and OCI chart support** — `CHART` accepts `oci://…`, `repo://…/chart`, plus `CHART_VERSION` and `REPO_URL` variables. (Closes #7.)
- [ ] **Dry-run / diff preview** — `DRY_RUN=true` runs `helm diff upgrade` (requires bundled `helm-diff` plugin) and surfaces the diff in pipeline logs for PR-preview workflows. No mutation against the cluster.
- [ ] **Rollback subcommand** — `ACTION=rollback` with `REVISION=<n>` triggers `helm rollback` instead of `upgrade --install`.
- [ ] **Release history pruning** — `HISTORY_MAX` variable wraps `helm --history-max`. (Closes #17.)
- [ ] **Opt-in Bitbucket metadata injection** — `INJECT_BITBUCKET_METADATA` variable, default `false` in v2 (was unconditional in v1). Breaking change. (Closes #16.)

**Distribution and supply-chain modernization**

- [ ] GitHub Actions release pipeline as the new source-of-truth (Bitbucket Pipelines becomes a thin mirror that only re-publishes the Pipe Marketplace listing)
- [ ] Conventional-Commits → automatic SemVer via `release-please` (replaces `semversioner` + `.changes/`)
- [ ] v2.0 Docker images pushed to **GitHub Container Registry only** (`ghcr.io/yves-vogl/aws-eks-helm-deploy`); Docker Hub (`yvogl/aws-eks-helm-deploy`) stays frozen at v1.3.0 as the v1.x archive
- [ ] Image signed with **Cosign** (keyless, GitHub Actions OIDC); SBOM published as image attestation (Syft + SPDX or CycloneDX)
- [ ] **Trivy** vulnerability scan as a CI gate on every build (image + Dockerfile + Helm-chart fixtures + secret-leak patterns)
- [ ] **pip-audit** dependency scan as a CI gate
- [ ] **Scheduled Trivy rescan** of the published GHCR image (daily cron); SARIF results upload to GitHub Code Scanning, `CRITICAL`/`HIGH` findings auto-open issues
- [ ] **Dependabot** for Python + Docker + GitHub Actions; base-image bumps use `fix(deps):` prefix so `release-please` cuts a patch release that re-publishes a freshly-scanned image
- [ ] **GitHub Private Vulnerability Reporting** as the CVE disclosure channel; responses published as GitHub Security Advisories linked from `CHANGELOG.md` patch entries
- [ ] Branch protection on `main` (signed commits, required reviews, required status checks)

**Documentation and community**

- [ ] **ADRs** (`docs/adr/`) for every architectural decision (forge primacy, OIDC over static keys, GitHub Actions over Bitbucket Pipelines for release, Cosign over GPG image signing, etc.)
- [ ] `CONTRIBUTING.md` with dev-loop instructions (`uv sync`, `ruff check`, `pytest`, `kind` setup)
- [ ] `SECURITY.md` with private-disclosure flow and supported-version policy
- [ ] `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1)
- [ ] `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml` + `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `examples/` directory with end-to-end `bitbucket-pipelines.yml` snippets per common scenario (basic, multi-env deployments, OIDC, OCI chart)
- [ ] Versioned documentation: `docs/v1/` retains v1.x usage, `docs/v2/` for v2 (`mkdocs-material` or similar, hosted via GitHub Pages — TBD by research)
- [ ] **Migration guide** v1 → v2 documenting every breaking change

### Out of Scope

<!-- Explicit boundaries with reasoning. Do not re-add without explicit revisit. -->

- **GitHub Actions as a first-party invocation surface** — This is a Bitbucket Pipelines Pipe. GitHub Actions consumers are pointed at `aws-actions/configure-aws-credentials` + a Helm action. Reason: the Bitbucket Pipes Toolkit shapes the entire env-var-driven invocation contract; turning this into an Action would be a different project.
- **Multi-cluster atomic deploy in one Pipe call** — Composability via multiple pipe steps in `bitbucket-pipelines.yml` is sufficient. Reason: complexity blast radius too high for v2.0 timeline.
- **GUI / web frontend** — The product is a CI Pipe. Reason: not applicable.
- **Self-hosting helm chart of this pipe** — out of scope; this is a CLI-style container, not a service.
- **Kubernetes-in-Kubernetes nested cluster deployment** — not in EKS focus area. Reason: scope creep.
- **GPG signing of Docker images** — replaced by Cosign keyless signing. Reason: GPG image signing is dead-tech for OCI distribution.
- **`semversioner`-managed releases** — replaced by `release-please` driven by Conventional Commits. Reason: tighter GitHub-Actions integration and Conventional-Commit alignment.

## Context

**Existing user base:**
- Public GitHub repo: 9 stars, 15 forks, **2 open issues** (now triaged to v2.0.0 milestone), 10 closed PRs.
- Docker Hub: `yvogl/aws-eks-helm-deploy` with measurable pull activity (badge in README).
- Real consumers exist and pin to `:1.3.0` — **v2.0 is a clean break, marked clearly, with v1.x supported via existing image tags** (no rebuild).

**Active backlog ingested into v2.0 (GitHub milestone v2.0.0):**
- [#17 — `--history-max` support](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/17) — community-suggested, simple integration
- [#16 — opt-out for injected Bitbucket metadata](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/16) — chart-schema-validation conflict; in v2 the default flips to opt-in (breaking change)
- [#3 — OIDC support](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/3) (closed but never implemented) — re-prioritized as a v2.0 baseline feature
- [#7 — chart repo / version support](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/7) (closed but never implemented) — re-prioritized

**Tech baseline of v1.3.0 (the modernization starting point):**
- Python with `requirements.txt`: `awscli ~=1.32`, `bitbucket-pipes-toolkit ~=4.4`, `docker ~=7.1`, `Jinja2 ~=3.1`, `MarkupSafe ~=2.1`
- Source layout: `pipe/{pipe.py, schema.py, test.py, eks/, helm/, templates/}` — flat, no `src/`
- Helm `3.15.1` from `alpine/helm` base; image base `python:3-alpine`
- Tests: **acceptance only** (`test/acceptance/test_pipe.py` builds the image and runs `docker run` with mocked Helm via `/opt/pipe/test.py`); **no unit tests, no `pytest-cov`, no lint, no type check**
- CI: Bitbucket Pipelines runs acceptance tests on every push, then on main pushes via `bitbucketpipelines/bitbucket-pipe-release:5.6.1` to Docker Hub
- Releases: `semversioner add-change --type {major|minor|patch} --description "..."` writes `.changes/next-release/*.json`; on main merge, the Bitbucket release pipe bumps version, regenerates `CHANGELOG.md`, updates `pipe.yml` + README version, tags, pushes to Docker Hub
- Code style: 2-space indents (non-PEP8), no type hints, no formatter config, `BaseException` subclasses

**Maintainer constraints (project-specific carry-over from user-global standards):**
- All technical artefacts in English (code, commits, PRs, ADRs, READMEs, docstrings)
- All commits and tags must be GPG-signed (`commit.gpgsign=true`, signing key on file)
- Conventional Commits everywhere
- Never commit directly to `main` — all changes via feature branch + PR
- No AI/Claude attribution in commits, PRs, or any artefact (maintainer is the only listed author)
- Maximum cost discipline: Sonnet for implementation subagents, Opus reserved for strategy and review

## Constraints

- **Distribution channel**: Bitbucket Pipes Marketplace requires `pipe.yml` + Docker Hub image + Bitbucket-hosted listing repo. Bitbucket-side mirror must remain functional even when GitHub becomes primary.
- **Backwards compatibility**: v2.0 is a **clean major-version break**. The promise to existing v1.x consumers is "your pinned image keeps working forever" — not "v2 is a drop-in replacement". Every breaking change is explicit in the migration guide.
- **Auth**: AWS OIDC requires Bitbucket Pipelines to issue the OIDC token (`BITBUCKET_STEP_OIDC_TOKEN`) and the configured AWS IAM role to trust the Bitbucket OIDC provider. The pipe itself only exchanges the token via STS — IAM setup is the consumer's responsibility (documented).
- **Helm version skew**: The bundled Helm version dictates which Kubernetes minor versions the pipe supports (see Helm version skew policy). v2.0 ships with Helm 3.16+ at minimum; pinning policy is one of the ADRs.
- **Performance**: cold pipe execution should complete in under 60 seconds for a trivial chart on a small EKS cluster (no regression from v1.3.0). The full `awscli` dependency is the current latency hotspot.
- **Security**: no long-lived secrets in pipe code or image. OIDC keyless signing requires GitHub Actions to be the release driver (not Bitbucket).
- **Test infrastructure**: a Bitbucket account is required for end-to-end pipe acceptance tests (must run inside Bitbucket Pipelines to exercise the real `bitbucket-pipes-toolkit` runtime). Unit + Kubernetes-integration tests run on GitHub Actions.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GitHub becomes primary forge; Bitbucket reduces to read-only mirror + Pipe-Marketplace publishing | Modern security toolchain (OIDC, Cosign, Dependabot) lives in GitHub Actions; PR/issue community is larger on GitHub | — Pending |
| v2.0 is a clean break, not backwards-compatible with v1.x | Allows fixing the `NAMESPACE` default bug, flipping `INJECT_BITBUCKET_METADATA` to off, and renaming variables for clarity | — Pending |
| `release-please` replaces `semversioner` | Tighter Conventional-Commits + GitHub-native release flow; eliminates `.changes/` ceremony | — Pending |
| Cosign keyless signing replaces unsigned Docker images | OIDC-driven, no key management, OCI-native | — Pending |
| `boto3`-only for EKS token generation (drop full `awscli`) | Removes ~120 MB and a fragile internal import (`awscli.customizations.eks.get_token`) | — Pending |
| `uv` for dependency and venv management | Fastest modern Python tooling, lockfile-driven, replaces ad-hoc `pip install -r requirements.txt` | — Pending |
| Bundle `helm-diff` plugin in the image for dry-run support | Required for the `DRY_RUN` feature; small footprint | — Pending |
| Documentation site (`mkdocs-material` vs. GitHub Pages from README only) | TBD by research phase | — Pending |
| Multi-arch image (`linux/amd64` + `linux/arm64`) | Apple Silicon developers can pull the image locally; some EKS Graviton runners; cost negligible with `docker buildx` | — Pending |
| **GitHub Container Registry (`ghcr.io`) as the sole v2.0 publish target** (Docker Hub frozen at v1.3.0, no v2 image pushed there) | Eliminates `DOCKER_HUB_PAT` as a long-lived CI secret (OIDC push from GH Actions); keeps SLSA provenance + Cosign keyless inside a single trust domain; no anonymous-pull rate limit; Bitbucket Pipelines can pull from GHCR without auth | — Pending (decided 2026-06-16) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-16 after initialization*
