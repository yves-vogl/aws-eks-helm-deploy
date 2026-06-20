---
phase: 05-log-masking-diff-rollback-metadata-flip
plan: "05"
subsystem: rollback-safe-upgrade
tags: [helm, rollback, safe-upgrade, pipe, action, argv, security]
dependency_graph:
  requires: ["05-01", "05-02", "05-03"]
  provides: ["PIPE-04", "PIPE-05"]
  affects: ["helm/client.py", "actions/upgrade.py", "actions/rollback.py", "cli.py"]
tech_stack:
  added: []
  patterns:
    - "SAFE_UPGRADE_DESCRIPTION constant — single source of truth for the pipe:safe-upgrade marker"
    - "Pre-flight history check before helm rollback (D5 safety contract)"
    - "safe_upgrade kwarg threaded through _build_argv -> upgrade_install -> UpgradeAction"
key_files:
  created:
    - src/aws_eks_helm_deploy/actions/rollback.py
    - tests/unit/test_rollback_action.py
  modified:
    - src/aws_eks_helm_deploy/helm/client.py
    - src/aws_eks_helm_deploy/actions/upgrade.py
    - src/aws_eks_helm_deploy/cli.py
    - tests/unit/test_helm_client_argv.py
    - tests/unit/test_helm_client_run.py
    - tests/unit/test_upgrade_action.py
    - tests/unit/test_cli.py
decisions:
  - "SAFE_UPGRADE_DESCRIPTION constant defined in helm/client.py as single authoritative source"
  - "safe_upgrade kwarg keyword-only (*) to prevent positional misuse"
  - "rollback() returns None — action layer logs success; stdout discarded"
  - "_run_rollback extracted to private helper for mypy narrowing clarity"
  - "assert-based Optional narrowing for mypy strict (no type: ignore hacks)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 9
---

# Phase 05 Plan 05: Rollback + SAFE_UPGRADE Wiring (PIPE-04/05) Summary

End-to-end implementation of `ACTION=rollback` + `SAFE_UPGRADE=true` argv extension. The pre-flight check enforces the safety contract from CONTEXT D5: rollback is only authorised when the target revision's description contains `"pipe:safe-upgrade"` — the marker set by `SAFE_UPGRADE=true` upgrades.

## New HelmClient Methods

### `_build_rollback_argv(release, revision, namespace) -> list[str]` (pure)

Returns the stable 8-element list:
```
["helm", "rollback", release, str(revision), "--namespace", namespace, "--kubeconfig", path]
```

No `--wait` / `--timeout` — helm rollback uses its own defaults. Safety is enforced by RollbackAction's pre-flight, not by the rollback argv itself.

### `rollback(release, revision, namespace, timeout) -> None` (subprocess)

Mirrors `upgrade_install` error handling:
- `returncode != 0` → `HelmExecutionError` (exit=5), stderr redacted via `self._redactor`
- `TimeoutExpired` → `HelmTimeoutError` (exit=6), partial stderr redacted
- Success → returns `None` (action layer logs result; stdout not needed)

### `SAFE_UPGRADE_DESCRIPTION: Final[str] = "pipe:safe-upgrade"`

Module-level constant in `helm/client.py`. Imported by both `actions/upgrade.py` (argv construction) and `actions/rollback.py` (pre-flight substring check). The literal `"pipe:safe-upgrade"` appears ONLY in the constant declaration line — never hardcoded elsewhere in code.

## 4-Flag argv Extension for SAFE_UPGRADE

`_build_argv` now accepts a keyword-only `safe_upgrade: bool = False` parameter. When `True`, appends after `--history-max`:

```
["--wait", "--atomic", "--description", "pipe:safe-upgrade"]
```

`upgrade_install` also gains `safe_upgrade: bool = False` (forwarded to `_build_argv`). Default `False` preserves full backward compatibility — all 15 Phase 3 snapshot tests pass unchanged.

`UpgradeAction.run` forwards `safe_upgrade=s.safe_upgrade` at **both** `client.upgrade_install` call sites (kubeconfig_override test-scaffold branch + production write_kubeconfig branch).

## RollbackAction — LOC Count + Pre-Flight Behavior

`src/aws_eks_helm_deploy/actions/rollback.py` is 181 lines total (docstrings + imports + class). The `run()` body is 48 lines, within the < 50 LOC budget. `_run_rollback()` is the private helper that contains the pre-flight logic.

**Pre-flight sequence in `_run_rollback`:**

1. `client.history(release, namespace)` — fetches list of `HelmRevision` records
2. Find `target = next((r for r in history if r.revision == revision), None)`
3. If `target is None` → `ChartResolutionError` naming available revisions
4. If `SAFE_UPGRADE_DESCRIPTION not in target.description` → `ChartResolutionError` with remedy
5. `client.rollback(release, revision, namespace, timeout)` — only reached if pre-flight passes

No chart resolution (no `select_chart_source` import). No subprocess in this module (D6 invariant preserved).

## Consumer-Facing Error Messages (UX Review)

**Revision not found:**
```
Revision 99 not found in release 'my-release' history. Available revisions: [1, 2, 3].
```

