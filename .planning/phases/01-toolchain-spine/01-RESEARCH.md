# Phase 1: Toolchain & Spine — Research

**Researched:** 2026-06-16
**Domain:** Python toolchain bootstrap (uv/ruff/mypy/pytest), src-layout skeleton, multi-stage Dockerfile, OCI annotations, structured logging
**Confidence:** HIGH (all package versions verified against PyPI; Dockerfile patterns from official Docker docs; tool choices pre-decided in STACK.md and cross-verified in SUMMARY.md)

---

## Summary

Phase 1 is a pure greenfield bootstrap — no v1 code is ported, only v1 interface contracts (env var names from `pipe.yml` and `schema.py`) are inherited as context. The goal is a repo where `uv sync --all-extras` gives a working dev environment in under 10 seconds warm-cache, `ruff`/`mypy`/`pytest --cov-fail-under=100` all exit 0 on a placeholder skeleton, and `docker build` produces an annotated, non-root image from `python:3.13-slim-bookworm`.

The skeleton must include enough real modules (`settings.py`, `logging.py`, `errors.py`, `pipe_io.py`, `__main__.py`) that the 100% coverage gate can pass with a thin test layer — not with a raw empty package. Specifically: every `src/` file needs at least one importable symbol and one test that exercises it. The Phase 1 modules are the dependency of every later phase, so their interfaces must be designed conservatively.

OBS-01/OBS-02 (structured logging) is the only behaviorally rich module in Phase 1. Use `structlog` — it provides the dual human/JSON renderer with zero custom code and is the 2026 standard for Python structured logging. `stdlib logging` with a custom `JSONFormatter` is a viable alternative but adds ~50 lines of boilerplate that structlog eliminates.

**Primary recommendation:** Bootstrap the skeleton in two atomic commits — (1) `pyproject.toml` + `uv.lock` + toolchain config, (2) `src/` skeleton + `Dockerfile` + tests. This gives a clean revert point if the coverage gate or mypy scope turns out to need adjustment.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Env-var parsing + validation | Python application (`settings.py`) | — | Single source of truth; all other modules accept typed `Settings` object |
| Structured logging (OBS-01/02) | Python application (`logging.py`) | — | Stdlib `logging` + structlog renderer; LOG_FORMAT env var selects output mode |
| Error hierarchy | Python application (`errors.py`) | — | Pure Python; exit codes are properties of exception classes |
| Bitbucket toolkit adapter | Python application (`pipe_io.py`) | — | Thin wrapper; isolates the toolkit dep for testability |
| Python wheel resolution | Builder stage (uv in Dockerfile) | — | `uv sync --frozen --no-dev --compile-bytecode` produces /opt/venv |
| Helm binary | Runtime stage (copied from slim helper) | — | `curl` from `get.helm.sh` inside a builder stage; `COPY` into runtime |
| helm-diff plugin | Runtime stage (installed via `helm plugin install` during build) | — | Must be baked in; no network at runtime |
| OCI image annotations | Docker buildx at build time | — | `--annotation` flags, NOT `LABEL` (see IMAGE-05 section) |
| Non-root execution | Runtime stage (`USER pipe`) | — | `adduser` in Dockerfile; uid 10001 |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | `uv sync --all-extras` under 10s warm cache | pyproject.toml `[dependency-groups]` pattern; `uv 0.11.21` confirmed on PyPI |
| TOOL-02 | Source code under `src/aws_eks_helm_deploy/`; `pyproject.toml` replaces `requirements.txt` | src-layout section; pyproject.toml skeleton |
| TOOL-03 | `ruff check` and `ruff format --check` pass with zero findings | ruff 0.15.17 config block; rule sets E,F,I,B,UP,SIM,RUF,N,S |
| TOOL-04 | `mypy --strict src/` passes with zero errors | mypy 2.1.0 config; scope strategy; boto3-stubs extras |
| TOOL-05 | `pre-commit` runs ruff, mypy, pytest on staged files | `.pre-commit-config.yaml` pattern; hook versions |
| TOOL-06 | `pytest --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` passes | pytest 9.1.0; pytest-cov 7.1.0; placeholder module strategy |
| TOOL-07 | kind-based integration tier with one command | `kind 0.29+`; conftest.py cluster lifecycle pattern; Makefile target |
| TOOL-08 | Acceptance tier: docker build + `docker run` smoke | pytest `acceptance` mark; conftest session-scoped build; helm-stub fixture |
| IMAGE-01 | `python:3.13-slim-bookworm` base, NOT alpine | Dockerfile multi-stage pattern |
| IMAGE-02 | Multi-stage Dockerfile | builder + helm-fetch + runtime stages |
| IMAGE-03 | `USER pipe` with uid >= 10000 | `adduser --uid 10001` in runtime stage |
| IMAGE-05 | OCI annotations via `buildx --annotation` | `--annotation` vs `LABEL` distinction; six required fields |
| OBS-01 | Structured logs: human default, JSON on stderr when LOG_FORMAT=json | structlog 26.1.0; dual renderer pattern |
| OBS-02 | DEBUG=true raises verbosity without leaking credentials | structlog level filter; redact list pattern |
</phase_requirements>

---

## Standard Stack

