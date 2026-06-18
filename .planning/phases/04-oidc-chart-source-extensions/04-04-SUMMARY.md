---
phase: 04-oidc-chart-source-extensions
plan: 4
subsystem: docs/auth
tags:
  - iam
  - trust-policy
  - bitbucket-oidc
  - documentation
  - stringlike-erratum
  - phase-4-draft
  - phase-7-polish
dependency_graph:
  requires: []
  provides:
    - docs/guides/oidc-setup.md (IAM trust-policy template with 5 placeholders)
    - tests/unit/test_iam_trust_policy_template.py (5 structural assertions)
  affects:
    - Phase 7 docs site (consumes docs/guides/oidc-setup.md for mkdocs-material rendering)
    - Plan 04-03 (OidcWebIdentityStrategy — the runtime side of the OIDC contract)
tech_stack:
  added: []
  patterns:
    - markdown + jsonc fenced block for copy-pasteable IAM trust policies
    - pathlib + re + json structural test pattern (no fixtures, no external services)
key_files:
  created:
    - docs/guides/oidc-setup.md
    - tests/unit/test_iam_trust_policy_template.py
  modified: []
decisions:
  - sub condition under StringLike (not StringEquals) — RESEARCH §2 erratum honored; wildcard * in {uuid}:{uuid}:* only works under StringLike
  - Terraform companion snippet deferred to Phase 7 (Deviation 1 — Phase 4 is heavy; snippet is additive)
  - IAM template JSON is FINAL (no Phase 7 changes); only surrounding prose is drafted
metrics:
  duration_minutes: ~5
  completed: "2026-06-18"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 4 Plan 4: Bitbucket OIDC IAM Trust-Policy Template Summary

**One-liner:** Drafted Bitbucket Pipelines OIDC IAM trust-policy template with `StringLike`-corrected `sub` condition and 5 structural unit-test assertions locking AUTH-05.

## Objective

Ship `docs/guides/oidc-setup.md` containing the copy-pasteable AWS IAM trust-policy JSON
template for Bitbucket Pipelines OIDC authentication, plus `tests/unit/test_iam_trust_policy_template.py`
with 5 assertions enforcing structural correctness. Zero production code changes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 04-4-01 | Ship oidc-setup.md + 5-assertion unit test | `54816e5` | `docs/guides/oidc-setup.md`, `tests/unit/test_iam_trust_policy_template.py` |

## Placeholder Verification (CONTEXT D4 Plan-Check obligation)

All 5 placeholders confirmed present verbatim in `docs/guides/oidc-setup.md`:

| Placeholder | Present |
|-------------|---------|
| `<ACCOUNT_ID>` | YES |
| `<WORKSPACE>` | YES |
| `<OIDC_AUDIENCE>` | YES |
| `<BITBUCKET_WORKSPACE_UUID>` | YES |
| `<BITBUCKET_REPO_UUID>` | YES |

## StringLike Erratum — CONTEXT D4 Honored

The `sub` condition lives under `StringLike` (NOT `StringEquals`). The CONTEXT D4 JSON sketch
used `StringEquals` for `sub` — this is the documented erratum. Per RESEARCH §2: Bitbucket emits
`sub` as `{<WORKSPACE_UUID>}:{<REPO_UUID>}:<step-UUID>` and IAM only treats `*` as a wildcard
under `StringLike`. The shipped template and its negative grep assertion in `<verify>` both enforce.

The `aud` condition correctly uses `StringEquals` with `<OIDC_AUDIENCE>` (exact-match — correct).

## Unit Test Results

```
6 passed in 0.01s
```

All 5 test functions + helper pass. Tests verified:

1. `test_template_has_all_required_placeholders` — all 5 placeholders present
2. `test_template_parses_as_valid_json` — jsonc block parses as valid JSON, Version=2012-10-17
3. `test_sub_condition_uses_string_like_not_string_equals` — StringLike erratum enforced
4. `test_aud_condition_uses_string_equals_with_placeholder` — aud under StringEquals
5. `test_action_is_assume_role_with_web_identity` — Action is sts:AssumeRoleWithWebIdentity
6. `test_federated_principal_matches_bitbucket_oidc_issuer_pattern` — canonical Bitbucket ARN pattern

## Linting

`ruff check`: all checks passed
`ruff format --check`: 1 file already formatted

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Three ruff E501 (line too long) violations in test file**
- **Found during:** initial ruff check after writing test file
- **Issue:** three assert message strings exceeded 100-char line limit
- **Fix:** split long assert strings across multiple lines using parenthesized string concatenation
- **Files modified:** `tests/unit/test_iam_trust_policy_template.py`
- **Commit:** `54816e5` (included in same commit — pre-commit hook caught and passed after fix)

### Documented Plan Deviations (expected, from plan frontmatter)

**Deviation 1:** Terraform companion snippet deferred to Phase 7 — `docs/guides/oidc-setup-terraform.md` not shipped. Explicitly marked in the doc's "Polish coming in Phase 7" section.

**Deviation 2:** `sub` under `StringLike` (honoring CONTEXT D4 erratum, overriding D4 JSON sketch). This is the correct behavior per RESEARCH §2.

**Deviation 3:** Prose intro marked as draft. IAM template JSON is final (no Phase 7 wording changes to the JSON block).

## Phase Path

- Exact file path: `docs/guides/oidc-setup.md` — matches CONTEXT D4 verbatim.
- Phase 7 cross-reference: mkdocs-material rendering + Terraform companion (`aws_iam_role` + `data.tls_certificate`) + migration notes for v1 → v2 OIDC setup.
- Plan 04-03 cross-reference: `OidcWebIdentityStrategy` in `auth/oidc.py` is the runtime side of the OIDC contract — the trust-policy template is the consumer-side IAM gate that STS validates the JWT `aud` claim against.

## Known Stubs

The prose sections ("Draft. Polished in Phase 7 alongside the mkdocs site." blockquote +
"Polish coming in Phase 7" section) are acknowledged drafts. The IAM template JSON itself is
FINAL — placeholders are stable contracts, no Phase 7 changes to the JSON block.

The Terraform companion (`docs/guides/oidc-setup-terraform.md`) is explicitly deferred to Phase 7
per Deviation 1. Not a functional gap for AUTH-05.

## Self-Check: PASSED

```
FOUND: docs/guides/oidc-setup.md
FOUND: tests/unit/test_iam_trust_policy_template.py
FOUND: 54816e5 (git log verified)
6 passed (pytest --no-cov)
ruff check: all checks passed
ruff format --check: 1 file already formatted
```
