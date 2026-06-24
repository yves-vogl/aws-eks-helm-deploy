# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.11.24
ARG HELM_VERSION=3.21.1
ARG HELM_DIFF_VERSION=3.15.10
ARG COSIGN_VERSION=2.6.3

# Base image digests — pinned for reproducible builds and supply-chain safety.
# Dependabot's `docker` ecosystem (.github/dependabot.yml) keeps these current
# weekly; bumps land as `fix(deps):` commits which release-please reads as a
# patch bump and triggers a fresh image publish.
# Resolve via: docker buildx imagetools inspect <image>:<tag>
ARG PYTHON_BASE_DIGEST=sha256:05b95397cac02b060ff1251afaa78087d92d7034369afbc8eb765631cada8257
ARG DEBIAN_BASE_DIGEST=sha256:96e378d7e6531ac9a15ad505478fcc2e69f371b10f5cdf87857c4b8188404716

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

# ── Stage 2: Helm binary fetch ────────────────────────────────────────────────
FROM debian:bookworm-slim@${DEBIAN_BASE_DIGEST} AS helm-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG HELM_VERSION
ARG TARGETARCH

# Multi-arch (Phase 6 / IMAGE-04 / D4): TARGETARCH is auto-set by BuildKit to amd64 or arm64
# when --platform linux/amd64 or linux/arm64 is targeted. Single Dockerfile builds both arches
# natively (no QEMU) when invoked from the release.yml matrix.
# Files are saved under their UPSTREAM names so sha256sum -c can resolve the filename
# embedded in the .sha256sum file (sha256sum format: "<hash>  <filename>").
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
        -o "/tmp/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
    && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum" \
        -o "/tmp/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum" \
    && cd /tmp \
    && sha256sum -c "helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum" \
    && tar -xz -f "helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
    && mv linux-${TARGETARCH}/helm /helm \
    && chmod +x /helm \
    && rm -rf "helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
              "helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum" \
              linux-${TARGETARCH}

# ── Stage 2.5: Cosign binary fetch ───────────────────────────────────────────
# R12: this stage is placed BETWEEN helm-fetch and runtime for layer-cache ordering.
# cosign 2.x keyless is the default (RESEARCH §3); COSIGN_EXPERIMENTAL=1 not needed.
FROM debian:bookworm-slim@${DEBIAN_BASE_DIGEST} AS cosign-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG COSIGN_VERSION
ARG TARGETARCH

# Multi-arch (Phase 6 / IMAGE-04 / D4): TARGETARCH selects cosign-linux-amd64 OR cosign-linux-arm64
# from the upstream Sigstore release; the cosign_checksums.txt file contains entries for both arches.
# The grep pattern (two spaces + end-anchor) is the Sigstore-canonical pinning pattern (RESEARCH §6).
RUN curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-${TARGETARCH}" \
        -o "/tmp/cosign-linux-${TARGETARCH}" \
    && curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign_checksums.txt" \
        -o "/tmp/cosign_checksums.txt" \
    && cd /tmp \
    && grep "  cosign-linux-${TARGETARCH}$" cosign_checksums.txt | sha256sum -c \
    && mv cosign-linux-${TARGETARCH} /cosign \
    && chmod +x /cosign \
    && rm -f /tmp/cosign_checksums.txt

# ── Stage 2.7: helm-diff plugin fetch ────────────────────────────────────────
# Phase 5 D2: build-time bundle of the helm-diff plugin (eliminates the runtime plugin-fetch step).
# Mirrors the cosign-fetch stage (CONTEXT D8 / Phase 4 D8) verbatim except for binary identity.
# SHA256 verified via upstream `helm-diff_${HELM_DIFF_VERSION}_checksums.txt` (T-05-05 mitigation).
FROM debian:bookworm-slim@${DEBIAN_BASE_DIGEST} AS helm-diff-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG HELM_DIFF_VERSION
ARG TARGETARCH

# Multi-arch (Phase 6 / IMAGE-04 / D4): helm-diff-linux-${TARGETARCH}.tgz exists for both arches;
# the extracted tarball always extracts to `diff/` regardless of arch (directory name is fixed).
# Upstream `helm-diff_${HELM_DIFF_VERSION}_checksums.txt` contains entries for both amd64 and arm64;
# the grep pattern selects the right one.
RUN curl -fsSL "https://github.com/databus23/helm-diff/releases/download/v${HELM_DIFF_VERSION}/helm-diff-linux-${TARGETARCH}.tgz" \
        -o "/tmp/helm-diff-linux-${TARGETARCH}.tgz" \
    && curl -fsSL "https://github.com/databus23/helm-diff/releases/download/v${HELM_DIFF_VERSION}/helm-diff_${HELM_DIFF_VERSION}_checksums.txt" \
        -o "/tmp/helm-diff_checksums.txt" \
    && cd /tmp \
    && grep "  helm-diff-linux-${TARGETARCH}.tgz$" helm-diff_checksums.txt | sha256sum -c \
    && tar -xzf helm-diff-linux-${TARGETARCH}.tgz \
    && rm helm-diff-linux-${TARGETARCH}.tgz helm-diff_checksums.txt

# ── Stage 3: Runtime image ────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST} AS runtime

# System deps: ca-certificates for TLS (git + curl no longer needed — helm-diff is bundled
# via helm-diff-fetch stage; see Phase 5 D2 / CONTEXT D2).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (IMAGE-03): uid 10001
RUN addgroup --gid 10001 pipe \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos "" pipe

# Copy the installed venv from builder (includes the package wheel from src/)
COPY --from=builder /build/.venv /opt/venv

# Copy Helm binary from helm-fetch stage
COPY --from=helm-fetch /helm /usr/local/bin/helm

# Copy Cosign binary from cosign-fetch stage (CHART-04; R12 ordered after helm)
COPY --from=cosign-fetch /cosign /usr/local/bin/cosign

# Copy helm-diff plugin from helm-diff-fetch stage (Phase 5 D2).
# Plugin directory name MUST be `diff` (matches `name: "diff"` in plugin.yaml);
# destination is pipe user's HELM_PLUGINS path (NOT /root — see RESEARCH CONTRADICTION 1).
COPY --from=helm-diff-fetch /tmp/diff /home/pipe/.local/share/helm/plugins/diff

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