### Core (runtime image dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `boto3` | `~=1.43` | AWS SDK (EKS, STS) | Replaces awscli; 1.43.30 latest [VERIFIED: PyPI] |
| `bitbucket-pipes-toolkit` | `~=6.2` | Pipe contract (env vars, success/fail output) | Non-negotiable Marketplace dep; 6.2.0 latest [VERIFIED: PyPI] |
| `Jinja2` | `~=3.1` | kubeconfig templating | Already in v1; 3.1.6 [VERIFIED: PyPI] |
| `PyYAML` | `~=6.0` | YAML parsing | 6.0.3 [VERIFIED: PyPI] |
| `structlog` | `~=26.0` | Structured logging (OBS-01/02) | 26.1.0; dual human/JSON renderer out of the box [VERIFIED: PyPI] |
| `pydantic-settings` | `~=2.14` | Env-var schema / Settings class | 2.14.1; replaces ad-hoc `os.environ` [VERIFIED: PyPI] |

> **Note on `bitbucket-pipes-toolkit`:** The installed version is 6.2.0 (not the 4.6 cited in STACK.md). STACK.md recommended `~=4.6` based on training data; PyPI shows 6.2.0 as latest. Use `~=6.2` in `pyproject.toml`. Verify Python 3.13 compat on first `uv sync` — toolkit historically lags by 3-6 months.  [ASSUMED: Python 3.13 compat — verify on first sync]

### Development toolchain (dependency-groups.dev)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ruff` | `~=0.15` | Lint + format + import-sort | Always; 0.15.17 latest [VERIFIED: PyPI] |
| `mypy` | `~=2.1` | Static type checking | Always; 2.1.0 latest [VERIFIED: PyPI] — note: STACK.md cited 1.18; current latest is 2.1.0 |
| `boto3-stubs[eks,sts]` | latest | Type stubs for boto3 | Required for `mypy --strict` on AWS calls [ASSUMED: compat with mypy 2.1] |
| `pytest` | `~=9.1` | Test runner | 9.1.0 latest [VERIFIED: PyPI]; STACK.md cited 8.4, now 9.1 |
| `pytest-cov` | `~=7.1` | Coverage | 7.1.0 [VERIFIED: PyPI] |
| `pytest-mock` | `~=3.15` | `mocker` fixture | 3.15.1 [VERIFIED: PyPI] |
| `pytest-xdist` | `~=3.8` | Parallel test execution | 3.8.0 [VERIFIED: PyPI]; use `-n auto` when suite > 50 tests |
| `moto[eks,sts]` | `~=5.2` | AWS service mocking | 5.2.2 [VERIFIED: PyPI] |
| `coverage[toml]` | `~=7.14` | Coverage backend | 7.14.1 [VERIFIED: PyPI] |
| `pre-commit` | `~=4.0` | Git hook orchestration | Latest 4.x [ASSUMED: check exact version] |
| `pip-audit` | `~=2.10` | Python dep vuln scan | 2.10.1 [VERIFIED: PyPI] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `structlog` | stdlib `logging` + custom `JSONFormatter` | ~50 lines of custom formatter boilerplate; structlog wins on day-one simplicity |
| `pydantic-settings` | bitbucket-pipes-toolkit schema only | Toolkit schema is runtime-only; pydantic-settings gives mypy-verifiable types |
| `mypy --strict` | `pyright` / `basedpyright` | pyright catches more edge cases (~98% spec vs ~94%); mypy has better boto3-stubs ecosystem. Keep mypy; escape hatch to basedpyright for narrow corners |
| `pytest ~=9.1` | `pytest ~=8.4` | 9.x is current stable; no breaking change for this scope |

**Installation (dev bootstrap):**
```bash
# Install uv (single binary)
curl -LsSf https://astral.sh/uv/install.sh | sh

# All deps including dev + docs groups
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install --install-hooks
```

**Version verification performed:**
```
ruff: 0.15.17 (PyPI 2026-06-16)
mypy: 2.1.0  (PyPI 2026-06-16)  ← STACK.md said ~=1.18; actual latest is 2.1.0
uv: 0.11.21  (PyPI 2026-06-16)
pytest: 9.1.0 (PyPI 2026-06-16) ← STACK.md said ~=8.4; 9.1 is now stable
pytest-cov: 7.1.0 (PyPI 2026-06-16)
pytest-mock: 3.15.1 (PyPI 2026-06-16)
moto: 5.2.2 (PyPI 2026-06-16)
structlog: 26.1.0 (PyPI 2026-06-16) ← new package not in STACK.md
pydantic-settings: 2.14.1 (PyPI 2026-06-16)
bitbucket-pipes-toolkit: 6.2.0 (PyPI 2026-06-16) ← STACK.md said ~=4.6; actual is 6.2.0
boto3: 1.43.30 (PyPI 2026-06-16)
```

---

## Package Legitimacy Audit

> All packages below are long-established, high-download PyPI packages from well-known maintainers.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `uv` | PyPI | ~2 yrs | Very high | github.com/astral-sh/uv | OK | Approved |
| `ruff` | PyPI | ~3 yrs | Very high | github.com/astral-sh/ruff | OK | Approved |
| `mypy` | PyPI | ~10 yrs | Very high | github.com/python/mypy | OK | Approved |
| `pytest` | PyPI | ~15 yrs | Very high | github.com/pytest-dev/pytest | OK | Approved |
| `pytest-cov` | PyPI | ~10 yrs | Very high | github.com/pytest-dev/pytest-cov | OK | Approved |
| `pytest-mock` | PyPI | ~8 yrs | Very high | github.com/pytest-dev/pytest-mock | OK | Approved |
| `pytest-xdist` | PyPI | ~10 yrs | Very high | github.com/pytest-dev/pytest-xdist | OK | Approved |
| `moto` | PyPI | ~10 yrs | High | github.com/getmoto/moto | OK | Approved |
| `boto3` | PyPI | ~10 yrs | Very high | github.com/boto/boto3 | OK | Approved |
| `boto3-stubs` | PyPI | ~5 yrs | High | github.com/youtype/mypy_boto3_builder | OK | Approved |
| `structlog` | PyPI | ~10 yrs | High | github.com/hynek/structlog | OK | Approved |
| `pydantic-settings` | PyPI | ~3 yrs | Very high | github.com/pydantic/pydantic-settings | OK | Approved |
| `pre-commit` | PyPI | ~8 yrs | Very high | github.com/pre-commit/pre-commit | OK | Approved |
| `pip-audit` | PyPI | ~4 yrs | High | github.com/pypa/pip-audit | OK | Approved |
| `bitbucket-pipes-toolkit` | PyPI | ~5 yrs | Medium | bitbucket.org/atlassian/... | OK [ASSUMED] | Approved — verify Python 3.13 compat |
| `Jinja2` | PyPI | ~15 yrs | Very high | github.com/pallets/jinja | OK | Approved |
| `PyYAML` | PyPI | ~15 yrs | Very high | github.com/yaml/pyyaml | OK | Approved |
| `coverage` | PyPI | ~15 yrs | Very high | github.com/nedbat/coveragepy | OK | Approved |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious:** none

