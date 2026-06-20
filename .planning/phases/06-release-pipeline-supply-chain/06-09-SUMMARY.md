---
phase: 06-release-pipeline-supply-chain
plan: "09"
subsystem: supply-chain-hygiene
tags: [sec-04, sec-10, trivyignore, scorecard, d2-grammar, d3-grammar, ci-enforcement]
dependency_graph:
  requires: [06-01]
  provides: [trivyignore-d2-enforcement, scorecard-d3-enforcement, scorecard-badge]
  affects: [.github/workflows/ci.yml, .github/workflows/scorecard.yml]
tech_stack:
  added: []
  patterns:
    - "180-day CVE suppression cap (D2) enforced via Python parser + shell wrapper"
    - "180-day Scorecard exception review_date cap (D3) enforced via Python parser"
    - "importlib module loading for hyphenated script filenames (mirrors rescan-issue-creator pattern)"
key_files:
  created:
    - .trivyignore
    - .scorecard-exception.md
    - scripts/_trivyignore_parser.py
    - scripts/trivyignore-check.sh
    - scripts/scorecard-exception-check.py
    - scripts/__init__.py
    - tests/unit/test_trivyignore_check.py
    - tests/unit/test_scorecard_exception_check.py
  modified:
    - .github/workflows/ci.yml
    - .github/workflows/scorecard.yml
    - tests/structural/test_ci_yml_structure.py
    - README.md
    - CONTRIBUTING.md
    - pyproject.toml
decisions:
  - "D2 grammar uses custom inline-comment format: CVE-ID # expires=YYYY-MM-DD rationale='...' reviewer=handle (Trivy honours CVE-ID only; comment is for human review hygiene)"
  - "D3 grammar uses YAML frontmatter exceptions list with review_date; missing file is an error (unlike .trivyignore which is optional)"
  - "scripts/ needs __init__.py to make _trivyignore_parser importable as scripts._trivyignore_parser; rescan-issue-creator uses importlib workaround for hyphenated names"
  - "N999 added to pyproject.toml scripts/** per-file-ignores to allow hyphenated module filenames"
  - "Both trivy jobs (trivy-image + trivy-dockerfile) gained uv setup steps to enable the Python parser invocation"
  - "scorecard.yml extended with uv setup + exception-check pre-step before Run Scorecard analysis"
  - "scorecard.dev/viewer URL used in README badge (was securityscorecards.dev/viewer)"
metrics:
  duration: "~40 minutes"
  completed: "2026-06-20T20:49:18Z"
  tasks_completed: 4
  tasks_total: 4
  files_created: 8
  files_modified: 6
---

# Phase 06 Plan 09: Trivyignore + Scorecard Exception Grammar Enforcement Summary

**One-liner:** D2 (`.trivyignore` 180-day expiry/rationale/reviewer grammar) + D3 (`.scorecard-exception.md` 180-day review_date) enforced in CI via Python parsers; Scorecard badge added to README; CONTRIBUTING.md documents D2.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | .trivyignore D2 grammar + parser + shell wrapper + unit tests | 0a19b1f | .trivyignore, scripts/_trivyignore_parser.py, scripts/trivyignore-check.sh, tests/unit/test_trivyignore_check.py, scripts/__init__.py |
| 2 | Wire trivyignore-check.sh into ci.yml trivy jobs | 29c66f9 | .github/workflows/ci.yml |
| 3 | .scorecard-exception.md D3 schema + checker + tests + scorecard.yml extension | e2a7d7d | .scorecard-exception.md, scripts/scorecard-exception-check.py, tests/unit/test_scorecard_exception_check.py, .github/workflows/scorecard.yml, pyproject.toml |
| 4 | Extend ci structural test + README badge + CONTRIBUTING.md section | 8f8771d | tests/structural/test_ci_yml_structure.py, README.md, CONTRIBUTING.md |

---

## D2 Grammar (`.trivyignore`)

Each CVE suppression must appear as a single line:

```
CVE-XXXX-NNNNN  # expires=YYYY-MM-DD rationale="<short why>" reviewer=<github-handle>
```

