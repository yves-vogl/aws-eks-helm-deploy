# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.11.21
ARG HELM_VERSION=3.18.6
ARG HELM_DIFF_VERSION=3.10.0

# ── Stage 1: Python dependency builder ───────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# Copy uv from the official Astral image — no curl/install needed
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /uvx /bin/

WORKDIR /build

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --frozen: use locked versions exactly; --no-dev: no dev tools in image
# --no-editable: install the package itself as a wheel (not .pth editable install)
#               so the venv is fully self-contained when COPYd to the runtime stage
# --compile-bytecode: pre-compile .pyc for faster import at runtime
RUN uv sync --frozen --no-dev --no-editable --compile-bytecode

# ── Stage 2: Helm binary fetch ────────────────────────────────────────────────
FROM debian:bookworm-slim AS helm-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG HELM_VERSION

# linux/amd64 explicitly for Phase 1; multi-arch native-runner matrix lands in Phase 6
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
    | tar -xz -C /tmp \
    && mv /tmp/linux-amd64/helm /helm \
    && chmod +x /helm

# ── Stage 3: Runtime image ────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

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

# Purge curl — no longer needed after plugin install (sec-02)
# ca-certificates and git are retained: git is used by helm-diff for plugin updates
USER root
RUN apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
USER pipe

WORKDIR /home/pipe

# OCI annotations are attached via 'docker buildx build --annotation manifest:org.opencontainers.image.*=...'
# — see docs/build.md. Do NOT add LABEL org.opencontainers.image.* directives here.

ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]