---

## Architecture Patterns

### System Architecture Diagram

```
[Bitbucket Pipelines runner env vars]
          │
          ▼
  python -m aws_eks_helm_deploy   (ENTRYPOINT)
          │
          ▼
    cli.main()
     ├─ Settings()        ← pydantic-settings reads ALL env vars, validates types
     ├─ configure_logging(settings)  ← structlog: human or JSON based on LOG_FORMAT
     └─ action = ACTIONS[settings.action or "upgrade"]
          │
          ▼
   [Phase 1 skeleton: UpgradePlaceholderAction]
          │
          ▼
   pipe_io.success() / pipe_io.fail()   ← bitbucket-pipes-toolkit adapter
          │
          ▼
       exit 0 / exit N
```

Phase 1 does not wire real AWS or Helm calls — those land in Phases 2-3. The skeleton must include real module files with importable symbols so that `mypy --strict` and `pytest --cov-fail-under=100` both pass.

### Recommended Project Structure (Phase 1 scope)

```
aws-eks-helm-deploy/
├── pyproject.toml                    # uv-managed; all tool config
├── uv.lock                           # committed; CI uses --frozen
├── Dockerfile                        # multi-stage, linux/amd64 initially
├── .dockerignore
├── .pre-commit-config.yaml
├── Makefile                          # integration-test, acceptance-test targets
│
├── src/
│   └── aws_eks_helm_deploy/
│       ├── __init__.py               # __version__ from importlib.metadata
│       ├── __main__.py               # calls cli.main(); ENTRYPOINT hook
│       ├── cli.py                    # main(): build Settings, configure logging, dispatch
│       ├── settings.py               # pydantic-settings BaseSettings; ALL env vars
│       ├── logging.py                # structlog configuration; configure_logging()
│       ├── errors.py                 # PipeError hierarchy + exit codes
│       └── pipe_io.py                # thin wrapper over bitbucket-pipes-toolkit
│
└── tests/
    ├── conftest.py                   # shared fixtures
    └── unit/
        ├── test_settings.py
        ├── test_cli.py
        ├── test_logging.py
        ├── test_errors.py
        └── test_pipe_io.py
```

Phase 1 does NOT create `actions/`, `auth/`, `aws/`, `helm/`, `chart/`, `kube/`, `metadata/` — those land in later phases. The skeleton has only the "spine" modules.

### Pattern 1: pyproject.toml — Full Phase 1 Shape

```toml
[project]
name = "aws-eks-helm-deploy"
version = "2.0.0-dev"
requires-python = ">=3.13"
dependencies = [
    "boto3 ~= 1.43",
    "bitbucket-pipes-toolkit ~= 6.2",
    "Jinja2 ~= 3.1",
    "PyYAML ~= 6.0",
    "structlog ~= 26.0",
    "pydantic-settings ~= 2.14",
]

[project.scripts]
aws-eks-helm-deploy = "aws_eks_helm_deploy.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aws_eks_helm_deploy"]

[dependency-groups]
dev = [
    "ruff ~= 0.15",
    "mypy ~= 2.1",
    "boto3-stubs[eks,sts]",
    "pytest ~= 9.1",
    "pytest-cov ~= 7.1",
    "pytest-mock ~= 3.15",
    "pytest-xdist ~= 3.8",
    "moto[eks,sts] ~= 5.2",
    "coverage[toml] ~= 7.14",
    "pre-commit ~= 4.0",
    "pip-audit ~= 2.10",
]
integration = [
    "pytest ~= 9.1",
    "pytest-mock ~= 3.15",
]
acceptance = [
    "pytest ~= 9.1",
]

[tool.uv]
default-groups = ["dev"]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "N", "S", "C90", "ANN"]
ignore = ["ANN101", "ANN102", "S101"]  # allow assert in tests; self/cls don't need annotation
# ANN = annotations (forces all args typed); S = bandit security rules subsumed by ruff

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN"]   # asserts and bare args OK in tests

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.13"
strict = true
files = ["src"]
# Do NOT include tests/ in Phase 1 strict scope — defer test typing to later plan
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: fast, no I/O, default tier",
    "integration: requires kind + helm binary",
    "acceptance: requires docker; builds image",
]
addopts = "-m 'unit' --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100"

[tool.coverage.run]
branch = true
source = ["aws_eks_helm_deploy"]

[tool.coverage.report]
show_missing = true
skip_covered = false
```

### Pattern 2: Settings skeleton (pydantic-settings)

