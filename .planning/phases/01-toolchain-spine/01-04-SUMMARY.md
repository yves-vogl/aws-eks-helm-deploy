---
phase: 01-toolchain-spine
plan: 04
subsystem: observability
tags: [structlog, logging, observability, credentials, json, tdd]

# Dependency graph
requires:
  - "01-01"  # Settings (log_format, debug fields), cli.py skeleton, pyproject.toml with structlog dep
provides:
  - src/aws_eks_helm_deploy/logging.py (configure_logging, get_logger, STABLE_FIELDS, CREDENTIAL_BLOCKLIST, bind_safe_context)
  - tests/unit/test_logging.py (100% line+branch on logging.py)
  - cli.py extended with configure_logging(settings) call
  - tests/unit/test_cli.py extended with test_main_calls_configure_logging
affects:
  - 01-02 (Plan B: --cov-fail-under=100 gate stays green — logging.py now has 100% coverage)
  - Phase 3+ (action dispatch will call bind_safe_context with STABLE_FIELDS keys)
  - Phase 5 (SEC-06: lint enforcement of bind_safe_context over direct bind_contextvars)

# Tech tracking
tech-stack:
  added:
    - structlog 26.1.0 (already in pyproject.toml from Plan A; Plan D provides the consumer)
  patterns:
    - configure_logging(settings) called once at startup in cli.main() — between Settings() and PipeIO()
    - shared_processors list: merge_contextvars, add_log_level, TimeStamper(fmt="iso")
    - JSON branch: dict_tracebacks + JSONRenderer(); Human branch: ConsoleRenderer(colors=True)
    - PrintLoggerFactory(file=sys.stderr) in both branches — toolkit owns stdout
    - STABLE_FIELDS tuple is the OBS-01 contract; Phase 2+ binds them at action entry
    - CREDENTIAL_BLOCKLIST frozenset is the OBS-02 gate; bind_safe_context() is sole wrapper
    - cast(structlog.BoundLogger, structlog.get_logger(name)) to satisfy mypy --strict

key-files:
  created:
    - src/aws_eks_helm_deploy/logging.py
    - tests/unit/test_logging.py
  modified:
    - src/aws_eks_helm_deploy/cli.py (configure_logging import + call added)
    - tests/unit/test_cli.py (test_main_calls_configure_logging + configure_logging patch)

key-decisions:
  - "structlog.stdlib.add_logger_name removed from shared_processors — incompatible with PrintLogger (no .name attribute); only works with stdlib Logger wrapped by BoundLogger"
  - "cast(structlog.BoundLogger, structlog.get_logger()) required — structlog.get_logger() is typed as Any in 26.x; cast satisfies mypy --strict without type: ignore"
  - "STABLE_FIELDS keys are not automatically bound in Phase 1 — they define the OBS-01 contract for Phase 2+ action dispatch; documented as explicit stub"
  - "Direct bind_contextvars() calls are convention-excluded in Phase 1 — Phase 5 (SEC-06) adds lint enforcement"
  - "@pytest.mark.unit added explicitly to all test functions — no conftest autouse-marker exists; follows existing pattern from test_cli.py"
  - "event key confirmed as 'event' in structlog 26.x (not 'msg') — JSON test asserts parsed['event'] == 'hello'"

# Metrics
duration: 25min
completed: 2026-06-17
---

# Phase 01 Plan 04: Structured Logging Summary

**structlog configure_logging with dual human/JSON renderer, DEBUG level control, OBS-01 stable field contract (STABLE_FIELDS), OBS-02 credential guard (bind_safe_context over CREDENTIAL_BLOCKLIST), wired into cli.main() — 100% line+branch coverage**

## Performance

- **Duration:** ~25 min (including 2 auto-fix iterations)
- **Completed:** 2026-06-17
- **Tasks:** 3 (D1, D2, D3)
- **Files modified:** 4 (2 new, 2 modified)

## Accomplishments

- `src/aws_eks_helm_deploy/logging.py` created with `configure_logging`, `get_logger`, `bind_safe_context`, `STABLE_FIELDS`, `CREDENTIAL_BLOCKLIST`
- `mypy --strict src` exits 0 on all 7 source files
- `ruff check src tests` exits 0
- 17 new unit tests in `test_logging.py` covering all branches; 100% line+branch on `logging.py`
- `cli.py` calls `configure_logging(settings)` immediately after `Settings()` and before `PipeIO()`
- 1 new test in `test_cli.py` asserting `configure_logging` call count and argument type
- Full unit suite: 31 tests, all green

## STABLE_FIELDS and CREDENTIAL_BLOCKLIST (as committed)

```python
STABLE_FIELDS: tuple[str, ...] = (
    "action",
    "cluster",
    "release",
    "namespace",
    "chart_source",
    "auth_strategy",
    "duration_ms",
)

CREDENTIAL_BLOCKLIST: frozenset[str] = frozenset({
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "session_token",
    "bitbucket_step_oidc_token",
    "bitbucket_token",
    "registry_password",
})
```

## JSON event key (structlog 26.x)

structlog 26.x normalizes the log message under the `event` key (not `msg`). The JSON test (`test_configure_logging_json_emits_parseable_json`) asserts `parsed.get("event") == "hello"` — confirmed working against structlog 26.1.0.

## Task Commits

Each task was committed atomically:

1. **Task D1: logging.py creation** — `6c0afb6` (feat)
2. **Task D2: test_logging.py + logging.py fix** — `807a893` (test)
3. **Task D3: cli.py wiring + test_cli.py extension** — `657e661` (feat)

