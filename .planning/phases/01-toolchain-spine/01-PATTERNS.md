# Phase 1: Toolchain & Spine — Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 19
**Analogs found:** 8 / 19 (11 are greenfield with no v1 analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | none | `requirements.txt` (v1) | concept-only — format entirely different |
| `uv.lock` | config | none | — | no analog |
| `.python-version` | config | none | — | no analog |
| `.pre-commit-config.yaml` | config | none | — | no analog |
| `Dockerfile` | container | none | `Dockerfile` (v1) | partial — same 2-stage concept, different base + structure |
| `.dockerignore` | config | none | — | no analog |
| `src/aws_eks_helm_deploy/__init__.py` | source-module | none | `pipe/__init__.py` (v1, empty) | structural only |
| `src/aws_eks_helm_deploy/cli.py` | source-module | request-response | `pipe/pipe.py` lines 131-136 `main()` | concept-only — v2 dispatches actions via typed `Settings` |
| `src/aws_eks_helm_deploy/logging.py` | source-module | none | — | no analog (v1 used toolkit logger directly) |
| `src/aws_eks_helm_deploy/errors.py` | source-module | none | `pipe/helm/error.py` | partial — same pattern of `Exception` subclasses |
| `tests/unit/test_smoke.py` | test | none | `pipe/test.py` | concept-only — v1 test runs module-level, no pytest markers |
| `tests/integration/conftest.py` | test | none | — | no analog |
| `tests/integration/test_helm_smoke.py` | test | none | `pipe/test.py` lines 46-65 | concept-only |
| `tests/acceptance/test_image_smoke.py` | test | none | `test/acceptance/` (not read) | concept-only |
| `Makefile` | config | none | — | no analog |
| `pipe.yml` | config | none | `pipe.yml` (v1) | exact — KEEP unchanged |
| `.gitignore` | config | none | — | no analog |

---

## Pattern Assignments

### `pyproject.toml` (config)

**Analog:** `requirements.txt` (v1) — carries over env-var names from `pipe/schema.py`

**V1 dependency names to preserve** (`pipe/schema.py` lines 24-40 + `requirements.txt`):
```
# Env-var names from schema.py → become Field(alias=...) in Settings:
AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, ROLE_ARN, SESSION_NAME,
CLUSTER_NAME, CHART, RELEASE_NAME, NAMESPACE, CREATE_NAMESPACE,
SET, VALUES, WAIT, DEBUG, TIMEOUT

# V1 deps being REPLACED (requirements.txt):
awscli~=1.32       → REMOVED
docker~=7.1        → REMOVED
bitbucket-pipes-toolkit~=4.4  → bumped to ~=6.2
Jinja2~=3.1        → KEPT
MarkupSafe~=2.1    → transitive, drop explicit pin
```

**Target shape** (from RESEARCH.md Pattern 1):
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
integration = ["pytest ~= 9.1", "pytest-mock ~= 3.15"]
acceptance  = ["pytest ~= 9.1"]

[tool.uv]
default-groups = ["dev"]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "N", "S", "C90", "ANN"]
ignore = ["ANN101", "ANN102", "S101"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.13"
strict = true
files = ["src"]
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
omit = ["*/tests/*", "*/__main__.py"]

[tool.coverage.report]
show_missing = true
skip_covered = false
```

---

### `Dockerfile` (container — REPLACE)

**Analog:** `Dockerfile` (v1, lines 1-17)

**V1 pattern to retire** (v1 Dockerfile lines 1-17):
```dockerfile
# V1 — DO NOT COPY:
FROM alpine/helm:3.15.1 as helm     # alpine base — retire
FROM python:3-alpine                  # floating tag + musl — retire
RUN pip install -r /opt/pipe/requirements.txt  # no lock — retire
ENTRYPOINT ["python"]
CMD ["/opt/pipe/pipe.py"]            # flat script entrypoint — retire
```

**Target shape** (from RESEARCH.md Pattern 5):
```dockerfile
# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG HELM_VERSION=3.18.3          # VERIFY at build time: github.com/helm/helm/releases/latest
ARG HELM_DIFF_VERSION=3.10.0    # VERIFY: github.com/databus23/helm-diff/releases

# Stage 1: Python dependency builder
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --compile-bytecode

# Stage 2: Helm binary fetch
FROM debian:bookworm-slim AS helm-fetch
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG HELM_VERSION
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
    | tar -xz -C /tmp \
    && mv /tmp/linux-amd64/helm /helm \
    && chmod +x /helm

# Stage 3: Runtime image
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
ARG HELM_DIFF_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN addgroup --gid 10001 pipe \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos "" pipe
COPY --from=builder /build/.venv /opt/venv
COPY --from=helm-fetch /helm /usr/local/bin/helm
ENV PATH="/opt/venv/bin:${PATH}" \
    HELM_PLUGINS=/home/pipe/.local/share/helm/plugins \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# CRITICAL: switch USER before helm plugin install
USER pipe
RUN helm plugin install \
    https://github.com/databus23/helm-diff \
    --version "v${HELM_DIFF_VERSION}"

WORKDIR /home/pipe
# OCI annotations: use `docker buildx build --annotation` at build time — NOT LABEL here
ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]
```

---

### `src/aws_eks_helm_deploy/__init__.py` (source-module)

**Analog:** `pipe/__init__.py` (v1, empty)

**Target shape:**
```python
from __future__ import annotations
from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("aws-eks-helm-deploy")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
```

---

### `src/aws_eks_helm_deploy/cli.py` (source-module, request-response)

**Analog:** `pipe/pipe.py` lines 131-136 (v1 `main()` + `HelmPipe.run()`)

**V1 entry pattern** (`pipe/pipe.py` lines 131-136):
```python
# V1 — shape to supersede:
def main():
    pipe = HelmPipe(pipe_metadata='pipe.yml', schema=schema.get_schema())
    pipe.run()

