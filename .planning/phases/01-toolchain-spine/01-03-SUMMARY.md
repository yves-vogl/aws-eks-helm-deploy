---
phase: 01-toolchain-spine
plan: 03
subsystem: container
tags: [docker, oci, helm, helm-diff, multi-stage, non-root]

# Dependency graph
requires:
  - "01-01"  # pyproject.toml + uv.lock + src/ (builder stage COPYs them)
provides:
  - Dockerfile (3-stage: builder/helm-fetch/runtime; python:3.13-slim-bookworm base)
  - .dockerignore (lean build context; excludes .git, .planning, tests, dev artifacts)
  - docs/build.md (canonical docker buildx --annotation command; IMAGE-05 contract)
affects:
  - 01-02 (Plan B: acceptance tier builds the image from this Dockerfile)
  - Phase 6 (release.yml mirrors docs/build.md annotation command via docker/metadata-action@v5)

# Tech tracking
tech-stack:
  added:
    - Helm 3.18.6 (pinned; verified against github.com/helm/helm/releases at execution time)
    - helm-diff 3.10.0 (pinned; only 3.10.x release; k8s.io/cli-runtime 0.32.x compatible with Helm 3.18.6)
    - uv (from ghcr.io/astral-sh/uv:latest; COPY into builder stage — no curl needed)
    - python:3.13-slim-bookworm (runtime and builder base; replaces v1 python:3-alpine)
    - debian:bookworm-slim (helm-fetch stage only)
  patterns:
    - Three-stage Docker build: builder (uv) / helm-fetch (curl) / runtime
    - uv sync --frozen --no-dev --no-editable --compile-bytecode: self-contained venv for COPY
    - USER pipe before helm plugin install (Pitfall 4 prevention)
    - HELM_PLUGINS env var routes plugin install to /home/pipe/.local/share/helm/plugins
    - OCI annotations via buildx --annotation manifest:org.opencontainers.image.*=... (not LABEL)
    - RUN helm diff version as build-time smoke (fails build if Pitfall 4 recurs)
    - docs/build.md as source-of-truth for annotation command (Phase 6 mirrors it)

key-files:
  created:
    - docs/build.md
  modified:
    - Dockerfile (v1 17-line alpine shape fully replaced)
    - .dockerignore (expanded from 2 lines to full exclusion list)

key-decisions:
  - "HELM_VERSION=3.18.6 (latest 3.18.x at execution time; research had 3.18.3 as assumption)"
  - "HELM_DIFF_VERSION=3.10.0 (only 3.10.x release; k8s.io/cli-runtime 0.32.1 is compatible with Helm 3.18.6)"
  - "curl added to runtime stage apt-get install — required by helm-diff plugin installer (Rule 1 fix)"
  - "uv sync --no-editable flag required — without it, uv creates an editable .pth pointing to /build/src which is absent in runtime stage after COPY --from=builder /build/.venv /opt/venv"
  - "RUN helm diff version added as final builder step — build-time Pitfall 4 guard; adds ~0.4s"
  - "docs/ directory created (did not exist); docs/build.md is the first file there"

# Metrics
duration: 35min
completed: 2026-06-17
---

# Phase 01 Plan 03: Docker Image (multi-stage slim-bookworm + Helm 3.18.6 + helm-diff 3.10.0) Summary

**Multi-stage Dockerfile replacing the v1 alpine image: python:3.13-slim-bookworm runtime with uv-managed venv, Helm 3.18.6 binary, helm-diff 3.10.0 plugin installed as non-root `pipe` user (uid 10001), Pitfall 4 verified closed**

## Performance

- **Duration:** ~35 min (including 2 auto-fix iterations + docker build × 3 runs)
- **Completed:** 2026-06-17
- **Tasks:** 3 (C1, C2, C3)
- **Files modified:** 3 (1 replaced, 1 expanded, 1 new)

## Accomplishments

- v1 17-line alpine Dockerfile fully replaced by 3-stage `python:3.13-slim-bookworm` Dockerfile (82 lines)
- `docker build -t aws-eks-helm-deploy:dev .` exits 0
- `python --version` in container: Python 3.13.14
- `helm version --short` in container: v3.18.6+gb76a950
- `helm diff version` in container: 3.10.0 (exits 0 — Pitfall 4 closed)
- `id -u` in container: 10001; `whoami`: pipe
- Build context: 1.14 kB (down from full repo with .dockerignore expanded)
- `docs/build.md` created with canonical `docker buildx build --annotation ...` command
- No `LABEL org.opencontainers.image.*` in Dockerfile; OCI annotations via `--annotation` per IMAGE-05

