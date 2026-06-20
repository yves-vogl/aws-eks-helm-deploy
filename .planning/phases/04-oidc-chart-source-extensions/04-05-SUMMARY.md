---
phase: 04-oidc-chart-source-extensions
plan: 5
subsystem: chart
tags:
  - chart-source
  - protocol
  - refactor
  - context-manager
  - factory
  - resolve-local-chart-removal
  - legacy-deletion-gate
  - actions-upgrade-wiring
dependency_graph:
  requires:
    - 04-02 (Settings fields: repo_url, chart_version, registry_username, registry_password, chart_verify, chart_verify_certificate_identity, chart_verify_certificate_oidc_issuer)
  provides:
    - chart/base.py (ChartSource Protocol + ResolvedChart)
    - chart/local.py (LocalChart class; legacy function removed)
    - chart/__init__.py (select_chart_source factory)
    - actions/upgrade.py (factory-wired; with chart_source.resolve())
  affects:
    - Plan 04-06 (RepoChart imports ChartSource; lifts pragma in chart/__init__.py)
    - Plan 04-07 (OciChart imports ChartSource; lifts pragma in chart/__init__.py)
tech_stack:
  added:
    - contextlib.AbstractContextManager[ResolvedChart] (Protocol return type)
    - typing.Protocol + runtime_checkable (ChartSource)
  patterns:
    - ChartSource Protocol (structural subtyping — runtime_checkable)
    - Degenerate context-manager (LocalChart.resolve yields existing path; no tempdir)
    - select_chart_source factory (prefix routing; pragma-guarded forward imports)
key_files:
  created:
    - src/aws_eks_helm_deploy/chart/base.py
    - tests/unit/test_chart_base.py
    - tests/unit/test_chart_init_select_source.py
  modified:
    - src/aws_eks_helm_deploy/chart/local.py
    - src/aws_eks_helm_deploy/chart/__init__.py
    - src/aws_eks_helm_deploy/actions/upgrade.py
    - src/aws_eks_helm_deploy/helm/client.py
    - tests/unit/test_chart_local.py
    - tests/unit/test_upgrade_action.py
decisions:
  - "LocalChart uses degenerate @contextmanager (yield-and-return; no cleanup) to satisfy ChartSource Protocol shape shared with RepoChart/OciChart which DO use tempdir lifecycle"
  - "_build_oci_chart + _build_repo_chart private helpers with # pragma: no cover chosen over NotImplementedError: ships real factory signature now; Plans 04-06/04-07 lift pragmas"
  - "helm/client.py ResolvedChart import updated from chart.local to chart.base (Rule 3 auto-fix; blocking issue)"
  - "type: ignore (no error code) used on forward import lines in pragma-excluded helpers: handles both import-not-found (no venv) and import-untyped (venv active) without triggering unused-ignore"
metrics:
  duration: ~45 minutes
  completed: "2026-06-18"
  tasks: 3
  files: 10
---

# Phase 4 Plan 5: ChartSource Protocol + LocalChart Refactor + Factory Summary

One-line: ChartSource Protocol + ResolvedChart promoted to chart/base.py; LocalChart class with @contextmanager resolve() replaces legacy resolve_local_chart(); select_chart_source(settings) factory routes by prefix; actions/upgrade.py rewired to factory + with chart_source.resolve().

## What Was Built

### Task 04-5-01: chart/base.py — ChartSource Protocol + ResolvedChart

- **`src/aws_eks_helm_deploy/chart/base.py`** (NEW): two public symbols:
  - `ResolvedChart` — frozen dataclass with `name: str`, `version: str`, `source_path: pathlib.Path` (promoted from chart/local.py, same Phase 3 shape)
  - `ChartSource` — `@runtime_checkable Protocol` with `def resolve(self) -> contextlib.AbstractContextManager[ResolvedChart]: ...`
- **`tests/unit/test_chart_base.py`** (NEW): 3 tests — frozen dataclass, field order/types, runtime-checkable duck-type

### Task 04-5-02: chart/local.py — LocalChart class + legacy removal