Rules enforced by `scripts/_trivyignore_parser.py` (called via `scripts/trivyignore-check.sh`):
- `expires=YYYY-MM-DD` must be in the future AND within 180 days of today.
- `rationale="…"` must be non-empty.
- `reviewer=<github-handle>` must be present.
- Lines starting with `#` or blank lines are skipped.
- Absent `.trivyignore` is acceptable (no suppressions needed).

CI enforcement: both `trivy-image` and `trivy-dockerfile` jobs in `ci.yml` run `bash scripts/trivyignore-check.sh .trivyignore` BEFORE the trivy-action scan. A malformed or stale entry blocks both Trivy scan jobs.

## D3 Grammar (`.scorecard-exception.md`)

YAML frontmatter at the top of the file:

```yaml
---
exceptions:
  - check: Token-Permissions
    reason: "<short prose explaining why this sub-check is allowed to fail>"
    review_date: YYYY-MM-DD     # must be in the future AND within 180 days of today
    owner: <github-handle>
---
```

Rules enforced by `scripts/scorecard-exception-check.py`:
- `exceptions:` must be a YAML list (empty list `[]` is valid).
- Each entry must have: `check`, `reason`, `review_date`, `owner`.
- `review_date` must be in the future AND within 180 days of today.
- Missing file is an error (unlike `.trivyignore`).

CI enforcement: `scorecard.yml` runs `uv run python scripts/scorecard-exception-check.py .scorecard-exception.md` BEFORE the `Run Scorecard analysis` step. The `id-token: write` permission on the `analysis` job-level is preserved (required for OIDC publishing to the Scorecard API).

## ci.yml trivy jobs now validate .trivyignore

**Confirmed:** Plan 06-01's `trivy-image` and `trivy-dockerfile` jobs now have the grammar validation pre-step. The structural test `test_trivy_jobs_validate_trivyignore_grammar` asserts this invariant.

uv setup steps were added to both trivy jobs (they previously had no Python/uv setup) to enable `uv run python scripts/_trivyignore_parser.py`.

## scorecard.yml extension

The existing `permissions: id-token: write` at job level is preserved. The new exception-check step was inserted BEFORE `Run Scorecard analysis`. uv setup steps were added before the new step. YAML is valid; digest-pin test passes.

## README badge

The OpenSSF Scorecard badge now appears in the README badge row pointing to `scorecard.dev/viewer`:

```markdown
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy/badge)](https://scorecard.dev/viewer/?uri=github.com/yves-vogl/aws-eks-helm-deploy)
```

Previous URL was `securityscorecards.dev/viewer` — updated to canonical `scorecard.dev/viewer`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Added scripts/__init__.py**
- **Found during:** Task 1
- **Issue:** `_trivyignore_parser.py` starts with underscore, making it importable as `scripts._trivyignore_parser` only if `scripts/` is a Python package. Without `__init__.py`, mypy reports "Source file found twice under different module names" and imports fail.
- **Fix:** Created `scripts/__init__.py` as a package marker.
- **Files modified:** `scripts/__init__.py`
- **Commit:** 0a19b1f

**2. [Rule 1 - Bug] Fixed `main(argv=[])` returning 0 instead of 2**
- **Found during:** Task 1 test execution
- **Issue:** `args = argv or sys.argv[1:]` — Python evaluates `[] or sys.argv[1:]` as `sys.argv[1:]` (empty list is falsy), so `main([])` fell through to file-check instead of returning 2.
- **Fix:** Changed to `args = sys.argv[1:] if argv is None else argv`.
- **Files modified:** `scripts/_trivyignore_parser.py`
- **Commit:** 0a19b1f

**3. [Rule 1 - Bug] Corrected `test_malformed_iso_date_fails` test**
- **Found during:** Task 1 test execution
- **Issue:** Test used `expires=not-a-date` which doesn't match the `LINE_RE` regex (`\d{4}-\d{2}-\d{2}`), yielding "missing required grammar" not "malformed expires=".
- **Fix:** Changed to `expires=2099-13-40` (digit pattern matching regex but invalid calendar date for `date.fromisoformat()`).
- **Files modified:** `tests/unit/test_trivyignore_check.py`
- **Commit:** 0a19b1f