## Files Created/Modified

- `src/aws_eks_helm_deploy/logging.py` — 120 lines; configure_logging, get_logger, bind_safe_context, STABLE_FIELDS, CREDENTIAL_BLOCKLIST
- `tests/unit/test_logging.py` — 243 lines; 17 unit tests with @pytest.mark.unit markers
- `src/aws_eks_helm_deploy/cli.py` — extended: added configure_logging import + call
- `tests/unit/test_cli.py` — extended: added test_main_calls_configure_logging + configure_logging patch in module_runs test

## Plan B 100% Gate Status

`logging.py` and `cli.py` are both at 100% line+branch coverage. Plan B's `--cov-fail-under=100` gate is achievable once Plan B merges (Plan A + Plan D combined already achieve 100% on the 4 fully-covered modules; `__init__.py`'s PackageNotFoundError branch is the only gap which Plan B will address).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed structlog.stdlib.add_logger_name from shared_processors**
- **Found during:** Task D2 (first test run)
- **Issue:** `structlog.stdlib.add_logger_name` calls `logger.name` but `PrintLoggerFactory` gives a `PrintLogger` (not a stdlib `logging.Logger`), which has no `.name` attribute. This caused `AttributeError` on every log emission in tests.
- **Fix:** Removed `structlog.stdlib.add_logger_name` from `shared_processors` list. Logger name is still passed to `structlog.get_logger(name)` as the logger identifier.
- **Files modified:** `src/aws_eks_helm_deploy/logging.py`
- **Verification:** All 17 tests pass after removal; mypy still exits 0
- **Committed in:** `807a893`

**2. [Rule 1 - Bug] Added cast() for get_logger return type**
- **Found during:** Task D1 (mypy --strict run)
- **Issue:** `structlog.get_logger()` is typed as returning `Any` in structlog 26.x. mypy --strict flags `no-any-return` when the function declares return type `structlog.BoundLogger`.
- **Fix:** Added `from typing import cast` and `return cast(structlog.BoundLogger, structlog.get_logger(name))`
- **Files modified:** `src/aws_eks_helm_deploy/logging.py`
- **Verification:** `mypy --strict src/aws_eks_helm_deploy/logging.py` exits 0
- **Committed in:** `6c0afb6`

**3. [Rule 1 - Bug] Added @pytest.mark.unit to all test functions**
- **Found during:** Task D2 (running tests with addopts -m unit)
- **Issue:** Plan's test spec said "all unmarked → default unit marker via conftest hook" but no conftest with that autouse hook exists. The existing test files (test_cli.py) use explicit `@pytest.mark.unit` markers. Without the marker, all test_logging.py tests were deselected.
- **Fix:** Added `@pytest.mark.unit` to all 11 test functions and the parametrize decorator
- **Files modified:** `tests/unit/test_logging.py`
- **Verification:** `uv run pytest tests/unit/test_logging.py -q --no-cov` shows 17 passed
- **Committed in:** `807a893`

**4. [Rule 2 - Missing] Added noqa: S106 to hardcoded credential test**
- **Found during:** Task D2 commit (ruff pre-commit hook)
- **Issue:** `bind_safe_context(AWS_SECRET_ACCESS_KEY="secret")` triggered ruff S106 (Possible hardcoded password). This is intentional test code, not a real credential.
- **Fix:** Added `# noqa: S106` comment on the line
- **Files modified:** `tests/unit/test_logging.py`
- **Committed in:** `807a893`

**5. [Rule 1 - Bug] Fixed test_main_module_runs to patch configure_logging**
- **Found during:** Task D3 (existing test now calls configure_logging which modifies global structlog state)
- **Issue:** After wiring configure_logging into cli.main(), the `test_main_module_runs` test would configure global structlog state without reset — potential interference with test isolation.
- **Fix:** Added `mocker.patch("aws_eks_helm_deploy.cli.configure_logging")` to the test
- **Files modified:** `tests/unit/test_cli.py`
- **Committed in:** `657e661`

## Known Stubs

| Stub | File | Reason |
|------|------|---------|
| STABLE_FIELDS keys not bound automatically | `src/aws_eks_helm_deploy/logging.py` | Phase 1 only provides the contract; Phase 2+ binds them at action entry via `bind_safe_context(action=..., cluster=..., ...)` |
| Direct bind_contextvars not lint-enforced | `src/aws_eks_helm_deploy/logging.py` docstring | Convention-only in Phase 1; Phase 5 (SEC-06) adds the ruff/grep guard |

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns beyond the plan's threat model. The credential guard (T-01-D-01 mitigation) is implemented as specified. T-01-D-02 (direct bind_contextvars bypass) is accepted for Phase 1 per the threat register with SEC-06 follow-up planned.

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `src/aws_eks_helm_deploy/logging.py` exists | FOUND |
| `tests/unit/test_logging.py` exists | FOUND |
| `cli.py` contains `configure_logging(settings)` | FOUND |
| `test_cli.py` contains `test_main_calls_configure_logging` | FOUND |
| Commit `6c0afb6` (D1 — logging.py) | FOUND |
| Commit `807a893` (D2 — test_logging.py + fix) | FOUND |
| Commit `657e661` (D3 — cli.py wiring) | FOUND |
| `mypy --strict src` exits 0 | PASSED |
| `ruff check src tests` exits 0 | PASSED |
| 17 tests in test_logging.py all green | PASSED |
| logging.py line+branch coverage 100% | PASSED |
| cli.py line coverage 100% | PASSED |

---
*Phase: 01-toolchain-spine*
*Completed: 2026-06-17*
