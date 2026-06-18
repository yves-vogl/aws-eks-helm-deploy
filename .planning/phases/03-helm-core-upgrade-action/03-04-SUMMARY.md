---
phase: 03-helm-core-upgrade-action
plan: 4
subsystem: upgrade-action-orchestration
tags:
  - actions
  - orchestration
  - cli
  - settings
  - history-max
  - bitbucket-metadata
  - success-message
  - error-mapping
dependency_graph:
  requires:
    - phase: 03-helm-core-upgrade-action/03-01
      provides: ClusterAccess + get_cluster_access + write_kubeconfig + KubeconfigError=7
    - phase: 03-helm-core-upgrade-action/03-02
      provides: HelmClient + HelmResult + HelmExecutionError + HelmTimeoutError
    - phase: 03-helm-core-upgrade-action/03-03
      provides: ResolvedChart + resolve_local_chart
    - phase: 02-aws-layer-auth-foundation
      provides: select_strategy + AuthStrategy + AwsCredentials.to_boto3_kwargs
  provides:
    - aws_eks_helm_deploy.actions.upgrade.UpgradeAction(settings, *, strategy=None, kubeconfig_override=None)
    - aws_eks_helm_deploy.actions.upgrade.build_bitbucket_set_args(logger) -> list[str]
    - aws_eks_helm_deploy.actions.upgrade.BITBUCKET_META_VARS (5-tuple list, order-stable)
    - aws_eks_helm_deploy.settings.Settings.history_max: int | None = Field(ge=0)
    - aws_eks_helm_deploy.settings.Settings.timeout default updated to "600s"
  affects:
    - 03-05-PLAN.md: consumes UpgradeAction(settings, kubeconfig_override=path) for kind integration
tech_stack:
  added: []
  patterns:
    - structlog.BoundLogger passed to build_bitbucket_set_args (testable injection)
    - kubeconfig_override test-only scaffold (kind integration hook)
    - pragma: no cover on defensive else branch (Phase 5 forward-compat)
    - type: ignore[arg-type] on boto3.session.Session **kwargs spread (mypy strict limitation)
key_files:
  created:
    - src/aws_eks_helm_deploy/actions/__init__.py
    - src/aws_eks_helm_deploy/actions/upgrade.py
    - tests/unit/test_upgrade_action.py
  modified:
    - src/aws_eks_helm_deploy/settings.py (history_max field + timeout default 5m->600s)
    - src/aws_eks_helm_deploy/cli.py (Phase 2 placeholder replaced by UpgradeAction dispatch)
    - tests/unit/test_settings.py (6 new tests + timeout default assertion updated)
    - tests/unit/test_cli.py (Phase 2 placeholder tests removed; 4 new dispatch tests added)
    - pyproject.toml (S106 added to tests per-file-ignores)
    - tests/unit/test_logging.py (removed redundant noqa S106)
decisions:
  - "UpgradeAction.__init__ accepts strategy kwarg to avoid double select_strategy call (cli.py already called it for structlog binding)"
  - "kubeconfig_override kwarg added as test-only scaffold; skips steps 4+5 (cluster access + EKS token) + write_kubeconfig; Plan 03-05 uses this for kind"
  - "boto3.session.Session called with **creds.to_boto3_kwargs() + type: ignore[arg-type]; mypy strict rejects **dict[str,str] spread into Session positional args"
  - "pragma: no cover on else: raise ConfigurationError in cli.py; Settings.action Literal['upgrade'] makes branch unreachable in Phase 3; Phase 5 removes pragma when Literal widens"
  - "S106 added to tests per-file-ignores (hardcoded test credentials as kwargs trigger ruff S106)"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 6
---

# Phase 03 Plan 04: UpgradeAction Orchestration + CLI Wire-in Summary

