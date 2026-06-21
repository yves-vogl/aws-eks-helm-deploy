---
phase: 07-documentation-site-migration-guide
plan: 06
subsystem: governance / docs
tags: [governance, docs, security, contributing, code-of-conduct, structural-tests]
requirements_completed: [DOC-01, DOC-05, DOC-06, DOC-07]
status: complete
wave: 3
depends_on: []
commits:
  - c4d8fcc — Task 1: README polish (3 additive badges + docs-site link + Status callout rewrite)
  - 8a0b616 — Task 2: SECURITY.md D10 6-month placeholder + DOC-06 structural gate
  - 5d34b7a — Task 3: DOC-05 + DOC-07 structural gates (CONTRIBUTING + CoC verification, zero source edits)
files_created:
  - tests/structural/test_security_md.py
  - tests/structural/test_contributing.py
  - tests/structural/test_code_of_conduct.py
files_modified:
  - README.md
  - SECURITY.md
  - tests/structural/test_readme_polish.py
files_verified_only:
  - CONTRIBUTING.md (zero edits — all DOC-05 tokens already present)
  - CODE_OF_CONDUCT.md (zero edits — Contributor Covenant 2.1 already referenced)
key_decisions:
  - D6 honored: README badges are purely additive — 7 existing badges byte-identical to pre-edit form, 3 new badges appended after OpenSSF Scorecard with ?style=flat-square.
  - D10 honored: SECURITY.md placeholder committed verbatim ('2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.'); 90-day disclosure timeline unchanged.
  - DOC-05 + DOC-07: governance files passed structural-test verification without source edits.
metrics:
  duration: ~7 minutes
  completed: 2026-06-21
  new_structural_tests: 24 (9 readme-polish + 6 security-md + 7 contributing + 4 code-of-conduct, minus 4 pre-existing)
---

# Phase 07 Plan 06: README badge polish + SECURITY.md 6-month placeholder + governance verification Summary

Polished governance files per D6 (additive-only) and D10 (literal 6-month placeholder verbatim); added 4 structural test gates (DOC-01 hardened, DOC-05, DOC-06, DOC-07) covering README badges, SECURITY.md placeholder, CONTRIBUTING dev loop, and Contributor Covenant 2.1 reference.

## What shipped

### README.md (Task 1, commit c4d8fcc)

- **3 additive badges appended after the existing OpenSSF Scorecard badge** (line 10–12), all with `?style=flat-square` per D6:
  - `[![Sponsors](https://img.shields.io/github/sponsors/yves-vogl?style=flat-square)](https://github.com/sponsors/yves-vogl)`
  - `[![Stars](https://img.shields.io/github/stars/yves-vogl/aws-eks-helm-deploy?style=flat-square)](.../stargazers)`
  - `[![Open issues](https://img.shields.io/github/issues/yves-vogl/aws-eks-helm-deploy?style=flat-square)](.../issues)`
- **Existing 7-badge row is byte-identical to the pre-edit form** — `git diff` shows only `+` lines, no reorder, no style churn (verified line-by-line).
- **Docs-site link surfaced prominently** right after the badge row: `📖 **Documentation site:** [yves-vogl.github.io/aws-eks-helm-deploy](https://yves-vogl.github.io/aws-eks-helm-deploy/) — versioned via mike (v1 frozen, v2 current).`
- **Status callout sharpened** to v2.0 narrative with a link to `docs/migration/v1-to-v2.md`.

### SECURITY.md (Task 2, commit 8a0b616)

- **Line 8** holds the D10 placeholder verbatim: `Security fixes for 6 months from the v2.0.0 release date — ending `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` Frozen at v1.3.0 on Docker Hub.`
- **`## Reporting a vulnerability`, `## Disclosure timeline` (Day-0/14/60/90), `## Scope`, `## What we do automatically`, `## Acknowledgements`** — all preserved byte-identical (D10 explicit constraint).

### CONTRIBUTING.md + CODE_OF_CONDUCT.md (Task 3, commit 5d34b7a)

- **Zero source edits.** Both files already satisfied all required tokens.
- CONTRIBUTING.md verified to document `uv sync` (line 14), `pre-commit` (line 22), `pytest` (line 19, via `make test`), `kind` (line 20, via `make integration-test`), and `Conventional Commits` (line 23).
- CODE_OF_CONDUCT.md verified to reference Contributor Covenant 2.1 (line 3), with `## Reporting` (line 5) and `## Enforcement` (line 9) sections.

### Structural tests (3 new + 1 hardened)

- `tests/structural/test_readme_polish.py` — **hardened from 4 → 9 tests**: badge-row baseline now 10 badges, plus sponsors / stars / open-issues / docs-site / migration-guide / flat-square assertions.
- `tests/structural/test_security_md.py` — **6 new tests** covering D10 placeholder (SI-07-07 gate), 6-month wording, PVR link, Day 90 (max) marker, Scope section.
- `tests/structural/test_contributing.py` — **7 new tests** covering DOC-05 dev-loop tokens.
- `tests/structural/test_code_of_conduct.py` — **4 new tests** covering DOC-07 Contributor Covenant 2.1 reference.

## Verification

```text
$ uv run pytest tests/structural -q --no-cov
187 passed in 1.05s

$ uv run pytest tests/unit tests/structural -q --no-cov
703 passed (above 637 baseline; Phase 7 plans 07-01..07-05 added the rest)

$ uv run --extra docs mkdocs build --strict
INFO    -  Documentation built in 0.24 seconds

$ grep -F '2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.' SECURITY.md docs/migration/v1-to-v2.md | wc -l
2  # SI-07-07 cross-file gate satisfied

$ grep -rE "import subprocess" src/aws_eks_helm_deploy/ --include="*.py" | wc -l
2  # D6 subprocess invariant preserved (helm/client.py + chart/oci.py only)
```

## D10 placeholder location for verifier

- `SECURITY.md` line 8 (in `## Supported versions` table, v1.x row).
- `docs/migration/v1-to-v2.md` line 16 (Status callout) — already shipped by Plan 07-04.

## Deviations from Plan

None. Plan executed exactly as written: additive-only README edits, byte-verbatim D10 placeholder, zero edits to CONTRIBUTING.md / CODE_OF_CONDUCT.md (expected outcome per the plan's "verification only" design).

## Self-Check: PASSED

- README.md badge additions present: FOUND (`grep` returns sponsors/stars/issues badge sources).
- SECURITY.md D10 placeholder present: FOUND (line 8).
- 3 new structural test files exist: FOUND.
- Commits c4d8fcc, 8a0b616, 5d34b7a present in `git log`: FOUND.
- D6 subprocess invariant (== 2): VERIFIED.
- SI-07-07 cross-file gate (placeholder count == 2): VERIFIED.
