---
phase: 01-toolchain-spine
plan: 01
subsystem: toolchain
tags: [python, uv, ruff, mypy, pre-commit, pydantic-settings, structlog, boto3, pytest, bootstrap]

# Dependency graph
requires: []
provides:
  - pyproject.toml with runtime deps and dev/integration/acceptance dependency groups
  - uv.lock (pinned resolver; downstream uv sync --frozen is deterministic)
  - .python-version pinning Python 3.13 (uv-managed interpreter)
  - src/aws_eks_helm_deploy/ with six skeleton modules (__init__, __main__, cli, settings, errors, pipe_io)
  - tests/unit/ with four test files covering all skeleton modules
  - .pre-commit-config.yaml with ruff + ruff-format + mypy + pre-commit-hooks + pytest-quick
  - requirements.txt removed (v1 dep manifest retired)
affects:
  - 01-02 (Plan B: test infra — wires --cov-fail-under=100 gate added in Plan A)
  - 01-03 (Plan C: Dockerfile — COPY pyproject.toml + uv.lock + src/)
  - 01-04 (Plan D: structured logging — adds logging.py that cli.py will call)
  - all future plans (Settings, PipeError hierarchy, PipeIO stub are dependency roots)

# Tech tracking
tech-stack:
  added:
    - uv 0.11.21 (installed via homebrew — not on PATH before this plan)
    - ruff 0.15.17 (lint + format)
    - mypy 2.1.0 (strict type checking; note: STACK.md said 1.18, actual latest is 2.1.0)
    - pytest 9.1.0 + pytest-cov 7.1.0 + pytest-mock 3.15.1 + pytest-xdist 3.8.0
    - pydantic-settings 2.14.1 (Settings BaseSettings)
    - structlog 26.1.0 (deferred to Plan D; present in deps)
    - boto3 1.43.31 + boto3-stubs[eks,sts] (type stubs)
    - bitbucket-pipes-toolkit 6.2.0 (Python 3.13 compatible — ASSUMED resolved OK)
    - moto[eks,sts] 5.2.2 (AWS service mocking)
    - coverage[toml] 7.14.1 (coverage backend)
    - pre-commit 4.6.0 (hook orchestration)
    - pip-audit 2.10.1 (dep vulnerability scan)
    - hatchling (build backend)
  patterns:
    - src-layout: all source under src/aws_eks_helm_deploy/
    - PipeError hierarchy: typed exit codes, user_message property, caught only in cli.main()
    - Settings-first: pydantic-settings BaseSettings with Field(alias=ENV_VAR) for all config
    - PipeIO stub: lazy toolkit init, full schema-driven init deferred to Phase 2
    - from __future__ import annotations on every src/ module
    - pytest markers: unit (default via addopts), integration, acceptance
    - pre-commit hooks scoped to src/ and tests/ only (v1 pipe/ excluded)

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .python-version
    - .pre-commit-config.yaml
    - src/aws_eks_helm_deploy/__init__.py
    - src/aws_eks_helm_deploy/__main__.py
    - src/aws_eks_helm_deploy/cli.py
    - src/aws_eks_helm_deploy/settings.py
    - src/aws_eks_helm_deploy/errors.py
    - src/aws_eks_helm_deploy/pipe_io.py
    - tests/__init__.py
    - tests/unit/__init__.py
    - tests/unit/test_settings.py
    - tests/unit/test_errors.py
    - tests/unit/test_pipe_io.py
    - tests/unit/test_cli.py
  modified:
    - .gitignore (extended with .venv, caches, dist artifacts)
  deleted:
    - requirements.txt (v1 dep manifest retired)

key-decisions:
  - "bitbucket-pipes-toolkit 6.2.0 confirmed Python 3.13 compatible (import OK); no downgrade needed"
  - "ruff BLE rule added to select (BLE001 needed for noqa in cli.py); ANN101/ANN102 removed (rules deleted in ruff 0.15)"
  - "mypy pre-commit hook uses pass_filenames: false to avoid duplicate-module error in src-layout"
  - "pre-commit hooks scoped to src/ and tests/ via files: patterns; v1 pipe/ directory excluded from v2 linting"
  - "NAMESPACE default fixed from kube-public (v1 bug) to 'default' in Settings; regression test added"
  - "addopts in [tool.pytest.ini_options] does NOT include --cov-fail-under=100 in Plan A; Plan B wires the gate"

