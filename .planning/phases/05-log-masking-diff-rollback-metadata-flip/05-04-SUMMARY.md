---
phase: 05-log-masking-diff-rollback-metadata-flip
plan: "04"
subsystem: bitbucket
tags: [pipe-03, pr-comment, idempotency, token-scrub, stdlib-urllib, diff-action]
dependency_graph:
  requires: ["05-01", "05-02", "05-03"]
  provides: ["PIPE-03"]
  affects: ["actions/diff.py", "bitbucket/pr_comment.py"]
tech_stack:
  added:
    - stdlib urllib.request (HTTP client — no new package dep)
    - bitbucket package (new: src/aws_eks_helm_deploy/bitbucket/)
  patterns:
    - GET-then-POST-or-PUT idempotency via HTML comment marker
    - SecretStr unwrap at single call site (R13 pattern, mirrors Phase 4 registry_password)
    - _sanitize_response_body as choke-point before every log.warning body= arg
    - Defensive BLE001 exception guard in DiffAction (best-effort observability)
key_files:
  created:
    - src/aws_eks_helm_deploy/bitbucket/__init__.py
    - src/aws_eks_helm_deploy/bitbucket/pr_comment.py
    - tests/unit/test_pr_comment.py
  modified:
    - src/aws_eks_helm_deploy/actions/diff.py
    - tests/unit/test_diff_action.py
decisions:
  - "stdlib urllib.request chosen over bitbucket-pipes-toolkit (CONTRADICTION 1 from 05-RESEARCH: toolkit has no PR-comment wrapper and hard-fails on 4xx)"
  - "Single SecretStr unwrap site in DiffAction._maybe_post_pr_comment (R13 carry-forward)"
  - "run() body extracted _maybe_post_pr_comment helper to stay within LOC budget"
  - "pagelen=100 first-page only; paginated next-URL iteration deferred to v2.1"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-20T08:44:17Z"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 21
  files_created: 3
  files_modified: 2
---

# Phase 05 Plan 04: PR-Comment Poster (PIPE-03) Summary

One-liner: Idempotent Bitbucket PR-comment posting of helm diffs via stdlib urllib.request — GET/POST/PUT marker algorithm with _sanitize_response_body token-scrub (T-05-02 mitigation), wired into DiffAction behind 5-gate conditional.

## What Was Built

### New Module Inventory

| File | LOC | Purpose |
|---|---|---|
| `src/aws_eks_helm_deploy/bitbucket/__init__.py` | 7 | Package marker, re-exports `post_diff_comment` |
| `src/aws_eks_helm_deploy/bitbucket/pr_comment.py` | 219 | Core implementation: `_api_request`, `_sanitize_response_body`, `post_diff_comment` |
| `tests/unit/test_pr_comment.py` | ~290 | 14 unit tests, 100% line+branch coverage on `pr_comment.py` |

### Extended Files

| File | Changes |
|---|---|
| `src/aws_eks_helm_deploy/actions/diff.py` | Added `os` + `post_diff_comment` imports; extracted `_maybe_post_pr_comment` helper; wired call after `helm diff` |
| `tests/unit/test_diff_action.py` | Added 7 PR-comment integration tests + `structlog`, `SecretStr` imports |

### Algorithm (CONTEXT D3)

1. GET `/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments?pagelen=100`
2. Iterate `values[]` — search `content.raw` for marker `<!-- aws-eks-helm-deploy:diff -->`
3. If marker found → PUT `.../comments/{comment_id}` (idempotent update)
4. If not found → POST `.../comments` (new comment)
5. All 4xx/5xx → `logger.warning` with `_sanitize_response_body(body, token)` → return (no raise)

### 5-Gate Conditional in DiffAction

```
post_diff_as_comment=True
AND bitbucket_token is not None
AND BITBUCKET_PR_ID env var is set
AND BITBUCKET_WORKSPACE env var is set
AND BITBUCKET_REPO_SLUG env var is set
```

When gates unmet: `bitbucket.pr_comment.skipped_gate_unmet` INFO log with individual gate booleans.
When `post_diff_comment` raises unexpectedly: `bitbucket.pr_comment.unexpected_exception` WARN, DiffAction returns 0.

## Test Coverage

### test_pr_comment.py (14 tests)

| Test | Behavior |
|---|---|
| `test_post_when_no_existing_comment` | GET empty → POST issued |
| `test_put_when_marker_comment_found` | GET with marker comment → PUT issued |
| `test_put_body_contains_new_diff` | PUT body contains new diff, not old |
| `test_post_when_existing_comment_has_no_marker` | Comment without marker → POST (branch coverage) |
| `test_401_get_token_is_scrubbed_from_warn_log` | **T-05-02 gate**: token absent from WARN log |
| `test_401_get_authorization_header_stripped_from_warn_log` | Auth header scrubbed from WARN body |
| `test_500_on_post_emits_warn_and_returns` | 500 POST error → WARN, no raise |
| `test_urlopen_urleerror_emits_warn_and_returns` | Network failure → WARN status=0, no raise |
| `test_malformed_json_in_get_response_emits_warn_and_returns` | 2xx non-JSON → WARN phase=get_parse |
| `test_sanitize_response_body_scrubs_token_and_auth_header` | Direct unit test: token + header scrub |
| `test_sanitize_response_body_empty_body_returns_empty` | Empty body edge case |
| `test_sanitize_response_body_empty_token_scrubs_auth_header_only` | Empty token: only header scrub |
| `test_post_body_contains_marker` | MARKER appears on line 1 of POST body |
| `test_post_body_contains_diff_text` | diff_text embedded in POST body |

### test_diff_action.py (7 new tests)