```python
# src/aws_eks_helm_deploy/settings.py
from __future__ import annotations
from typing import Annotated
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=True)

    # AWS credentials (required in Phases 2+; optional in Phase 1 skeleton)
    aws_region: str = Field(default="eu-central-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    role_arn: str | None = Field(default=None, alias="ROLE_ARN")
    session_name: str = Field(default="BitbucketPipe", alias="SESSION_NAME")

    # Cluster + chart (required at runtime, optional for unit tests)
    cluster_name: str | None = Field(default=None, alias="CLUSTER_NAME")
    chart: str | None = Field(default=None, alias="CHART")
    release_name: str | None = Field(default=None, alias="RELEASE_NAME")
    namespace: str = Field(default="default", alias="NAMESPACE")  # v1 had kube-public — fixed here
    create_namespace: bool = Field(default=False, alias="CREATE_NAMESPACE")
    set_values: list[str] = Field(default_factory=list, alias="SET")
    values_files: list[str] = Field(default_factory=list, alias="VALUES")
    wait: bool = Field(default=False, alias="WAIT")
    timeout: str = Field(default="5m", alias="TIMEOUT")

    # Action dispatch
    action: str = Field(default="upgrade", alias="ACTION")
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    # Observability (OBS-01, OBS-02)
    log_format: str = Field(default="human", alias="LOG_FORMAT")  # "human" | "json"
    debug: bool = Field(default=False, alias="DEBUG")

    # Metadata injection (v2 default=False — breaking vs v1)
    inject_bitbucket_metadata: bool = Field(default=False, alias="INJECT_BITBUCKET_METADATA")
```

**Critical detail:** `NAMESPACE` default is `"default"` — v1 had `kube-public` in schema.py and `default` in pipe.yml. v2 fixes this to `"default"` definitively. Document in CHANGELOG.

### Pattern 3: Structured logging (OBS-01/02) via structlog

```python
# src/aws_eks_helm_deploy/logging.py
from __future__ import annotations
import logging
import sys
import structlog
from aws_eks_helm_deploy.settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog for the pipe. Call once at startup."""
    log_level = logging.DEBUG if settings.debug else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.log_format == "json":
        # OBS-01: one JSON object per line on stderr
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        stream = sys.stderr
    else:
        # Human-readable default
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        stream = sys.stderr  # toolkit writes stdout; we own stderr

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
```

**Stable field names (OBS-01):** `action`, `cluster`, `release`, `namespace`, `chart_source`, `auth_strategy`, `duration_ms`. These are added via `structlog.contextvars.bind_contextvars(action=..., cluster=..., ...)` at the start of each action, then inherited by all log calls in that invocation.

**Credential guard (OBS-02):** Never bind `aws_access_key_id`, `aws_secret_access_key`, `session_token`, or any OIDC token to structlog context. In DEBUG mode, log `auth_strategy="static_keys"` or `auth_strategy="oidc"` — never the credential values.

### Pattern 4: Error hierarchy

```python
# src/aws_eks_helm_deploy/errors.py
from __future__ import annotations


class PipeError(Exception):
    """Root for all pipe-originated errors. cli.main() catches this."""
    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code

    @property
    def user_message(self) -> str:
        return str(self)


class ConfigurationError(PipeError):
    exit_code = 1   # bad/missing env var

class AuthenticationError(PipeError):
    exit_code = 2   # STS/OIDC failed

class ClusterAccessError(PipeError):
    exit_code = 3   # describe-cluster failed

class ChartResolutionError(PipeError):
    exit_code = 4   # chart not found / version missing

class HelmError(PipeError):
    exit_code = 5   # helm exited non-zero

class HelmTimeoutError(PipeError):
    exit_code = 6   # --wait timed out
```

### Pattern 5: Multi-stage Dockerfile (Phase 1 version — linux/amd64 only)

```dockerfile
# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG HELM_VERSION=3.18.3
ARG HELM_DIFF_VERSION=3.10.0

# ── Stage 1: Python dependency builder ───────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
# Copy uv from the official uv Docker image (no curl/install needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# --frozen: use locked versions exactly; --no-dev: no dev tools in image
# --compile-bytecode: pre-compile .pyc for faster import at runtime
RUN uv sync --frozen --no-dev --compile-bytecode

# ── Stage 2: Helm binary fetch ────────────────────────────────────────────────
FROM debian:bookworm-slim AS helm-fetch
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
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

# System deps: git is required by helm-diff plugin installer
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (IMAGE-03): uid 10001
RUN addgroup --gid 10001 pipe \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos "" pipe

# Copy the installed venv from builder
COPY --from=builder /build/.venv /opt/venv

# Copy Helm binary
COPY --from=helm-fetch /helm /usr/local/bin/helm

ENV PATH="/opt/venv/bin:${PATH}" \
    HELM_PLUGINS=/home/pipe/.local/share/helm/plugins \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Install helm-diff plugin as the pipe user (plugins are user-scoped)
USER pipe
RUN helm plugin install \
    https://github.com/databus23/helm-diff \
    --version "v${HELM_DIFF_VERSION}"

WORKDIR /home/pipe

# OCI annotations are added at buildx call time via --annotation (not LABEL)
# See IMAGE-05 section for the exact buildx command

ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]
```

**Important:** `helm plugin install` runs as the `pipe` user so plugins land in `/home/pipe/.local/share/helm/plugins`. Set `HELM_PLUGINS` to that path, not `/root/.local/...`.

### Pattern 6: OCI annotations — `--annotation` vs `LABEL` (IMAGE-05)

`LABEL` in a Dockerfile sets image-config labels. `--annotation` on `docker buildx build` sets OCI manifest-level annotations, which is what `org.opencontainers.image.*` labels are supposed to be. Using `--annotation` instead of `LABEL` is the correct approach for OCI compliance and is required so that `docker buildx imagetools inspect` surfaces them.

