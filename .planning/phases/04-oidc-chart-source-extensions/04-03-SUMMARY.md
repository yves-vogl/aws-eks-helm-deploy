---
phase: 04-oidc-chart-source-extensions
plan: 3
subsystem: auth
tags:
  - oidc
  - auth-strategy
  - select-strategy
  - warn-log
  - precedence
  - auth-06
  - botocore-chain
dependency_graph:
  requires:
    - 04-01  # REQUIREMENTS revision (AUTH-04 revised wording)
    - 04-02  # Settings.oidc_audience field
  provides:
    - OidcWebIdentityStrategy integrated into select_strategy composition root
    - AUTH-03 closed (strategy exists and is reachable via select_strategy)
    - AUTH-04 revised closed (static-keys-win precedence + WARN log)
    - AUTH-06 closed (misconfig errors for OIDC token without ROLE_ARN, without OIDC_AUDIENCE, ROLE_ARN without any base)
  affects:
    - src/aws_eks_helm_deploy/auth/__init__.py
    - tests/unit/test_auth_init_select_strategy.py
    - tests/unit/test_auth_select.py
tech_stack:
  added: []
  patterns:
    - structlog WARN log for precedence surfacing (auth.precedence.static_keys_won_over_oidc)
    - os.environ read for platform-supplied BITBUCKET_STEP_OIDC_TOKEN (documented deviation)
key_files:
  created:
    - tests/unit/test_auth_init_select_strategy.py
  modified:
    - src/aws_eks_helm_deploy/auth/__init__.py
    - tests/unit/test_auth_select.py
decisions:
  - "OIDC branch placed AFTER static-keys branch in select_strategy (R2 + botocore default chain order)"
  - "BITBUCKET_STEP_OIDC_TOKEN read from os.environ, not Settings (Deviation 1: token in Settings risks log leak)"
  - "WARN log fired when static keys win over OIDC token (AUTH-04 revised); no-op if only one credential type present"
  - "AUTH-06 error messages revised: ROLE_ARN-without-base message extended to mention OIDC as alternative"
  - "test_auth_select.py Phase 2 error-message assertion updated to match new AUTH-06 ROLE_ARN wording (Rule 1 fix)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-18"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 2
---

# Phase 04 Plan 03: select_strategy OIDC Integration Summary

**One-liner:** Integrated OidcWebIdentityStrategy into `select_strategy` with AUTH-04 static-keys-win precedence + structlog WARN log + AUTH-06 misconfig errors for all OIDC misconfiguration cases.

## What Shipped

### Task 2 (this commit — `0313cd0`)

**`src/aws_eks_helm_deploy/auth/__init__.py`** — extended `select_strategy` with:

1. Import of `OidcWebIdentityStrategy` from `auth.oidc`; `get_logger` from `aws_eks_helm_deploy.logging`; module-level `logger = get_logger(__name__)`.
2. `OidcWebIdentityStrategy` added to `__all__` (alphabetical order between `AwsCredentials` and `StaticKeysStrategy`).
3. Updated module docstring decision-tree pseudocode to reflect the full 4-branch tree.
4. `select_strategy` body replaced with 4-branch decision tree:
   - Branch 1 (static keys): unchanged Phase 2 logic + new WARN log `auth.precedence.static_keys_won_over_oidc` when `BITBUCKET_STEP_OIDC_TOKEN` is also present.
   - Branch 2 (OIDC): `BITBUCKET_STEP_OIDC_TOKEN` read from `os.environ`, validated (ROLE_ARN + OIDC_AUDIENCE required), then constructs `OidcWebIdentityStrategy` via `_derive_session_name` reuse.
   - Branch 3 (ROLE_ARN without base): updated error message to mention OIDC as alternative.
   - Branch 4 (no creds): updated error message to mention OIDC path.
5. Phase 4 TODO marker `# Phase 4: insert OIDC check here (OidcWebIdentityStrategy)` removed.
6. `select_strategy` docstring updated to enumerate all 5 decision outcomes.

