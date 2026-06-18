# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.11.21
ARG HELM_VERSION=3.18.6
ARG HELM_DIFF_VERSION=3.10.0
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

# linux/amd64 explicitly for Phase 1; multi-arch native-runner matrix lands in Phase 6
# Download Helm tarball + SHA256 checksum and verify integrity before extraction (sec-14).
# Files are saved under their UPSTREAM names so sha256sum -c can resolve the filename
# embedded in the .sha256sum file (e.g. "3f43c0aa...  helm-v3.18.6-linux-amd64.tar.gz").
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
        -o "/tmp/helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
    && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz.sha256sum" \
        -o "/tmp/helm-v${HELM_VERSION}-linux-amd64.tar.gz.sha256sum" \
    && cd /tmp \
    && sha256sum -c "helm-v${HELM_VERSION}-linux-amd64.tar.gz.sha256sum" \
    && tar -xz -f "helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
    && mv linux-amd64/helm /helm \
    && chmod +x /helm \
    && rm -rf "helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
              "helm-v${HELM_VERSION}-linux-amd64.tar.gz.sha256sum" \
              linux-amd64

# ── Stage 2.5: Cosign binary fetch ───────────────────────────────────────────
# R12: this stage is placed BETWEEN helm-fetch and runtime for layer-cache ordering.
# cosign 2.x keyless is the default (RESEARCH §3); COSIGN_EXPERIMENTAL=1 not needed.
FROM debian:bookworm-slim@${DEBIAN_BASE_DIGEST} AS cosign-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG COSIGN_VERSION

# linux/amd64 only — multi-arch lands Phase 6 alongside helm-fetch
# Downloads cosign-linux-amd64 + cosign_checksums.txt (Sigstore canonical pinning pattern,
# RESEARCH §6). The checksum file lists ~115 assets; grep filters to the exact file.
RUN curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64" \
        -o "/tmp/cosign-linux-amd64" \
    && curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign_checksums.txt" \
        -o "/tmp/cosign_checksums.txt" \
    && cd /tmp \
    && grep "  cosign-linux-amd64$" cosign_checksums.txt | sha256sum -c \
    && mv cosign-linux-amd64 /cosign \
    && chmod +x /cosign \
    && rm -f /tmp/cosign_checksums.txt

# ── Stage 3: Runtime image ────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST} AS runtime

ARG HELM_DIFF_VERSION

# System deps: git + curl are required by helm-diff plugin installer; ca-certificates for TLS
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
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

ENV PATH="/opt/venv/bin:${PATH}" \
    HELM_PLUGINS=/home/pipe/.local/share/helm/plugins \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# CRITICAL: switch USER before helm plugin install so the plugin lands in
# /home/pipe/.local/share/helm/plugins (not /root/.local/...) — see PITFALL 4
USER pipe

# Install helm-diff plugin as the pipe user (plugins are user-scoped via HELM_PLUGINS)
RUN helm plugin install \
    https://github.com/databus23/helm-diff \
    --version "v${HELM_DIFF_VERSION}"

# Verify helm-diff is reachable as pipe user — build fails early if Pitfall 4 recurs
RUN helm diff version

# Purge curl and git — neither is needed at runtime (sec-02, sec-14).
# helm-diff plugin updates are a BUILD-TIME operation (helm plugin install above);
# the runtime pipe only calls `helm diff` which does not exec git.
USER root
RUN apt-get purge -y curl git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
USER pipe

WORKDIR /home/pipe

# OCI annotations are attached via 'docker buildx build --annotation manifest:org.opencontainers.image.*=...'
# — see docs/build.md. Do NOT add LABEL org.opencontainers.image.* directives here.

ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]
