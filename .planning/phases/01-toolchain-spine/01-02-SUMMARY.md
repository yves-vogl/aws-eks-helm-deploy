---
phase: 01-toolchain-spine
plan: 02
subsystem: test-infrastructure
tags: [pytest, pytest-cov, coverage, kind, docker, integration, acceptance, makefile]

# Dependency graph
requires:
  - "01-01"  # skeleton modules, pyproject.toml base config, unit tests
  - "01-04"  # logging.py + test_logging.py (required for 100% coverage gate)
  - "01-03"  # Dockerfile (acceptance tier builds + runs the image)
provides:
  - pyproject.toml with --cov-fail-under=100 in addopts (TOOL-06 gate enforced)
  - tests/conftest.py with auto-unit-marker hook
  - tests/unit/test_init.py covering PackageNotFoundError branch in __init__.py
  - tests/integration/ tier with kind_cluster fixture + helm smoke (TOOL-07)
  - tests/acceptance/ tier with built_image fixture + 3 smoke tests (TOOL-08)
  - Makefile with bootstrap/lint/type-check/unit/integration/acceptance + aliases
affects:
  - all future plans (unit gate must stay green; acceptance gate grows in Phase 2+)
  - Phase 6 (GHA wires acceptance-test as required CI gate)

# Tech tracking
tech-stack:
  added: []  # no new packages; all deps already present from Plan A
  patterns:
    - "100% line+branch coverage gate enforced via --cov-fail-under=100 in addopts"
    - "sys.modules eviction + importlib.metadata.version patch for testing try/except at import time"
    - "session-scoped fixtures for both integration (kind_cluster) and acceptance (built_image)"
    - "--entrypoint override pattern for acceptance docker run tests against non-trivial ENTRYPOINT"
    - "Makefile integration-test and acceptance-test aliases point to integration and acceptance targets"
    - "S603 + S607 ruff ignores added to tests/** for intentional subprocess calls against known CLI tools"

key-files:
  created:
    - tests/conftest.py
    - tests/unit/test_init.py
    - tests/integration/__init__.py
    - tests/integration/conftest.py
    - tests/integration/test_helm_smoke.py
    - tests/acceptance/__init__.py
    - tests/acceptance/conftest.py
    - tests/acceptance/test_image_smoke.py
    - Makefile
  modified:
    - pyproject.toml (addopts: added --cov-fail-under=100; per-file-ignores: added S603, S607 for tests)

key-decisions:
  - "--entrypoint override required for id -u and python -c acceptance tests; docker run appends CMD to ENTRYPOINT rather than replacing it"
  - "sys.modules.pop + importlib.metadata.version patch chosen for __init__.py PackageNotFoundError branch; importlib.reload alone does not re-execute the try/except if the module is cached"
  - "S603 + S607 added to tests/** per-file-ignores — subprocess calls in test fixtures are test-author-controlled, not user-input-driven"
  - "integration tests skip (not fail) when kind/helm absent — TOOL-07 wiring is verified by file existence and the pytest -m integration plumbing; actual cluster run deferred to CI in Phase 6"
  - "acceptance test_help_exits_without_traceback does NOT assert a specific exit code — Phase 1 cli.main() returns 0 (placeholder success); Phase 2+ may change this when env-var validation lands"

# Metrics
duration: 25min
completed: 2026-06-17
---

# Phase 01 Plan 02: Test Infrastructure Summary

**Three-tier pytest suite (unit/integration/acceptance) with 100% line+branch coverage gate, kind cluster lifecycle fixture, Docker image smoke tests (non-root uid, uid>=10000, no-traceback), and full Makefile developer workflow**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-06-17
- **Tasks:** 3 (B1, B2, B3)
- **Files modified:** 10 (9 new, 1 modified)

## Accomplishments

- `uv run pytest` (no args) runs 33 unit tests with 100% line+branch coverage gate enforced — exit 0
- `tests/unit/test_init.py` closes the `__init__.py` PackageNotFoundError branch gap (was 71% before this plan)
- `tests/conftest.py` auto-applies the `unit` marker to unmarked tests under `tests/unit/`
- `tests/integration/` wired: `kind_cluster` fixture skips cleanly on hosts without kind/helm; `test_helm_version_in_cluster` marked `@pytest.mark.integration`
- `tests/acceptance/` wired: `built_image` fixture builds the Plan C image; all 3 smoke tests pass (non-root, uid 10001, no traceback)
- `Makefile` exposes 9 targets including `integration-test` and `acceptance-test` aliases