## Version Pins Verified at Execution Time

| Component | Research Assumption | Verified Value | Source |
|-----------|---------------------|----------------|--------|
| Helm 3.18.x | 3.18.3 (ASSUMED) | **3.18.6** | github.com/helm/helm/releases |
| helm-diff 3.10.x | 3.10.0 (ASSUMED) | **3.10.0** | github.com/databus23/helm-diff/releases |

**helm-diff 3.10.0 compatibility with Helm 3.18.6:** Verified compatible. The 3.10.0 release notes show `k8s.io/cli-runtime` bumped from 0.32.0 to 0.32.1 and `k8s.io/apiextensions-apiserver` from 0.32.0 to 0.32.1 — these are the Kubernetes 1.32.x client libraries used by both Helm 3.18.x and helm-diff 3.10.x. No incompatibility found; `helm diff version` returns 3.10.0 cleanly after install.

## Runtime Image Size

**144.9 MB** — informational baseline for Phase 6's cold-start benchmark (IMAGE-06). The v1 image used `python:3-alpine` with `pip install` from `requirements.txt` (no lockfile); the v2 image uses `python:3.13-slim-bookworm` which is larger but uses glibc (required for boto3 binary deps), `uv sync --frozen` (deterministic), and pre-compiled bytecode.

## Pitfall 4 Status: CLOSED

- `USER pipe` appears on line 56 of the Dockerfile, BEFORE `RUN helm plugin install` on line 59
- Plugin is installed into `/home/pipe/.local/share/helm/plugins` (confirmed via `HELM_PLUGINS` env var)
- `RUN helm diff version` on line 63 runs as `pipe` and returns 3.10.0 — build fails if plugin is unreachable
- Post-build: `docker run --rm --entrypoint helm aws-eks-helm-deploy:dev diff version` exits 0

## Task Commits

Each task was committed atomically:

1. **Task C1: Multi-stage Dockerfile** — `d58791a` (feat)
2. **Task C2: .dockerignore expansion** — `bbb590f` (chore)
3. **Task C3: docs/build.md** — `6ca6291` (docs)

## Files Created/Modified

- `Dockerfile` — 82 lines; 3 stages (builder/helm-fetch/runtime); ARG HELM_VERSION=3.18.6, ARG HELM_DIFF_VERSION=3.10.0, ARG PYTHON_VERSION=3.13; USER pipe before helm plugin install; `# syntax=docker/dockerfile:1.7` header; no LABEL directives
- `.dockerignore` — 45 lines; excludes .venv/, .git/, .planning/, tests/, .ruff_cache/, .mypy_cache/, .pytest_cache/, htmlcov/, .coverage, *.pyc, __pycache__/, dist/, *.egg-info/, .changes/, RELEASING.md, CHANGELOG.md, logo assets, bitbucket-pipelines.yml
- `docs/build.md` — 171 lines; canonical buildx command with 6 OCI annotations; `manifest:` prefix rationale; LABEL vs --annotation explanation; GH Actions Phase 6 snippet; acceptance check note; multi-arch deferral note

## Decisions Made

- **Helm 3.18.6** — Updated from research assumption of 3.18.3. Latest 3.18.x at execution time (2026-06-17).
- **helm-diff 3.10.0 compatibility** — Only 3.10.x release available; compatible with Helm 3.18.6 (verified by k8s client library version alignment and `helm diff version` in built image).
- **curl in runtime stage** — Added to `apt-get install` list because helm-diff's plugin installer calls `curl` to download the plugin binary from GitHub. RESEARCH.md Pattern 5 omitted curl from the runtime stage; added as Rule 1 auto-fix.
- **uv sync --no-editable** — Added because `uv sync` in a project directory with `src/` layout installs the package as an editable install (`.pth` file pointing to `/build/src`). Without `--no-editable`, the installed venv was not self-contained after `COPY --from=builder /build/.venv /opt/venv` — `import aws_eks_helm_deploy` failed with `ModuleNotFoundError`. Added `--no-editable` as Rule 1 auto-fix.
- **docs/ directory created** — Did not exist in the repo; created as part of Task C3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] curl required in runtime stage for helm-diff plugin installer**
- **Found during:** Task C1 (first docker build; `helm plugin install` fails with "Either curl or wget is required")
- **Issue:** The plan's runtime stage apt-get list included only `git ca-certificates`. The helm-diff plugin installer script downloads the plugin binary using curl. Without curl in the runtime stage, `helm plugin install` fails with exit code 1.
- **Fix:** Added `curl` to the runtime stage's `apt-get install -y --no-install-recommends git curl ca-certificates` list.
- **Files modified:** `Dockerfile`
- **Verification:** Second `docker build` succeeds; `helm plugin install` downloads helm-diff-linux-arm64.tgz and reports "Installed plugin: diff"
- **Committed in:** `d58791a` (included in C1 commit — the fix was identified before the first commit)