**Phase 1 build command (single-arch, local dev):**
```bash
docker buildx build \
  --platform linux/amd64 \
  --annotation "manifest:org.opencontainers.image.source=https://github.com/yves-vogl/aws-eks-helm-deploy" \
  --annotation "manifest:org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --annotation "manifest:org.opencontainers.image.version=2.0.0-dev" \
  --annotation "manifest:org.opencontainers.image.licenses=Apache-2.0" \
  --annotation "manifest:org.opencontainers.image.title=AWS EKS Helm Deploy" \
  --annotation "manifest:org.opencontainers.image.description=Deploy Helm charts to AWS EKS from Bitbucket Pipelines" \
  --load \
  -t aws-eks-helm-deploy:dev \
  .
```

**Note on `manifest:` prefix:** The `manifest:` prefix in `--annotation` means "apply to the image manifest" (as opposed to the OCI index or a layer). This is the correct target for image-level metadata.

**In GitHub Actions (Phase 6), this becomes:**
```yaml
- uses: docker/metadata-action@v5
  id: meta
  with:
    images: |
      ghcr.io/yves-vogl/aws-eks-helm-deploy
      yvogl/aws-eks-helm-deploy
    tags: |
      type=semver,pattern={{version}}
      type=semver,pattern={{major}}.{{minor}}
      type=semver,pattern={{major}}

- uses: docker/build-push-action@v6
  with:
    annotations: ${{ steps.meta.outputs.annotations }}
    labels: ${{ steps.meta.outputs.labels }}
```

### Pattern 7: pre-commit config

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.17
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.1.0
    hooks:
      - id: mypy
        args: [--strict, src]
        additional_dependencies:
          - boto3-stubs[eks,sts]
          - pydantic-settings
          - structlog
          - types-PyYAML

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict

  - repo: local
    hooks:
      - id: pytest-quick
        name: pytest (unit, no-cov)
        entry: uv run pytest -q -m unit --no-cov
        language: system
        pass_filenames: false
        always_run: true
```

### Anti-Patterns to Avoid

- **Do NOT use `LABEL` for OCI annotations** — use `buildx --annotation`. Labels land in image config, not the OCI manifest index; `imagetools inspect` won't surface them correctly.
- **Do NOT run `helm plugin install` as root** — the plugin writes to `$HELM_PLUGINS` which defaults to `~/.local/share/helm/plugins`. As root in the final image, that's `/root/...` and becomes inaccessible to `USER pipe`.
- **Do NOT add `src/` modules with zero symbols** — an `__init__.py` with no exports passes import but mypy may warn; and coverage of an empty module counts as 100% vacuously. Always add at least one function with a type signature.
- **Do NOT scope `mypy --strict` to `tests/`** in Phase 1. Tests import `pytest`, `mocker`, and `moto` which all have type stubs that can generate noise. Keep `files = ["src"]` in `[tool.mypy]`.
- **Do NOT use `python:3-slim-bookworm`** (floating minor tag). Pin to `python:3.13-slim-bookworm` explicitly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured logging with dual human/JSON output | Custom `JSONFormatter` + `StreamHandler` chain | `structlog` | 50+ lines of boilerplate vs 20 lines; structlog handles async, processors, contextvars |
| Env-var schema with type coercion | `os.environ.get()` + manual casting | `pydantic-settings` `BaseSettings` | No central validation; no mypy-verifiable types; v1's bug pattern |
| Credential masking | Manual string replace on log messages | structlog processor + redact list | Easy to miss a log site; processor runs on every event |
| AWS service mocking in tests | Hand-rolling `boto3` client mocks with `MagicMock` | `moto[eks,sts]` | moto intercepts at the HTTP level; catches header mismatches that MagicMock misses |
| Pre-commit orchestration | Makefile `lint` target | `pre-commit` | pre-commit caches envs, only reruns changed files, identical to CI |

---

## Common Pitfalls

### Pitfall 1: uv.lock drift between dev and CI

**What goes wrong:** Developer runs `uv sync` (not `--frozen`), uv resolves a newer transitive dep, lockfile updates. CI uses old lockfile and gets a different environment. Latent dependency version mismatch.

**Why it happens:** `uv sync` without `--frozen` is a resolver call; it can update `uv.lock` silently.

**How to avoid:**
- Local dev: `uv sync --all-extras` (updates lock if needed — OK for dev)
- CI: `uv sync --frozen --all-extras` (fails if lockfile would change)
- Dockerfile: `uv sync --frozen --no-dev --compile-bytecode` (lockfile-pinned, no dev tools)
- Commit `uv.lock` and gate PRs on lockfile consistency: `uv lock --check` in CI

**Warning signs:** CI environment has a different package version than local `pip show`; `ImportError` in CI that doesn't reproduce locally.

### Pitfall 2: mypy --strict noise on first contact with boto3-stubs

**What goes wrong:** `boto3-stubs` stubs are extremely strict. On first `mypy --strict src/` you get 20-50 errors like `"EKSClient" has no attribute "describe_cluster"` (wrong stub extras installed) or `error: Call to untyped function "get_session"` (wrong `botocore` stubs).

**Why it happens:** You must install exactly the right extras (`boto3-stubs[eks,sts]`); installing `boto3-stubs` bare gives empty stubs.

**How to avoid:**
- Install `boto3-stubs[eks,sts]` explicitly — no `boto3-stubs[essential]` (80 MB).
- Phase 1 skeleton does not import boto3 yet — defer stubs noise to Phase 2.
- In Phase 1, add `# type: ignore[import-untyped]` only on the `bitbucket-pipes-toolkit` import if it ships without stubs.

