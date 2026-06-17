---
phase: 02-aws-layer-auth-foundation
plan: 2
subsystem: auth-contracts
tags:
  - auth
  - protocol
  - dataclass
  - aws-credentials
  - typing
dependency_graph:
  requires:
    - 01-toolchain-spine (logging.py CREDENTIAL_BLOCKLIST, test infra, pyproject.toml toolchain)
    - 02-01 (sibling — no dependency; contracts are session-agnostic)
  provides:
    - aws_eks_helm_deploy.auth.base.AuthStrategy (Protocol, @runtime_checkable)
    - aws_eks_helm_deploy.auth.base.AwsCredentials (frozen dataclass)
    - AwsCredentials.to_boto3_kwargs() -> dict[str, str]
    - AwsCredentials.__repr__() -> str (masked)
  affects:
    - 02-03 (StaticKeysStrategy + AssumeRoleStrategy satisfy AuthStrategy structurally)
    - 02-04 (select_strategy fills auth/__init__.py; cli wires creds.to_boto3_kwargs())
tech_stack:
  added: []
  patterns:
    - typing.Protocol with @runtime_checkable for structural subtyping (no inheritance required)
    - dataclasses.dataclass(frozen=True) for immutable value objects with __hash__
    - custom __repr__ masking sensitive fields (STRIDE T-02-02-01)
key_files:
  created:
    - src/aws_eks_helm_deploy/auth/__init__.py
    - src/aws_eks_helm_deploy/auth/base.py
    - tests/unit/test_auth_base.py
  modified: []
decisions:
  - "AwsCredentials.__repr__ omits expiration (informational only; revealing datetime leaks AWS session topology)"
  - "session_token presence shown as '<redacted>' marker in repr — operators need to know if creds are temporary vs long-term"
  - "__all__ sorted alphabetically: AuthStrategy before AwsCredentials (ruff RUF022)"
  - "Combined test+implementation commit required by pre-commit pytest-quick gate (always_run:true blocks RED-only commits)"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-17"
  tasks_completed: 1
  tasks_total: 1
  files_created: 3
  files_modified: 0
  commits: 1
---

# Phase 02 Plan 02: AuthStrategy Protocol + AwsCredentials Dataclass Summary

**One-liner:** `@runtime_checkable AuthStrategy` Protocol + `frozen=True AwsCredentials` dataclass with masked `__repr__` and `to_boto3_kwargs()`, delivering the typed credential contracts for Plans 02-03 and 02-04.

---

## What Was Built

### New Files

**`src/aws_eks_helm_deploy/auth/__init__.py`** (3 lines)
Empty subpackage marker: module docstring + `from __future__ import annotations`. `select_strategy()` will be added by Plan 02-04 — this plan deliberately leaves `__init__.py` blank as documented in `<known_stubs>`.

**`src/aws_eks_helm_deploy/auth/base.py`** (96 lines)
- Module docstring with AUTH-01 traceability header and STRIDE security note
- `from __future__ import annotations` + imports: `dataclasses`, `datetime`, `typing.Protocol`, `typing.runtime_checkable`
- `__all__: list[str] = ["AuthStrategy", "AwsCredentials"]` (sorted per ruff RUF022)
- `AwsCredentials` — `@dataclasses.dataclass(frozen=True)` with four fields in order:
  - `access_key_id: str` (required)
  - `secret_access_key: str` (required)
  - `session_token: str | None = None`
  - `expiration: datetime | None = None`
  - `__repr__(self) -> str` — shows `...{last4}` or `...****` for access_key_id, `<redacted>` for secret, `session_token=<redacted>` marker when set, expiration omitted
  - `to_boto3_kwargs(self) -> dict[str, str]` — includes `aws_session_token` only when set; expiration never included
- `AuthStrategy` — `@runtime_checkable` Protocol with `get_credentials(self) -> AwsCredentials: ...`

**`tests/unit/test_auth_base.py`** (205 lines)
19 unit tests under `@pytest.mark.unit` covering all behavior bullets. Module-level constants (`_ACCESS_KEY`, `_SECRET_KEY`, `_SESSION_TOKEN`, `_DUMMY_SECRET`) with `# noqa: S105` follow the project pattern established in `test_eks_token.py`.