patterns-established:
  - "Pattern: PipeError subclasses carry typed exit codes; cli.main() is the sole catch site"
  - "Pattern: Settings uses pydantic-settings BaseSettings with Field(alias=ENV_NAME); never os.environ outside settings.py"
  - "Pattern: PipeIO stub wraps toolkit with lazy init; src modules tested via mocker.patch on the Pipe class"

requirements-completed: [TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05]

# Metrics
duration: 10min
completed: 2026-06-17
---

# Phase 01 Plan 01: Toolchain Spine Summary

**uv-managed Python 3.13 workspace with ruff/mypy/pytest toolchain, pydantic-settings Settings, typed PipeError hierarchy, PipeIO stub, and pre-commit hooks — all green on the v2 skeleton**

## Performance

- **Duration:** ~10 min (wall-clock; fast due to warm Homebrew caches after uv install)
- **Started:** 2026-06-17T06:27:11Z
- **Completed:** 2026-06-17T06:37:00Z
- **Tasks:** 3 (A1, A2, A3)
- **Files modified:** 19 (16 new, 1 modified, 1 extended, 1 deleted)

## Accomplishments

- Bootstrapped `uv sync --all-extras --frozen` workspace; warm-cache run completes in 21ms (target: <10s)
- Six source modules in `src/aws_eks_helm_deploy/` pass `ruff check`, `ruff format --check`, and `mypy --strict`
- 13 unit tests cover all four skeleton modules (settings, errors, pipe_io, cli); all green under `pytest -m unit`
- `pre-commit run --all-files` exits 0 with ruff, mypy, pre-commit-hooks, and pytest-quick hooks scoped to `src/` and `tests/`

## bitbucket-pipes-toolkit version

**Pinned: 6.2.0** — Python 3.13 compat confirmed. `import bitbucket_pipes_toolkit` succeeded without errors after `uv sync`. No downgrade was required. The `[ASSUMED]` flag from RESEARCH.md is resolved: A1 assumption confirmed OK.

## Warm-cache timing (TOOL-01 informational)

`uv sync --all-extras --frozen` on warm cache: **21ms** (well under the 10s target). Verified on Apple M-series via Homebrew uv 0.11.21.

## Task Commits

Each task was committed atomically:

1. **Task A1: pyproject.toml + uv.lock + toolchain bootstrap** — `933f9e6` (chore)
2. **Task A2: src/aws_eks_helm_deploy/ skeleton + unit tests** — `99ea144` (feat)
3. **Task A3: .pre-commit-config.yaml + pre-commit parity** — `059ebb7` (chore)

## Files Created/Modified

