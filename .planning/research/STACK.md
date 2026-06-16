# Stack Research

**Domain:** CI-pipeline Docker container (Python) wrapping `helm` + AWS SDK, distributed as a Bitbucket Pipes Marketplace pipe; primary forge = GitHub
**Researched:** 2026-06-16
**Confidence:** HIGH (toolchain), MEDIUM (docs system — Material-for-MkDocs is in maintenance mode; safe for 12-18 months but Zensical migration looms)

## Scope Reminder

This stack covers the **v2.0 modernization**: replacing v1.3.0's ad-hoc `requirements.txt` + `awscli` + `semversioner` + Bitbucket-Pipelines-only setup with a 2026 SOTA equivalent. The v1.x stack is treated as the baseline being replaced; recommendations below are the targets.

---

## Recommended Stack

### (A) Runtime / Container

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | **3.13** (CPython, on slim image) | Pipe runtime | 3.13 is the current security-supported minor (3.14 lands EOL-2030); 3.13 has the new free-threading prelude and stable `typing.TypedDict` features used by `pyproject.toml` consumers. v1.x runs on `python:3-alpine` which floats — pinning to 3.13 fixes the implicit-bump foot-gun. |
| Base image | **`python:3.13-slim-bookworm`** (Debian) | Build & runtime | Switch away from `alpine`. Alpine's musl libc is a perennial source of `boto3`/`urllib3`/`grpcio` wheel-availability and DNS-resolution bugs, and the savings vs. Debian-slim are ~20 MB after multi-stage build. For an Apache-2.0 OSS pipe used by 9+ public consumers, fewer surprises > 20 MB. |
| Helm | **3.18.x** (latest stable in the 3.x line) | Chart engine | Bump from v1.x's pinned `3.15.1`. 3.16+ is required for the OIDC/IRSA and OCI-stable feature matrix the project commits to. Use `alpine/helm:3.18` as a build-stage source and `COPY --from=...` the binary into the Debian runtime — avoids re-implementing Helm-build logic. |
| `helm-diff` plugin | **3.10.x** | `DRY_RUN` preview | Required by the new `DRY_RUN` feature (PROJECT.md "Active"). Install via `helm plugin install` during image build. |
| `aws-iam-authenticator` | **NOT USED** | — | Not needed. `boto3` + a hand-rolled presigned-URL `eks get-token` (see (B)) eliminates the binary entirely. |

### (B) Python Application Dependencies

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| `boto3` | **~=1.40** | AWS SDK | Replaces full `awscli ~=1.32` (~120 MB saved per PROJECT.md "Key Decisions"). Generate the EKS token by signing an STS `GetCallerIdentity` presigned URL (the documented mechanism — `kind: ExecCredential` payload that `aws eks get-token` produces is reproducible in ~30 lines of Python). |
| `botocore` | (transitive via `boto3`) | low-level signer | Used directly for the EKS-token presigning step (`botocore.signers.RequestSigner`). |
| `eks-token` | **~=0.4** (OR roll our own) | Optional helper | If we want zero hand-rolled crypto, the `eks-token` PyPI package wraps the STS-presign flow in one call. **Recommendation: roll our own (~30 LOC)** — adds an ADR-worthy decision, but kills another transitive dependency and we already need typed `boto3` calls. Mark as **MEDIUM confidence**: revisit if the token logic grows beyond 50 LOC. |
| `bitbucket-pipes-toolkit` | **~=4.6** (latest) | Pipe contract / env-var handling / logging | Required by the Bitbucket Pipes Marketplace listing — non-negotiable. Bump from v1.x's `~=4.4`. |
| `Jinja2` | **~=3.1** | kubeconfig + values templating | Already used in v1.x for kubeconfig rendering; keep. No SOTA replacement that is materially better for this small templating surface. |
| `PyYAML` | **~=6.0** | YAML parsing for chart values / `pipe.yml` | Standard. Used implicitly via `bitbucket-pipes-toolkit` already; pin explicitly. |
| `pydantic` | **NOT USED** for v2.0 | — | Tempting for schema validation, but `bitbucket-pipes-toolkit` already has its own `schema` validator and adding Pydantic v2 bloats the wheel set for marginal value. Revisit if schema complexity grows. **Mark MEDIUM: reconsider in v2.1.** |
| `awscli` | **REMOVED** | — | Per PROJECT.md "Key Decisions". Drop entirely. |

