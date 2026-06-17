# Phase 01 — Audit Deferred Items

Items acknowledged during Round 2 audit but deferred to later phases.

## qa-12 — Helm binary fetch hardcoded to linux/amd64

**Severity:** LOW
**Deferred to:** Phase 6 (multi-arch native-runner build matrix)

The `helm-fetch` Docker stage explicitly targets `linux-amd64`. Multi-arch support
(ARM64 runners) is documented Phase 6 scope. Risk is limited to the Phase 1 Docker
build context: Bitbucket Pipelines runners are `linux/amd64`, so incorrect arch
only manifests if the image is built on an ARM64 host — not a current scenario.

Acceptable as-is for Phase 1 through Phase 5.

## sec-10 — Makefile bootstrap uses curl|sh install pattern

**Severity:** LOW
**Deferred to:** Phase 6 / developer documentation update

`make bootstrap` uses the standard astral.sh installer (`curl -LsSf
https://astral.sh/uv/install.sh | sh`). Hash-pinning would break on every uv
upstream release; OS-specific package managers are too varied for a cross-platform
Makefile.

The Makefile is excluded from the Docker build context via `.dockerignore`, so this
is dev-machine risk only. For macOS, the recommended alternative is `brew install uv`.

This will be documented in `docs/build.md` during Phase 6 when the developer
onboarding guide is written.