- `pyproject.toml` — package metadata, runtime deps, dev/integration/acceptance groups, ruff/mypy/pytest/coverage config (88 packages resolved)
- `uv.lock` — pinned resolver output (1626 lines; CI uses `uv sync --frozen`)
- `.python-version` — `3.13` (uv-managed interpreter)
- `.gitignore` — extended with `.venv/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `htmlcov/`, `.coverage`, `*.pyc`, `__pycache__/`, `dist/`, `*.egg-info/`
- `.pre-commit-config.yaml` — ruff + ruff-format (v0.15.17), mypy (v2.1.0, pass_filenames: false), pre-commit-hooks (v5.0.0), local pytest-quick hook
- `src/aws_eks_helm_deploy/__init__.py` — `__version__` from importlib.metadata
- `src/aws_eks_helm_deploy/__main__.py` — `sys.exit(main())` shim
- `src/aws_eks_helm_deploy/settings.py` — `Settings(BaseSettings)` with all v1 env-var aliases + v2 fields
- `src/aws_eks_helm_deploy/errors.py` — PipeError hierarchy (exit codes 1-6)
- `src/aws_eks_helm_deploy/pipe_io.py` — PipeIO STUB (lazy toolkit init; full init in Phase 2)
- `src/aws_eks_helm_deploy/cli.py` — `main(argv) -> int` placeholder (Phase 1 success path)
- `tests/__init__.py`, `tests/unit/__init__.py` — package markers
- `tests/unit/test_settings.py` — 3 tests including NAMESPACE v1-bug regression
- `tests/unit/test_errors.py` — 3 tests covering all exit codes + custom exit_code
- `tests/unit/test_pipe_io.py` — 3 tests covering success/fail delegation + lazy init
- `tests/unit/test_cli.py` — 4 tests covering placeholder success, PipeError catch, bare Exception, __main__ module run
- `requirements.txt` — DELETED (v1 dep manifest retired, TOOL-02)

## Decisions Made

- **bitbucket-pipes-toolkit 6.2.0** — imported cleanly on Python 3.13; RESEARCH.md [ASSUMED] resolved OK. No downgrade.
- **ruff config**: `BLE` added to `select` list (required for `# noqa: BLE001` in `cli.py` to be valid); `ANN101`/`ANN102` removed from `ignore` (these ruff rules were deleted in a recent ruff version).
- **mypy pre-commit hook**: `pass_filenames: false` required to avoid "Duplicate module named aws_eks_helm_deploy" error that occurs when `mirrors-mypy` receives individual file paths in a src-layout project. Hook still runs on `files: ^src/` trigger.
- **pre-commit file scoping**: All hooks use `files: ^(src|tests)/` patterns to exclude the coexisting v1 `pipe/` directory from v2 linting. The v1 code has intentional type annotation and style differences.
- **Plan A addopts**: `--cov=aws_eks_helm_deploy --cov-branch` without `--cov-fail-under=100`. The 100% gate is wired by Plan B after `logging.py` (Plan D) is present.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed deleted ruff rules ANN101/ANN102 from ignore list**
- **Found during:** Task A2 (ruff check after writing source modules)
- **Issue:** `pyproject.toml` had `ignore = ["ANN101", "ANN102", "S101"]` but ruff 0.15.17 has removed these rules — they emit a warning and fail `--check`
- **Fix:** Removed `ANN101` and `ANN102` from ignore; added `BLE` to select list (required for `# noqa: BLE001` in cli.py as specified in PATTERNS.md)
- **Files modified:** `pyproject.toml`
- **Verification:** `uv run ruff check src tests` exits 0
- **Committed in:** `99ea144` (Task A2 commit)

**2. [Rule 1 - Bug] Fixed mypy `Unused type: ignore` on pipe_io.py**
- **Found during:** Task A2 (mypy --strict run)
- **Issue:** RESEARCH.md Pitfall 2 said to add `# type: ignore[import-untyped]` on the bitbucket_pipes_toolkit import, but with both `import bitbucket_pipes_toolkit` and `from bitbucket_pipes_toolkit import Pipe`, the ignore comment needed to be on the right line only
- **Fix:** `# type: ignore[import-untyped]` placed on `import bitbucket_pipes_toolkit` (line 15); the `from bitbucket_pipes_toolkit import Pipe` line has no ignore
- **Files modified:** `src/aws_eks_helm_deploy/pipe_io.py`
- **Verification:** `uv run mypy --strict src` exits 0 with zero errors
- **Committed in:** `99ea144` (Task A2 commit)

**3. [Rule 3 - Blocking] Installed uv via Homebrew (uv not on PATH)**
- **Found during:** Task A1 (uv lock command failed — uv not on PATH)
- **Issue:** RESEARCH.md documented `uv: No (not on PATH)` with the install fallback. uv needed to be installed before any work could begin.
- **Fix:** `brew install uv` (Homebrew-managed, not the astral.sh shell pipe). uv 0.11.21 installed.
- **Files modified:** None (system-level install)
- **Verification:** `which uv && uv --version` returns `/opt/homebrew/bin/uv` / `uv 0.11.21`
- **Committed in:** N/A (system install, not tracked in git)

**4. [Rule 2 - Missing] Added `files:` scoping to pre-commit hooks**
- **Found during:** Task A3 (first `pre-commit run --all-files` ran hooks on entire repo including v1 `pipe/` directory)
- **Issue:** Pre-commit without `files:` patterns applied ruff/mypy to v1 `pipe/*.py` which has no type annotations, 2-space indents, and legacy patterns — causing 68+ lint errors. The plan didn't specify file scoping because it assumed no coexisting v1 code.
- **Fix:** Added `files: ^(src|tests)/` to ruff, trailing-whitespace, check-yaml hooks; `pass_filenames: false` + `files: ^src/` to mypy hook
- **Files modified:** `.pre-commit-config.yaml`
- **Verification:** `uv run pre-commit run --all-files` exits 0; all 9 hooks pass
- **Committed in:** `059ebb7` (Task A3 commit)

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs, 1 Rule 3 blocking, 1 Rule 2 missing)
**Impact on plan:** All auto-fixes necessary for correctness (ruff config), mypy clean pass, uv availability, and pre-commit parity. No scope creep. The `files:` scoping deviation is required in any brownfield plan where v1 and v2 code coexist.

