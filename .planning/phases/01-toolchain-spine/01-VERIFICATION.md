---
phase: 01-toolchain-spine
verified: 2026-06-17T00:10:00Z
status: human_needed
score: 4/5
overrides_applied: 0
human_verification:
  - test: "Run `LOG_FORMAT=json docker run --rm -e LOG_FORMAT=json aws-eks-helm-deploy:dev 2>&1 | python3 -c \"import sys, json; [json.loads(l) for l in sys.stdin]\"` and confirm it exits 0"
    expected: "At least one parseable JSON object emitted to stderr by the pipe runtime (not just toolkit stdout). Phase 1 current state emits zero bytes to stderr — only toolkit success message goes to stdout."
    why_human: "SC5 requires the pipe entrypoint to emit structured log lines with stable field names during actual execution. In Phase 1, the placeholder success path uses toolkit's pipe.success() (stdout) without any structlog.info() call. The logging infrastructure is tested in isolation (unit tests pass), but end-to-end emission from the running pipe is absent until Phase 2+ action dispatch wires bind_safe_context() calls. The VALIDATION.md explicitly lists this as a manual-only check."
---

# Phase 1: Toolchain & Spine — Verification Report

**Phase Goal:** A maintainer can clone the repo, run `uv sync --all-extras`, and get green `ruff`, `mypy --strict`, and `pytest` (with placeholder modules); the base Dockerfile builds for `linux/amd64` from `python:3.13-slim-bookworm` with OCI annotations and non-root user.
**Verified:** 2026-06-17T00:10:00Z
**Status:** PARTIAL → human_needed (SC5 infrastructure present, runtime emission deferred to Phase 2+)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | `uv sync --all-extras` completes <10s warm cache; `.venv/` produced with all dev tools (TOOL-01) | PASS | Warm-cache run: 16ms (`uv sync --all-extras --frozen` exits 0; 88 packages checked). All six runtime imports (`aws_eks_helm_deploy`, `bitbucket_pipes_toolkit`, `boto3`, `pydantic_settings`, `structlog`, `Jinja2`) verified. |
| SC2 | `ruff check`, `ruff format --check`, `mypy --strict src/` exit 0; `pre-commit run --all-files` runs same checks locally (TOOL-03, TOOL-04, TOOL-05) | PASS | All four commands exit 0 with zero findings. `pre-commit run --all-files` shows 9 hooks pass including ruff, ruff-format, mypy, pre-commit-hooks, pytest-quick. |
| SC3 | `pytest --cov --cov-branch --cov-fail-under=100` exits 0; integration tier provisions `kind` + helm smoke; acceptance tier builds image and runs `docker run` (TOOL-06, TOOL-07, TOOL-08) | PASS | 33 unit tests pass, 100% line+branch coverage (all 6 modules). Integration: 1 test skips cleanly when `kind` absent (correct behavior per VALIDATION). Acceptance: 3 tests pass (non-root, uid=10001, no-traceback). |
| SC4 | `docker build` produces `linux/amd64` from `python:3.13-slim-bookworm` with Helm 3.18.x + helm-diff 3.10.x, `USER pipe` (uid ≥ 10000), six OCI annotations via `buildx --annotation` (IMAGE-01, IMAGE-02, IMAGE-03, IMAGE-05) | PASS | `docker run --entrypoint id` → `10001`. `helm version --short` → `v3.18.6+gb76a950`. `helm diff version` → `3.10.0`. OCI annotations verified via `docker save` + manifest inspection: all 6 fields (`source`, `revision`, `version`, `licenses=Apache-2.0`, `title`, `description`) present on the `linux/amd64` manifest blob. `docs/build.md` documents the canonical `buildx --annotation` command. No `LABEL org.opencontainers.*` in Dockerfile. |
| SC5 | Pipe entrypoint emits human-readable logs by default and JSON on stderr with stable fields (`action`, `cluster`, `release`, `namespace`, `chart_source`, `auth_strategy`, `duration_ms`) when `LOG_FORMAT=json`; `DEBUG=true` raises verbosity without leaking credentials (OBS-01, OBS-02) | PARTIAL | Infrastructure: `configure_logging()` wired in `cli.main()` between `Settings()` and `PipeIO()`. Unit tests prove JSON/human renderers, DEBUG threshold, idempotency, and credential guard (`bind_safe_context` raises `ValueError` on blocklisted keys). **Gap:** Running `LOG_FORMAT=json docker run ... 2>&1` shows zero bytes on stderr — the Phase 1 placeholder path uses `pipe.success()` (toolkit stdout) without any `structlog.info()` calls. `STABLE_FIELDS` is defined but not bound at pipe execution time (Phase 2+ per documented design). |

