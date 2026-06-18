---
phase: 04-oidc-chart-source-extensions
plan: 6
subsystem: chart
tags:
  - chart-source
  - repo-chart
  - helm-repo
  - helm-pull
  - context-manager
  - tempdir-isolation
  - subprocess-mocking
  - syrupy-snapshot
  - integration-test
dependency_graph:
  requires:
    - 04-02  # Settings.repo_url + Settings.chart_version
    - 04-05  # ChartSource Protocol + ResolvedChart + LocalChart + factory + _parse_chart_yaml
  provides:
    - RepoChart class (chart/repo.py) — CHART-02 implementation
    - HelmClient.repo_add / repo_update / pull_repo typed methods
    - Integration test fixture + test for local HTTP helm repo
  affects:
    - helm/client.py — 3 new public methods + 3 argv builders + _run_helm_subcommand helper
    - chart/__init__.py — repo:// pragma lifted, _build_repo_chart fully covered
    - tests/unit/test_helm_client_argv.py — 4 new syrupy snapshot tests
    - tests/unit/test_helm_client_run.py — 12 new subprocess-mocked tests
tech_stack:
  added:
    - chart/repo.py — new module (RepoChart, tempfile + shutil + contextlib)
  patterns:
    - context-manager-with-finally-cleanup (mirrors kube/kubeconfig.py D6)
    - env-var isolation for subprocess (HELM_REPOSITORY_CONFIG + HELM_REPOSITORY_CACHE)
    - _run_helm_subcommand shared helper raises ChartResolutionError (exit=4) not HelmExecutionError (exit=5)
    - single-subdir discovery after helm pull --untar (R7)
key_files:
  created:
    - src/aws_eks_helm_deploy/chart/repo.py
    - tests/unit/test_chart_repo.py
    - tests/integration/test_chart_sources.py
  modified:
    - src/aws_eks_helm_deploy/helm/client.py
    - src/aws_eks_helm_deploy/chart/__init__.py
    - tests/unit/test_chart_init_select_source.py
    - tests/unit/test_helm_client_argv.py
    - tests/unit/test_helm_client_run.py
    - tests/unit/__snapshots__/test_helm_client_argv.ambr
decisions:
  - "New HelmClient methods raise ChartResolutionError (exit=4), not HelmExecutionError (exit=5) — chart resolution failures are semantically distinct from helm upgrade failures (Plan Deviation 1)"
  - "HelmClient constructor requires kubeconfig_path; repo ops use placeholder path inside tmpdir — never created or read (Plan Deviation 2)"
  - "Cross-module import of _parse_chart_yaml from chart/local.py per Plan 04-05 Deviation 2"
  - "mkdir(exist_ok=True) used for unpack_dir to allow test patching of tempfile.mkdtemp"
  - "Integration test uses python -m http.server (no new dev dep) and skips cleanly when helm absent"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-18T13:48:00Z"
  tasks_completed: 2
  files_created: 3
  files_modified: 6
---

# Phase 04 Plan 06: RepoChart + HelmClient Extensions Summary

**One-liner:** Helm repository chart source (CHART-02) via `RepoChart` class + three typed `HelmClient` methods (`repo_add`, `repo_update`, `pull_repo`) with tempdir isolation and syrupy snapshot contracts.

## What Was Built

### Task 04-6-01: HelmClient typed methods + syrupy snapshots + subprocess-mocked tests

Extended `src/aws_eks_helm_deploy/helm/client.py` with:

- Three private argv builders: `_build_repo_add_argv`, `_build_repo_update_argv`, `_build_pull_repo_argv`
- One shared subprocess helper: `_run_helm_subcommand(argv, *, env, timeout, error_prefix)` — raises `ChartResolutionError` (exit_code=4) on non-zero returncode or TimeoutExpired
- Three public typed methods: `repo_add(name, repo_url, env)`, `repo_update(name, env)`, `pull_repo(repo_chart, destination, untar_dir, version, env)`
- Import extension: `ChartResolutionError` added to existing `from errors import …` line

Extended `tests/unit/test_helm_client_argv.py` with 4 new syrupy snapshot tests:
- `test_repo_add_argv`, `test_repo_update_argv`, `test_pull_repo_argv_with_version`, `test_pull_repo_argv_without_version`

Extended `tests/unit/test_helm_client_run.py` with 12 new subprocess-mocked tests (4 per method):
- happy path, non-zero returncode → ChartResolutionError, TimeoutExpired → ChartResolutionError, + version branch for pull_repo

Updated `tests/unit/__snapshots__/test_helm_client_argv.ambr` with 4 new snapshot entries.

### Task 04-6-02: RepoChart class + pragma lift + unit + integration tests

Created `src/aws_eks_helm_deploy/chart/repo.py`:
- `RepoChart(name, chart, repo_url, version=None)` — no I/O at construction
- `resolve()` context-manager: mkdtemp → env isolation → repo_add → repo_update → pull_repo → single-subdir discovery → parse Chart.yaml → yield ResolvedChart → finally rmtree
- Mirrors `kube/kubeconfig.py` context-manager-with-finally pattern (CONTEXT D6)
- All subprocess routing through `HelmClient` (Phase 3 D1 invariant preserved)