### (C) Development Toolchain

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **`uv`** | **0.11.x** (latest 0.11 line) | Env + dependency + lock + project manager | **Decision: `uv` over `poetry`/`pdm`.** `uv` is 10-100× faster than poetry, writes a PEP 751-compatible `uv.lock`, supports `uv sync --frozen --no-dev` for reproducible Docker builds, and is the default in 2026 greenfield Python. Yves' user-global rules favor `uv` explicitly. Confidence: **HIGH**. |
| **`ruff`** | **0.15.x** (latest, ships the "2026 style guide") | Lint + format + import-sort | **Decision: `ruff` replaces `black + isort + flake8 + pyupgrade + pydocstyle` entirely.** One binary, one config (`[tool.ruff]` in `pyproject.toml`), single source of truth. Ruff 0.15's formatter is now a fully credible Black replacement. Confidence: **HIGH**. |
| **`mypy`** | **~=1.18** with `--strict` | Static type-check | **Decision: `mypy --strict` over `pyright`.** Rationale: (1) `mypy` runs natively as a Python tool — fits the `uv`-managed dev env without a Node toolchain; (2) the 1.18+ mypyc-compiled wheel is now competitive with pyright on speed; (3) `boto3-stubs` and `bitbucket-pipes-toolkit` ecosystem integration is better tested under mypy. **Caveat**: if dev experience suffers, fall back to `basedpyright` (the community fork with strict-by-default) — leave that as an escape hatch. Confidence: **HIGH** for mypy, MEDIUM for the no-pyright recommendation. |
| `boto3-stubs[eks,sts]` | **latest** | Type stubs for the only AWS services we touch | Required for `mypy --strict` to type-check `boto3` calls. Only install the `eks` + `sts` extras — full `boto3-stubs[essential]` is ~80 MB. |
| `pytest` | **~=8.4** | Test runner | Industry default; v1.x already uses it for acceptance tests. |
| `pytest-cov` | **~=7.1** | Coverage | Wraps `coverage.py`. Required for the 100% line+branch coverage goal. Configure with `--cov-branch --cov-fail-under=100`. |
| `pytest-mock` | **~=3.14** | `mocker` fixture | Cleaner than `unittest.mock.patch` decorators for mocking `subprocess`, `boto3` clients, and the Helm wrapper. |
| `pytest-xdist` | **~=3.6** | Parallel test execution | Speeds the unit suite on CI. Mark `-n auto` in `pyproject.toml` once the suite >50 tests. |
| `moto` | **~=5.x** | AWS service mocking | Mocks EKS `describe_cluster` and STS `assume_role`/`assume_role_with_web_identity` end-to-end. Far better than hand-mocking boto3 clients with `pytest-mock`. |
| `responses` | **NOT USED** initially | HTTP mock | Only if we end up making non-boto3 HTTP calls (e.g. for Helm OCI repo auth). Defer. |
| `coverage[toml]` | **~=7.6** | Underlying coverage engine | Pulled by `pytest-cov`; configure via `[tool.coverage.*]` in `pyproject.toml`. |
| `kind` | **0.30.x** | Local k8s for integration tests | Industry default for "real kubectl/helm in CI"; runs on GitHub Actions ubuntu-24.04 runners in <90s. Use over `k3d` because the Kubernetes-SIG-owned project has the most stable release cadence and best GHA integration. **Alternative: `k3d`** — slightly faster startup, smaller footprint; choose `k3d` if the integration suite exceeds 10 tests and CI time becomes a problem. |
| `pre-commit` | **~=3.8** | Local git-hook orchestration | Runs `ruff check --fix`, `ruff format`, `mypy`, and `pytest --quiet` on staged files before commit. Integrate with `lefthook` instead if startup time matters; `pre-commit` is the safer default. |
| `commitizen` | **~=3.x** | Conventional Commits linter | Optional — but Yves' user-global rules mandate Conventional Commits everywhere. `cz check --rev-range origin/main..HEAD` in CI gates non-conforming commits cleanly. Confidence: **MEDIUM** (could also be enforced via release-please's PR-title-linter alone). |