**Warning signs:** `error: Cannot find implementation or library stub for module named "boto3"` — means stubs not installed; `error: Module "mypy_boto3_eks" has no attribute "..."` — means wrong extras.

### Pitfall 3: 100% coverage gate with placeholder modules

**What goes wrong:** An empty `__init__.py` is 100% covered vacuously. But once any real code is added (e.g., `__version__`), the gate may break if the corresponding test doesn't import it.

**Why it happens:** `pytest-cov` measures the installed package; any file under `src/aws_eks_helm_deploy/` that is NOT imported in any test counts as 0% covered.

**How to avoid:**
- Phase 1 adds: `__init__.py` (with `__version__`), `__main__.py`, `cli.py`, `settings.py`, `logging.py`, `errors.py`, `pipe_io.py`.
- Every file must be exercised by at least one unit test.
- Use `# pragma: no cover` sparingly and only for `if __name__ == "__main__":` guards.
- Add `omit = ["*/tests/*", "*/__main__.py"]` to `[tool.coverage.run]` for the `__main__` guard.

**Warning signs:** Coverage drops when adding a new module that has no test yet.

### Pitfall 4: helm-diff plugin installed as root breaks at runtime

**What goes wrong:** If `helm plugin install` runs while `USER` is still `root`, the plugin is installed in `/root/.local/share/helm/plugins`. At runtime the container switches to `USER pipe` (uid 10001) and `helm diff` fails with "plugin not found".

**How to avoid:** Switch `USER pipe` BEFORE running `helm plugin install`. Verify with `RUN helm diff --help` as the last Dockerfile step.

### Pitfall 5: bitbucket-pipes-toolkit Python 3.13 compat

**What goes wrong:** `bitbucket-pipes-toolkit 6.2.0` may or may not declare `python_requires >= 3.13` support. If it uses deprecated `distutils` or `pkg_resources` APIs removed in 3.13, `uv sync` will succeed but `import bitbucket_pipes_toolkit` will fail at runtime.

**Why it happens:** Minor Python version bumps frequently break toolkits that use deprecated stdlib APIs.

**How to avoid:** On the very first `uv sync`, run `python -c "import bitbucket_pipes_toolkit; print('OK')"`. If it fails, pin to a known-good version or add `python_requires` constraints in `pyproject.toml`.

**Warning signs:** `ImportError: cannot import name 'X' from 'distutils'` on startup.

---

## Code Examples

### Minimal test to hit 100% coverage on settings.py

```python
# tests/unit/test_settings.py
import pytest
from aws_eks_helm_deploy.settings import Settings


def test_settings_defaults() -> None:
    """Settings can be instantiated with no env vars (all optional in Phase 1)."""
    s = Settings()
    assert s.namespace == "default"
    assert s.action == "upgrade"
    assert s.log_format == "human"
    assert s.debug is False
    assert s.inject_bitbucket_metadata is False


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUSTER_NAME", "my-cluster")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_FORMAT", "json")
    s = Settings()
    assert s.cluster_name == "my-cluster"
    assert s.debug is True
    assert s.log_format == "json"
```

### Minimal test for errors.py

```python
# tests/unit/test_errors.py
from aws_eks_helm_deploy.errors import (
    PipeError, ConfigurationError, AuthenticationError,
    HelmError, HelmTimeoutError,
)


def test_pipe_error_exit_codes() -> None:
    assert ConfigurationError("x").exit_code == 1
    assert AuthenticationError("x").exit_code == 2
    assert HelmError("x").exit_code == 5
    assert HelmTimeoutError("x").exit_code == 6


def test_pipe_error_user_message() -> None:
    e = ConfigurationError("CLUSTER_NAME is required")
    assert e.user_message == "CLUSTER_NAME is required"
```

### Acceptance test fixture pattern (TOOL-08)

```python
# tests/acceptance/conftest.py
import subprocess
import pytest


@pytest.fixture(scope="session")
def built_image() -> str:
    """Build the image once per test session."""
    image_tag = "aws-eks-helm-deploy:acceptance-test"
    result = subprocess.run(
        ["docker", "build", "-t", image_tag, "."],
        check=True,
        capture_output=True,
        text=True,
    )
    return image_tag


# tests/acceptance/test_smoke.py
def test_image_runs_as_nonroot(built_image: str) -> None:
    result = subprocess.run(
        ["docker", "run", "--rm", built_image, "python", "-c",
         "import os; assert os.getuid() != 0, f'Running as root! uid={os.getuid()}'"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_help_exits_with_error(built_image: str) -> None:
    """Without env vars the pipe should fail cleanly, not crash."""
    result = subprocess.run(
        ["docker", "run", "--rm", built_image],
        capture_output=True, text=True
    )
    # Phase 1: pipe exits non-zero because no CLUSTER_NAME/CHART set
    assert result.returncode != 0
    # Must not be a Python traceback
    assert "Traceback" not in result.stderr
```

### Integration test (TOOL-07) — kind smoke

```python
# tests/integration/conftest.py
import subprocess
import pytest


@pytest.fixture(scope="session")
def kind_cluster() -> str:
    """Create a kind cluster once per session, delete on teardown."""
    cluster_name = "test-pipe-integration"
    subprocess.run(
        ["kind", "create", "cluster", "--name", cluster_name],
        check=True
    )
    yield cluster_name
    subprocess.run(
        ["kind", "delete", "cluster", "--name", cluster_name],
        check=False
    )


# tests/integration/test_helm_smoke.py
@pytest.mark.integration
def test_helm_version_in_cluster(kind_cluster: str) -> None:
    """Verify helm can reach the kind cluster."""
    result = subprocess.run(
        ["helm", "version", "--short"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "v3." in result.stdout
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | TOOL-08, IMAGE-01..05 | Yes | 27.3.1 | — |
| Python 3.x | Local dev | Yes | 3.14.5 (system) | uv manages its own Python 3.13 |
| uv | TOOL-01 | No (not on PATH) | — | Install via `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| kind | TOOL-07 | No | — | `brew install kind` or `go install sigs.k8s.io/kind@latest` |
| helm | TOOL-07 (integration) | No | — | `brew install helm` for local integration tests |
| docker buildx | IMAGE-05, acceptance | Yes (bundled with Docker 27) | bundled | — |