**Score:** 4/5 truths PASS; SC5 is PARTIAL (infrastructure ready, runtime emission absent in Phase 1)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Package metadata + tool config + `--cov-fail-under=100` | VERIFIED | 86 lines; `[project]`, `[project.scripts]`, `[dependency-groups]`, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` with `cov-fail-under=100`, `[tool.coverage.*]` all present. |
| `uv.lock` | Pinned resolver output | VERIFIED | 218,565 bytes; 88 packages resolved. |
| `.python-version` | `3.13` | VERIFIED | Contains `3.13\n`. |
| `.pre-commit-config.yaml` | ruff + mypy + pre-commit-hooks + pytest-quick | VERIFIED | `astral-sh/ruff-pre-commit v0.15.17`, `mirrors-mypy v2.1.0`, `pre-commit-hooks v5.0.0`, local `pytest-quick` hook. `pass_filenames: false` on mypy; `files: ^(src|tests)/` scoping correct. |
| `src/aws_eks_helm_deploy/__init__.py` | `__version__` from `importlib.metadata` | VERIFIED | 10 lines; `__version__ = "2.0.0.dev0"` on installed package. |
| `src/aws_eks_helm_deploy/settings.py` | `Settings(BaseSettings)` with all v1 aliases + v2 fields | VERIFIED | 61 lines; `class Settings(BaseSettings)` with 19 fields using `Field(alias=...)`. NAMESPACE default `"default"` (v1 bug fixed). `extra="ignore"` in `SettingsConfigDict`. |
| `src/aws_eks_helm_deploy/errors.py` | PipeError hierarchy with typed exit codes | VERIFIED | 67 lines; 7 classes, exit codes 1–6 matching spec. |
| `src/aws_eks_helm_deploy/pipe_io.py` | `PipeIO` stub (lazy toolkit init) | VERIFIED (stub) | 45 lines; `PipeIO` with `success()` and `fail()` delegating to `bitbucket_pipes_toolkit.Pipe`. Documented as Phase 1 stub; schema-driven init in Phase 2. |
| `src/aws_eks_helm_deploy/cli.py` | `main(argv) -> int` with `configure_logging` call | VERIFIED | 46 lines; `configure_logging(settings)` called after `Settings()`, before `PipeIO()`. PipeError catch + bare Exception catch wired. |
| `src/aws_eks_helm_deploy/logging.py` | `configure_logging` + `get_logger` + `bind_safe_context` + `STABLE_FIELDS` + `CREDENTIAL_BLOCKLIST` | VERIFIED | 119 lines; all 5 exports present; dual JSON/human renderer; 7-element `STABLE_FIELDS` tuple; 7-element `CREDENTIAL_BLOCKLIST` frozenset. |
| `Dockerfile` | 3-stage: builder/helm-fetch/runtime; python:3.13-slim-bookworm; Helm 3.18.x; helm-diff 3.10.x; USER pipe | VERIFIED | 82 lines; `ARG PYTHON_VERSION=3.13`, `ARG HELM_VERSION=3.18.6`, `ARG HELM_DIFF_VERSION=3.10.0`; `USER pipe` on line 66 before `RUN helm plugin install` on line 69; uid 10001 confirmed. |
| `.dockerignore` | Excludes `.venv/`, `.git/`, `.planning/`, `tests/`, build artifacts | VERIFIED | 45 lines; all expected exclusions present. |
| `docs/build.md` | Canonical `docker buildx build --annotation ...` command | VERIFIED | 171 lines; 6 `manifest:org.opencontainers.image.*` entries; rationale for `--annotation` over `LABEL`; `manifest:` prefix explanation. |
| `tests/conftest.py` | Auto-unit-marker hook | VERIFIED | Present; `pytest_collection_modifyitems` applies `unit` mark to unmarked tests under `tests/unit/`. |
| `tests/integration/conftest.py` | `kind_cluster` session fixture with skip guard | VERIFIED | Contains `kind_cluster` fixture; `shutil.which("kind")` skip guard present. |
| `tests/integration/test_helm_smoke.py` | `test_helm_version_in_cluster` | VERIFIED | Present; `@pytest.mark.integration`; `helm version --short` asserted. |
| `tests/acceptance/conftest.py` | `built_image` session fixture | VERIFIED | Contains `built_image`; `docker build -t aws-eks-helm-deploy:acceptance-test .` |
| `tests/acceptance/test_image_smoke.py` | `test_image_runs_as_nonroot` + 2 more | VERIFIED | 3 tests: nonroot, uid>=10000, no-traceback. All 3 PASS in acceptance run. |
| `Makefile` | bootstrap/lint/type-check/unit/integration/acceptance + aliases | VERIFIED | 9 `.PHONY` targets including `integration-test` and `acceptance-test` aliases. |
| `requirements.txt` | Must NOT exist | VERIFIED | Absent. `test ! -f requirements.txt` exits 0. |

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `src/aws_eks_helm_deploy/cli.py` | `src/aws_eks_helm_deploy/settings.py` | `from aws_eks_helm_deploy.settings import Settings` | WIRED | `cli.py:15`: `from aws_eks_helm_deploy.settings import Settings`; `cli.py:27`: `settings = Settings()` |
| `src/aws_eks_helm_deploy/cli.py` | `src/aws_eks_helm_deploy/logging.py` | `from aws_eks_helm_deploy.logging import configure_logging` | WIRED | `cli.py:13`: import present; `cli.py:28`: `configure_logging(settings)` called |
| `src/aws_eks_helm_deploy/cli.py` | `src/aws_eks_helm_deploy/errors.py` | `except PipeError as exc` | WIRED | `cli.py:12`: `from aws_eks_helm_deploy.errors import PipeError`; `cli.py:35`: `except PipeError as exc` |
| `src/aws_eks_helm_deploy/__main__.py` | `src/aws_eks_helm_deploy/cli.py` | `from aws_eks_helm_deploy.cli import main; sys.exit(main())` | WIRED | `__main__.py` lines 1-2 match exactly |
| `pyproject.toml [project.scripts]` | `cli.py::main` | console_script entry point | WIRED | `pyproject.toml:15`: `aws-eks-helm-deploy = "aws_eks_helm_deploy.cli:main"` |
| `pyproject.toml [tool.pytest.ini_options]` | coverage gate | `--cov-fail-under=100` in addopts | WIRED | `pyproject.toml:76`: `addopts = "-m 'unit' --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100"` |
| `tests/integration/conftest.py::kind_cluster` | kind CLI | `shutil.which("kind")` skip guard | WIRED | `conftest.py`: `shutil.which("kind")` and `subprocess.run(["kind", "create", ...])` |
| `tests/acceptance/conftest.py::built_image` | Dockerfile | `docker build -t aws-eks-helm-deploy:acceptance-test .` | WIRED | `conftest.py`: `subprocess.run(["docker", "build", "-t", _IMAGE_TAG, ...])` |
| `Dockerfile builder stage` | `pyproject.toml + uv.lock` | `COPY pyproject.toml uv.lock README.md ./` + `uv sync --frozen` | WIRED | `Dockerfile:14,21`: COPY and `uv sync --frozen --no-dev --no-editable --compile-bytecode` |
| `Dockerfile runtime USER pipe` | helm plugin install | `USER pipe` before `RUN helm plugin install` | WIRED | `Dockerfile:66,69`: `USER pipe` on line 66, `RUN helm plugin install` on line 69. Pitfall 4 closed. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `cli.py` | `settings` | `Settings()` reads env vars via pydantic-settings | Yes — pydantic validates from os.environ | FLOWING |
| `logging.py::configure_logging` | `settings.log_format`, `settings.debug` | `Settings` object passed as arg | Yes — reads real env vars | FLOWING |
| `logging.py::bind_safe_context` | context kwargs | caller (Phase 2+ action dispatch) | N/A in Phase 1 — not yet called at runtime | STUB (documented) |
| `pipe_io.py::PipeIO` | toolkit Pipe | `bitbucket_pipes_toolkit.Pipe(pipe_metadata=...)` | Yes — lazy init on first call | FLOWING (stub schema) |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `uv sync --all-extras` warm cache <10s | `time uv sync --all-extras --frozen` (twice) | Second run: 16ms real time | PASS |
| `ruff check` exits 0 | `uv run ruff check src tests` | `All checks passed!` | PASS |
| `ruff format --check` exits 0 | `uv run ruff format --check src tests` | `22 files already formatted` | PASS |
| `mypy --strict src` exits 0 | `uv run mypy --strict src` | `Success: no issues found in 7 source files` | PASS |
| `pytest --cov-fail-under=100` exits 0 | `uv run pytest --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100` | 33 passed, 100% coverage, `Required test coverage of 100% reached` | PASS |
| Integration tier skips cleanly | `uv run pytest -m integration -q --no-cov` | `1 skipped, 36 deselected` (kind not installed) | PASS |
| Acceptance tier passes | `uv run pytest -m acceptance -q --no-cov` | `3 passed, 34 deselected` | PASS |
| pre-commit all hooks pass | `uv run pre-commit run --all-files` | All 9 hooks: Passed | PASS |
| Docker image runs as uid 10001 | `docker run --rm --entrypoint id aws-eks-helm-deploy:dev -u` | `10001` | PASS |
| Helm 3.18.x in image | `docker run --rm --entrypoint helm aws-eks-helm-deploy:dev version --short` | `v3.18.6+gb76a950` | PASS |
| helm-diff 3.10.x in image | `docker run --rm --entrypoint helm aws-eks-helm-deploy:dev diff version` | `3.10.0` | PASS |
| OCI annotations on built image | `docker buildx build --annotation ... --load` + manifest inspection via `docker save` | All 6 annotations in `blobs/sha256/<amd64-manifest>` | PASS |
| Package importable | `uv run python -c "import aws_eks_helm_deploy; print(__version__)"` | `2.0.0.dev0` | PASS |
| requirements.txt absent | `test ! -f requirements.txt` | exits 0 | PASS |
| NAMESPACE default fixed from v1 bug | `Settings().namespace` | `"default"` (not `"kube-public"`) | PASS |
| Credential guard raises ValueError | `bind_safe_context(aws_access_key_id='AKIA...')` | `ValueError: Credential leak: 'aws_access_key_id' is blocklisted` | PASS |
| JSON log format emits parseable JSON (unit) | `uv run pytest tests/unit/test_logging.py::test_configure_logging_json_emits_parseable_json` | 1 passed | PASS |
| DEBUG=true lowers threshold (unit) | `uv run pytest tests/unit/test_logging.py::test_debug_true_lowers_threshold` | 1 passed | PASS |
| LOG_FORMAT=json actual Docker emission | `docker run -e LOG_FORMAT=json ... 2>&1` | **0 bytes on stderr** — only toolkit stdout | NEEDS HUMAN |

---

### Probe Execution

No probe scripts present (`scripts/*/tests/probe-*.sh` pattern not found). Step 7c: SKIPPED (no probes defined for Phase 1).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| TOOL-01 | Plan 01 | `uv sync --all-extras` <10s warm cache | SATISFIED | 16ms warm-cache run verified; `.venv/` populated with 88 packages |
| TOOL-02 | Plan 01 | `src/aws_eks_helm_deploy/` layout; `pyproject.toml` as sole dep manifest; `requirements.txt` removed | SATISFIED | All 7 modules present; `requirements.txt` absent; `pyproject.toml` is the entry point |
| TOOL-03 | Plan 01 | `ruff check` + `ruff format --check` exit 0 | SATISFIED | Both exit 0; `All checks passed!` |
| TOOL-04 | Plan 01 | `mypy --strict src/` exits 0 | SATISFIED | `Success: no issues found in 7 source files` |
| TOOL-05 | Plan 01 | `pre-commit run --all-files` exits 0 | SATISFIED | All 9 hooks pass; mirrors CI checks |
| TOOL-06 | Plan 02 | `pytest --cov-fail-under=100` exits 0 | SATISFIED | 100% line+branch on all 6 modules; 33 tests pass |
| TOOL-07 | Plan 02 | `make integration-test` or `uv run pytest tests/integration` provisions kind cluster | SATISFIED (conditional) | Fixture exists and wired; skips cleanly when kind absent; actual cluster run deferred to CI (Phase 6) per plan |
| TOOL-08 | Plan 02 | Acceptance tier builds image and runs `docker run` | SATISFIED | 3 acceptance tests pass (non-root, uid>=10000, no-traceback) |
| IMAGE-01 | Plan 03 | `python:3.13-slim-bookworm` base; not Alpine | SATISFIED | `FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime`; `python --version` → `3.13.14` |
| IMAGE-02 | Plan 03 | Helm 3.18.x + helm-diff 3.10.x bundled | SATISFIED | `helm version --short` → `v3.18.6`; `helm diff version` → `3.10.0` |
| IMAGE-03 | Plan 03 | Non-root `USER pipe` with uid ≥ 10000 | SATISFIED | `id -u` → `10001`; `whoami` → `pipe`; `adduser --uid 10001` in Dockerfile |
| IMAGE-05 | Plan 03 | OCI annotations via `buildx --annotation` (not LABEL) | SATISFIED | 6 annotations in manifest blob verified via `docker save` inspection; `docs/build.md` canonical command documented |
| OBS-01 | Plan 04 | Structured log lines: JSON on stderr when `LOG_FORMAT=json`; stable field names | PARTIAL | Infrastructure: `configure_logging` wired, dual renderer tested, `STABLE_FIELDS` defined. **Gap:** Actual pipe execution emits 0 bytes to stderr in Phase 1 — no `structlog.info()` calls in the placeholder path. Stable fields (`action`, `cluster`, etc.) are not bound at runtime until Phase 2+ action dispatch. |
| OBS-02 | Plan 04 | `DEBUG=true` raises verbosity; no credential leaks | SATISFIED | Credential guard (`bind_safe_context` raises `ValueError`) confirmed. DEBUG threshold tested in unit tests. |

**Requirements summary:** 13/14 SATISFIED; OBS-01 is PARTIAL (infrastructure present, runtime emission Phase 2+).

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/aws_eks_helm_deploy/pipe_io.py` | 1 | Documented stub (no schema validation) | INFO | Intentional; Phase 2 replaces with schema-driven `Pipe(pipe_metadata=..., schema=...)`. Explicitly documented in module docstring. |
| `src/aws_eks_helm_deploy/cli.py` | 32 | Placeholder success path (`"Phase 1 skeleton — no action executed"`) | INFO | Intentional; Phase 3+ adds real ACTION dispatch. Documented in module docstring. |
| No TBD/FIXME/XXX/unreferenced debt markers found | — | — | — | Clean scan on all Phase 1 modified files |

No unreferenced debt markers (`TBD`, `FIXME`, `XXX`) detected. All stubs are documented with explicit Phase references.

---

### Human Verification Required

#### 1. OBS-01 Runtime JSON Emission Check (SC5 final gate)

**Test:** Run `docker run --rm -e LOG_FORMAT=json aws-eks-helm-deploy:dev 2>/tmp/stderr.txt; cat /tmp/stderr.txt` and verify the file contains at least one parseable JSON line with an `event` key.

**Expected:** The pipe emits at least one structlog JSON line on stderr during execution (e.g., a startup log or action-level log). The JSON line should parse cleanly and contain the `event` key (and ideally some of the STABLE_FIELDS keys when context is bound).

**Why human:** Currently the Phase 1 placeholder path (`pipe.success()` via toolkit) writes to stdout, not stderr. No `structlog.info()` or `get_logger().info()` calls exist in `cli.py` or any Phase 1 module. The logging infrastructure is verified in unit isolation but produces zero stderr output in the actual running pipe. The VALIDATION.md marks this as "Manual-Only" and acknowledges it as a Phase 1 limitation. If the intent is that the Phase 1 skeleton MUST emit at least a startup log line via structlog (even if STABLE_FIELDS aren't all populated), then `cli.py` needs a `get_logger(__name__).info("pipe starting", action=settings.action)` call added. If this is acceptable as Phase 2+ work, then SC5 can be downgraded to PASS for Phase 1.

**Recommended resolution:** Add a single `get_logger(__name__).info("pipe invoked", action=settings.action)` call in `cli.py` after `configure_logging(settings)`. This would make the Docker `LOG_FORMAT=json` test emit one parseable JSON line and satisfy SC5 end-to-end without waiting for Phase 2+ action dispatch.

---

### Gaps Summary

**SC5 (OBS-01) is the sole gap.** The logging *infrastructure* (configure_logging, JSON renderer, credential guard, STABLE_FIELDS contract) is complete and tested to 100% unit coverage. What is missing is the *emission point* in the actual pipe execution path: the Phase 1 `cli.py` has no `get_logger().info()` call, so running the image with `LOG_FORMAT=json` produces zero bytes on stderr.

**Root cause:** The Phase 1 placeholder success path was designed to route output through `bitbucket_pipes_toolkit.Pipe.success()` (which writes to stdout), deferring all structlog logging to Phase 2+ action dispatch. This is a documented design decision in PLAN-04 Known Stubs and VALIDATION.md Manual-Only items.

**Remediation (low effort):** Add one `get_logger(__name__).info("pipe invoked", action=settings.action)` call in `cli.py` after `configure_logging(settings)`. This satisfies OBS-01 without scope creep and makes the Phase 1 end-to-end observable.

**If accepted as-is:** The VALIDATION.md explicitly defers end-to-end OBS-01 Docker smoke to "after Plan C + D merge" with the manual-only note. One could argue Phase 1 scope is complete with the infrastructure in place. An override could be applied if the team agrees.

---

## Overall Verdict

**PARTIAL / human_needed**

- **4/5 Success Criteria: PASS** — The toolchain (SC1–SC2), test infrastructure (SC3), and Docker image (SC4) all meet the phase goal exactly.
- **1/5 Success Criteria: PARTIAL** — SC5 (OBS-01/02) has the logging infrastructure fully in place and tested, but the pipe entrypoint does not emit any structlog lines at runtime. The stable field names are defined but not bound during pipe execution. This is a documented Phase 2+ item.
- **13/14 Requirements: SATISFIED** — OBS-01 is PARTIAL for the same reason.

The phase goal is **substantively achieved**. A maintainer can clone, `uv sync --all-extras`, and get green `ruff`, `mypy --strict`, and `pytest`. The Dockerfile builds correctly. The only open question is whether a single `get_logger().info()` call should be added to `cli.py` to close SC5 end-to-end before declaring Phase 1 complete.

---

## Evidence Index

| Item | Location | Verified Value |
|------|----------|----------------|
| uv warm-cache timing | `uv sync` output | 16ms (target: <10s) |
| pytest coverage | `.coverage` file + stdout | 100% line+branch, 33 tests |
| Docker image uid | `docker run --entrypoint id aws-eks-helm-deploy:dev -u` | `10001` |
| Helm version | `docker run --entrypoint helm ... version --short` | `v3.18.6+gb76a950` |
| helm-diff version | `docker run --entrypoint helm ... diff version` | `3.10.0` |
| OCI annotations | `docker save` + manifest blob `a374d62...` | 6 annotations confirmed |
| ruff exit | `uv run ruff check src tests` | exit 0 |
| mypy exit | `uv run mypy --strict src` | exit 0, 7 source files |
| pre-commit | `uv run pre-commit run --all-files` | 9 hooks: Passed |
| requirements.txt | `test ! -f requirements.txt` | absent |
| NAMESPACE default | `Settings().namespace` | `"default"` |
| Credential guard | `bind_safe_context(aws_access_key_id=...)` | raises `ValueError` |
| JSON renderer (unit) | `test_configure_logging_json_emits_parseable_json` | 1 PASSED |
| Docker stderr (LOG_FORMAT=json) | `docker run -e LOG_FORMAT=json ... 2>/tmp/err.txt` | **0 bytes** — gap |

---

*Verified: 2026-06-17T00:10:00Z*
*Verifier: Claude (gsd-verifier, claude-sonnet-4-6)*
*Branch: phase/01-toolchain-spine @ ccb07e0*