## Pre-commit Auto-fixes Applied to Working Tree

The first `pre-commit run --all-files` (before file scoping) ran `end-of-file-fixer` on v1 files, adding missing trailing newlines to:
- `.changes/1.0.0.json`, `.changes/1.0.1.json`, `.changes/1.0.2.json`, `.changes/1.1.0.json`, `.changes/1.2.0.json`, `.changes/1.2.1.json`, `.changes/1.3.0.json`
- `logo.pxd`
- `pipe/eks/client.py`, `pipe/helm/__init__.py`, `pipe/helm/client.py`, `pipe/helm/duration.py`, `pipe/helm/error.py`, `pipe/pipe.py`, `pipe/schema.py`, `pipe/test.py`
- `test/acceptance/requirements.txt`, `test/acceptance/test_pipe.py`

These are trivially-correct whitespace fixes (no newline at end of file → newline added). All included in commit `059ebb7`.

## Known Stubs

| Stub | File | Reason |
|------|------|---------|
| `PipeIO` | `src/aws_eks_helm_deploy/pipe_io.py` | Lazy toolkit init without schema validation; `Pipe(pipe_metadata=..., schema={})` is a placeholder. Phase 2 replaces with schema-driven `Pipe(pipe_metadata=..., schema=actual_schema)` once CLUSTER_NAME-required schema exists. |
| `cli.main()` placeholder | `src/aws_eks_helm_deploy/cli.py` | Calls `pipe.success("Phase 1 skeleton — no action executed")` and returns 0. Real ACTION dispatch (upgrade/diff/rollback) lands in Phase 3+. |

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the plan's threat model documented. T-01-A-01 (lockfile drift) is mitigated: `uv.lock` committed, `uv sync --frozen` is the CI invocation. T-01-A-02 (env-var injection): `extra="ignore"` on `SettingsConfigDict` confirmed in place.

## Issues Encountered

- **mypy 2.1.0 `Unused type: ignore` strictness**: mypy 2.1 flags `# type: ignore` comments that reference codes not generated for the given context. This required careful placement of the `[import-untyped]` comment on exactly the right import statement.
- **ruff 0.15.17 rule removal**: `ANN101` and `ANN102` were removed from ruff. Plans or research documents referencing these rules should be treated as stale.

## Next Phase Readiness

- Plan B (test infra): `pyproject.toml` base config ready; Plan B flips `--cov-fail-under=100` in `addopts`. The 13 unit tests already hit 100% line+branch on the four skeleton modules.
- Plan C (Dockerfile): `pyproject.toml` + `uv.lock` + `src/` are in place; `uv sync --frozen --no-dev --compile-bytecode` will work in the builder stage.
- Plan D (structured logging): `structlog 26.1.0` is installed in the venv; `src/aws_eks_helm_deploy/logging.py` stub can be added and `cli.py` extended to call `configure_logging(settings)`.

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `pyproject.toml` exists | FOUND |
| `uv.lock` exists | FOUND |
| `.python-version` exists | FOUND |
| `.pre-commit-config.yaml` exists | FOUND |
| `src/aws_eks_helm_deploy/__init__.py` exists | FOUND |
| `src/aws_eks_helm_deploy/settings.py` exists | FOUND |
| `src/aws_eks_helm_deploy/errors.py` exists | FOUND |
| `src/aws_eks_helm_deploy/pipe_io.py` exists | FOUND |
| `src/aws_eks_helm_deploy/cli.py` exists | FOUND |
| `requirements.txt` deleted | CONFIRMED |
| Commit `933f9e6` (A1) | FOUND |
| Commit `99ea144` (A2) | FOUND |
| Commit `059ebb7` (A3) | FOUND |

---
*Phase: 01-toolchain-spine*
*Completed: 2026-06-17*