### (D) Release Automation

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **`googleapis/release-please-action`** | **v4** | Conventional-Commits → SemVer release PRs | **Decision: `release-please` over `python-semantic-release`.** Already locked in PROJECT.md "Key Decisions". Rationale: (1) PR-based release flow (release-PR is reviewable, signed-commit-friendly — matches Yves' "GPG-signed commits / no direct main" rules); (2) GitHub-native, no extra runtime to install; (3) updates `pyproject.toml`, `CHANGELOG.md`, and `pipe.yml` version field in a single PR via `extra-files`. **Config:** `release-type: python`, `package-name: aws-eks-helm-deploy`, `extra-files: [pipe.yml, README.md]` (use the `$schema`/regex form to bump the `image:` tag in `pipe.yml`). Confidence: **HIGH**. |
| `semversioner` | **REMOVED** | — | Per PROJECT.md "Out of Scope". Drop `.changes/` directory after migration. |
| `python-semantic-release` | **NOT USED** | — | Strictly Python-centric and pushes tags directly to `main` — conflicts with branch protection + release-PR review flow. |

### (E) Docker / Image Build

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| `docker/setup-buildx-action` | **v3** | Buildx in GHA | Required for multi-arch + layer cache. |
| `docker/setup-qemu-action` | **v3** | ARM64 emulation | Use **only** if we keep single-runner builds. For sub-2-minute builds, prefer the **native-runner-per-arch** pattern (one job on `ubuntu-24.04`, one on `ubuntu-24.04-arm`, then `buildx imagetools create` to assemble the manifest list). Confidence: **HIGH** that native-per-arch is the 2026 best practice; **MEDIUM** that the public GHA `ubuntu-24.04-arm` runner availability is sufficient for an Apache-2.0 OSS project (it is, as of June 2026). |
| `docker/build-push-action` | **v6** | Build + push | Layer cache via `cache-from: type=gha,scope=...` + `cache-to: type=gha,mode=max`. |
| `docker/metadata-action` | **v5** | OCI labels + tag derivation | Emits `org.opencontainers.image.*` annotations (closes PROJECT.md "OCI image labels" requirement). Configure `tags:` to emit `latest`, `vX.Y.Z`, `vX.Y`, `vX`. |
| `docker/login-action` | **v3** | Registry auth | For both Docker Hub (PAT in secret) and GHCR (`GITHUB_TOKEN` with `packages: write`). |

### (F) Supply-Chain Security

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **`cosign`** | **2.4.x** | Keyless image signing + attestations | Sign images with GitHub Actions OIDC → Fulcio short-lived cert → Rekor transparency-log entry. Zero key management. Use `sigstore/cosign-installer@v3` in the workflow. Verify with `cosign verify --certificate-identity-regexp 'https://github\.com/yves-vogl/aws-eks-helm-deploy/\.github/workflows/release\.ya?ml@refs/tags/v.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com <image>`. Confidence: **HIGH**. |
| **`syft`** | **1.42.x** | SBOM generation | `syft <image> -o spdx-json=sbom.spdx.json -o cyclonedx-json=sbom.cdx.json` — emit **both** formats. SPDX for NTIA/license auditing, CycloneDX for vuln-correlation tools. Attach as a Cosign attestation: `cosign attest --predicate sbom.spdx.json --type spdx <image>`. Confidence: **HIGH**. |
| **`trivy`** | **0.59.x** | Vulnerability + IaC + secret scan in CI | **Decision: `trivy` over `grype`.** Rationale: (1) one binary covers image vulns + Dockerfile lint + filesystem scan + Helm-chart scan + secret detection — matches our four-axis CI gate; (2) trivy's multi-source DB (NVD + RH + Debian + Ubuntu + Alpine) reduces false negatives on Debian-slim base; (3) `aquasecurity/trivy-action@0.x` is the most mature GHA wrapper. **Caveat:** Trivy is ~18% noisier than Grype on backport-patched CVEs — mitigate with `.trivyignore` + severity gate `HIGH,CRITICAL`. Confidence: **HIGH**. |
| `grype` | **NOT USED** | — | Better risk-scoring (EPSS+KEV+CVSS) but narrower scope; revisit only if vuln-prioritization becomes a bottleneck. |
| **`pip-audit`** | **~=2.7** | Python dependency vuln scan | Run `uv run pip-audit --strict` against the locked deps. Complementary to Trivy: pip-audit pulls from PyPI advisory DB which has Python-specific CVEs that trivy can miss. |
| **`Dependabot`** | (built-in) | Auto-bump | Three ecosystems: `pip` (pyproject.toml), `docker` (Dockerfile FROM tags), `github-actions`. Per PROJECT.md, auto-merge on green is enabled — implement via `dependabot/fetch-metadata` + `gh pr merge --auto`. |
| `SLSA provenance` | via `actions/attest-build-provenance@v1` | Build attestation | Emits SLSA v1 provenance attached as a Sigstore Rekor entry. Free + zero-config when running on GitHub-hosted runners. Closes the "SLSA level 2+" baseline noted in 2026 supply-chain guidance. |

### (G) Documentation System

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **`mkdocs-material`** | **9.5.x** (latest) | Documentation site | **Decision: `mkdocs-material` over Sphinx or README-only.** Rationale: (1) Markdown-first matches Conventional-Commits and PR-review culture; (2) the project is prose-heavy (migration guide, ADRs, `examples/`, OIDC setup) — Sphinx's autodoc/rST strength is wasted on a 5-module pipe; (3) the `mkdocstrings[python]` plugin covers the small API-reference need; (4) GitHub Pages hosting is one workflow step. **Caveat (MEDIUM confidence):** Material-for-MkDocs entered maintenance mode in early 2026; the successor `Zensical` will read existing `mkdocs.yml` configs. Safe for the v2.0 timeline (12-18 months) — migrate to Zensical when the v2.1 docs refresh lands. |
| `mkdocs-material` plugins | latest | — | `mkdocs-minify-plugin`, `mkdocs-git-revision-date-localized-plugin`, `mkdocs-redirects` (for the `docs/v1/` → `docs/v2/` URL transitions), `mike` (for versioned docs deploy — required by PROJECT.md "versioned documentation"). |
| `mkdocstrings[python]` | latest | API reference from docstrings | Only needed if we expose any public Python API. For a CLI-style pipe, this is minimal — keep but lightly used. |
| `Sphinx` | **NOT USED** | — | Overkill for prose-first docs; the rST learning curve cost is real for contributors. |
| `pdoc` | **NOT USED** | — | Too lightweight; lacks the navigation, search, and versioning Material gives us. |
| `Zensical` | **WATCH** | future migrant | Track its 1.0 release; migrate when stable (likely late 2026 / early 2027). |

---

## Installation

### Local dev bootstrap

```bash
# uv (single binary, no Python needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Project deps + dev tools (declared in pyproject.toml)
uv sync --all-extras --dev

# Install pre-commit hooks
uv run pre-commit install --install-hooks

# Local Kubernetes for integration tests
brew install kind helm  # or: go install sigs.k8s.io/kind@latest
```

### `pyproject.toml` skeleton (dependency section only)

```toml
[project]
name = "aws-eks-helm-deploy"
requires-python = ">=3.13"
dependencies = [
    "boto3 ~= 1.40",
    "bitbucket-pipes-toolkit ~= 4.6",
    "Jinja2 ~= 3.1",
    "PyYAML ~= 6.0",
]

[dependency-groups]
dev = [
    "ruff ~= 0.15",
    "mypy ~= 1.18",
    "boto3-stubs[eks,sts]",
    "pytest ~= 8.4",
    "pytest-cov ~= 7.1",
    "pytest-mock ~= 3.14",
    "pytest-xdist ~= 3.6",
    "moto[eks,sts] ~= 5.0",
    "pre-commit ~= 3.8",
    "pip-audit ~= 2.7",
]
docs = [
    "mkdocs-material ~= 9.5",
    "mkdocstrings[python]",
    "mkdocs-minify-plugin",
    "mkdocs-redirects",
    "mike",
]
```

### CI tool installs (GitHub Actions snippets)

```yaml
- uses: astral-sh/setup-uv@v3
- uses: sigstore/cosign-installer@v3
- uses: anchore/sbom-action@v0   # wraps syft
- uses: aquasecurity/trivy-action@0.x
- uses: helm/kind-action@v1       # for integration tests
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v6
- uses: googleapis/release-please-action@v4
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `uv` | `poetry` | If team is large and already poetry-fluent; not the case here. |
| `uv` | `pdm` | If you specifically need PEP 582's `__pypackages__` workflow (rare). |
| `uv` | `pip-tools` + venv | If you want pure-stdlib tooling. Loses 100× speedup and lock-file ergonomics. |
| `ruff` | `black + isort + flake8` | If a critical Ruff rule is missing or behaves differently (verify per-rule; most projects migrate cleanly). |
| `mypy --strict` | `pyright` / `basedpyright` | If we want stricter unannotated-code analysis and don't care about plugin ecosystem. **Pyright catches more edge cases (98% spec conformance vs. mypy's ~94%).** Reasonable fallback. |
| `release-please` | `python-semantic-release` | If we ever lose GitHub-native release-PR flow (e.g. mirror to a non-GH forge as primary — but Bitbucket-as-mirror doesn't need release automation). |
| `trivy` | `grype` | When risk-scoring (EPSS + KEV + CVSS composite) becomes the gating metric, not coverage breadth. |
| `mkdocs-material` | `Sphinx` + `furo` theme | If the project ever becomes a Python library with a large public API surface and >50 modules. |
| `mkdocs-material` | `Docusaurus` | If documentation grows to multi-product and we want React-component embeds. Overkill here. |
| Native multi-arch (per-runner) | QEMU emulation | If `ubuntu-24.04-arm` runner availability degrades or the arm64 build becomes serial/slow — fall back to single-runner QEMU. |
| `cosign` keyless | `cosign` keyed | Only if Sigstore public-good infrastructure becomes unreliable (low-probability in 2026). |
| `kind` | `k3d` | If integration-test startup time exceeds 90s consistently. |
| Roll our own EKS token | `eks-token` PyPI package | If the presign logic grows past ~50 LOC or we add token-caching/refresh. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `awscli` as a Python dependency | ~120 MB, drags ancient `urllib3`/`botocore` constraints, internal-import (`awscli.customizations.eks.get_token`) is unsupported | `boto3` + hand-rolled STS-presign for `eks get-token` |
| `python:3-alpine` (or any unpinned `python:3*`) | musl-libc wheel-availability + DNS-resolver quirks, floating tag causes silent CPython bumps | `python:3.13-slim-bookworm` |
| `requirements.txt` | No lock file, no dev/prod split, no Python-version constraint | `pyproject.toml` + `uv.lock` |
| `setup.py` / `setup.cfg` | Deprecated for new projects since PEP 621 | `pyproject.toml` (PEP 621 metadata) |
| `BaseException` subclasses (carried over from v1.x) | Intercepts `KeyboardInterrupt` + `SystemExit` — debugging hell | `Exception` subclasses; PROJECT.md "Active" flags this explicitly |
| `flake8` + `black` + `isort` + `pyupgrade` (separate tools) | 4 tools, 4 configs, 4 CI installs, all slower than one Ruff invocation | `ruff check` + `ruff format` |
| `semversioner` | Yves' v1.x history shows the `.changes/` ceremony adds friction; PR-based release-please is cleaner | `release-please` (already locked in PROJECT.md) |
| GPG image signing (e.g. Notary v1) | Dead-tech for OCI distribution; no GitHub-native flow | `cosign` keyless (already locked in PROJECT.md) |
| `docker scan` (Snyk-backed) | License-restricted; degraded free tier in 2025 | `trivy` (Apache-2.0) |
| `safety` (Python vuln scanner) | Commercial DB; free tier has latency on advisories | `pip-audit` (PyPA-blessed) |
| `bandit` as a standalone tool | Mostly subsumed by Ruff's `S` (flake8-bandit) rule family | Ruff `select = ["S"]` |
| `tox` | Multi-Python-version matrix without `uv`'s speed; redundant when we target only 3.13 | `uv run pytest` directly; GHA matrix if we ever multi-version |
| `sphinx-autoapi` / `pdoc` | Doc-generation tools for projects we aren't — a CLI pipe doesn't need autodoc-heavy docs | `mkdocs-material` + a short `mkdocstrings` section if needed |
| Building all arches with QEMU on a single runner | Slow (5-10× for arm64); becomes a CI bottleneck as the image grows | Native `ubuntu-24.04-arm` runner + `buildx imagetools create` |
| Storing the Cosign verification public key in the repo | Defeats the point of keyless | Verify by GitHub OIDC issuer + certificate identity regex |
| Pushing to Docker Hub only | Single point of distribution, rate-limit risk for consumers | Mirror to GHCR (`ghcr.io/yves-vogl/aws-eks-helm-deploy`) too — PROJECT.md "Active" |

---

## Stack Patterns by Variant

**If the project later adds GitHub Actions as a first-party invocation surface** (currently out-of-scope per PROJECT.md):
- Add a `action.yml` at the repo root.
- Add `aws-actions/configure-aws-credentials@v4` to the recommended consumer snippets.
- Keep the same Python codebase — only the wrapper changes.

**If consumer demand for Azure / GCP grows** (currently AWS-only):
- Split cloud-provider auth into a `pipe/cloud/` package with `eks.py`, `aks.py`, `gke.py`.
- Add `azure-identity` and `google-auth` to optional `pyproject.toml` extras.
- Reconsider Pydantic for the now-multi-shape config schema.

**If Helm-chart vulnerability scanning becomes a required output** (currently only image scanning):
- Add a `trivy config <chart-dir>` step (Trivy already covers Helm chart scanning).
- Surface results as a PR comment via `aquasecurity/trivy-action` `format: sarif` + `github/codeql-action/upload-sarif`.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `python ~=3.13` | `boto3 ~=1.40` | Full support |
| `python ~=3.13` | `bitbucket-pipes-toolkit ~=4.6` | Verify on first `uv sync` — toolkit historically lags Python releases by 3-6 months |
| `helm 3.18` | Kubernetes 1.30, 1.31, 1.32 | Per Helm's version-skew policy (n-3 supported); document the minimum K8s in the README |
| `helm 3.18` + `helm-diff 3.10` | OK | helm-diff tracks Helm major; 3.x covers Helm 3.x |
| `mypy 1.18` + `boto3-stubs` | OK | boto3-stubs ships per-service extras; only install `[eks,sts]` to keep image build cache hot |
| `ruff 0.15` + `pyproject.toml` | OK | All config under `[tool.ruff]` and `[tool.ruff.format]`; remove separate `.ruff.toml` |
| `release-please v4` + `release-type: python` | Updates `pyproject.toml` `version` and `CHANGELOG.md` | Use `extra-files` to also bump `pipe.yml` (regex form) |
| `cosign 2.4` + GHA OIDC | Requires `permissions: id-token: write` + `contents: read` (or `write` for releases) | Don't grant `id-token` on PR workflows from forks |
| `trivy 0.59` + `.trivyignore` | OK | `.trivyignore` syntax is stable since 0.50 |
| `mkdocs-material 9.5` + `mike` | OK | `mike` handles the `docs/v1/` vs `docs/v2/` versioned-docs requirement |
| `uv 0.11` + `pyproject.toml` (PEP 621) | OK | `uv.lock` is the project lock file; `requirements.txt` only generated if a consumer needs it (`uv export`) |

---

## Sources

- [astral-sh/uv changelog](https://github.com/astral-sh/uv/blob/main/CHANGELOG.md) — confirmed 0.11.8 (Apr 27 2026) as the current line; **HIGH** confidence
- [astral-sh/ruff PyPI](https://pypi.org/project/ruff/) and [Ruff 0.15 + 2026 Style Guide](https://www.pyblog.in/programming/ruff-0-15-2026-style-guide-modern-python-formatting-explained/) — Ruff 0.15 (Feb 2026) is the Black-replacement-credible release; **HIGH**
- [mypy vs Pyright vs ty 2026](https://www.danilchenko.dev/posts/ty-vs-mypy-vs-pyright/) — mypy 1.18 mypyc-compiled now competitive with pyright on speed; **HIGH**
- [pytest plugins ranking 2026 — PythonTest](https://pythontest.com/top-pytest-plugins/) — pytest-cov/mock/xdist remain the top-4 by downloads as of March 2026; **HIGH**
- [Trivy vs Grype 2026](https://lucaberton.com/blog/trivy-vs-grype-2026/) and [Container scanning 2026 — HostMyCode](https://www.hostmycode.com/blog/container-image-vulnerability-scanning-strategies-production-security-trivy-grype-snyk-2026) — Trivy = breadth, Grype = depth on prioritization; **HIGH**
- [Syft SBOM generator 2026](https://appsecsanta.com/syft) — Syft 1.42.0 (Feb 10 2026); SPDX + CycloneDX dual emit best-practice; **HIGH**
- [Cosign keyless GHA guide](https://www.qcecuring.com/blog/sigstore-cosign-keyless-github-actions) and [chainguard.dev keyless container signing](https://edu.chainguard.dev/open-source/sigstore/how-to-keyless-sign-a-container-with-sigstore/) — id-token:write permission, Fulcio + Rekor flow; **HIGH**
- [MkDocs vs Sphinx 2026](https://gautamkhorana.com/static-site-generators/compare/mkdocs-vs-sphinx/) — MkDocs wins for new prose-first projects; Material-for-MkDocs in maintenance mode, Zensical successor incoming; **HIGH for choice, MEDIUM for long-term Material viability**
- [Docker multi-arch GHA best practice](https://docs.docker.com/build/ci/github-actions/multi-platform/) and [Blacksmith ARM64 builds](https://www.blacksmith.sh/blog/building-multi-platform-docker-images-for-arm64-in-github-actions) — native-runner-per-arch + `buildx imagetools create` is 2026 SOTA; QEMU is the fallback; **HIGH**
- [Helm OCI registries 2026](https://helm.sh/docs/topics/registries/) — OCI stable since 3.8, default-on; **HIGH**
- [release-please v4 with Python](https://github.com/googleapis/release-please/issues/1741) and [release-please action marketplace](https://github.com/googleapis/release-please-action) — `release-type: python`, `extra-files` regex bumper; **HIGH**
- [boto3 EKS token generation patterns](https://github.com/boto/boto3/issues/2309) and [analogous.dev EKS auth](https://www.analogous.dev/blog/using-the-kubernetes-python-client-with-aws/) — STS-presign + EXEC plugin payload pattern is the documented `aws eks get-token` reproduction; **HIGH**

---
*Stack research for: CI-pipeline Docker container (Python) wrapping helm + AWS, distributed via Bitbucket Pipes Marketplace*
*Researched: 2026-06-16*
