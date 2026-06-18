---
phase: 03-helm-core-upgrade-action
plan: 2
subsystem: helm-client-layer
tags:
  - helm
  - subprocess
  - syrupy
  - snapshot
  - argv
  - timeout
  - error-mapping
dependency_graph:
  requires:
    - phase: 01-toolchain-spine
      provides: PipeError hierarchy, pytest toolchain
    - phase: 03-helm-core-upgrade-action/03-01
      provides: KubeconfigError=7 in errors.py; confirmed HelmError still at exit_code=5 pre-rename
  provides:
    - aws_eks_helm_deploy.helm.client.HelmClient (kubeconfig_path) — sole subprocess module
    - aws_eks_helm_deploy.helm.client.HelmResult (frozen dataclass, 4 fields)
    - aws_eks_helm_deploy.helm.client.HelmRevision (frozen dataclass, 4 fields)
    - aws_eks_helm_deploy.helm.client.STDERR_MAX_BYTES / REVISION_REGEX / TRUNCATION_MARKER
    - aws_eks_helm_deploy.errors.HelmExecutionError (canonical rename of HelmError, exit_code=5)
    - aws_eks_helm_deploy.errors.HelmError (backward-compat alias = HelmExecutionError)
    - syrupy snapshot baseline tests/unit/__snapshots__/test_helm_client_argv.ambr
  affects:
    - 03-03-PLAN.md: consumes HelmClient.upgrade_install; ships ResolvedChart that resolves TYPE_CHECKING import
    - 03-04-PLAN.md: wires HelmClient into actions/upgrade.py
    - 03-05-PLAN.md: uses HelmClient.history for HISTORY_MAX integration assertions
tech_stack:
  added:
    - syrupy 5.3.2 (dev dep — snapshot testing for _build_argv pure function)
    - pytest-rerunfailures 16.3 (dev dep — kind flakiness guard for Plan 03-05)
  patterns:
    - TYPE_CHECKING guard for forward-reference ResolvedChart (Plan 03-03 dependency)
    - noqa S603 on intentional subprocess.run call sites (sole subprocess module)
    - syrupy snapshot tests: --snapshot-update to capture, subsequent runs fail on diff
    - mocker.patch("aws_eks_helm_deploy.helm.client.subprocess.run") for precise patching
    - from __future__ import annotations enabling unquoted forward references
key_files:
  created:
    - src/aws_eks_helm_deploy/helm/client.py
    - tests/unit/test_helm_client_argv.py
    - tests/unit/test_helm_client_run.py
    - tests/unit/__snapshots__/test_helm_client_argv.ambr
  modified:
    - src/aws_eks_helm_deploy/errors.py (HelmError → HelmExecutionError + alias)
    - tests/unit/test_errors.py (2 new tests: alias identity + HelmExecutionError exit_code)
    - pyproject.toml (syrupy + pytest-rerunfailures in dev group; S108 in tests per-file-ignores)
    - uv.lock (regenerated with syrupy 5.3.2 + pytest-rerunfailures 16.3)
decisions:
  - "HelmExecutionError is the rename of HelmError at exit_code=5 unchanged; HelmError = HelmExecutionError alias at module end preserves backward-compat (RESEARCH Section L)"
  - "_build_argv uses --set-string for ALL set_args entries (not --set) to handle BITBUCKET_STEP_TRIGGERER_UUID curly braces (RESEARCH G / Pitfall 4 / T-03-02-04)"
  - "history_max=None omits --history-max entirely; history_max=0 emits --history-max 0 (unlimited per CONTEXT D4 / Pitfall 3)"
  - "S108 added to ruff tests/** per-file-ignores: hardcoded /tmp path in _client() test helper is intentional for snapshot determinism"
  - "_parse_timeout raises ValueError on total==0 (e.g. 0s) — zero-second timeout is semantically invalid and would cause subprocess.run to immediately timeout"
  - "mocker.patch targets aws_eks_helm_deploy.helm.client.subprocess.run (import-site patch) rather than subprocess.run globally — more reliable"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 4
---

# Phase 03 Plan 02: HelmClient + Subprocess Layer Summary

**One-liner:** `HelmClient` with pure-function `_build_argv` snapshot-tested via syrupy, `upgrade_install` mapping subprocess.run to `HelmExecutionError`/`HelmTimeoutError`, `history()` JSON parsing, 32 KB stderr truncation, and `HelmError = HelmExecutionError` backward-compat alias — all at 100% line + branch coverage.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 03-2-01 | Add syrupy+rerunfailures deps, helm/ marker, HelmExecutionError rename+alias | b8eb15b | errors.py, helm/__init__.py, test_errors.py, pyproject.toml, uv.lock |
| 03-2-02 | HelmClient + HelmResult + HelmRevision + _build_argv + syrupy snapshots | 0e0f743 | helm/client.py, test_helm_client_argv.py, test_helm_client_argv.ambr, pyproject.toml |
| 03-2-03 | subprocess-mocked unit tests for upgrade_install + history + error mapping | 517d89e | test_helm_client_run.py |