---

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check src tests` | PASS (0 errors) |
| `ruff format --check src tests` | PASS (0 files would reformat) |
| `mypy --strict src` | PASS (11 source files, 0 issues) |
| `pytest -q` (full unit tier, 100% gate) | PASS (84 passed, 100% line+branch) |
| Manual: `repr` masking | PASS — "supersecret" not in repr; `<redacted>` present |
| Manual: short key branch | PASS — `len("AKI") < 4` → `****` in repr |
| Manual: `to_boto3_kwargs()` blocklist | PASS — `ValueError: Credential leak: 'aws_access_key_id' is blocklisted` |
| Manual: `frozen=True` | PASS — `FrozenInstanceError` on mutation |

### Coverage on auth/base.py

```
Name                                    Stmts   Miss Branch BrPart  Cover
---------------------------------------------------------------------------
src/aws_eks_helm_deploy/auth/base.py      25      0      4      0   100%
```

**100% line + 100% branch.** All 4 branches exercised:
1. `__repr__` len >= 4 branch (access key shows last 4)
2. `__repr__` len < 4 branch (`****`)
3. `to_boto3_kwargs()` without session_token (no `aws_session_token` key)
4. `to_boto3_kwargs()` with session_token (`aws_session_token` key present)

### Coverage confirmation

Final full suite output:
```
84 passed, 8 deselected in 1.16s
Required test coverage of 100% reached. Total coverage: 100.00%
```

### Tool versions at execution time

| Tool | Version |
|------|---------|
| mypy | 2.1.0 (compiled: yes) |
| ruff | 0.15.17 |
| pytest | 9.1.x |
| Python | 3.13.14 |

---

## Deviations from Plan

### Deviation 1 (Plan-Documented): expiration omitted from __repr__

As documented in `02-02-PLAN.md <deviations> Deviation 1`. No code change needed — implemented as specified.

### Deviation 2 (Plan-Documented): session_token=<redacted> marker shown when set

As documented in `02-02-PLAN.md <deviations> Deviation 2`. Implemented as specified.

### Deviation 3 (Auto-fix, Rule 1): __all__ sort order

**Found during:** ruff check pre-commit gate
**Issue:** `["AwsCredentials", "AuthStrategy"]` violated ruff RUF022 (isort-style sort requires `AuthStrategy` before `AwsCredentials`)
**Fix:** Changed to `["AuthStrategy", "AwsCredentials"]`
**Impact:** Zero behavior change — ordering in `__all__` has no semantic effect

### Deviation 4 (Process): RED commit blocked by pre-commit pytest-quick gate

**Found during:** First commit attempt with test-only files
**Issue:** The pre-commit hook `pytest-quick` runs `uv run pytest -q -m unit --no-cov` with `always_run: true`. A test-only RED commit causes an `ImportError` on collection — the hook exits 1 and blocks the commit.
**Fix:** Combined tests + implementation into a single GREEN commit. RED phase was manually verified (`ModuleNotFoundError: No module named 'aws_eks_helm_deploy.auth.base'`) before writing implementation.
**Impact:** TDD spirit preserved (RED verified manually); git history has 1 commit instead of 2 (test + impl separate). This matches the pre-commit gate's behavior.

---

## Contract Verification

### bind_safe_context(**creds.to_boto3_kwargs()) raises ValueError

CONFIRMED. Test `test_aws_credentials_to_boto3_kwargs_collides_with_blocklist` passes:
```
ValueError: Credential leak: 'aws_access_key_id' is blocklisted
```
The CREDENTIAL_BLOCKLIST in `logging.py` contains `aws_access_key_id`, `aws_secret_access_key`, and `aws_session_token` — all three keys that `to_boto3_kwargs()` may produce. This is the intended behavior enforcing OBS-02.

### len(access_key_id) < 4 branch exercised

YES — `test_aws_credentials_repr_short_access_key` uses `AwsCredentials("AKI", ...)` (len=3 < 4), asserting `"****" in repr(creds)` and `"AKI" not in repr(creds)`. Branch coverage confirms this path is hit.

### auth/__init__.py is empty (Plan 02-04 will fill it)

CONFIRMED. File contains exactly:
```python
"""Auth subpackage — AuthStrategy Protocol + concrete strategy implementations."""

from __future__ import annotations
```
No re-exports, no `select_strategy`, no `__all__`. Plan 02-04 adds `select_strategy(settings: Settings) -> AuthStrategy`.

---

## Known Stubs

- `src/aws_eks_helm_deploy/auth/__init__.py` is intentionally empty — this is the correct shape for Plan 02-02 scope. Plan 02-04 adds `select_strategy()`. Not a behavior stub.

---

## Threat Flags

No new security surface introduced beyond the plan's documented threat model. The `auth/base.py` module introduces no network endpoints, no auth paths, no file access patterns, and no external dependencies (stdlib only: `dataclasses`, `datetime`, `typing`).

T-02-02-SC (supply-chain): CONFIRMED — zero external imports in `base.py`.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `src/aws_eks_helm_deploy/auth/__init__.py` exists | FOUND |
| `src/aws_eks_helm_deploy/auth/base.py` exists | FOUND |
| `tests/unit/test_auth_base.py` exists | FOUND |
| Commit `1b856fb` (Task 02-2-01) exists | FOUND |
| `AuthStrategy` importable | OK |
| `AwsCredentials("AKIA", "s").to_boto3_kwargs()` returns dict | OK |
| `repr` masking verified | OK |
| 100% coverage on auth/base.py | CONFIRMED |
