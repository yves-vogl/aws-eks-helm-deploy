---
phase: 05-log-masking-diff-rollback-metadata-flip
plan: "06"
subsystem: metadata-detection
tags: [META-02, META-03, MIG-02, deprecation-warn, bitbucket, upgrade-action, cli]
dependency_graph:
  requires: ["05-01"]
  provides: [META-02, META-03, MIG-02]
  affects:
    - src/aws_eks_helm_deploy/actions/upgrade.py
    - src/aws_eks_helm_deploy/cli.py
tech_stack:
  added: []
  patterns:
    - static-grep-values-yaml (META-03 detection without helm template invocation)
    - tri-state-bool-none (inject_bitbucket_metadata: True/False/None sentinel)
    - startup-env-scan (MIG-02 unconditional os.environ scan)
key_files:
  modified:
    - src/aws_eks_helm_deploy/actions/upgrade.py
    - src/aws_eks_helm_deploy/cli.py
    - tests/unit/test_upgrade_action.py
    - tests/unit/test_cli.py
decisions:
  - "META-03 detector uses re.MULTILINE so it matches any line with leading whitespace, not just line-start anchored"
  - "MIG-02 test for main() mocks configure_logging to prevent structlog pipeline clobber in capture_logs() context"
  - "Test function names lowercased to satisfy ruff N802 (no uppercase in test names)"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-20T09:05:05Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 05 Plan 06: META-02/META-03/MIG-02 Metadata Flip + Deprecation WARN Summary

Closes the metadata-flip trifecta: META-02 default-off gate, META-03 detection WARN, MIG-02 v1 env-var startup scan. Closes GitHub issue #16. Addresses Pitfall #2 from ROADMAP (silent stealth-coupling between v1 charts and v2 pipe).

## What Was Built

### Task 1: META-02/META-03 — `_check_bitbucket_values_yaml` in `actions/upgrade.py`

**New symbols:**

- `BITBUCKET_VALUES_REGEX: Final[re.Pattern[str]]` — `re.compile(r"^\s*bitbucket\s*:", re.MULTILINE)` placed at module scope after `build_bitbucket_set_args`.
- `_check_bitbucket_values_yaml(chart_dir, inject_bitbucket_metadata, log) -> None` — static grep helper that reads `<chart_dir>/values.yaml`, applies the regex, and emits `meta.bitbucket_values_detected_without_opt_in` WARN exactly when the regex matches AND `inject_bitbucket_metadata is None`.

**Integration call site in `UpgradeAction.run`:** placed AFTER `chart_source.resolve()` opens and BEFORE the kubeconfig context manager branches, as required by CONTEXT D4:
```python
_check_bitbucket_values_yaml(resolved.source_path, s.inject_bitbucket_metadata, logger)
```

**META-02 default-flip behavior chart:**

| `inject_bitbucket_metadata` | `bitbucket_args` injected? | WARN emitted? |
|-----------------------------|---------------------------|---------------|
| `None` (default)            | NO (falsy gate)           | YES if `bitbucket:` in values.yaml |
| `False`                     | NO (falsy gate)           | NO (explicit choice) |
| `True`                      | YES                       | NO (explicit choice) |

The existing line `build_bitbucket_set_args(logger) if s.inject_bitbucket_metadata else []` was already correct for META-02 — `None` and `False` are both falsy. No logic change was required to that line; only the META-03 detection was added.

**WARN event name (grep gate):** `meta.bitbucket_values_detected_without_opt_in`
**WARN payload:** `chart_dir=str(chart_dir), values_yaml=str(values_yaml)` — no content from the file is logged (T-05-01 defense in depth).

### Task 2: MIG-02 — `_warn_on_v1_env_vars` in `cli.py`

**New symbols:**

- `V1_DEPRECATED_ENV_VARS: Final[tuple[str, ...]] = ("SET", "VALUES")` — the two v1-era env var names that v2 reuses with different syntax (space-separated → comma-separated).
- `_warn_on_v1_env_vars(log: structlog.BoundLogger) -> None` — emits one `mig.v1_env_var_detected` WARN per present, non-empty env var. Unconditional — not gated by any setting (D4 contract).

**Integration call site in `main()`:** placed AFTER `configure_logging(settings)` and BEFORE `select_strategy(settings)`:
```python
_warn_on_v1_env_vars(get_logger(__name__))
```

**WARN event name (grep gate):** `mig.v1_env_var_detected`
**WARN payload:** `name=<env_var_name>` — the VALUE is never logged (consumer privacy if accidentally set to a secret).

## Tests Added