| Test | Gate verified |
|---|---|
| `test_pr_comment_post_called_when_all_gates_met` | All 5 gates met → called once with correct args |
| `test_pr_comment_called_with_unwrapped_secret_str` | token arg is plain str (not SecretStr) |
| `test_pr_comment_not_called_when_post_diff_as_comment_false` | Feature disabled → silent no-op |
| `test_pr_comment_not_called_when_pr_id_missing` | BITBUCKET_PR_ID unset → INFO log, no call |
| `test_pr_comment_not_called_when_bitbucket_token_missing` | bitbucket_token=None → INFO log, no call |
| `test_pr_comment_not_called_when_workspace_missing` | BITBUCKET_WORKSPACE unset → INFO log, no call |
| `test_diff_action_returns_zero_even_if_post_diff_comment_raises` | Defensive exception guard → WARN, DiffAction returns 0 |

## Invariants Verified

| Invariant | Status |
|---|---|
| D6: `grep '^import subprocess' src/aws_eks_helm_deploy/ \| wc -l` = 2 | PASS |
| D3: no `requests` import in `bitbucket/` | PASS |
| D3: no `bitbucket_pipes_toolkit` import | PASS |
| MARKER constant present exactly once | PASS |
| `BITBUCKET_TOKEN` literal: 0 occurrences outside docstrings | PASS (1 docstring reference, permitted) |
| `grep '_redactor(' src/helm/client.py` >= 10 | PASS (10 hits) |
| `post_diff_comment` wired in `actions/diff.py` | PASS |
| `s.bitbucket_token.get_secret_value()` called exactly once | PASS (single unwrap in `_maybe_post_pr_comment`) |

## Quality Gates

| Gate | Result |
|---|---|
| `uv run pytest tests/unit -q --no-cov` | PASS (421 tests) |
| `uv run pytest tests/unit --cov=... --cov-fail-under=100` | PASS (100% line+branch) |
| `uv run mypy --strict src/aws_eks_helm_deploy/bitbucket/ src/aws_eks_helm_deploy/actions/diff.py` | PASS |
| `uv run ruff check src/aws_eks_helm_deploy/bitbucket/ tests/unit/test_pr_comment.py` | PASS |

## Deviations from Plan

**1. [Rule 1 - Bug] ruff S310 noqa placement**
- **Found during:** Task 1 verification
- **Issue:** S310 (audit URL open) flagged `urllib.request.Request(...)` AND `urllib.request.urlopen(...)` — both lines need `# noqa: S310`. Initial placement was only on the `urlopen` line.
- **Fix:** Added `# noqa: S310` to both lines with explanatory comments (static BITBUCKET_API_BASE base + caller path segments, no http:// possible).
- **Files modified:** `src/aws_eks_helm_deploy/bitbucket/pr_comment.py`
- **Commit:** part of 0dd5d6d

**2. [Rule 1 - Bug] Test assertion for Authorization header scrub**
- **Found during:** Task 2 test run
- **Issue:** `assert "Authorization:" not in logged_body` failed because the replacement sentinel `"[Authorization: <redacted>]"` itself contains the substring `"Authorization:"`. Tests 5, 9, 11 all needed to assert `"Authorization: Bearer"` not in result (the original untransformed header line).
- **Fix:** Changed assertions to check for `"Authorization: Bearer"` absence (the specific original value being scrubbed), keeping positive assertion for `"[Authorization: <redacted>]"`.
- **Files modified:** `tests/unit/test_pr_comment.py`
- **Commit:** part of 779e8ca

**3. [Rule 1 - Bug] Missing branch coverage: comment-without-marker path**
- **Found during:** Task 2 coverage check (99% → 100%)
- **Issue:** Branch `183->181` (for-loop iterating a comment that does NOT contain the marker) was not covered by the 11 planned tests.
- **Fix:** Added `test_post_when_existing_comment_has_no_marker` — GET response has one comment without the marker, asserts POST is still issued.
- **Files modified:** `tests/unit/test_pr_comment.py`
- **Commit:** part of 779e8ca

**4. [Rule 2 - Missing test] T-05-02 test added for PUT error path (POST 500)**
- **Found during:** Task 2 planning — plan specified `test_500_on_post_emits_warn_and_returns` as test 6.
- **Action:** Included explicitly. The 500 POST test covers the error path in `post_diff_comment` where `existing_id is None` → POST → 500 → sanitize body before logging. Confirms _sanitize_response_body is called on POST/PUT error paths, not just GET.

**5. [Rule 2 - Process] ruff-format pre-commit reformatted files**
- **Found during:** Tasks 1 and 3 commits
- **Action:** Re-staged reformatted files, recommitted. Both commits landed cleanly.

## Known Stubs

None. `post_diff_comment` makes real HTTP calls (mocked in tests). All wiring paths are fully connected.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers (T-05-02 handled by `_sanitize_response_body`; T-05-04 handled structurally via D6 subprocess invariant).

## Commits

| Hash | Message |
|---|---|
| `0dd5d6d` | feat(05-04): create bitbucket/ package with pr_comment.py |
| `779e8ca` | test(05-04): add test_pr_comment.py — 14 tests, 100% branch coverage |
| `2ffdc8d` | feat(05-04): wire post_diff_comment into DiffAction |

## Self-Check: PASSED

- `src/aws_eks_helm_deploy/bitbucket/__init__.py` — FOUND
- `src/aws_eks_helm_deploy/bitbucket/pr_comment.py` — FOUND
- `tests/unit/test_pr_comment.py` — FOUND
- Commit `0dd5d6d` — FOUND
- Commit `779e8ca` — FOUND
- Commit `2ffdc8d` — FOUND
- 421 tests pass, 100% coverage — VERIFIED
- mypy --strict 0 errors — VERIFIED
- D6 subprocess count = 2 — VERIFIED