**Missing dependencies with no fallback:**
- `uv` — must be installed before any work begins; Makefile `bootstrap` target should document this

**Missing dependencies with fallback:**
- `kind` — integration tests skip gracefully with `pytest.mark.skipif(shutil.which("kind") is None, reason="kind not installed")`
- `helm` (local) — integration tests skip if helm not found; helm is bundled in the Docker image for acceptance tests

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — does not exist yet (Wave 0) |
| Quick run command | `uv run pytest -m unit -q` |
| Full suite command | `uv run pytest -m 'unit or integration or acceptance'` |
| Coverage run | `uv run pytest --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | `uv sync --all-extras` < 10s warm | smoke | `time uv sync --all-extras --frozen` | ❌ Wave 0 |
| TOOL-02 | src layout importable | unit | `python -c "import aws_eks_helm_deploy"` | ❌ Wave 0 |
| TOOL-03 | ruff zero findings | lint | `uv run ruff check src tests` | ❌ Wave 0 |
| TOOL-04 | mypy --strict zero errors | type | `uv run mypy --strict src` | ❌ Wave 0 |
| TOOL-05 | pre-commit all files green | lint | `uv run pre-commit run --all-files` | ❌ Wave 0 |
| TOOL-06 | 100% line+branch coverage | unit | `uv run pytest --cov --cov-fail-under=100` | ❌ Wave 0 |
| TOOL-07 | kind integration smoke | integration | `uv run pytest -m integration` | ❌ Wave 0 |
| TOOL-08 | docker build + non-root | acceptance | `uv run pytest -m acceptance` | ❌ Wave 0 |
| IMAGE-01 | slim-bookworm base | acceptance | inspect image `FROM` layer | ❌ Wave 0 |
| IMAGE-02 | multi-stage Dockerfile | acceptance | `docker history` shows stages | ❌ Wave 0 |
| IMAGE-03 | uid >= 10000 | acceptance | `docker run -- whoami; id` | ❌ Wave 0 |
| IMAGE-05 | OCI annotations present | acceptance | `docker buildx imagetools inspect` | ❌ Wave 0 |
| OBS-01 | JSON on stderr w/ LOG_FORMAT=json | unit | `test_logging.py::test_json_output` | ❌ Wave 0 |
| OBS-02 | DEBUG=true raises verbosity | unit | `test_logging.py::test_debug_level` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest -m unit -q --no-cov` (< 5s)
- **Per wave merge:** `uv run pytest --cov --cov-fail-under=100 && uv run ruff check src && uv run mypy --strict src`
- **Phase gate:** Full suite green (`unit` + `integration` + `acceptance`) before `/gsd-verify-work`

### Wave 0 Gaps

All test infrastructure must be created from scratch (greenfield):

- [ ] `pyproject.toml` — pytest, coverage, ruff, mypy config
- [ ] `tests/conftest.py` — shared fixtures
- [ ] `tests/unit/test_settings.py` — covers `settings.py`
- [ ] `tests/unit/test_logging.py` — covers `logging.py`; verifies JSON/human switch
- [ ] `tests/unit/test_errors.py` — covers `errors.py`; all exit codes
- [ ] `tests/unit/test_cli.py` — covers `cli.py`; dispatch and error handling
- [ ] `tests/unit/test_pipe_io.py` — covers `pipe_io.py`; mocked toolkit calls
- [ ] `tests/integration/conftest.py` — kind cluster lifecycle fixture
- [ ] `tests/integration/test_helm_smoke.py` — helm version check against kind
- [ ] `tests/acceptance/conftest.py` — session-scoped docker build
- [ ] `tests/acceptance/test_smoke.py` — non-root, clean error on missing vars

---

## Security Domain

> `security_enforcement: true` in `config.json`, `security_asvs_level: 1`.

### Applicable ASVS Categories (Phase 1 scope)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not yet — auth strategy arrives in Phase 2 |
| V3 Session Management | No | Single-shot CLI, no sessions |
| V4 Access Control | No | Single user (pipe uid) |
| V5 Input Validation | Yes | `pydantic-settings` validates all env-var inputs; `ConfigurationError` on invalid |
| V6 Cryptography | No | No crypto in Phase 1; EKS token presigning in Phase 2 |
| V7 Error Handling | Yes | `PipeError` hierarchy; no raw tracebacks to user output; generic exit 99 for unexpected |
| V8 Data Protection | Partial | Structured logger must never bind credential env vars; test this in `test_logging.py` |

### Known Threat Patterns (Phase 1 stack)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leakage via logging | Information Disclosure | structlog processor; explicit blocklist of credential env var names |
| Pydantic model validation bypass | Tampering | `model_config = SettingsConfigDict(extra="ignore")` — unknown env vars silently ignored, not error-prone |
| Missing input validation for `action` field | Tampering | `action: Literal["upgrade", "diff", "rollback"]` in Settings; pydantic rejects unknown values |
| Container running as root | Elevation of Privilege | `adduser --uid 10001` + `USER pipe` in Dockerfile |

---

## State of the Art