## Coverage Gate Status (TOOL-06)

| Module | Lines | Miss | Branch | BrPart | Cover |
|--------|-------|------|--------|--------|-------|
| `__init__.py` | 7 | 0 | 0 | 0 | **100%** |
| `cli.py` | 18 | 0 | 0 | 0 | **100%** |
| `errors.py` | 22 | 0 | 2 | 0 | **100%** |
| `logging.py` | 22 | 0 | 6 | 0 | **100%** |
| `pipe_io.py` | 17 | 0 | 2 | 0 | **100%** |
| `settings.py` | 24 | 0 | 0 | 0 | **100%** |
| **TOTAL** | **110** | **0** | **10** | **0** | **100%** |

`Required test coverage of 100% reached. Total coverage: 100.00%`

**Coverage gap fixed:** `__init__.py` lines 7-8 (PackageNotFoundError except branch) were at 71% before this plan. `tests/unit/test_init.py` closes the gap using `sys.modules.pop` + `importlib.metadata.version` patch.

## Integration Tier (TOOL-07)

**Host status:** `kind` = not installed, `helm` = not installed

`uv run pytest -m integration -q --no-cov` → 1 skipped, 0 failed — graceful skip with message "kind not installed — integration tier skipped (install via brew install kind)"

Integration fixture and test files are wired and correct. Real cluster runs will occur in CI (Phase 6) where `kind` is available.

## Acceptance Tier (TOOL-08)

**Host status:** Docker 27.3.1 available and running

`uv run pytest -m acceptance -q --no-cov` → 3 passed (after building the Plan C image `aws-eks-helm-deploy:acceptance-test`)

| Test | Result | Assertion |
|------|--------|-----------|
| `test_image_runs_as_nonroot` | PASS | `os.getuid() != 0` via `--entrypoint python -c "..."` |
| `test_image_uid_is_at_least_10000` | PASS | `id -u` returns 10001 >= 10000 via `--entrypoint id -u` |
| `test_help_exits_without_traceback` | PASS | No `Traceback` in stderr when run without env vars |

## Task Commits

Each task was committed atomically:

1. **Task B1: pyproject.toml gate + tests/conftest.py + test_init.py** — `5567ee7` (feat)
2. **Task B2: Integration tier** — `473a554` (feat)
3. **Task B3: Acceptance tier + Makefile** — `982f6c2` (feat)

## Files Created/Modified

- `pyproject.toml` — addopts gains `--cov-fail-under=100`; per-file-ignores for tests adds `S603`, `S607`
- `tests/conftest.py` — `pytest_collection_modifyitems` auto-applies `unit` mark to unmarked tests under `tests/unit/`
- `tests/unit/test_init.py` — 2 tests: `test_version_is_string`, `test_version_fallback_on_package_not_found`
- `tests/integration/__init__.py` — empty package marker
- `tests/integration/conftest.py` — session-scoped `kind_cluster` fixture with skip guards and unconditional teardown
- `tests/integration/test_helm_smoke.py` — `test_helm_version_in_cluster` marked `@pytest.mark.integration`
- `tests/acceptance/__init__.py` — empty package marker
- `tests/acceptance/conftest.py` — session-scoped `built_image` fixture: skip if no docker, build, yield, rmi teardown
- `tests/acceptance/test_image_smoke.py` — 3 tests: nonroot, uid>=10000, no-traceback
- `Makefile` — 9 `.PHONY` targets: bootstrap, lint, type-check, unit, integration, integration-test, acceptance, acceptance-test, all

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `--entrypoint` override to `docker run` acceptance tests**
- **Found during:** Task B3 (first acceptance test run)
- **Issue:** `docker run --rm <img> id -u` appended `id -u` as CMD arguments to the image's ENTRYPOINT (`python -m aws_eks_helm_deploy`) rather than executing `id -u` as a standalone command. The test received ANSI-decorated pipe output instead of a uid integer, causing `int()` to raise `ValueError`.
- **Fix:** Added `--entrypoint id` before the image name for the uid test; added `--entrypoint python` for the nonroot assertion test. The `test_help_exits_without_traceback` test intentionally uses the default entrypoint.
- **Files modified:** `tests/acceptance/test_image_smoke.py`
- **Verification:** 3/3 acceptance tests pass; uid = 10001 confirmed
- **Committed in:** `982f6c2`

