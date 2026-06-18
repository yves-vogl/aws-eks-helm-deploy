---
phase: 03-helm-core-upgrade-action
plan: 3
subsystem: chart-resolver-layer
tags:
  - chart
  - resolved-chart
  - pyyaml
  - local-path
  - validation
  - structlog
dependency_graph:
  requires:
    - phase: 01-toolchain-spine
      provides: errors.py ChartResolutionError(exit_code=4); PyYAML ~= 6.0 in project.dependencies
    - phase: 03-helm-core-upgrade-action/03-01
      provides: KubeconfigError=7 in errors.py; confirmed ChartResolutionError stable
    - phase: 03-helm-core-upgrade-action/03-02
      provides: HelmClient.upgrade_install TYPE_CHECKING-imports ResolvedChart (forward ref now resolves)
  provides:
    - aws_eks_helm_deploy.chart.local.ResolvedChart (frozen dataclass, 3 fields)
    - aws_eks_helm_deploy.chart.local.resolve_local_chart(chart_spec, repo_root=None) -> ResolvedChart
  affects:
    - 03-04-PLAN.md: actions/upgrade.py calls resolve_local_chart(settings.chart) -> ResolvedChart
    - 03-05-PLAN.md: integration test resolves charts/minimal via resolve_local_chart
tech_stack:
  added: []
  patterns:
    - frozen dataclass value object (ResolvedChart mirrors AwsCredentials/ClusterAccess shape)
    - yaml.safe_load (NEVER yaml.load) per T-03-03-01 security constraint
    - structlog.warning for non-fatal Chart.yaml shortcomings (missing version, v1 apiVersion)
    - structlog.testing.capture_logs() in tests for warning assertion without configure_logging()
    - _parse_chart_yaml helper to reduce cyclomatic complexity below C901 threshold (10)
key_files:
  created:
    - src/aws_eks_helm_deploy/chart/__init__.py
    - src/aws_eks_helm_deploy/chart/local.py
    - tests/unit/test_chart_local.py
  modified:
    - src/aws_eks_helm_deploy/helm/client.py (removed stale TYPE_CHECKING type: ignore)
decisions:
  - "ResolvedChart is a concrete frozen dataclass (not a Protocol): YAGNI — one implementation; Phase 4 refactors to ChartSource Protocol when RepoChart/OciChart arrive (CHART-02/03)"
  - "resolve_local_chart accepts repo_root parameter for testable cwd-independent path resolution (relative paths without monkeypatch.chdir)"
  - "Empty Chart.yaml raises ChartResolutionError with 'empty or malformed' message (yaml.safe_load returns None for empty files)"
  - "Non-mapping Chart.yaml raises ChartResolutionError with 'must be a YAML mapping' message (defensive against YAML list at top level)"
  - "_parse_chart_yaml helper extracted to reduce resolve_local_chart cyclomatic complexity from 12 to acceptable (C901 <= 10)"
  - "yaml.safe_load type: ignore NOT needed — types-PyYAML dev dep (from 03-01) provides full type stubs"
  - "Removed stale TYPE_CHECKING type: ignore[import-untyped] from helm/client.py — chart.local now exists and is fully typed"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-18"
  tasks_completed: 1
  tasks_total: 1
  files_created: 3
  files_modified: 1
---

# Phase 03 Plan 03: Local Chart Resolver Summary

**One-liner:** `ResolvedChart` frozen dataclass + `resolve_local_chart` with PyYAML safe_load, 15-branch path coverage, structlog warnings on missing-version and v1 apiVersion, explicit repo:// + oci:// rejection pointing to Phase 4.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 03-3-01 | chart/ skeleton + ResolvedChart + resolve_local_chart + tests | c97ded6 | chart/__init__.py, chart/local.py, test_chart_local.py, helm/client.py |

## Coverage Results

| Module | Line Coverage | Branch Coverage |
|--------|--------------|----------------|
| `src/aws_eks_helm_deploy/chart/local.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/chart/__init__.py` | 100% | 100% |
| TOTAL (all 20 source files) | 100% | 100% |

**Full suite:** 197 tests passed, 10 deselected (integration/acceptance tier), 0 failed.

## Branch Coverage Checklist

All 15 branches enumerated in the behavior section were exercised:

| Branch | Test |
|--------|------|
| `repo://` prefix rejection | `test_repo_prefix_raises_chart_resolution_error` |
| `oci://` prefix rejection | `test_oci_prefix_raises_chart_resolution_error` |
| Relative path with repo_root | `test_relative_path_resolved_against_repo_root` |
| Relative path without repo_root (cwd) | `test_relative_path_resolved_against_cwd_when_no_repo_root` |
| Absolute path (no base resolution) | `test_absolute_path_used_directly` |
| `path.exists() is False` | `test_missing_directory_raises` |
| `path.is_dir() is False` | `test_path_is_file_not_directory_raises` |
| `chart_yaml_path.exists() is False` | `test_missing_chart_yaml_raises` |
| `yaml.YAMLError` branch | `test_invalid_yaml_raises` |
| `data is None` branch | `test_empty_chart_yaml_raises` |
| `not isinstance(data, dict)` branch | `test_non_mapping_chart_yaml_raises` |
| `name` missing -> fallback to dir name | `test_missing_name_falls_back_to_dir_name` |
| `version` missing -> fallback + warn | `test_missing_version_falls_back_to_empty_string_and_warns` |
| `apiVersion == "v1"` -> warn branch | `test_v1_api_version_warns_but_proceeds` |
| Happy path (all fields present, v2) | `test_happy_path_full_chart_yaml` |

## PyYAML Version

`PyYAML 6.0.3` — confirmed in project venv (`uv run python -c "import yaml; print(yaml.__version__)"`). This is the version already declared in `pyproject.toml` as `"PyYAML ~= 6.0"`. No new dependency was added.