**`tests/unit/test_upgrade_action.py` (+22 tests):**
- 9 `_check_bitbucket_values_yaml` unit tests covering: match+None=WARN, match+True=silent, match+False=silent, no-match=silent, missing file=silent, indented key=WARN, OSError=silent, commented key=silent (# prefix), integration call in UpgradeAction.run.
- 4 `BITBUCKET_VALUES_REGEX` correctness tests: top-level key, indented key, comment exclusion, partial-key non-match.
- 3 META-02 tri-state integration tests: metadata_is_none, metadata_is_false (both no inject), metadata_is_true (inject).
- Previous total: 30 tests. New total: **43 tests** (+13 net, some overlap with renamed test coverage).

**`tests/unit/test_cli.py` (+6 tests):**
- `test_warn_on_v1_env_vars_emits_warn_when_set_is_set` — SET present → WARN with name="SET".
- `test_warn_on_v1_env_vars_emits_warn_when_values_is_set` — VALUES present → WARN with name="VALUES".
- `test_warn_on_v1_env_vars_emits_two_warns_when_both_set` — both present → 2 WARNs.
- `test_warn_on_v1_env_vars_silent_when_neither_set` — absent → 0 WARNs.
- `test_warn_on_v1_env_vars_silent_when_set_is_empty_string` — empty string treated as unset.
- `test_main_calls_warn_on_v1_env_vars_after_configure_logging_and_before_dispatch` — integration: WARN appears before `auth strategy selected` INFO in log stream.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Naming] Ruff N802: uppercase letters in test function names**
- **Found during:** Task 2 ruff check
- **Issue:** Plan specified test names `test_warn_on_v1_env_vars_emits_warn_when_SET_is_set` etc. containing uppercase `SET`/`VALUES` — ruff N802 flags function names with uppercase letters.
- **Fix:** Lowercased the env var portion of each affected test name: `SET` → `set`, `VALUES` → `values`. Semantics unchanged.
- **Files modified:** `tests/unit/test_cli.py`

**2. [Rule 1 - Bug] configure_logging clobbers structlog capture_logs pipeline**
- **Found during:** Task 2 test debugging
- **Issue:** The plan's integration test for `main()` calling `_warn_on_v1_env_vars` used `capture_logs()` without mocking `configure_logging`. `configure_logging()` calls `structlog.configure(cache_logger_on_first_use=True)` which replaces the `capture_logs` processor, causing the WARN not to be captured.
- **Fix:** Added `mocker.patch("aws_eks_helm_deploy.cli.configure_logging")` to the integration test — consistent with the existing `test_main_module_runs` pattern in the same file.
- **Files modified:** `tests/unit/test_cli.py`

**3. [Rule 2 - Convention] En-dash in docstring flagged by ruff RUF002**
- **Found during:** Task 2 ruff check
- **Issue:** Docstring used `0–2` (EN DASH U+2013); ruff RUF002 requires HYPHEN-MINUS.
- **Fix:** Changed to `0-2`.
- **Files modified:** `src/aws_eks_helm_deploy/cli.py`

## Known Stubs

None — no stub data, placeholder text, or unwired components in this plan.

## Threat Flags

None. As documented in the plan's threat model, this plan ships UX warnings only. WARN log payloads include only file paths and env var names, never file contents or env var values.

## Quality Gates

| Gate | Result |
|------|--------|
| `uv run pytest tests/unit -q --no-cov` | PASS (469 tests) |
| `uv run pytest tests/unit --cov=... --cov-fail-under=100` | PASS (100.00%) |
| `uv run mypy --strict src/aws_eks_helm_deploy` | PASS (0 errors, 32 files) |
| `uv run ruff check src/ tests/` | PASS |
| `grep -E '^import subprocess' src/aws_eks_helm_deploy/` returns 2 files | PASS (D6 invariant) |
| `grep -F 'meta.bitbucket_values_detected_without_opt_in' actions/upgrade.py` | PASS (2 hits) |
| `grep -F 'mig.v1_env_var_detected' cli.py` | PASS (2 hits) |
| `grep -F 'BITBUCKET_VALUES_REGEX' actions/upgrade.py` | PASS (2 hits) |

## Commits

| Hash | Message |
|------|---------|
| `ae1172d` | feat(05-06): META-02/META-03 bitbucket values detection in UpgradeAction |
| `a714bd0` | feat(05-06): MIG-02 v1 env-var startup scan in cli.py (CONTEXT D4) |

## Self-Check: PASSED

- `src/aws_eks_helm_deploy/actions/upgrade.py` — exists, contains `_check_bitbucket_values_yaml`, `BITBUCKET_VALUES_REGEX`, `meta.bitbucket_values_detected_without_opt_in`
- `src/aws_eks_helm_deploy/cli.py` — exists, contains `_warn_on_v1_env_vars`, `V1_DEPRECATED_ENV_VARS`, `mig.v1_env_var_detected`
- Commits `ae1172d` and `a714bd0` verified in git log
- 100% line+branch coverage on all 32 source files