**`tests/unit/test_auth_init_select_strategy.py`** (NEW, 11 tests):
- `test_select_strategy_returns_oidc_when_token_and_role_arn_and_audience_set` — AUTH-03 happy path
- `test_select_strategy_static_keys_win_over_oidc_and_emits_warn` — AUTH-04 precedence + WARN log
- `test_select_strategy_static_keys_without_oidc_token_does_not_emit_warn` — no-WARN path
- `test_select_strategy_oidc_token_without_role_arn_raises_config_error` — AUTH-06 misconfig
- `test_select_strategy_token_and_role_arn_without_audience_raises_config_error` — AUTH-06 misconfig
- `test_select_strategy_role_arn_without_creds_error_message_mentions_oidc` — AUTH-06 extended message
- `test_select_strategy_no_credentials_at_all_raises_config_error` — no-creds branch
- `test_select_strategy_oidc_strategy_receives_correct_session_name` — session name derivation
- `test_select_strategy_oidc_strategy_receives_correct_region_and_audience` — strategy attributes
- `test_select_strategy_oidc_strategy_oidc_token_matches_env_var` — token passthrough
- `test_select_strategy_phase2_static_keys_plus_role_arn_regression` — Phase 2 regression guard

**`tests/unit/test_auth_select.py`** (MODIFIED — 1 assertion updated):
- `test_select_role_arn_without_base_raises_configuration_error`: assertion changed from `"Phase 4" in msg` (old forward-pointer text) to `"ROLE_ARN requires" in msg` and `"BITBUCKET_STEP_OIDC_TOKEN" in msg` (new AUTH-06 message wording).

## Wave-Race Note (Task 1 artifacts in a different commit)

Due to a wave-2 parallel execution race, Task 1's artifacts (`auth/oidc.py` + `tests/unit/test_auth_oidc.py`) landed in commit `090a4de` (plan 04-06's commit) instead of an 04-03 commit. The implementation is correct and was verified via `git show 090a4de --stat`. History is left as-is (no rewrite). This SUMMARY covers only Task 2 (the integration), which lands in commit `0313cd0`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated Phase 2 error-message assertion in test_auth_select.py**
- **Found during:** Running full unit suite after implementing new select_strategy body.
- **Issue:** `test_select_role_arn_without_base_raises_configuration_error` asserted `"Phase 4" in str(exc_info.value)` — the old forward-pointer text. The Phase 4 plan explicitly replaces this with the AUTH-06 message mentioning OIDC as an alternative.
- **Fix:** Updated assertion to `"ROLE_ARN requires" in msg` and `"BITBUCKET_STEP_OIDC_TOKEN" in msg` — matches the new AUTH-06 message wording in the plan.
- **Files modified:** `tests/unit/test_auth_select.py`
- **Commit:** `0313cd0`

**2. [Rule 3 - Line-length] Shortened three docstring lines in test_auth_init_select_strategy.py**
- **Found during:** ruff check.
- **Issue:** Three single-line docstrings exceeded 100-char limit.
- **Fix:** Shortened docstring text in-place; no semantic change.
- **Files modified:** `tests/unit/test_auth_init_select_strategy.py`
- **Commit:** `0313cd0`

## Acceptance Gate Results

| Gate | Result |
|------|--------|
| `uv run pytest tests/unit/test_auth_init_select_strategy.py -x -q` | 11 passed |
| `uv run pytest -m unit -q` (full suite) | 310 passed, 100% coverage |
| `uv run mypy --strict src/aws_eks_helm_deploy/auth` | Success: no issues in 5 source files |
| `uv run ruff check src/.../auth tests/unit/test_auth_init_select_strategy.py` | All checks passed |
| `uv run ruff format --check ...` | 6 files already formatted |
| `grep -F 'auth.precedence.static_keys_won_over_oidc' auth/__init__.py` | 2 hits (docstring + code) |
| `grep -F 'Phase 4: insert OIDC check here' auth/__init__.py` | 0 hits (marker removed) |
| `grep -F 'OidcWebIdentityStrategy' auth/__init__.py` | 6+ hits (import, __all__, docstrings, body) |
| R2 structural: static-keys line (178) < OIDC branch line (200) | PASS |

## Known Stubs

None — all OIDC paths are wired end-to-end through `OidcWebIdentityStrategy.get_credentials()` and verified by `test_auth_oidc.py` under `@mock_aws`.

## Threat Flags

None — no new network endpoints or auth paths beyond those documented in the plan's threat model (T-04-03-01 through T-04-03-06). The WARN log carries no credential material (only `reason` + `hint` strings).

## Self-Check: PASSED

- `src/aws_eks_helm_deploy/auth/__init__.py` — exists and modified
- `tests/unit/test_auth_init_select_strategy.py` — exists (created)
- `tests/unit/test_auth_select.py` — exists and modified
- Commit `0313cd0` — confirmed via `git log --oneline -1`
