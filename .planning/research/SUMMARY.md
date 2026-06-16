# Research Summary — aws-eks-helm-deploy v2.0

**Domain:** Bitbucket Pipelines Pipe — Helm chart deployment to AWS EKS
**Synthesized from:** STACK.md · FEATURES.md · ARCHITECTURE.md · PITFALLS.md
**Date:** 2026-06-16
**Confidence:** HIGH (all four research dimensions converged on the same conclusions for the load-bearing decisions)

---

## 1. The 60-second TL;DR

v2.0 is **best-in-class by being first to ship supply-chain modernization in the Bitbucket Pipe ecosystem**, not by adding more deployment knobs. The Atlassian baseline has neither OIDC nor Helm support; no Pipe ships a Cosign-signed image with SBOM. By dropping `awscli` in favor of pure `boto3`, the cold-start budget goes from ~25 s to a defensible sub-10 s — a marketing claim no competitor currently makes. The three load-bearing architectural decisions are: **(a)** a `Protocol`-based `AuthStrategy` with `AssumeRoleStrategy` as a composable decorator (so OIDC + role-assume is free), **(b)** a `ChartSource` Protocol mirroring auth (local / repo / OCI as orthogonal strategies), **(c)** a `helm/` module that only sees a `KUBECONFIG` env var, never auth or chart-source state.

The three highest-blast-radius pitfalls are **(1)** under-constrained Bitbucket OIDC trust policies (consumer-side IAM mistake, our doc problem), **(2)** the `INJECT_BITBUCKET_METADATA: false` default flip silently breaking v1 consumers, and **(3)** multi-arch QEMU producing broken arm64 images that are invisible from Bitbucket's amd64-only runners.

---

## 2. Decision Sheet

The chosen tool + version + one-line "why" for every slot the roadmap needs to fill. All HIGH confidence unless noted.

### Language & runtime

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| Python version | CPython | 3.13 | EOL 2029-10; PEP-695 generic syntax; supported by `boto3`, `mypy`, `ruff`. |
| Base image | `python:3.13-slim-bookworm` | latest digest | **NOT alpine** — musl-libc breaks `boto3` wheel availability and slows builds. |
| Package manager + env | `uv` | 0.11.x | Single Rust binary, 10–100× faster than Poetry, PEP-751-compatible `uv.lock`. |
| Dependency resolution | `uv lock` + `uv sync --frozen --no-dev` | — | Reproducible Docker builds without dev tooling. |

### Code quality

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| Lint + format + import-sort + security | `ruff` | 0.15.x | Single binary replaces `black + isort + flake8 + pyupgrade + pydocstyle + bandit`. |
| Type checker | `mypy --strict` | ~=1.18 | mypyc-compiled (now ≈ pyright speed); strongest `boto3-stubs` ecosystem. |
| Type-check escape hatch | `basedpyright` | latest | Reserved for narrow corners where mypy is wrong. |
| Pre-commit | `pre-commit` | ≥4.0 | Same checks locally + CI. |

### Tests

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| Runner | `pytest` | ≥8.4 | Standard. |
| Coverage | `pytest-cov` + `coverage[toml]` | latest | Line + branch coverage; integrate into `pyproject.toml`. |
| AWS mocks | `moto` | ≥5.0 | Drop-in `boto3` stub for unit tests. |
| Kubernetes integration | `kind` | ≥0.29 | Lightest local-cluster runner. `k3d` rejected: extra Rancher dependency. |
| Acceptance | existing Docker-image-spawn pattern, ported to GitHub Actions | — | Real `bitbucket-pipes-toolkit` runtime exercised via the image itself. |
| Snapshot | `syrupy` | latest | For Helm-argv generation tests. |

### Supply chain & release

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| Release automation | `release-please` (GitHub Action `googleapis/release-please-action@v4`) | v4 | PR-based release (matches "no direct push to main"); `release-type: python` + `extra-files` updates `pipe.yml` image tag atomically with `pyproject.toml`. **Rejects `python-semantic-release`** (pushes to `main` directly). |
| Image registry, primary | GHCR (`ghcr.io/yves-vogl/aws-eks-helm-deploy`) | — | Primary publish target; Cosign keyless integrates natively. |
| Image registry, secondary | Docker Hub (`yvogl/aws-eks-helm-deploy`) | — | Preserves the v1.x discovery path for existing consumers and the Bitbucket Pipe Marketplace expectation. |
| Image signing | `cosign sign` | 2.4 | **Keyless** via GitHub OIDC → Fulcio → Rekor. Zero key management. |
| SBOM | `syft` | 1.42 | Emit **both** SPDX and CycloneDX; attach as Cosign attestations. |
| Vuln scan | `trivy` | 0.59 | **Beats Grype** — covers image + Dockerfile + Helm chart + secret-leak in one binary; mitigate noise via `.trivyignore`. |
| Python dep audit | `pip-audit` | latest | Gates on PyPI advisory DB. |
| Provenance | `actions/attest-build-provenance@v1` | v1 | SLSA provenance attestation. |
| Dependency bot | Dependabot | — | Python + Docker + GH Actions; auto-merge when CI green (incl. major bumps, per maintainer policy). |