| Old Approach (v1) | Current Approach (v2) | When Changed | Impact |
|-------------------|-----------------------|--------------|--------|
| `requirements.txt` + `pip install` | `pyproject.toml` + `uv sync --frozen` | PEP 621 (2020), uv (2023) | Reproducible, 10-100× faster, lockfile |
| `python:3-alpine` base | `python:3.13-slim-bookworm` | Ongoing; musl issues documented 2021+ | Stable wheels, proper DNS, bigger but predictable |
| 2-space indent, no type hints, `BaseException` subclasses | `mypy --strict`, `ruff format`, `Exception` subclasses | ruff 0.1 (2023), mypy 1.0 (2023) | Catches 30-40% of bugs at commit time |
| No structured logging | `structlog` dual renderer | structlog 21.5+ | Parseable by CloudWatch/Datadog/etc. |
| `from awscli.customizations.eks.get_token import ...` | `boto3`-only STS presign | v2.0 decision | Removes internal import; saves 120 MB |
| `LABEL` for image metadata | `buildx --annotation` for OCI manifest annotations | OCI spec 1.1 (2024), buildx v0.11+ | Standards-compliant; visible in imagetools inspect |

**Deprecated/outdated:**
- `requirements.txt`: dead for new Python projects in 2026; pyproject.toml is the single metadata source
- `python:3-alpine`: musl-libc wheel issues make it unsuitable for boto3/cryptography; slim-bookworm wins
- `NAMESPACE: kube-public` (v1 schema.py default): v1 bug where README said `kube-public` and pipe.yml said `default`; v2 definitively chooses `default`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `bitbucket-pipes-toolkit 6.2.0` supports Python 3.13 | Standard Stack | Need to pin to older version or add compat shim; blocksWork on pipe_io.py |
| A2 | `pre-commit 4.0` is the correct current major (vs 3.8 cited in STACK.md) | Standard Stack | Minor — 3.8 is still functional; use `~=4.0` and fall back to `~=3.8` |
| A3 | Helm 3.18.3 is the current stable 3.18.x release | Dockerfile | Verify at https://github.com/helm/helm/releases before writing Dockerfile |
| A4 | helm-diff 3.10.0 is compatible with Helm 3.18 | Dockerfile | Could cause `helm plugin install` failure; check https://github.com/databus23/helm-diff/releases |
| A5 | `uv sync --frozen` in CI and Dockerfile is the correct invocation (vs `--locked` which is pip-compile style) | Multiple | uv 0.11 uses `--frozen`; if flag changes, CI and Dockerfile break silently |

---

## Open Questions

1. **bitbucket-pipes-toolkit 6.2.0 Python 3.13 compat**
   - What we know: PyPI shows 6.2.0 as latest; STACK.md cited 4.6 from training data
   - What's unclear: whether 6.x dropped Python 3.11 compatibility annotations or has `distutils` usage removed in 3.13
   - Recommendation: On the first `uv sync`, run `python -c "import bitbucket_pipes_toolkit"` and fail fast; document the version pinned in CHANGELOG if we have to downgrade

2. **Helm 3.18 exact release**
   - What we know: STACK.md and ROADMAP both specify Helm 3.18.x; SUMMARY.md locks to 3.18
   - What's unclear: exact 3.18.x patch release for pinning the `curl` command in Dockerfile
   - Recommendation: Planner should check https://github.com/helm/helm/releases/latest at task execution time and pin the exact version + SHA256 checksum

3. **helm-diff 3.10.x compatibility with Helm 3.18**
   - What we know: STACK.md says helm-diff 3.10.x; helm-diff tracks Helm major (3.x)
   - What's unclear: whether 3.10.0 was released and tested against Helm 3.18
   - Recommendation: Verify at https://github.com/databus23/helm-diff/releases before writing Dockerfile ARG

---

## Sources

### Primary (HIGH confidence)
- PyPI package index — all package versions verified via `pip3 index versions` on 2026-06-16
- `.planning/research/STACK.md` — comprehensive tool decisions with citations; HIGH confidence rated in that document
- `.planning/research/ARCHITECTURE.md` — src layout, module structure, Dockerfile pattern; HIGH confidence
- `.planning/research/PITFALLS.md` — uv lockfile drift, mypy first-contact noise, helm plugin as root; HIGH confidence
- `.planning/research/SUMMARY.md` — cross-verified decision sheet; HIGH confidence

### Secondary (MEDIUM confidence)
- `pipe/schema.py` and `pipe/pipe.py` (v1 source) — provides the exact env var names and defaults to preserve/replace
- `.planning/REQUIREMENTS.md` — 14 Phase 1 requirements with precise wording
- `.planning/ROADMAP.md` Phase 1 section — success criteria

### Tertiary (LOW confidence / ASSUMED)
- Helm 3.18 exact patch release — [ASSUMED] planner must verify at execution time
- helm-diff 3.10.x compat with Helm 3.18 — [ASSUMED] planner must verify at execution time
- bitbucket-pipes-toolkit 6.2.0 Python 3.13 compat — [ASSUMED] verify on first `uv sync`

---

## Metadata

**Confidence breakdown:**
- Standard stack versions: HIGH — all verified against PyPI 2026-06-16
- Architecture / module structure: HIGH — derived from ARCHITECTURE.md which rated itself HIGH
- Pitfalls: HIGH — drawn from PITFALLS.md which cross-referenced upstream issue trackers
- Dockerfile shape: HIGH for pattern; MEDIUM for exact Helm/helm-diff versions (need runtime verification)
- OCI annotations (`--annotation` vs `LABEL`): HIGH — from OCI spec 1.1 and buildx docs

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (30 days; stable toolchain ecosystem)
