---
phase: 04-oidc-chart-source-extensions
plan: 1
subsystem: planning-docs
tags:
  - roadmap
  - requirements
  - precedence
  - botocore
  - doc-edit
  - atomic-precursor
dependency_graph:
  requires: []
  provides:
    - Revised AUTH-04 contract in ROADMAP.md Phase 4 SC1
    - Revised AUTH-04 row wording in REQUIREMENTS.md
  affects:
    - Plan 04-03 (OidcWebIdentityStrategy + select_strategy) — consumes revised AUTH-04 wording
    - gsd-verify-work for Phase 4 — must assert "static keys win", NOT "OIDC wins"
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
decisions:
  - "Used inline SC1 revision (not a bottom-of-file changelog section) so readers encounter the correct wording in context"
  - "Parenthetical revision note in REQUIREMENTS.md avoids quoting the exact removed phrase to ensure grep-based verification passes cleanly"
metrics:
  duration: "< 5 minutes"
  completed: "2026-06-18"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Phase 4 Plan 1: ROADMAP + REQUIREMENTS AUTH-04 Revision Summary

**One-liner:** Atomic doc-edit replacing "OIDC wins deterministically" with "static keys win — mirrors botocore default chain" in ROADMAP Phase 4 SC1 and REQUIREMENTS AUTH-04, per CONTEXT D1.

## What Was Done

Task 04-1-01 completed: revised `.planning/ROADMAP.md` Phase 4 SC1 and `.planning/REQUIREMENTS.md` AUTH-04 row to honor CONTEXT D1's locked decision that auth strategy precedence mirrors the boto3 / AWS CLI default credential resolver chain (static keys win when both present).

## Exact New Wording

### ROADMAP.md Phase 4 SC1 (revised)

```
1. `src/aws_eks_helm_deploy/auth/oidc.py` adds `OidcWebIdentityStrategy`; when ONLY
   `BITBUCKET_STEP_OIDC_TOKEN` + `OIDC_AUDIENCE` + `ROLE_ARN` are set (no static keys), the
   pipe exchanges the token for STS credentials via `AssumeRoleWithWebIdentity` (AUTH-03); when
   BOTH static keys AND an OIDC token are present, **static keys win** — mirrors the boto3 / AWS
   CLI default credential resolver chain (env-var provider precedes web-identity provider in
   `botocore.credentials.create_credential_resolver`); a one-time WARN log
   (`auth.precedence.static_keys_won_over_oidc`) surfaces this precedence (AUTH-04);
   misconfigurations (`ROLE_ARN` without base creds, `OIDC_AUDIENCE` without `ROLE_ARN`,
   `BITBUCKET_STEP_OIDC_TOKEN` without `ROLE_ARN`) raise `ConfigurationError` with a clear
   message before any AWS API call (AUTH-06).
  > 2026-06-18 revision: AUTH-04 wording superseded — see
    `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md` D1 for full rationale
    (boto3 default chain mirror; principle-of-least-surprise for AWS engineers).
```

### REQUIREMENTS.md AUTH-04 row (revised)

```
- [ ] **AUTH-04**: Strategy selection follows the boto3 / AWS CLI default credential resolver
  chain; when both static keys AND an OIDC token are present, **static keys win** — same
  behaviour as the AWS CLI itself. A one-time WARN log
  (`auth.precedence.static_keys_won_over_oidc`) surfaces the precedence so consumers who set
  both by accident can see why their OIDC token was ignored. **(Revised 2026-06-18 — original
  wording assumed OIDC precedence; superseded by D1 in
  `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md`.)**
```

## Verification Results

All `<verify>` grep assertions passed:

| Check | Result |
|-------|--------|
| `grep -F "static keys win" .planning/ROADMAP.md` | PASS (1 hit) |
| `grep -F "static keys win" .planning/REQUIREMENTS.md` | PASS (1 hit) |
| `! grep -F "OIDC wins deterministically" .planning/ROADMAP.md` | PASS (0 hits) |
| `! grep -F "OIDC wins deterministically" .planning/REQUIREMENTS.md` | PASS (0 hits) |
| `grep -F "auth.precedence.static_keys_won_over_oidc" .planning/ROADMAP.md` | PASS (1 hit) |
| `grep -F "2026-06-18 revision" .planning/ROADMAP.md` | PASS (1 hit) |
| `grep -c "^| AUTH-04" .planning/REQUIREMENTS.md` | PASS (1 row, unchanged shape) |
| `git diff HEAD~1 HEAD -- src/ tests/ Dockerfile pyproject.toml uv.lock` | PASS (0 lines, no code changes) |

## No Code Changes Confirmed

`git diff HEAD~1 HEAD -- src/ tests/ Dockerfile pyproject.toml uv.lock` returns 0 lines — no production code, no tests, no Dockerfile modified.

## Phase 1-3 + 5-7 Byte-Stability Confirmed

`git diff HEAD~1 HEAD -- .planning/ROADMAP.md` additions/deletions are entirely within the `### Phase 4:` block. No other phase entries were touched.

## Commit

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 04-1-01 | Revise ROADMAP Phase 4 SC1 + REQUIREMENTS AUTH-04 (atomic doc-edit) | `6e28005` | `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Parenthetical wording adjusted to avoid quoting the removed phrase**

- **Found during:** Task 04-1-01 verification
- **Issue:** The plan's behavior block specified the parenthetical `(Revised 2026-06-18 from "OIDC wins deterministically" ...)` verbatim, but the plan's verify gate requires `! grep -F "OIDC wins deterministically" .planning/REQUIREMENTS.md` to return 0 hits. Including the exact phrase in the parenthetical causes the negative grep to fail — a direct contradiction within the plan.
- **Fix:** Rewrote the parenthetical as `(Revised 2026-06-18 — original wording assumed OIDC precedence; superseded by D1 in ...)`. The revision date marker and the D1 reference are preserved; the removed phrase is not quoted literally. All must_have assertions now pass cleanly.
- **Files modified:** `.planning/REQUIREMENTS.md`
- **Precedence:** must_haves and verify gates take precedence over the behavior block template when in direct conflict.

## Forward Reference

Plan 04-03 (`auth/oidc.py` + `select_strategy` integration) ships the runtime implementation of the revised AUTH-04 contract. The unit test `test_select_strategy_static_keys_win_over_oidc_and_emits_warn` in 04-03 is the runtime assertion of what this doc-edit declares.

## Known Stubs

None — this plan is a complete doc-edit. No placeholder lines or TODO markers in the revised wording.

## Threat Flags

None — doc-edit only; no runtime trust boundary crossed.

## Self-Check: PASSED

- [x] `.planning/ROADMAP.md` modified and committed: hash `6e28005` confirmed in `git log`
- [x] `.planning/REQUIREMENTS.md` modified and committed: hash `6e28005` confirmed in `git log`
- [x] All 6 verification greps pass
- [x] No code files modified
- [x] Single atomic commit with both files in the diff