**One-liner:** `UpgradeAction` orchestrates the 9-step helm upgrade chain via typed primitives (auth -> EKS -> kubeconfig -> chart -> helm), wired into `cli.py` for `ACTION=upgrade`; `Settings.history_max` closes #17 with `ge=0` validation; `build_bitbucket_set_args` implements META-01 opt-in injection with structlog warnings on missing vars.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 03-4-01 | Settings.history_max + timeout default update | 93b0a57 | settings.py, test_settings.py |
| 03-4-02 | actions/upgrade.py — UpgradeAction + build_bitbucket_set_args | 41adae0 | actions/__init__.py, actions/upgrade.py, test_upgrade_action.py, pyproject.toml |
| 03-4-03 | cli.py wire-in — replace Phase 2 placeholder with UpgradeAction dispatch | 97a7356 | cli.py, test_cli.py |
| (fix) | Remove redundant noqa S106 from test_logging.py | f4e5c1a | test_logging.py |

## Coverage Results

| Module | Line Coverage | Branch Coverage |
|--------|--------------|----------------|
| `src/aws_eks_helm_deploy/settings.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/actions/__init__.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/actions/upgrade.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/cli.py` | 100% | 100% |
| TOTAL (all 23 source files) | 100% | 100% |

**Full unit suite:** 230 tests passed, 10 deselected (integration/acceptance tier), 0 failed.

## LOC Audit — UpgradeAction.run Body

The `run` method body (lines 117-199) contains approximately **45 executable lines** (excluding docstring, comments, and blank lines), within the < 50 LOC budget from CONTEXT D1. Total file size: 200 lines including imports, docstring, constants, helper function, and class boilerplate.

## CHART-05 Success Message (exact text)

From `test_run_returns_0_on_success`:

```
Deployed chart minimal (0.1.0) to release test-release in namespace default on cluster test-cluster
```

Format template: `f"Deployed chart {resolved.name} ({resolved.version}) to release {s.release_name} in namespace {s.namespace} on cluster {cluster_name}"`

## OBS-01 Structlog Event Keys (test_run_emits_structlog_info_with_all_obs01_fields)

Event name: `"upgrade complete"` with keys:

| Key | Type | Example Value |
|-----|------|---------------|
| `action` | str | `"upgrade"` |
| `release` | str | `"test-release"` |
| `namespace` | str | `"default"` |
| `chart_source` | str | `"/tmp/chart-fixture"` |
| `chart_name` | str | `"minimal"` |
| `chart_version` | str | `"0.1.0"` |
| `cluster` | str | `"test-cluster"` |
| `helm_revision` | int | `3` |
| `duration_ms` | int | `<measured>` |

`auth_strategy` is bound separately by `cli.py` via `bind_safe_context` (Phase 2 contract).

## kubeconfig_override Scaffold

Yes — `UpgradeAction.__init__` accepts `kubeconfig_override: pathlib.Path | None = None` (marked `# test-only`). When set:
- Step 4 (cluster_access) is SKIPPED
- Step 5 (eks_token) is SKIPPED
- `write_kubeconfig` context manager is SKIPPED
- `HelmClient(self._kubeconfig_override)` used directly

Test `test_kubeconfig_override_skips_cluster_access_and_token_generation` asserts all three mocks are not called when override is set. Plan 03-05 integration tests use this hook.

## pragma: no cover

Yes — one `# pragma: no cover` exists in `cli.py` on the `raise ConfigurationError(f"Unsupported action: {settings.action!r}")` line. Inline justification: "defensive; reachable once Phase 5 widens Settings.action Literal". The `if settings.action == "upgrade"` branch above is fully tested; the unreachable else is forward-compat for Phase 5.

## Grep Audits

**subprocess.run audit (CONTEXT D1):**
```
grep -RIn "import subprocess" src/aws_eks_helm_deploy/
src/aws_eks_helm_deploy/helm/client.py:27:import subprocess
```
Result: ONLY `helm/client.py` imports `subprocess`. `actions/upgrade.py` does NOT.

**os.environ.get in upgrade.py:**
```
grep "os.environ.get" src/aws_eks_helm_deploy/actions/upgrade.py
```
Result: `os.environ.get` appears ONLY in `build_bitbucket_set_args` (the documented exception).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] type: ignore[arg-type] on boto3.session.Session **kwargs**