**Not safe-upgraded:**
```
Refusing rollback to revision 1 of release 'my-release' — that revision was NOT deployed with SAFE_UPGRADE=true (no --wait/--atomic guarantee). Re-deploy with SAFE_UPGRADE=true first, then retry rollback.
```

Both messages name `SAFE_UPGRADE=true` literally — the user-facing env var name as documented in 05-VALIDATION.md UAT scenarios.

## Test Counts

| Area | Tests Added |
|------|-------------|
| `test_helm_client_argv.py` — SAFE_UPGRADE argv + rollback argv | 5 |
| `test_helm_client_run.py` — rollback run-mode + redactor + timeout | 7 |
| `test_upgrade_action.py` — safe_upgrade kwarg forwarding | 2 |
| `test_rollback_action.py` — NEW: required-field guards + pre-flight + propagation | 10 |
| `test_cli.py` — rollback dispatch | 2 |
| **Total new tests** | **26** |

Total: 421 (baseline) + 26 = **447 tests**, all passing.

## Commits

- `3bb8de3`: `feat(05-05): HelmClient — _build_rollback_argv + rollback() + safe_upgrade kwarg (PIPE-04/05)`
- `59d26a5`: `feat(05-05): UpgradeAction forwards safe_upgrade=s.safe_upgrade to both upgrade_install sites (PIPE-05)`
- `42225c0`: `feat(05-05): PIPE-04/05 ACTION=rollback + SAFE_UPGRADE — HelmClient.rollback + pre-flight description marker + RollbackAction (CONTEXT D5)`

## Quality Gate Results

| Gate | Result |
|------|--------|
| `pytest tests/unit -q --no-cov` exits 0 | PASS (447 tests) |
| `pytest --cov --cov-fail-under=100` exits 0 | PASS (100.00%) |
| `mypy --strict src/aws_eks_helm_deploy` exits 0 | PASS (32 files) |
| `ruff check src/ tests/` clean | PASS |
| D6 invariant: exactly 2 files import subprocess | PASS |
| `SAFE_UPGRADE_DESCRIPTION` in `helm/client.py` >= 2 hits | PASS (6 hits) |
| `SAFE_UPGRADE_DESCRIPTION` in `actions/` >= 2 hits | PASS (rollback.py + upgrade.py) |
| `"pipe:safe-upgrade"` literal ONLY in `helm/client.py` | PASS |
| `safe_upgrade` in `actions/upgrade.py` >= 2 hits | PASS (3 hits) |
| `client.rollback(` in `actions/rollback.py` == 1 hit | PASS |
| `settings.action == "rollback"` in `cli.py` == 1 hit | PASS |
| `select_chart_source` NOT in `actions/rollback.py` | PASS (0 code refs) |
| `self._redactor(` in `helm/client.py` >= 12 hits | PASS (12 hits) |

## Deviations from Plan

**1. [Rule 2 - Missing Coverage] Added rollback timeout branch tests**

- **Found during:** Task 3 coverage check (99.14% → needed 100%)
- **Issue:** `rollback()` timeout handler has 2 branches (with/without `exc.stderr`) not covered
- **Fix:** Added `test_rollback_timeout_with_stderr_bytes_includes_partial_stderr` and `test_rollback_timeout_with_none_stderr_does_not_crash` in `test_helm_client_run.py`
- **Files modified:** `tests/unit/test_helm_client_run.py`
- **Commit:** `42225c0`

**2. [Rule 2 - Missing Coverage] Added kubeconfig_override + OSError branch tests for RollbackAction**

- **Found during:** Task 3 coverage check — rollback.py at 92% (lines 106-108, 115 uncovered)
- **Issue:** `kubeconfig_override` branch (test-scaffold path) and `OSError` wrapping branch not exercised
- **Fix:** Added `test_rollback_action_kubeconfig_override_skips_cluster_and_token` and `test_rollback_action_wraps_oserror_as_kubeconfig_error` tests
- **Files modified:** `tests/unit/test_rollback_action.py`
- **Commit:** `42225c0`

**3. [Rule 1 - Bug Fix] Fixed `_run_rollback` mypy strict error**

- **Found during:** `mypy --strict` check after initial Task 3 implementation
- **Issue:** `_run_rollback(client, s, pipe)` passed `Settings` which has `Optional[str/int]` fields; mypy couldn't see the pre-flight narrowing
- **Fix:** Extracted validated `release: str` and `revision: int` variables using `assert is not None` (mypy-canonical narrowing), then passed them directly to `_run_rollback`
- **Files modified:** `src/aws_eks_helm_deploy/actions/rollback.py`
- **Commit:** `42225c0`

## Known Stubs

None — all wiring is complete end-to-end. `HelmClient.rollback` runs real subprocess, `RollbackAction` performs real pre-flight via `HelmClient.history`.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond what was planned. The `rollback()` method follows the same subprocess security pattern as `upgrade_install()` and `diff()`. All stderr routes through `self._redactor()` before surfacing in errors (T-05-01 wiring).

## Self-Check: PASSED

- rollback.py: FOUND
- test_rollback_action.py: FOUND
- 42225c0: FOUND in git log
- 59d26a5: FOUND in git log
- 3bb8de3: FOUND in git log