**4. [Rule 2 - Missing critical] Added N999 to pyproject.toml scripts/** per-file-ignores**
- **Found during:** Task 3
- **Issue:** `scorecard-exception-check.py` filename contains hyphens, triggering ruff N999 (invalid module name). The existing `rescan-issue-creator.py` is exempt via `scripts/**` ignore but N999 was not listed.
- **Fix:** Added `"N999"` to `[tool.ruff.lint.per-file-ignores]` `"scripts/**"` list.
- **Files modified:** `pyproject.toml`
- **Commit:** e2a7d7d

**5. [Rule 2 - Missing critical] Refactored check() functions to reduce C901 complexity**
- **Found during:** Tasks 1 and 3
- **Issue:** Both `check()` functions exceeded ruff's C901 complexity limit (11 > 10).
- **Fix:** Extracted `_check_expiry()` helper in `_trivyignore_parser.py` and `_check_review_date()` + `_check_entry()` helpers in `scorecard-exception-check.py`.
- **Files modified:** `scripts/_trivyignore_parser.py`, `scripts/scorecard-exception-check.py`
- **Commit:** 0a19b1f, e2a7d7d

**6. [Rule 2 - Missing critical] Added uv setup steps to trivy jobs in ci.yml**
- **Found during:** Task 2
- **Issue:** Plan 06-01 created `trivy-image` and `trivy-dockerfile` as lightweight jobs without uv/Python setup. The new `bash scripts/trivyignore-check.sh` invokes `uv run python`, requiring uv to be installed.
- **Fix:** Added `setup-uv` + `uv python install` + `uv sync` steps to both trivy jobs before the grammar check step.
- **Files modified:** `.github/workflows/ci.yml`
- **Commit:** 29c66f9

**7. [Rule 2 - Missing critical] Added uv setup steps to scorecard.yml**
- **Found during:** Task 3
- **Issue:** `scorecard.yml` previously had no uv/Python setup; the new exception-check step invokes `uv run python`.
- **Fix:** Added `setup-uv` + `uv python install` + `uv sync` steps before the exception-check step.
- **Files modified:** `.github/workflows/scorecard.yml`
- **Commit:** e2a7d7d

## Known Stubs

None — all parsers are fully implemented and wired to CI. Both `.trivyignore` and `.scorecard-exception.md` start empty (correct initial state, not stubs).

## Threat Flags

None — no new trust boundaries introduced beyond what the plan's threat model covers. The parsers read local files only. The scorecard.yml `id-token: write` permission (pre-existing) is the only OIDC surface and it's for publishing Scorecard results, not for the new exception-check step.

## Self-Check: PASSED

Files exist:
- `.trivyignore` FOUND
- `scripts/_trivyignore_parser.py` FOUND
- `scripts/trivyignore-check.sh` FOUND
- `.scorecard-exception.md` FOUND
- `scripts/scorecard-exception-check.py` FOUND
- `tests/unit/test_trivyignore_check.py` FOUND
- `tests/unit/test_scorecard_exception_check.py` FOUND

Commits exist:
- 0a19b1f FOUND
- 29c66f9 FOUND
- e2a7d7d FOUND
- 8f8771d FOUND

Quality gates:
- `pytest tests/structural tests/unit -q --no-cov`: 592 passed
- `pytest tests/unit --cov=src --cov-fail-under=100`: 100.00% PASS
- `mypy --strict src/aws_eks_helm_deploy`: 0 errors
- `ruff check src/ tests/ scripts/`: clean
- `uv run python scripts/_trivyignore_parser.py .trivyignore`: OK
- `uv run python scripts/scorecard-exception-check.py .scorecard-exception.md`: OK
- `grep -c 'scripts/trivyignore-check.sh' ci.yml`: 2
- `grep -F 'scorecard-exception-check.py' scorecard.yml`: FOUND
- `grep -F 'api.securityscorecards.dev' README.md`: FOUND
- `grep -F 'expires=' CONTRIBUTING.md`: FOUND