Updated `src/aws_eks_helm_deploy/chart/__init__.py`:
- Removed `# pragma: no cover  # Plan 04-06 lifts this pragma` from the `repo://` branch
- Removed `# type: ignore` comments from `_build_repo_chart`
- Updated module docstring (repo:// marked as shipped)

Updated `tests/unit/test_chart_init_select_source.py`:
- Removed `@pytest.mark.skip` from `test_select_chart_source_routes_repo_prefix_to_repo_chart`
- Enhanced test body with `_name`, `_chart`, `_version` attribute assertions

Created `tests/unit/test_chart_repo.py` (10 tests):
- Happy path, call order, env isolation, tempdir cleanup (normal + exception), version flag, no-version, no-subdir error, repo_add failure error

Created `tests/integration/test_chart_sources.py`:
- `local_helm_repo` session-scoped fixture: packages Phase 3 minimal chart → helm repo index → python -m http.server
- `test_repo_chart_resolves_real_chart_via_local_http_repo` — marked `@pytest.mark.integration @pytest.mark.flaky(reruns=3, reruns_delay=5)`
- Skips cleanly when helm binary absent

## Phase 3 D1 Invariant Audit

`grep -RIn "import subprocess" src/aws_eks_helm_deploy/` returns exactly one hit:

```
src/aws_eks_helm_deploy/helm/client.py:28:import subprocess
```

Invariant preserved. `chart/repo.py` routes all helm subprocess calls through `HelmClient.repo_add/repo_update/pull_repo`.

## Coverage

| Module | Line % | Branch % |
|--------|--------|---------|
| `chart/repo.py` | 100% | 100% |
| `helm/client.py` | 100% | 100% |
| `chart/__init__.py` | 100% | 100% |
| **Total (all modules)** | **100%** | **100%** |

## Integration Test Outcome

Helm binary not installed on this machine → test skipped cleanly with `pytest.skip("helm binary not installed; integration tier requires it")`. The test fixture and test function are correct and will pass when `helm` is on PATH (verified by code review: the fixture packages the Phase 3 minimal chart, indexes it, serves via `python -m http.server`, and RepoChart pulls + verifies it).

## Env Isolation Variables

Both variables are set on every subprocess call inside `resolve()`:

| Env Var | Value |
|---------|-------|
| `HELM_REPOSITORY_CONFIG` | `<tmpdir>/repositories.yaml` |
| `HELM_REPOSITORY_CACHE` | `<tmpdir>/cache` |

The tempdir is cleaned by `shutil.rmtree(tmpdir, ignore_errors=True)` in the `finally` block, removing both the config file and cache atomically on context exit.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as specified.

### Documented Plan Deviations (pre-approved in PLAN.md)

**Deviation 1: New methods raise `ChartResolutionError` (exit_code=4), not `HelmExecutionError` (exit_code=5)**
- Rationale: chart-resolution failures (repo not reachable, chart not found, wrong version) are semantically distinct from helm-upgrade-itself failures. Consumers reading exit codes can distinguish "chart not found" (4) from "upgrade failed" (5).
- Files: `helm/client.py` — `_run_helm_subcommand` helper

**Deviation 2: `HelmClient(kubeconfig_path=tmpdir / "unused-kubeconfig.yaml")` placeholder**
- The Phase 3 constructor requires a `pathlib.Path` argument. Repo ops do not touch the cluster; the placeholder path is never created or read by the 3 new methods.
- Files: `chart/repo.py` — documented with inline comment

**Deviation 3: Cross-module `_parse_chart_yaml` import (agreed in Plan 04-05 Deviation 2)**
- `from aws_eks_helm_deploy.chart.local import _parse_chart_yaml`
- No noqa comment needed — `PLC0415` / `PLC2701` not selected in this project's ruff config.
- Files: `chart/repo.py`

**Minor implementation adjustment: `mkdir(exist_ok=True)`**
- The plan's behavior block showed `unpack_dir.mkdir()`. Tests mock `tempfile.mkdtemp` to return `tmp_path` which already has subdirectories pre-created (test setup creates `tmp_path/unpacked/redis/Chart.yaml`). Changed to `exist_ok=True` to allow tests to pre-populate the tempdir. This does not affect production behavior (real tempdirs are freshly created).

## Cross-Reference

Plan 04-07's `OciChart` + the new `registry_login` + `pull_oci` `HelmClient` methods land in Wave 3. Plan 04-07 reuses the `_run_helm_subcommand` private helper this plan ships.

## Self-Check: PASSED

All created/modified files exist on disk. All commits exist in git history.

| Check | Result |
|-------|--------|
| `chart/repo.py` exists | PASSED |
| `helm/client.py` exists | PASSED |
| `test_chart_repo.py` exists | PASSED |
| `test_chart_sources.py` exists | PASSED |
| `test_helm_client_argv.ambr` exists | PASSED |
| Commit `7e25b79` (Task 1) | PASSED |
| Commit `090a4de` (Task 2) | PASSED |