### AWS + Helm

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| AWS SDK | `boto3` only | ~=1.40 | **Drop `awscli` entirely** — saves ~120 MB, kills the fragile `awscli.customizations.eks.get_token` internal import. The pre-signed-STS-URL → `k8s-aws-v1.` token can be implemented in ~40 lines of `boto3` + base64url. |
| Helm | binary, copied multi-stage from `alpine/helm:3.18` | 3.18 | Active Helm release at v2.0 cut. |
| `helm-diff` plugin | bundled in the image | 3.10 | Required for `DRY_RUN` and for the **D-1 PR-comment differentiator**. |
| Pydantic settings | `pydantic-settings` | ≥2.5 | Single source of truth for the env-var schema; replaces hand-rolled validation. |

### Multi-arch build

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| Builder | `docker buildx` with **native runners per arch** | — | `ubuntu-24.04` for amd64 + `ubuntu-24.04-arm` for arm64 in a matrix; merge to one manifest. **QEMU rejected** — silently produces broken arm64 (Pitfall #5). |
| Build cache | GHA cache backend | — | `type=gha,mode=max`. |

### Documentation

| Slot | Choice | Version | Why |
|------|--------|---------|-----|
| Docs site | `mkdocs-material` + `mike` (versioned) | 9.5 + latest | Mike provides `/v1/` and `/v2/` URL spaces side-by-side; required for the v1→v2 migration guide. |
| Hosting | GitHub Pages | — | Free, owned by GitHub, no extra infra. |
| Future migration target | `Zensical` | TBD | **MEDIUM confidence** — `mkdocs-material` entered maintenance mode early 2026; track as v2.1+ migration. |

---

## 3. Top 3 Differentiators (advertise these)

1. **First Bitbucket Pipe with Cosign-signed image + SBOM + SLSA provenance.** No Pipe in the marketplace ships this as of mid-2026. The work is already in scope for v2.0; the marketing claim is free.
2. **Sub-10-second cold start.** Documented benchmark in README. Achieved by dropping the full `awscli` package and using `python:3.13-slim` over `python:3-alpine`. No competitor advertises cold-start time today.
3. **Helm-diff posted as a Bitbucket PR comment in `DRY_RUN` mode.** Genuinely novel in the Pipe ecosystem; `BITBUCKET_TOKEN` is auto-provided in Pipelines so the consumer needs no secret config. **Hard prerequisite:** the log-masking work (TS-9) must land first or this becomes a credential-leak vector (`helm get manifest` prints rendered `Secret` blocks in plaintext).

---

## 4. Top 5 Pitfalls (highest blast radius)

1. **Bitbucket OIDC trust policy under-constrained.** Permissive `aud`/`sub` templates allow any Bitbucket workspace to assume the role. **Mitigation:** ship a documented IAM trust-policy template scoped to `BITBUCKET_WORKSPACE_UUID` + repo UUID; provide a `terraform`/`cdk` snippet. **Phase:** OIDC implementation.
2. **`INJECT_BITBUCKET_METADATA: false` default flip silently breaks v1 consumers.** Charts referencing `.Values.bitbucket.*` template-fail at deploy time. **Mitigation:** detect prior-revision dependency in the new image; warn loudly on first-run; pin Docker Hub `:latest` to v1.3.0 forever, document `:2` rolling tag for opt-in. **Phase:** Migration guide + the metadata feature itself.
3. **Helm `--atomic`/`--wait` + rollback + `HISTORY_MAX` coupling.** A `--wait`-less previous revision breaks rollback to it; `HISTORY_MAX` pruning compounds the failure mode. Worst case: production traffic on a half-deployed release. **Mitigation:** single `SAFE_UPGRADE` flag couples `--wait` + `--atomic`; rollback runs a pre-flight `helm history` check. **Phase:** Rollback subcommand + #17 (ship together).
4. **Cosign keyless — three coupled failure modes:** dropped `id-token: write` permission (job-level inheritance), Rekor unavailable at verify time (no offline bundle), Fulcio cert expiry mid-job. **Mitigation:** workflow-level `permissions: id-token: write`, always `cosign sign --bundle`, separate short-lived signing job, verify-in-CI on every PR. **Phase:** Supply-chain modernization.
5. **Multi-arch QEMU silently produces broken arm64.** Invisible from amd64-only Bitbucket runners; explodes on Apple Silicon developers and EKS Graviton nodes. **Mitigation:** native ARM runner matrix on GitHub Actions; `docker buildx imagetools inspect` smoke-test post-build; base image pinned by digest. **Phase:** Multi-arch image build + GHA release.

---

## 5. Cross-file conflicts & resolutions

| Conflict | Resolution | Rationale |
|----------|------------|-----------|
| STACK recommends `python:3.13-slim-bookworm` (Debian), legacy Pipe uses `python:3-alpine`. | **Adopt Debian-slim.** | Eliminates musl-libc + `boto3` wheel quirks; image size delta is acceptable for the auth/cold-start wins. |
| FEATURES proposes the PR-comment `helm-diff` differentiator (D-1); PITFALLS flags Helm output as a credential-leak vector (TS-9). | **Build D-1 only after the log-masking subsystem ships.** | Reordering moves the log-masking work to a precondition phase, not a follow-up. |
| ARCHITECTURE proposes 10-phase build order; FEATURES sizes most table-stakes as S/M with explicit dependencies. | **Phase plan follows ARCHITECTURE's order; FEATURES sizing seeds per-phase plan creation.** | Single source of truth for build sequence is the dependency graph. |
| STACK rates `mkdocs-material` MEDIUM confidence (maintenance mode). | **Use `mkdocs-material` for v2.0; track `Zensical` as v2.1+ migration target.** | 12–18 month horizon is sufficient; migration premature now. |
| Existing v1.x bundles full `awscli`; STACK + FEATURES both recommend dropping it. | **Drop `awscli` entirely in v2.0.** | Frees ~120 MB, removes fragile internal-import path, enables sub-10 s cold-start claim. Documented in migration guide. |

---

## 6. Phase-sequencing implications

The research files together imply a non-negotiable ordering for v2.0:

1. **Project & toolchain bootstrap** — `pyproject.toml`, `uv`, `ruff`, `mypy`, `pytest`, repo restructure to `src/aws_eks_helm_deploy/...`, pre-commit. Nothing else can start until lint + types + tests are green on the existing v1.x logic.
2. **Auth strategy abstraction (no behavior change)** — extract `AuthStrategy` Protocol from current code, port static-keys + assume-role behind it. Pure refactor. Unblocks OIDC as an additive strategy.
3. **`boto3`-only EKS token generation** — replace `awscli.customizations.eks.get_token` with ~40-line `boto3` implementation. Unit-test with `moto`.
4. **Chart source abstraction (no behavior change)** — extract `ChartSource` Protocol; port local-path behind it. Unblocks OCI + repo as additive strategies.
5. **Bitbucket OIDC strategy** — adds `OidcWebIdentityStrategy`; includes the IAM trust-policy template + documented `aud`/`sub` constraints. **(Pitfall #1.)**
6. **OCI + repo chart sources** — adds `OciChartSource`, `RepoChartSource` + `CHART_VERSION`, `REPO_URL` vars.
7. **Log masking subsystem** — must land before D-1. Redacts `kind: Secret` payloads from any Helm output the pipe emits. **(Differentiator #3 precondition.)**
8. **Dry-run + helm-diff bundling + PR-comment poster** — `ACTION=diff` or `DRY_RUN=true`. **(Differentiator #3.)**
9. **Rollback subcommand** — `ACTION=rollback` + `REVISION` + `HISTORY_MAX` via `--history-max`. Ships with the `SAFE_UPGRADE` flag. **(Pitfall #3 + closes #17.)**
10. **Opt-in metadata injection** — flip the default; ship loud warning when v1 chart references detected. **(Pitfall #2 + closes #16.)**
11. **Multi-stage multi-arch image + Cosign + SBOM + Trivy + pip-audit** — GitHub Actions release pipeline. Native ARM runners, no QEMU. **(Differentiator #1 + Pitfall #4, #5.)**
12. **Documentation site** — `mkdocs-material` + `mike`, v1.x and v2 spaces side-by-side, migration guide is the headline page.
13. **Bitbucket-side discovery pipeline (mirror-only)** — minimal `bitbucket-pipelines.yml` that re-publishes the marketplace listing; no release responsibilities.

Phases 5/6, 8/9, 10 can be parallelized once 1–4 land.

---

## 7. Confidence calibration

- **HIGH:** every tool choice in §2, every differentiator in §3, pitfalls 1–3 and 5 in §4, all conflict resolutions in §5.
- **MEDIUM:** `mkdocs-material` choice (12–18 month horizon only), Cosign-keyless pitfall #4 (depends on Sigstore stability through 2026).
- **LOW:** none — every load-bearing decision is HIGH; the research convergence is unusually strong because the project scope is well-bounded.

---

## 8. Source attribution

Detailed analysis, citations, and full tables live in the four sibling files:

- [`STACK.md`](STACK.md) — concrete tool versions + anti-recommendations
- [`FEATURES.md`](FEATURES.md) — table-stakes / differentiators / anti-features with sizing + dependencies
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full `src/` layout, component graph, test pyramid, Dockerfile shape
- [`PITFALLS.md`](PITFALLS.md) — 13 pitfalls with warning signs + prevention + phase mapping + external sources

This SUMMARY.md is the decision sheet; the four files are the evidence.