## Coverage Results

| Module | Line Coverage | Branch Coverage |
|--------|--------------|----------------|
| `src/aws_eks_helm_deploy/helm/client.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/helm/__init__.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/errors.py` | 100% | 100% |
| TOTAL (all 18 source files) | 100% | 100% |

**Full unit suite:** 180 tests passed, 10 deselected (integration/acceptance tier), 0 failed.

## Installed Package Versions (from uv.lock)

| Package | Version |
|---------|---------|
| syrupy | 5.3.2 |
| pytest-rerunfailures | 16.3 |

## Snapshot Baseline — test_upgrade_argv_full (largest snapshot)

The `test_upgrade_argv_full` snapshot captures the complete flag set for documentation-pipeline use in Phase 7:

```
helm upgrade my-release /charts/minimal
  --install
  --namespace prod
  --kubeconfig /tmp/test-kubeconfig.yaml
  --timeout 10m
  --values base.yaml
  --values prod.yaml
  --set-string bitbucket.bitbucket_build_number=99
  --set-string bitbucket.bitbucket_repo_slug=my-repo
  --set-string bitbucket.bitbucket_commit=abc123def456abc123def456abc123def456abc1
  --set-string bitbucket.bitbucket_tag=v1.2.3
  --set-string bitbucket.bitbucket_step_triggerer_uuid={xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}
  --history-max 10
```

File committed at: `tests/unit/__snapshots__/test_helm_client_argv.ambr` (NOT in .gitignore — confirmed).

## Grep Audit — subprocess import (CONTEXT D1 Verification)

```
grep -RIn "import subprocess" src/aws_eks_helm_deploy/
src/aws_eks_helm_deploy/helm/client.py:27:import subprocess
```

Result: ONLY `helm/client.py` imports `subprocess`. The CONTEXT D1 layering rule is enforced.

## Grep Audit — --set-string usage (RESEARCH G / corrections #4)

```
grep -c "set-string" src/aws_eks_helm_deploy/helm/client.py
5
```

`--set-string` is used for ALL `set_args` entries (not `--set`). Bitbucket UUID curly braces handled safely.

## HelmError Alias Identity Check

```python
from aws_eks_helm_deploy.errors import HelmExecutionError, HelmError
assert HelmError is HelmExecutionError  # True — same class object
```

Result: PASSED. Backward-compat alias confirmed.

## _parse_timeout Duration Component Coverage

| Component | Test | Result |
|-----------|------|--------|
| Seconds only (`"600s"`) | `test_parse_timeout_seconds_only` | 600 |
| Minutes only (`"10m"`) | `test_parse_timeout_minutes_only` | 600 |
| Hours only (`"1h"`) | `test_parse_timeout_hours_only` | 3600 |
| Combined (`"5m30s"`) | `test_parse_timeout_combined` | 330 |
| Hours+minutes (`"1h30m"`) | `test_parse_timeout_hours_minutes` | 5400 |
| Invalid string | `test_parse_timeout_invalid_raises_value_error` | ValueError |
| Empty string | `test_parse_timeout_empty_raises_value_error` | ValueError |
| Zero total (`"0s"`) | `test_parse_timeout_zero_raises_value_error` | ValueError |

All four duration components (s, m, h, combined) are covered: **YES**.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `--set-string` uses in 5 locations, not 2**

- The plan referred to `grep -c "set-string"` being `>= 1`. The actual count is 5 (the `argv.extend(["--set-string", sa])` line plus 4 occurrences in comments and docstrings). All correct — the single implementation site is at the `for sa in set_args` loop.