## yaml.load Audit

```
grep -RIn "yaml\.load[^_]" src/
```

Result: One match in `src/aws_eks_helm_deploy/chart/local.py:15` — this is the **module docstring** warning ("NEVER yaml.load"). No actual `yaml.load(` call exists anywhere in `src/`. Audit is **CLEAN**.

## TYPE_CHECKING Forward Reference

The `helm/client.py` TYPE_CHECKING import of `ResolvedChart` previously required `# type: ignore[import-untyped]` because `chart/local.py` did not exist. Now that this plan ships `chart/local.py`:

- mypy --strict src exits 0 across all 21 source files
- The stale `# type: ignore[import-untyped]` was removed from `helm/client.py` (Rule 1 auto-fix)
- `uv run python -c "from aws_eks_helm_deploy.helm.client import HelmClient; from aws_eks_helm_deploy.chart.local import ResolvedChart; print('forward-reference resolved')"` exits 0

## type: ignore Comments

Zero `# type: ignore` comments in `chart/local.py` or `chart/__init__.py`. The `types-PyYAML` dev dependency (added in Plan 03-01) provides full type stubs for PyYAML, so no ignores are needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed stale TYPE_CHECKING type: ignore from helm/client.py**

- **Found during:** Task 03-3-01, `mypy --strict src` reporting `Unused "type: ignore" comment [unused-ignore]` on helm/client.py:33
- **Issue:** Plan 03-02 added `# type: ignore[import-untyped]` to the TYPE_CHECKING import of `ResolvedChart` because `chart/local.py` didn't exist yet. Now that chart/local.py is fully typed, the ignore is stale and unused.
- **Fix:** Removed the comment — `from aws_eks_helm_deploy.chart.local import ResolvedChart` under `TYPE_CHECKING` is clean.
- **Files modified:** `src/aws_eks_helm_deploy/helm/client.py`
- **Commit:** c97ded6

**2. [Rule 1 - Bug] Extracted _parse_chart_yaml helper to satisfy C901 complexity limit**

- **Found during:** Task 03-3-01, `ruff check` reporting `C901 resolve_local_chart is too complex (12 > 10)`.
- **Issue:** The initial single-function implementation had cyclomatic complexity 12, exceeding ruff's C901 limit of 10.
- **Fix:** Extracted `_parse_chart_yaml(path) -> dict[str, Any]` private helper. `resolve_local_chart` delegates Chart.yaml reading, parsing, and shape validation to this helper. Both functions have complexity within limits.
- **Files modified:** `src/aws_eks_helm_deploy/chart/local.py`
- **Commit:** c97ded6

**3. [Rule 1 - Bug] Removed yaml.safe_load type: ignore — types-PyYAML stubs cover it**

- **Found during:** Task 03-3-01, `mypy --strict src` reporting `Unused "type: ignore" comment [unused-ignore]` on the `yaml.safe_load` call.
- **Issue:** The plan's action section suggested `# type: ignore[no-untyped-call]` for yaml.safe_load. But `types-PyYAML` (added in Plan 03-01) provides full type stubs — no ignore needed.
- **Fix:** Removed the comment.
- **Files modified:** `src/aws_eks_helm_deploy/chart/local.py`
- **Commit:** c97ded6

### Documented Deviations (from PLAN.md)

All four documented deviations in the PLAN.md `<deviations>` section were followed as planned:

1. **ResolvedChart as concrete dataclass (not Protocol)** — shipped as frozen dataclass. ✓
2. **resolve_local_chart accepts repo_root parameter** — `resolve_local_chart(chart_spec: str, repo_root: pathlib.Path | None = None) -> ResolvedChart`. ✓
3. **Empty Chart.yaml raises ChartResolutionError** — `if data is None: raise ChartResolutionError("... empty or malformed")`. ✓
4. **Non-mapping Chart.yaml raises ChartResolutionError** — `if not isinstance(data, dict): raise ChartResolutionError("... must be a YAML mapping")`. ✓

## Known Stubs

No stubs. `chart/local.py` ships at its full Phase 3 behavior.

- `repo://` and `oci://` rejection branches are NOT stubs — they are the deliberate "Phase 4 only" UX for Phase 3. These branches will be replaced by real resolvers in Phase 4 (CHART-02, CHART-03).
- `chart/__init__.py` is intentionally empty — Phase 4 adds `chart/base.py` (Protocol) + resolvers.

## Threat Flags

No new security-relevant surface beyond what the PLAN.md threat model documents (T-03-03-01 through T-03-03-05). Mitigations implemented:

- T-03-03-01: `yaml.safe_load` exclusively — audit-gated (grep returns NOTHING for actual `yaml.load(` calls).
- T-03-03-04: `path.exists()` + `path.is_dir()` validate path before use — path traversal naturally rejected by non-directory check.

## Pre-commit + pip-audit

All pre-commit hooks pass:

```
ruff (legacy alias)  Passed
ruff format          Passed
mypy                 Passed
fix end of files     Passed
trim trailing whitespace  Passed
check yaml           Passed
check toml           Passed
check for merge conflicts  Passed
Detect hardcoded secrets  Passed
pytest (unit, no-cov)  Passed
```

`pip-audit` shows one pre-existing transitive vulnerability (`requests 2.32.5 CVE-2026-25645`) — not introduced by this plan. No new vulnerabilities.

## Self-Check: PASSED

Files verified on disk:

- `src/aws_eks_helm_deploy/chart/__init__.py` — FOUND
- `src/aws_eks_helm_deploy/chart/local.py` — FOUND
- `tests/unit/test_chart_local.py` — FOUND

Commit verified in git log:

- c97ded6 (03-3-01) — FOUND