if __name__ == '__main__':
    main()
```

**V1 error handling** (`pipe/pipe.py` lines 105-110) — note: catches library-specific exceptions, no typed exit codes:
```python
except HelmChartNotFoundError as error:
    self.fail(message = f'No valid helm chart found at path {error}')
except HelmError as error:
    self.fail(message = error)
```

**Target shape** (from RESEARCH.md Pattern 2, Architecture Pattern 2):
```python
from __future__ import annotations
import sys
from aws_eks_helm_deploy.errors import PipeError
from aws_eks_helm_deploy.logging import configure_logging
# settings and pipe_io imported here — not scattered across module bodies

def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    from aws_eks_helm_deploy.settings import Settings
    from aws_eks_helm_deploy.pipe_io import PipeIO
    settings = Settings()
    configure_logging(settings)
    pipe = PipeIO()
    try:
        # Phase 1: placeholder dispatch — real actions land in Phase 4+
        pipe.success("Phase 1 skeleton — no action executed")
        return 0
    except PipeError as exc:
        pipe.fail(exc.user_message)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001
        pipe.fail("Unexpected error — see logs")
        return 99

if __name__ == "__main__":
    sys.exit(main())
```

---

### `src/aws_eks_helm_deploy/logging.py` (source-module)

**Analog:** None in v1 (v1 used `bitbucket_pipes_toolkit.get_logger` directly)

**Target shape** (from RESEARCH.md Pattern 3):
```python
from __future__ import annotations
import logging
import sys
import structlog
from aws_eks_helm_deploy.settings import Settings