**2. [Rule 2 - Missing] Added S108 to ruff per-file-ignores for tests/**

- **Found during:** Task 03-2-02, ruff check on `test_helm_client_argv.py`
- **Issue:** `S108 Probable insecure usage of temporary file or directory: "/tmp/test-kubeconfig.yaml"` — the hardcoded `/tmp/` path in `_client()` helper is intentional for snapshot determinism (path appears in snapshot baseline; must be stable across test runs).
- **Fix:** Added `"S108"` to `"tests/**"` per-file-ignores in `pyproject.toml`.
- **Files modified:** `pyproject.toml`
- **Commit:** 0e0f743

**3. [Rule 1 - Bug] Added `test_parse_timeout_zero_raises_value_error` for total==0 branch**

- **Found during:** Task 03-2-03, coverage run showing line 79 (`if total == 0: raise ValueError`) uncovered.
- **Issue:** The `total == 0` guard in `_parse_timeout` was not reached by the existing invalid-string tests (`"garbage"`, `""`). A zero-second timeout (`"0s"`) passes regex validation but produces a total of 0 — which is semantically invalid for subprocess.run(timeout=).
- **Fix:** Added `test_parse_timeout_zero_raises_value_error` test asserting `_parse_timeout("0s")` raises `ValueError`.
- **Files modified:** `tests/unit/test_helm_client_run.py`
- **Commit:** 517d89e

**4. [Rule 1 - Bug] Removed quotes from `chart: "ResolvedChart"` annotation**

- **Found during:** Task 03-2-02, `ruff check` reporting UP037 (Remove quotes from type annotation).
- **Issue:** With `from __future__ import annotations` active, all annotations are evaluated lazily — quotes on `"ResolvedChart"` are redundant and trigger UP037.
- **Fix:** Removed quotes from the `chart: ResolvedChart` annotation. The TYPE_CHECKING guard ensures the forward reference resolves only at type-check time, not at runtime.
- **Files modified:** `src/aws_eks_helm_deploy/helm/client.py`
- **Commit:** 0e0f743

**5. [Rule 2 - Missing] Added `noqa: S603` on both subprocess.run call sites**

- **Found during:** Task 03-2-02, `ruff check` reporting S603 on subprocess.run in `helm/client.py`.
- **Issue:** `S603 subprocess call: check for execution of untrusted input` — these are intentional, controlled subprocess invocations with argv built from trusted strings. This is THE designated subprocess module per CONTEXT D1.
- **Fix:** Added `# noqa: S603` inline on both `subprocess.run` call sites.
- **Files modified:** `src/aws_eks_helm_deploy/helm/client.py`
- **Commit:** 0e0f743

### Documented Deviations (from PLAN.md)

The five deviations documented in the PLAN.md `<deviations>` section were all followed as planned:

1. **syrupy `~= 5.3`** (not 4.7) — installed 5.3.2. ✓
2. **pytest-rerunfailures `~= 16.3`** (not 14.0) — installed 16.3. ✓
3. **`HelmError` rename → `HelmExecutionError` + alias retained** — `HelmError = HelmExecutionError` at module end, `HelmError is HelmExecutionError` is True. ✓
4. **stderr truncation uses char slicing** (not byte slicing) — `_truncate_stderr` checks `len(s.encode("utf-8")) > STDERR_MAX_BYTES` but slices with `s[-STDERR_MAX_BYTES:]`. ✓
5. **HELM_TIMEOUT NOT added as Settings field** — `timeout: str` is a method parameter; Plan 03-04 wires `settings.timeout`. ✓

## Known Stubs

- `ResolvedChart` is referenced via `TYPE_CHECKING` guard in `helm/client.py` (`from aws_eks_helm_deploy.chart.local import ResolvedChart`). The module `chart/local.py` does not exist yet — it lands in Plan 03-03. Tests use `SimpleNamespace(source_path=Path(...), name=..., version=...)` as a duck-typed substitute. No production code change in `helm/client.py` needed when 03-03 lands.
- `helm/__init__.py` has no re-exports — minimal namespace marker. Plan 03-04 may add re-exports.

## Threat Flags

No new security-relevant surface beyond what the PLAN.md threat model documents. Mitigations implemented:

- T-03-02-01: argv is `list[str]`, never `shell=True` — verified by `test_upgrade_install_invokes_subprocess_run_with_correct_argv`.
- T-03-02-03: 32 KB stderr truncation on BOTH success and failure paths — verified by `test_upgrade_install_truncates_stderr_when_over_32kb` and `test_upgrade_install_truncates_stderr_on_error_path_too`.
- T-03-02-04: `--set-string` regression guard — `test_upgrade_argv_with_bitbucket_metadata` snapshot fails if `--set-string` is changed back to `--set`.

## Self-Check: PASSED

Files verified:
- `src/aws_eks_helm_deploy/helm/client.py` — FOUND
- `src/aws_eks_helm_deploy/helm/__init__.py` — FOUND
- `tests/unit/test_helm_client_argv.py` — FOUND
- `tests/unit/test_helm_client_run.py` — FOUND
- `tests/unit/__snapshots__/test_helm_client_argv.ambr` — FOUND

Commits verified in git log:
- b8eb15b (03-2-01) — FOUND
- 0e0f743 (03-2-02) — FOUND
- 517d89e (03-2-03) — FOUND