**2. [Rule 2 - Missing] Added `S603` + `S607` to `tests/**` per-file-ignores**
- **Found during:** Task B2 (ruff check on integration fixture)
- **Issue:** `subprocess.run(["kind", "create", ...])` in `tests/integration/conftest.py` triggered ruff S603 (subprocess with list) and S607 (partial executable path). These are intentional — test fixtures call known CLI tools with author-controlled arguments, not user input.
- **Fix:** Extended `"tests/**"` per-file-ignores to include `"S603", "S607"` in `pyproject.toml`
- **Files modified:** `pyproject.toml`
- **Verification:** `ruff check tests/` exits 0
- **Committed in:** `473a554`

**3. [Rule 1 - Bug] Added `tests/unit/test_init.py` to close `__init__.py` coverage gap**
- **Found during:** Task B1 (coverage run revealed `__init__.py` at 71% — lines 7-8 uncovered)
- **Issue:** The `PackageNotFoundError` except branch in `__init__.py` (lines 7-8) was not exercised by any existing test. Adding `--cov-fail-under=100` would immediately fail without covering this branch.
- **Fix:** Created `tests/unit/test_init.py` with 2 tests: `test_version_is_string` (happy path) and `test_version_fallback_on_package_not_found` (evicts module from `sys.modules`, patches `importlib.metadata.version` to raise `PackageNotFoundError`, re-imports, asserts `__version__ == "0.0.0-dev"`).
- **Files modified:** `tests/unit/test_init.py` (new)
- **Verification:** Coverage shows `__init__.py` 100%; full suite exits 0
- **Committed in:** `5567ee7`

## Known Stubs

| Stub | File | Reason |
|------|------|---------|
| Integration tier: one smoke test only (helm-version) | `tests/integration/test_helm_smoke.py` | Phase 1 wires the kind+helm plumbing; real `helm install`/`helm upgrade` cluster tests land in Phase 3 (CHART-01) after UpgradeAction is implemented |
| Acceptance tier: three smoke tests only | `tests/acceptance/test_image_smoke.py` | Phase 1 proves non-root, uid>=10000, and no-traceback. Phase 2+ adds auth strategy smoke; Phase 5 adds SEC-06 credential leak test; Phase 6 wires all into GHA as required CI gates |
| `test_help_exits_without_traceback` exit code | `tests/acceptance/test_image_smoke.py` | Phase 1 cli.main() returns 0 (placeholder success path); Phase 2+ may change to non-zero when env-var validation lands; test does not assert exit code to avoid hardcoding a Phase-1-only value |

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The acceptance `docker build` and `docker run` calls use only version-pinned base images from the Dockerfile (Plan C's supply-chain surface). The integration fixture calls `kind create/delete cluster` and `helm version` — all author-controlled test-only CLIs, not user-input-driven. T-01-B-01 through T-01-B-04 and T-01-B-SC from the plan's threat register are all satisfied as specified.

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `pyproject.toml` contains `--cov-fail-under=100` | FOUND |
| `tests/conftest.py` exists | FOUND |
| `tests/unit/test_init.py` exists | FOUND |
| `tests/integration/__init__.py` exists | FOUND |
| `tests/integration/conftest.py` exists (contains `kind_cluster`) | FOUND |
| `tests/integration/test_helm_smoke.py` exists (contains `test_helm_version`) | FOUND |
| `tests/acceptance/__init__.py` exists | FOUND |
| `tests/acceptance/conftest.py` exists (contains `built_image`) | FOUND |
| `tests/acceptance/test_image_smoke.py` exists (contains `test_image_runs_as_nonroot`) | FOUND |
| `Makefile` exists (contains `integration-test`) | FOUND |
| Commit `5567ee7` (B1 — coverage gate) | FOUND |
| Commit `473a554` (B2 — integration tier) | FOUND |
| Commit `982f6c2` (B3 — acceptance tier + Makefile) | FOUND |
| `uv run pytest -q` exits 0 (100% coverage) | PASSED |
| `uv run pytest -m integration -q --no-cov` skips cleanly | PASSED (1 skipped) |
| `uv run pytest -m acceptance -q --no-cov` passes | PASSED (3 passed) |
| `make -n integration-test` prints `uv run pytest -m integration --no-cov` | PASSED |
| `make -n acceptance-test` prints `uv run pytest -m acceptance --no-cov` | PASSED |

---
*Phase: 01-toolchain-spine*
*Completed: 2026-06-17*
