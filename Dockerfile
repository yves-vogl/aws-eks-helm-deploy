# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.11.21
ARG HELM_VERSION=4.2.4
ARG HELM_DIFF_VERSION=3.15.11
ARG COSIGN_VERSION=3.1.3

# Base image digests — pinned for reproducible builds and supply-chain safety.
# Dependabot's `docker` ecosystem (.github/dependabot.yml) keeps these current
# weekly; bumps land as `fix(deps):` commits which release-please reads as a
# patch bump and triggers a fresh image publish.
# Resolve via: docker buildx imagetools inspect <image>:<tag>
ARG PYTHON_BASE_DIGEST=sha256:05b95397cac02b060ff1251afaa78087d92d7034369afbc8eb765631cada8257
ARG DEBIAN_BASE_DIGEST=sha256:96e378d7e6531ac9a15ad505478fcc2e69f371b10f5cdf87857c4b8188404716
# golang:1.26.7-bookworm (buildpack-deps:bookworm-scm base — ships git, so no
# extra apt-get is needed in the go-source-build stage below).
ARG GOLANG_BASE_DIGEST=sha256:6ef6e30f0ea5c384f6d111cf856e024e3086bbdcb1779da3f3b3fbba0aea53d2

# ── Stage 0: uv binary source ────────────────────────────────────────────────
# Named stage required: Docker does not support ARG interpolation in COPY --from
# when referencing an external image directly (only stage names are interpolated).
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-source

# ── Stage 1: Python dependency builder ───────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST} AS builder

# Copy uv from the named uv-source stage — ARG-safe and BuildKit-compatible
COPY --from=uv-source /uv /uvx /bin/

WORKDIR /build

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --frozen: use locked versions exactly; --no-dev: no dev tools in image
# --no-editable: install the package itself as a wheel (not .pth editable install)
#               so the venv is fully self-contained when COPYd to the runtime stage
# --compile-bytecode: pre-compile .pyc for faster import at runtime
RUN uv sync --frozen --no-dev --no-editable --compile-bytecode

# ── Stage 2: Go toolchain source-build (helm, cosign, helm-diff) ────────────
# 2026-08 / SEC-06: upstream helm/cosign/helm-diff have NOT yet cut a release
# built against Go >= 1.26.6 (Go 1.26.6 fixed CVE-2026-33818, -39821, -39822,
# -46600, -56853, -56858, -56859, -56860, -56862 in the stdlib; released
# 2026-08-13, AFTER helm v4.2.4 (2026-08-13) / cosign v3.1.3 (2026-08-06) /
# helm-diff v3.15.11 (2026-08-01) were cut). Pre-built release binaries for
# all three tools therefore carry stdlib CVEs that have a published fix
# with no published fixed *binary* to consume. Per the "a real CVE is never
# suppressed" gate policy, we build the exact pinned upstream release TAGS
# ourselves against a newer Go toolchain instead of trusting a stale
# pre-built binary. Module-level CVEs surfaced by the same scan (oras-go,
# golang.org/x/mod, golang.org/x/text, google.golang.org/grpc) are bumped
# explicitly below via `go get`, each citing the CVE it closes — mirrors the
# `[tool.uv] override-dependencies` pattern used for the Python side
# (pyproject.toml) for the same class of problem.
#
# Supply-chain note: this trades "verify sha256sum of a downloaded binary
# against a checksums file fetched over the same channel" for "git clone a
# tag + Go module proxy/sumdb verification of every dependency" (GONOSUMCHECK
# is on by default; every module hash is checked against sum.golang.org).
# GPG verification of the upstream release tags is a further hardening step
# NOT implemented here — flagged for loop-security-engineer follow-up.
FROM golang:1.26.7-bookworm@${GOLANG_BASE_DIGEST} AS go-source-build
ENV CGO_ENABLED=0 \
    GOOS=linux \
    GOFLAGS=-mod=mod
WORKDIR /src

# ---- helm ----
ARG HELM_VERSION
ARG TARGETARCH
RUN git clone --depth 1 --branch "v${HELM_VERSION}" https://github.com/helm/helm.git helm
WORKDIR /src/helm
# oras.land/oras-go/v2 v2.6.1 (indirect, OCI registry client) — CVE-2026-50163
# (information disclosure / arbitrary file write via crafted tarball
# hardlinks). Fixed 2.6.2; not yet consumed by a helm patch release.
# golang.org/x/crypto v0.54.0 (indirect) — CVE-2026-56854 (x/crypto/ssh:
# authentication bypass, source-address restrictions not enforced). Fixed
# 0.55.0. Same CVE as the helm-diff stage below; helm carries it too.
RUN go get oras.land/oras-go/v2@v2.6.2 golang.org/x/crypto@v0.55.0 \
    && go mod tidy
RUN GOARCH=${TARGETARCH} go build -trimpath \
      -ldflags "-w -s \
        -X helm.sh/helm/v4/internal/version.version=v${HELM_VERSION} \
        -X helm.sh/helm/v4/internal/version.gitCommit=$(git rev-parse HEAD) \
        -X helm.sh/helm/v4/internal/version.gitTreeState=clean" \
      -o /out/helm ./cmd/helm