- **Found during:** Task 03-4-02, mypy --strict src
- **Issue:** `mypy --strict` rejects `**dict[str, str]` spread into `boto3.session.Session(...)` because the type stubs type the second positional as `Session | None`. The `to_boto3_kwargs()` return type is `dict[str, str]`; mypy can't prove the keys match named params.
- **Fix:** Added `# type: ignore[arg-type]` inline. Alternative (extract keys explicitly per assume_role.py) was tested first but failed at runtime because the test mock's `to_boto3_kwargs()` returns `{}` (empty dict), causing `KeyError: 'aws_access_key_id'`.
- **Files modified:** `src/aws_eks_helm_deploy/actions/upgrade.py`
- **Commit:** 41adae0

**2. [Rule 2 - Missing] Added S106 to tests per-file-ignores in pyproject.toml**

- **Found during:** Task 03-4-02, pre-commit ruff hook
- **Issue:** `_make_settings(aws_secret_access_key="wJalrXUtnFEMI/...")` triggers S106 ("Possible hardcoded password assigned to argument"). Other tests use dict literals which don't trigger S106.
- **Fix:** Added `"S106"` to `"tests/**"` per-file-ignores in pyproject.toml. The existing `# noqa: S106` in `test_logging.py` became a RUF100 unused directive (removed in fix commit f4e5c1a).
- **Files modified:** `pyproject.toml`, `tests/unit/test_logging.py`
- **Commit:** 41adae0 (S106 add), f4e5c1a (noqa removal)

### Documented Deviations (from PLAN.md)

All five documented deviations in the PLAN.md `<deviations>` section were followed as planned:

1. **UpgradeAction.__init__ accepts `strategy: AuthStrategy | None = None` kwarg** — implemented; cli.py passes `strategy=strategy`. ✓
2. **`os.environ` read inside `build_bitbucket_set_args`** — documented exception in module docstring. ✓
3. **`# pragma: no cover` on the `cli.py` `else: raise ConfigurationError` branch** — Option 1 chosen; inline comment explains Phase 5 widening. ✓
4. **`--history-max 0` passed through to helm** — `settings.history_max == 0` flows to `HelmClient.upgrade_install(history_max=0)`. `test_history_max_0_passes_0_to_helm_client` enforces. ✓
5. **META-02 + META-03 NOT implemented** — Phase 5 scope; `inject_bitbucket_metadata` defaults to `False` per Phase 1 field. ✓

## Known Stubs

- `# pragma: no cover` on `cli.py` `else: raise ConfigurationError` branch — defensive scaffold for Phase 5 action Literal widening. Intentional; removed in Phase 5.
- `kubeconfig_override` constructor kwarg in `UpgradeAction` — test-only scaffold for Plan 03-05 kind integration. NOT removed; preserved into Phase 4+.

## Threat Flags

No new security-relevant surface beyond what the PLAN.md threat model documents. Implemented mitigations:

- T-03-04-01: argv is `list[str]`, never `shell=True` — `build_bitbucket_set_args` returns `"key=value"` strings; `HelmClient._build_argv` renders as `["--set-string", "key=value"]`. Test `test_inject_true_with_uuid_curly_braces_passes_through_verbatim` enforces.
- T-03-04-02: `pydantic.Field(ge=0)` enforces non-negative `history_max`. Test `test_history_max_rejects_negative_integer` enforces.
- T-03-04-06: `raise KubeconfigError(...) from exc` preserves `__cause__`. Test `test_run_wraps_oserror_as_kubeconfig_error` asserts `__cause__ is OSError`.

## Self-Check: PASSED

Files verified on disk:
- `src/aws_eks_helm_deploy/actions/__init__.py` — FOUND
- `src/aws_eks_helm_deploy/actions/upgrade.py` — FOUND
- `src/aws_eks_helm_deploy/settings.py` — FOUND
- `src/aws_eks_helm_deploy/cli.py` — FOUND
- `tests/unit/test_settings.py` — FOUND
- `tests/unit/test_upgrade_action.py` — FOUND
- `tests/unit/test_cli.py` — FOUND

Commits verified in git log:
- 93b0a57 (03-4-01) — FOUND
- 41adae0 (03-4-02) — FOUND
- 97a7356 (03-4-03) — FOUND
- f4e5c1a (fix) — FOUND