- **`src/aws_eks_helm_deploy/chart/local.py`** (REFACTORED):
  - REMOVED `resolve_local_chart()` function (CONTEXT D3 Plan-Check obligation)
  - REMOVED local `ResolvedChart` dataclass (now imported from `chart.base`)
  - ADDED `LocalChart(chart_spec: str, repo_root: pathlib.Path | None = None)` class
  - `LocalChart.resolve()`: `@contextmanager` yielding `ResolvedChart` — degenerate (no tempdir cleanup)
  - Private helpers `_resolve_chart_path` + `_parse_chart_yaml` preserved for Plans 04-06/04-07
- **`tests/unit/test_chart_local.py`** (REFACTORED): 19 tests updated from `resolve_local_chart(...)` to `with LocalChart(...).resolve() as resolved:` (all Phase 3 branches preserved)

### Task 04-5-03: factory + upgrade rewire

- **`src/aws_eks_helm_deploy/chart/__init__.py`** (EXTENDED):
  - Exports: `ChartSource`, `LocalChart`, `ResolvedChart`, `select_chart_source`
  - `select_chart_source(settings) -> ChartSource` factory:
    - `oci://` → `_build_oci_chart()` (# pragma: no cover — Plan 04-07 lifts)
    - `repo://` → validation + `_build_repo_chart()` (# pragma: no cover — Plan 04-06 lifts)
    - else → `LocalChart(chart_spec=chart, repo_root=None)` (fully operational)
  - `ConfigurationError` raised for: `chart=None`, malformed `repo://`, `repo://` without `REPO_URL`
- **`src/aws_eks_helm_deploy/actions/upgrade.py`** (REWIRED):
  - Import: `from aws_eks_helm_deploy.chart import select_chart_source`
  - Step 6: `chart_source = select_chart_source(s)`
  - Step 8: `with chart_source.resolve() as resolved:` wraps helm install + success message
- **`src/aws_eks_helm_deploy/helm/client.py`** (auto-fix): `ResolvedChart` import updated from `chart.local` to `chart.base` (Rule 3 blocking fix)
- **`tests/unit/test_chart_init_select_source.py`** (NEW): 4 active + 2 `@pytest.mark.skip` tests
- **`tests/unit/test_upgrade_action.py`** (REWIRED): all 23 tests use `select_chart_source` mock instead of `resolve_local_chart`

## Verification Results

### Tests
```
262 passed, 2 skipped, 14 deselected in 2.45s
(2 skipped = test_select_chart_source_routes_repo_prefix_to_repo_chart, test_select_chart_source_routes_oci_prefix_to_oci_chart)
```

### Coverage
```
Total: 100% line + branch coverage
chart/base.py:    100%
chart/local.py:   100%
chart/__init__.py: 100% (pragma-excluded: _build_oci_chart, _build_repo_chart)
actions/upgrade.py: 100%
```

### Ruff
```
All checks passed — ruff check + ruff format --check
```

### Mypy
```
Success: no issues found in 24 source files (mypy --strict src/)
```

## Legacy Removal Audit (D3 Obligation)

```
grep -RIn "resolve_local_chart" src/ tests/
```
Results (comment/docstring only — NO functional code):
- `chart/base.py:8` — docstring: "refactored from resolve_local_chart"
- `chart/local.py:9` — docstring: "resolve_local_chart() was removed"
- `tests/test_chart_local.py:3` — docstring: "updated from resolve_local_chart() function shape"

ZERO functional imports, calls, or definitions of `resolve_local_chart` anywhere in src/ or tests/.

## ResolvedChart Definition Audit

```
grep -F "class ResolvedChart" src/aws_eks_helm_deploy/chart/local.py
```
Result: 0 hits — definition is ONLY in `chart/base.py`.

```
grep -F "class ResolvedChart" src/aws_eks_helm_deploy/chart/base.py
```
Result: 1 hit — canonical definition confirmed.

## Known Stubs (Pragma Lifts)

Per plan Deviation 1 (CHOSEN approach):

1. **`chart/__init__.py::_build_oci_chart()`** — `# pragma: no cover` on entire function.
   - Comment: `# Plan 04-07 lifts this pragma`
   - Plan 04-07 removes pragma + UNskips `test_select_chart_source_routes_oci_prefix_to_oci_chart`

2. **`chart/__init__.py::_build_repo_chart()`** — `# pragma: no cover` on entire function.
   - Comment: `# Plan 04-06 lifts this pragma`
   - Plan 04-06 removes pragma + UNskips `test_select_chart_source_routes_repo_prefix_to_repo_chart`

3. **`chart/__init__.py::select_chart_source` oci:// branch** — `# pragma: no cover  # Plan 04-07 lifts this pragma`

4. **`chart/__init__.py::select_chart_source` repo:// branch** — `# pragma: no cover  # Plan 04-06 lifts this pragma`

5. **`tests/unit/test_chart_init_select_source.py`** — 2 `@pytest.mark.skip` with reasons pointing at Plans 04-06 / 04-07.

## Stable Contracts Published for Plans 04-06 / 04-07

```python
class ChartSource(Protocol):
    def resolve(self) -> contextlib.AbstractContextManager[ResolvedChart]: ...

@dataclasses.dataclass(frozen=True)
class ResolvedChart:
    name: str
    version: str
    source_path: pathlib.Path

class LocalChart:
    def __init__(self, chart_spec: str, repo_root: pathlib.Path | None = None) -> None: ...
    @contextmanager
    def resolve(self) -> Iterator[ResolvedChart]: ...

def select_chart_source(settings: Settings) -> ChartSource: ...

# For Plans 04-06 / 04-07 helpers:
# from aws_eks_helm_deploy.chart.local import _parse_chart_yaml  (cross-module internal)
# from aws_eks_helm_deploy.chart.base import ResolvedChart  (canonical)
```

Cross-reference: "Plan 04-06 lifts the `# Plan 04-06 lifts this pragma` pragma + UNSkips the corresponding test; Plan 04-07 does the same for OciChart."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated helm/client.py import path for ResolvedChart**
- **Found during:** Task 04-5-02 commit (pre-commit hook: mypy error)
- **Issue:** `helm/client.py` still imported `ResolvedChart` from `chart.local` which no longer exports it after refactor
- **Fix:** Updated TYPE_CHECKING import in `helm/client.py` from `chart.local` to `chart.base`
- **Files modified:** `src/aws_eks_helm_deploy/helm/client.py`
- **Commit:** 1727b6d

**2. [Rule 3 - Blocking] Tasks 04-5-02 and 04-5-03 committed together**
- **Found during:** Task 04-5-02 commit attempt
- **Issue:** Pre-commit hook runs full pytest suite. With `actions/upgrade.py` still importing `resolve_local_chart` (removed in Task 02), the import fails and ALL tests error. Tasks 02 and 03 are atomically interdependent.
- **Fix:** Implemented Task 03 immediately after Task 02 and committed both together in a single commit that makes the full suite pass.
- **Commit:** 1727b6d

**3. [Deviation 1 from PLAN] `# pragma: no cover` with private helper functions**
- **Issue:** The `repo://` branch has partial coverage: validation raises `ConfigurationError` (covered by tests), but the `RepoChart` construction is unreachable (Plan 04-06). With the import inside `select_chart_source`, only the `return _build_repo_chart(...)` line needed pragma. But mypy also analyzes the forward import — which fails with different error codes depending on whether `.venv` is active (`import-untyped`) or not (`import-not-found`).
- **Chosen approach:** Extract `_build_oci_chart` and `_build_repo_chart` private helpers, both marked `# pragma: no cover`. Used bare `# type: ignore` (no error code) on forward import lines inside these helpers — handles both mypy contexts without `unused-ignore` warnings.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes beyond what was planned in the threat model. The `select_chart_source` factory and `LocalChart.resolve()` degenerate context-manager introduce no new attack surface.

## Self-Check

### Files Exist
- `src/aws_eks_helm_deploy/chart/base.py`: FOUND
- `src/aws_eks_helm_deploy/chart/local.py`: FOUND (refactored)
- `src/aws_eks_helm_deploy/chart/__init__.py`: FOUND (extended)
- `src/aws_eks_helm_deploy/actions/upgrade.py`: FOUND (rewired)
- `tests/unit/test_chart_base.py`: FOUND
- `tests/unit/test_chart_local.py`: FOUND (refactored)
- `tests/unit/test_chart_init_select_source.py`: FOUND
- `tests/unit/test_upgrade_action.py`: FOUND (rewired)

### Commits Exist
- `f5c06e2`: FOUND — Task 04-5-01 (chart/base.py + test_chart_base.py)
- `1727b6d`: FOUND — Tasks 04-5-02 + 04-5-03 (combined due to interdependency)

## Self-Check: PASSED