# ---- cosign ----
WORKDIR /src
ARG COSIGN_VERSION
RUN git clone --depth 1 --branch "v${COSIGN_VERSION}" https://github.com/sigstore/cosign.git cosign
WORKDIR /src/cosign
# golang.org/x/mod v0.37.0 (indirect) — CVE-2026-56864 / CVE-2026-56865
# (malicious GOSUMDB/GOPROXY could forge sumdb responses). Fixed 0.40.0.
# golang.org/x/text v0.38.0 (indirect) — CVE-2026-56852 (DoS via invalid
# UTF-8 input). Fixed 0.39.0; bumped to 0.41.0 because golang.org/x/mod
# v0.40.0 transitively requires golang.org/x/text >= 0.41.0.
# google.golang.org/grpc (indirect) — GHSA-hrxh-6v49-42gf (xDS RBAC and
# HTTP/2) was fixed in 1.82.1, which this line pinned; 1.82.1 then turned out
# vulnerable itself: CVE-2026-84304 (fixed 1.83.1) and CVE-2026-84445 (xDS
# server DoS, fixed 1.82.2 / 1.83.2). 1.83.2 is the first version clear of all
# three.
RUN go get golang.org/x/mod@v0.40.0 golang.org/x/text@v0.41.0 google.golang.org/grpc@v1.83.2 \
    && go mod tidy
# Matches the upstream `cosign:` Makefile target (CGO_ENABLED=0, no
# pivkey/pkcs11 build tags — same feature set as the release binary we
# previously downloaded).
RUN GOARCH=${TARGETARCH} go build -trimpath \
      -ldflags "-buildid= \
        -X sigs.k8s.io/release-utils/version.gitVersion=v${COSIGN_VERSION} \
        -X sigs.k8s.io/release-utils/version.gitCommit=$(git rev-parse HEAD) \
        -X sigs.k8s.io/release-utils/version.gitTreeState=clean" \
      -o /out/cosign ./cmd/cosign

# ---- helm-diff (helm plugin) ----
WORKDIR /src
ARG HELM_DIFF_VERSION
RUN git clone --depth 1 --branch "v${HELM_DIFF_VERSION}" https://github.com/databus23/helm-diff.git helm-diff
WORKDIR /src/helm-diff
# Same oras-go CVE-2026-50163 as helm above (helm-diff vendors helm.sh/helm/v4
# and inherits its indirect oras-go dependency).
# golang.org/x/crypto v0.54.0 (indirect) — CVE-2026-56854 (x/crypto/ssh:
# authentication bypass, source-address restrictions in authorized_keys are
# not enforced). Fixed 0.55.0. Trivy reports this for the plugin binary only;
# the helm and cosign binaries built above scan clean.
RUN go get oras.land/oras-go/v2@v2.6.2 golang.org/x/crypto@v0.55.0 \
    && go mod tidy
# Plugin layout mirrors the upstream `make dist` target: plugin.yaml +
# bin/diff under a single `diff/` directory (README/LICENSE omitted — not
# read by Helm's plugin loader).
RUN mkdir -p /out/diff-plugin/bin \
    && cp plugin.yaml /out/diff-plugin/ \
    && GOARCH=${TARGETARCH} go build -trimpath \
         -ldflags "-X github.com/databus23/helm-diff/v3/cmd.Version=${HELM_DIFF_VERSION}" \
         -o /out/diff-plugin/bin/diff .

# ── Stage 3: Runtime image ────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST} AS runtime

# System deps: ca-certificates for TLS (git + curl no longer needed — helm-diff is bundled
# via helm-diff-fetch stage; see Phase 5 D2 / CONTEXT D2).
#
# `upgrade -y` first: the python slim base is rebuilt on the upstream's cadence,
# not Debian's, so a security fix published between two upstream rebuilds is
# otherwise invisible until the digest moves. libpcre2-8-0 10.42-1 in the
# pinned digest is the case in point — CVE-2026-86145/-89157/-89161, fixed in
# 10.42-1+deb12u1. A blanket upgrade covers that class instead of a per-CVE
# package list. CI builds without a layer cache, so this layer is always fresh.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (IMAGE-03): uid 10001
RUN addgroup --gid 10001 pipe \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos "" pipe

# Copy the installed venv from builder (includes the package wheel from src/)
COPY --from=builder /build/.venv /opt/venv

# Copy Helm binary, built from source in go-source-build (SEC-06)
COPY --from=go-source-build /out/helm /usr/local/bin/helm

# Copy Cosign binary, built from source in go-source-build (CHART-04; R12 ordered after helm)
COPY --from=go-source-build /out/cosign /usr/local/bin/cosign

# Copy helm-diff plugin, built from source in go-source-build (Phase 5 D2 / SEC-06).
# Plugin directory name MUST be `diff` (matches `name: "diff"` in plugin.yaml);
# destination is pipe user's HELM_PLUGINS path (NOT /root — see RESEARCH CONTRADICTION 1).
COPY --from=go-source-build /out/diff-plugin /home/pipe/.local/share/helm/plugins/diff

ENV PATH="/opt/venv/bin:${PATH}" \
    HELM_PLUGINS=/home/pipe/.local/share/helm/plugins \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

USER pipe

# Verify helm-diff is reachable as pipe user — build fails early if plugin-discovery breaks
# (R4-equivalent: catches path/name errors at build time, not at runtime).
RUN helm diff version

WORKDIR /home/pipe

# OCI annotations are attached via 'docker buildx build --annotation manifest:org.opencontainers.image.*=...'
# — see docs/build.md. Do NOT add LABEL org.opencontainers.image.* directives here.

ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]