def configure_logging(settings: Settings) -> None:
    """Configure structlog. Call once at startup in cli.main()."""
    log_level = logging.DEBUG if settings.debug else logging.INFO
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.log_format == "json":
        processors = [*shared_processors, structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
    else:
        processors = [*shared_processors, structlog.dev.ConsoleRenderer(colors=True)]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
```

**Credential guard:** NEVER bind `aws_access_key_id`, `aws_secret_access_key`, `session_token`, or any OIDC token to structlog context — per OBS-02.

---

### `src/aws_eks_helm_deploy/errors.py` (source-module)

**Analog:** `pipe/helm/error.py` (v1) — same `Exception` subclass pattern, extended with exit codes

**V1 pattern** (inferred from `pipe/helm/client.py` lines 21-22 and `pipe/pipe.py` lines 105-108):
```python
# V1 — no exit codes, no unified root:
class HelmError(Exception): ...
class HelmChartNotFoundError(Exception): ...
class HelmInvalidTimeout(Exception): ...
```

**Target shape** (from RESEARCH.md Pattern 4):
```python
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

---

### `src/aws_eks_helm_deploy/settings.py` (source-module — implied, required for cli.py)

**Analog:** `pipe/schema.py` (v1) — exact env-var names and defaults to preserve

**V1 defaults to carry forward or fix** (`pipe/schema.py` lines 24-40):
```python
# V1 schema → v2 Settings mapping:
# 'AWS_REGION': default 'eu-central-1'          → KEEP
# 'AWS_ACCESS_KEY_ID': required=True             → optional in Phase 1 (required at runtime)
# 'AWS_SECRET_ACCESS_KEY': required=True         → optional in Phase 1
# 'ROLE_ARN': nullable                           → str | None = None
# 'SESSION_NAME': dynamic default                → Field(default="BitbucketPipe")
# 'CLUSTER_NAME': required=True                  → str | None = None in Phase 1
# 'CHART': required=True                         → str | None = None in Phase 1
# 'NAMESPACE': default='kube-public' (V1 BUG)   → FIX to 'default'
# 'CREATE_NAMESPACE': default=False              → KEEP
# 'SET': list default []                         → list[str] = []
# 'VALUES': list default []                      → list[str] = []
# 'WAIT': default=False                          → KEEP
# 'DEBUG': default=False                         → KEEP
# 'TIMEOUT': default="5m"                        → KEEP
# NEW in v2: ACTION, DRY_RUN, LOG_FORMAT, INJECT_BITBUCKET_METADATA
```

**Target shape** (RESEARCH.md Pattern 2 — full skeleton):
```python
from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=True, extra="ignore")

    aws_region: str = Field(default="eu-central-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    role_arn: str | None = Field(default=None, alias="ROLE_ARN")
    session_name: str = Field(default="BitbucketPipe", alias="SESSION_NAME")
    cluster_name: str | None = Field(default=None, alias="CLUSTER_NAME")
    chart: str | None = Field(default=None, alias="CHART")
    release_name: str | None = Field(default=None, alias="RELEASE_NAME")
    namespace: str = Field(default="default", alias="NAMESPACE")  # v1 had kube-public — BUG FIXED
    create_namespace: bool = Field(default=False, alias="CREATE_NAMESPACE")
    set_values: list[str] = Field(default_factory=list, alias="SET")
    values_files: list[str] = Field(default_factory=list, alias="VALUES")
    wait: bool = Field(default=False, alias="WAIT")
    timeout: str = Field(default="5m", alias="TIMEOUT")
    action: str = Field(default="upgrade", alias="ACTION")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    log_format: str = Field(default="human", alias="LOG_FORMAT")
    debug: bool = Field(default=False, alias="DEBUG")
    inject_bitbucket_metadata: bool = Field(default=False, alias="INJECT_BITBUCKET_METADATA")
```

---

### `tests/unit/test_smoke.py` (test)

**Analog:** `pipe/test.py` (v1) — note: v1 test.py runs at module-level without pytest markers

**V1 test anti-pattern to avoid** (`pipe/test.py` lines 49-53, 79-80):
```python
# V1 — DO NOT COPY: module-level execution, no markers, patches via decorator on wrong import path
@patch('botocore.client.BaseClient._make_api_call', new=mock_make_api_call)
@patch('helm.client.HelmClient._run', new=mock_helm_run)
def test():
    pipe.main()

tests = [test, test_valid_durations, test_invalid_durations]
[t() for t in tests]  # runs at import — DO NOT DO THIS
```

**Target shape** (RESEARCH.md Code Examples):
```python
# tests/unit/test_smoke.py
import pytest
from aws_eks_helm_deploy.settings import Settings
from aws_eks_helm_deploy.errors import ConfigurationError, HelmError


def test_settings_defaults() -> None:
    s = Settings()
    assert s.namespace == "default"
    assert s.action == "upgrade"
    assert s.log_format == "human"
    assert s.debug is False


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUSTER_NAME", "my-cluster")
    monkeypatch.setenv("DEBUG", "true")
    s = Settings()
    assert s.cluster_name == "my-cluster"
    assert s.debug is True


def test_pipe_error_exit_codes() -> None:
    assert ConfigurationError("x").exit_code == 1
    assert HelmError("x").exit_code == 5
```

---

### `tests/integration/conftest.py` (test)

**Analog:** None in v1.

**Target shape** (RESEARCH.md Code Examples, Integration Pattern):
```python
# tests/integration/conftest.py
import subprocess
import shutil
import pytest


@pytest.fixture(scope="session")
def kind_cluster() -> str:  # type: ignore[return]
    if shutil.which("kind") is None:
        pytest.skip("kind not installed")
    cluster_name = "test-pipe-integration"
    subprocess.run(["kind", "create", "cluster", "--name", cluster_name], check=True)
    yield cluster_name
    subprocess.run(["kind", "delete", "cluster", "--name", cluster_name], check=False)
```

---

### `tests/integration/test_helm_smoke.py` (test)

**Target shape:**
```python
import subprocess
import pytest


@pytest.mark.integration
def test_helm_version_in_cluster(kind_cluster: str) -> None:
    result = subprocess.run(["helm", "version", "--short"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "v3." in result.stdout
```

---

### `tests/acceptance/test_image_smoke.py` (test)

**Target shape** (RESEARCH.md Code Examples, Acceptance Pattern):
```python
# tests/acceptance/conftest.py
import subprocess
import pytest

@pytest.fixture(scope="session")
def built_image() -> str:
    image_tag = "aws-eks-helm-deploy:acceptance-test"
    subprocess.run(["docker", "build", "-t", image_tag, "."], check=True, capture_output=True)
    return image_tag

# tests/acceptance/test_image_smoke.py
import subprocess
import pytest

@pytest.mark.acceptance
def test_image_runs_as_nonroot(built_image: str) -> None:
    result = subprocess.run(
        ["docker", "run", "--rm", built_image, "python", "-c",
         "import os; assert os.getuid() != 0"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

@pytest.mark.acceptance
def test_help_exits_without_traceback(built_image: str) -> None:
    result = subprocess.run(["docker", "run", "--rm", built_image], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
```

---

### `.pre-commit-config.yaml` (config)

**Analog:** None in v1.

**Target shape** (RESEARCH.md Pattern 7):
```yaml
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

---

### `Makefile` (config)

**Analog:** None in v1.

**Minimum targets required:**
```makefile
.PHONY: bootstrap lint type-check unit integration acceptance

bootstrap:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync --all-extras
	uv run pre-commit install --install-hooks

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

type-check:
	uv run mypy --strict src

unit:
	uv run pytest -m unit --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100

integration:
	uv run pytest -m integration

acceptance:
	uv run pytest -m acceptance
```

---

### `pipe.yml` (config — KEEP UNCHANGED)

**V1 file at:** `pipe.yml` lines 1-47.
This is the Bitbucket Marketplace contract. Phase 1 does not change it. The `image:` tag line will be updated by release-please in a later phase.

---

### `.gitignore` entries to add (UPDATE)

```
.venv/
.ruff_cache/
.mypy_cache/
.pytest_cache/
htmlcov/
.coverage
*.pyc
__pycache__/
dist/
*.egg-info/
```

---

## Shared Patterns

### `from __future__ import annotations`
**Apply to:** Every `src/` Python file.
All modules use `from __future__ import annotations` as line 1 (enables PEP 563 lazy annotation evaluation, required for Python 3.13 + mypy --strict consistency).

### Error handling root
**Source:** `src/aws_eks_helm_deploy/errors.py` (to be created)
**Apply to:** All source modules — raise typed `PipeError` subclasses; catch only in `cli.main()`.
```python
# Raise at call sites:
raise ConfigurationError("CLUSTER_NAME is required")
raise HelmError(f"helm exited {returncode}: {stderr}")

# Catch only in cli.main():
except PipeError as exc:
    pipe.fail(exc.user_message)
    return exc.exit_code
```

### Settings injection (never `os.environ` in module bodies)
**Anti-pattern from v1** (`pipe/pipe.py` lines 39-50): `self.get_variable('CLUSTER_NAME')` spread across `run()`.
**v2 pattern:** `settings = Settings()` once in `cli.main()`; pass `settings` object to everything that needs it. Never call `os.environ.get(...)` outside `settings.py`.

### Test marker discipline
```python
# All unit tests: no marker needed (default via addopts "-m unit")
# Integration tests:
@pytest.mark.integration
# Acceptance tests:
@pytest.mark.acceptance
```

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `uv.lock` | config | Generated by uv; no v1 lockfile |
| `.python-version` | config | v1 used floating `python:3-alpine` |
| `src/aws_eks_helm_deploy/logging.py` | source-module | v1 delegated logging to toolkit; no structlog |
| `tests/integration/conftest.py` | test | v1 had no integration tier |
| `tests/acceptance/test_image_smoke.py` | test | v1 acceptance tests in `test/acceptance/` were not read but used Bitbucket CI directly |
| `Makefile` | config | v1 had no Makefile |
| `.dockerignore` | config | v1 had none or minimal |

---

## Critical Anti-Patterns (from v1 — do not repeat)

1. **`from awscli.customizations.eks.get_token import ...`** (`pipe/pipe.py` line 20) — internal import; removed in v2 entirely.
2. **`NAMESPACE` default `kube-public`** (`pipe/schema.py` line 33) — v1 bug; v2 Settings fixes to `"default"`.
3. **`ENTRYPOINT ["python"] CMD ["/opt/pipe/pipe.py"]`** (`Dockerfile` lines 16-17) — replaced with `ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]`.
4. **`FROM python:3-alpine`** (`Dockerfile` line 4) — replaced with `python:3.13-slim-bookworm`.
5. **Module-level test execution** (`pipe/test.py` line 80: `[t() for t in tests]`) — replaced with proper pytest functions + markers.
6. **`helm plugin install` before `USER pipe`** (not in v1 but documented pitfall) — always switch user first.

---

## Metadata

**Analog search scope:** `pipe/`, `test/`, root config files
**Files scanned:** 10 (pipe.py, schema.py, helm/client.py, test.py, Dockerfile, requirements.txt, pipe.yml, __init__.py, helm/error.py inferred)
**Pattern extraction date:** 2026-06-16