**2. [Rule 1 - Bug] uv sync requires --no-editable for self-contained venv in multi-stage build**
- **Found during:** Task C1 (first verification run after successful build; `docker run --rm aws-eks-helm-deploy:dev python -c "import aws_eks_helm_deploy"` fails with ModuleNotFoundError)
- **Issue:** `uv sync` in a project directory with `src/` layout installs the package as an editable install, creating `_editable_impl_aws_eks_helm_deploy.pth` pointing to `/build/src` in the venv. When the runtime stage copies only `/build/.venv` (not `/build/src`), the `.pth` file is broken and the package is unreachable.
- **Fix:** Added `--no-editable` to the `uv sync` invocation in the builder stage: `uv sync --frozen --no-dev --no-editable --compile-bytecode`.
- **Files modified:** `Dockerfile`
- **Verification:** Third `docker build` succeeds; `docker run ... python -c "import aws_eks_helm_deploy; print(aws_eks_helm_deploy.__version__)"` returns `2.0.0.dev0`.
- **Committed in:** `d58791a` (included in C1 commit — the fix was applied before committing)

## Known Stubs

| Stub | File | Reason |
|------|------|---------|
| OCI annotation verification | `docs/build.md` | The `docker buildx imagetools inspect` output check is explicitly deferred to Phase 6's release pipeline gate (too brittle for Phase 1 automated tests). `docs/build.md` notes this as the only Phase 1 acceptance gap. |
| Multi-arch build (IMAGE-04) | `Dockerfile` | `helm-fetch` stage explicitly targets `linux-amd64` in the curl URL. Phase 6 replaces this with a matrix build on native runners (ARM + AMD64). |
| Cold-start benchmark (IMAGE-06) | — | 144.9 MB baseline recorded; formal benchmark deferred to Phase 6. |

## Threat Surface Scan

The Dockerfile introduces two new network egress points at build time:
- `get.helm.sh/helm-v3.18.6-linux-amd64.tar.gz` (Helm binary download, TLS)
- `github.com/databus23/helm-diff` via `helm plugin install --version v3.10.0` (plugin download, TLS)

These match the plan's `<threat_model>` exactly (T-01-C-01 and T-01-C-02). Both are TLS-protected and version-pinned. No new threat surfaces beyond those documented. T-01-C-03 (build context disclosure) is mitigated by the expanded `.dockerignore`. T-01-C-04 (root container) is mitigated by `USER pipe` + uid 10001 verified at build time. T-01-C-05 (uv resolver) is mitigated by `--frozen --no-editable`.

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `Dockerfile` exists and is >= 45 lines | FOUND (82 lines) |
| `.dockerignore` exists | FOUND |
| `docs/build.md` exists | FOUND |
| `docs/build.md` contains `buildx --annotation` | FOUND |
| `docs/build.md` has >= 6 `manifest:org.opencontainers.image` occurrences | FOUND (6) |
| Commit `d58791a` (C1 — Dockerfile) | FOUND |
| Commit `bbb590f` (C2 — .dockerignore) | FOUND |
| Commit `6ca6291` (C3 — docs/build.md) | FOUND |
| `docker build` exits 0 | PASSED |
| `python --version` in image: 3.13.x | PASSED (3.13.14) |
| `helm version --short` in image: v3.18.x | PASSED (v3.18.6) |
| `helm diff version` exits 0 | PASSED (3.10.0) |
| `id -u` in image: 10001 | PASSED |
| `whoami` in image: pipe | PASSED |
| No actual `LABEL org.opencontainers` instruction in Dockerfile | PASSED |
| Module `aws_eks_helm_deploy` importable in image | PASSED (2.0.0.dev0) |
| Unit tests still green after all commits | PASSED (31 tests) |

---
*Phase: 01-toolchain-spine*
*Completed: 2026-06-17*
