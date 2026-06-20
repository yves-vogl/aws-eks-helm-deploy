---
phase: 05-log-masking-diff-rollback-metadata-flip
plan: "01"
subsystem: settings
tags: [settings, pydantic, phase-5, META-02, PIPE-03, PIPE-04, PIPE-05]
dependency_graph:
  requires: []
  provides:
    - "Settings.action: Literal[upgrade, diff, rollback]"
    - "Settings.inject_bitbucket_metadata: bool | None = None"
    - "Settings.post_diff_as_comment: bool = False"
    - "Settings.bitbucket_token: SecretStr | None = None"
    - "Settings.safe_upgrade: bool = False"
    - "Settings.revision: int | None = None"
  affects:
    - src/aws_eks_helm_deploy/cli.py (05-03 diff/rollback dispatch)
    - src/aws_eks_helm_deploy/actions/upgrade.py (05-05/06 safe_upgrade + META-03 wiring)
    - src/aws_eks_helm_deploy/actions/diff.py (05-03)
    - src/aws_eks_helm_deploy/actions/rollback.py (05-05)
    - src/aws_eks_helm_deploy/bitbucket/pr_comment.py (05-04)
tech_stack:
  added: []
  patterns:
    - "bool | None tri-state for D4 META-03 detector sentinel (None=unset, True=inject, False=skip)"
    - "SecretStr for BITBUCKET_TOKEN — same R4/T-05-02 pattern as REGISTRY_PASSWORD (Phase 4)"
    - "ge=0 constraint for REVISION — same as history_max (Phase 4)"
key_files:
  created: []
  modified:
    - src/aws_eks_helm_deploy/settings.py
    - tests/unit/test_settings.py
decisions:
  - "inject_bitbucket_metadata typed bool|None=None (META-02/D4): None is the D4 sentinel enabling META-03 one-time WARN when values.yaml references 'bitbucket:' without explicit opt-in; False = explicit silence; True = inject"
  - "bitbucket_token is SecretStr (not str): prevents repr(settings) from leaking the token (T-05-02/R4 carry-forward from REGISTRY_PASSWORD pattern in Phase 4)"
  - "revision uses ge=0 constraint mirroring history_max: non-negative invariant enforced at the settings boundary, not inside action logic"
  - "Literal widening upgrade→upgrade/diff/rollback: cli.py dispatch for new actions lands in 05-03/05-05; this plan only widens the type gate"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-20"
---

# Phase 05 Plan 01: Settings Additions Summary

**One-liner:** 5 new/changed Settings fields (action Literal widened to diff/rollback, inject_bitbucket_metadata tri-state flip, post_diff_as_comment, bitbucket_token as SecretStr, safe_upgrade, revision) with 13 new tests reaching 100% branch coverage.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Widen Settings.action + add 4 Phase 5 fields | 3a30237 | settings.py |
| 2 | Extend test_settings.py (11 new tests + 2 updates) | 3a30237 | test_settings.py |

## Field Signatures Added / Changed

| Field | Type | Default | Env Alias | Change |
|-------|------|---------|-----------|--------|
| `action` | `Literal["upgrade", "diff", "rollback"]` | `"upgrade"` | `ACTION` | Widened from `Literal["upgrade"]` |
| `inject_bitbucket_metadata` | `bool \| None` | `None` | `INJECT_BITBUCKET_METADATA` | Changed from `bool = False` (META-02/D4) |
| `post_diff_as_comment` | `bool` | `False` | `POST_DIFF_AS_COMMENT` | New (PIPE-03) |
| `bitbucket_token` | `SecretStr \| None` | `None` | `BITBUCKET_TOKEN` | New (PIPE-03, SecretStr for T-05-02) |
| `safe_upgrade` | `bool` | `False` | `SAFE_UPGRADE` | New (PIPE-05) |
| `revision` | `int \| None` | `None` | `REVISION` | New, ge=0 (PIPE-04) |

## Test Count

- **Before:** 45 test functions
- **After:** 58 test functions
- **New tests added:** 13 (2 action-widening cases + 1 bogus-action update; 3 inject_bitbucket_metadata tri-state; 7 Phase 5 field assertions including the R4 anti-leak gate)

## Settings.py Line Count Delta

- **Before:** ~163 lines
- **After:** 180 lines
- **Delta:** +17 lines (new fields + updated docstring)

## Phase 1–4 Fields Untouched

All existing Phase 1–4 fields (aws_*, oidc_*, cluster_*, chart_*, registry_*, cosign, log_format, debug, history_max, dry_run, set_values, values_files, wait, timeout, namespace, create_namespace, session_name) are unchanged. The existing `test_settings_defaults` assertion was updated only for `inject_bitbucket_metadata` (now asserts `is None` instead of `is False` — the D4 breaking change).

## Quality Gates

| Gate | Result |
|------|--------|
| `uv run pytest tests/unit/test_settings.py -x --no-cov` | PASS (58 tests) |
| `uv run pytest tests/unit -q` (full suite, 100% coverage) | PASS (356 tests, 100%) |
| `uv run mypy --strict src/aws_eks_helm_deploy/settings.py` | PASS (0 errors) |
| `uv run ruff check src/ tests/` | PASS |
| `grep -F 'inject_bitbucket_metadata: bool \| None'` | 1 hit |
| `grep -E 'inject_bitbucket_metadata: bool ='` | 0 hits (old shape gone) |
| `grep -F 'Literal["upgrade", "diff", "rollback"]'` | 1 hit |
| `grep -F 'bitbucket_token: SecretStr \| None'` | 1 hit |
| `grep -F '"MY-SECRET-TOKEN" not in repr'` | 1 hit (T-05-02 regression gate) |
| Pre-commit hooks (ruff, mypy, pytest unit, secret-detect) | ALL PASSED |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — no new trust boundaries introduced. `bitbucket_token` is typed as `SecretStr` per T-05-02, which is the plan's explicit mitigation.

## Self-Check: PASSED

- `src/aws_eks_helm_deploy/settings.py` exists and contains all 6 new/changed field declarations.
- `tests/unit/test_settings.py` exists with 58 test functions.
- Commit `3a30237` confirmed in git log.
- `repr(Settings(BITBUCKET_TOKEN="abc"))` does not contain `"abc"` — verified by `test_bitbucket_token_repr_does_not_leak_plaintext`.
