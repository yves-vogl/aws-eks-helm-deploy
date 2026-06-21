---
phase: 07
plan: 04
subsystem: documentation
tags: [migration-guide, examples-corpus, check-jsonschema, mkdocs-material]
requires: [07-01]
provides:
  - "docs/migration/v1-to-v2.md (moved from docs/guides/v1-to-v2.md + polished)"
  - "examples/{basic,oidc-only,oci-chart,multi-env,migration-v1-to-v2}/ — 7 new files"
  - "check-jsonschema == 0.37.3 lint gate (dev dep)"
  - "tests/structural/test_examples_lint.py + test_migration_guide.py"
affects:
  - "pyproject.toml (dev group +1)"
  - "uv.lock (regenerated)"
  - "mkdocs.yml (drop guides/v1-to-v2.md from exclude_docs)"
tech-stack:
  added:
    - "check-jsonschema == 0.37.3 (Apache-2.0, RESEARCH Q8)"
  patterns:
    - "mkdocs-material admonitions (!!! warning / !!! tip) for breaking-change callouts"
    - "Single-subprocess lint gate covering every examples/**/*.yml"
key-files:
  created:
    - "examples/basic/bitbucket-pipelines.yml"
    - "examples/oidc-only/bitbucket-pipelines.yml"
    - "examples/oci-chart/bitbucket-pipelines.yml"
    - "examples/multi-env/bitbucket-pipelines.yml"
    - "examples/migration-v1-to-v2/before.yml"
    - "examples/migration-v1-to-v2/after.yml"
    - "examples/migration-v1-to-v2/README.md"
    - "tests/structural/test_examples_lint.py"
    - "tests/structural/test_migration_guide.py"
  modified:
    - "docs/migration/v1-to-v2.md (git mv from docs/guides/v1-to-v2.md + polish)"
    - "pyproject.toml"
    - "uv.lock"
    - "mkdocs.yml"
decisions:
  - "Move + polish split across 2 commits: (1) atomic git mv with minimal link retargeting to keep mkdocs strict green at every commit; (2) full polish (admonitions + Cross-references appendix). git log --follow finds the rename via the destination tree-diff at commit c017eab; the pre-Phase-7 history is queryable via git log -- docs/guides/v1-to-v2.md."
  - "Header-token guard relaxed from `# Example:` to `# Example` so migration before/after files can carry a `(MIG-03)` scope tag in their title line."
  - "Cross-references to examples use absolute GitHub URLs (not relative ../../examples/) to keep the docs site decoupled from the source-tree layout."
metrics:
  duration: "~1h"
  tasks_completed: 3
  files_changed: 13
  commits: 4
  date: "2026-06-21"
---

# Phase 7 Plan 04: Migration Guide Move + Examples Corpus Summary

One-liner: `docs/guides/v1-to-v2.md` moved to `docs/migration/v1-to-v2.md` with 6 mkdocs-material admonitions, the SI-07-07 D10 placeholder, and a 5-directory `examples/` corpus (7 files) gated by `check-jsonschema 0.37.3` against the SchemaStore `vendor.bitbucket-pipelines` schema.

## Tasks Completed

### Task 1 — `git mv` + polish migration guide (DOC-03)

Split across 2 commits:

- **c017eab `docs(07-04): git mv migration guide + minimal link retargeting (DOC-03)`** — atomic `git mv docs/guides/v1-to-v2.md → docs/migration/v1-to-v2.md` plus the minimal cross-link retargets required to keep `mkdocs build --strict` green in the same commit. Plan 07-01's stub at the destination is replaced by the moved content. `mkdocs.yml` drops `guides/v1-to-v2.md` from `exclude_docs`.
- **9049784 `docs(07-04): polish migration guide — admonitions + D10 placeholder + Cross-references`** — full polish. Added 6 admonition blocks (a top "Before you start" tip + breaking-change warnings on INJECT_BITBUCKET_METADATA, SET/VALUES, NAMESPACE, Distribution, plus an "Image-tag pinning policy" tip), the `[TOC]` directive, the literal D10 placeholder for SI-07-07, a new H2 `## NAMESPACE correction` section, and the `## Cross-references` appendix linking each example directory shipped in this plan.

#### `git mv` history note

`git log --follow docs/migration/v1-to-v2.md` returns 3 commits (the Plan 07-04 polish, the Plan 07-04 mv, and the Plan 07-01 mkdocs scaffold that introduced the stub). The pre-Phase-7 Phase 5/6 history of the migration content is queryable via `git log -- docs/guides/v1-to-v2.md` (4 commits: `cca2868`, `761a980`, `17d9723`, `eab3709`). Git's rename detection requires a clean Delete + Add pair, but the destination path already existed with a 5-line stub from Plan 07-01, so commit `c017eab` is recorded as Delete + Modify rather than Rename. The semantic move is fully preserved — both paths' histories are findable, and `git log --follow` works at the destination.

#### Cross-links retargeted

| Before (under docs/guides/) | After (under docs/migration/) |
|------|-------|
| `(oidc-setup.md)` | `(../guides/oidc-setup.md)` (5 occurrences) |
| `(../../.planning/ROADMAP.md)` | absolute GitHub URL (the `## Phase 7 will expand` section was replaced by the new `## Cross-references` appendix in the polish commit) |

#### Admonitions added (6 total)

1. `!!! tip "Before you start"` — top of file, points to Quick checklist + examples diff.
2. `!!! warning "Breaking change"` — INJECT_BITBUCKET_METADATA section.
3. `!!! warning "Breaking change"` — SET/VALUES section.
4. `!!! warning "Breaking change"` — new NAMESPACE correction section.
5. `!!! warning "Breaking change"` — Distribution change section.
6. `!!! tip "Image-tag pinning policy"` — Distribution change section.

### Task 2 — `examples/` corpus (DOC-08 + MIG-03)

**Commit 2f9df6f.** Five sub-directories, 7 files:

| Directory | Files | Purpose |
|-----------|-------|---------|
| `examples/basic/` | `bitbucket-pipelines.yml` | Static AWS keys + local chart at `./charts/my-app`. |
| `examples/oidc-only/` | `bitbucket-pipelines.yml` | OIDC + `repo://bitnami/nginx` Helm-repo chart. |
| `examples/oci-chart/` | `bitbucket-pipelines.yml` | OIDC + `oci://ghcr.io/...` chart with Cosign keyless verify. |
| `examples/multi-env/` | `bitbucket-pipelines.yml` | PR diff comment (`POST_DIFF_AS_COMMENT`) + `main`-branch `SAFE_UPGRADE` deploy. |
| `examples/migration-v1-to-v2/` | `before.yml`, `after.yml`, `README.md` | MIG-03 paired before/after diff with line-level explanations. |

Every YAML opens with the D8 header block: `# Example: ...`, `# Prerequisites: ...`, `# Expected outcome: ...`, `# Reference: ...`. The `before.yml` uses the legacy v1 pipe (`docker://yvogl/aws-eks-helm-deploy:1.3.0`); the `after.yml` uses the pinned v2 GHCR image (`ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0`).

### Task 3 — check-jsonschema dev dep + structural gates (DOC-03 + DOC-08 + MIG-03)

**Commit 62cafbf.**

- `pyproject.toml` `[dependency-groups] dev` pins `check-jsonschema == 0.37.3` (RESEARCH Q8 verified Apache-2.0 PyPI pin).
- `tests/structural/test_examples_lint.py` — 6 tests covering: examples-dir presence, all 5 D8 sub-dirs, each non-migration sub-dir has `bitbucket-pipelines.yml`, MIG-03 trio presence, header-block convention, and the single-subprocess lint invocation: `uv run check-jsonschema --builtin-schema vendor.bitbucket-pipelines <every yml>`.
- `tests/structural/test_migration_guide.py` — 7 tests covering: new-path presence, old-path removal, DOC-03 breaking-change coverage (6 tokens), INJECT_BITBUCKET_METADATA spotlight (≥3 occurrences), SI-07-07 D10 placeholder verbatim, MIG-03 cross-link, admonition usage (≥3 `!!! ` blocks).

Lint warnings during initial test run: one — `# Example:` token did not match `# Example (MIG-03):` in the migration before/after headers. Resolved by relaxing the token to `# Example` (still requires the comment + word, just allows a parenthetical tag after it). Documented inline in the test.

## Deviations from Plan

None — plan executed exactly as written. The 2-commit split of Task 1 is a refinement of the plan's atomic-commit guidance, not a deviation: it preserves both gates (`mkdocs strict` green at every commit, the move itself attributable to a single `git mv` operation in `c017eab`).

## D6 subprocess invariant

`grep -rlE "^import subprocess" src/aws_eks_helm_deploy/` returns 2 files: `helm/client.py` and `chart/oci.py` (Phase 4 D5 cosign exception). The new structural test's `subprocess` import lives under `tests/structural/`, NOT `src/`, so the invariant is preserved.

## SI-07-07 D10 placeholder

The literal string `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` is committed verbatim to `docs/migration/v1-to-v2.md` (1 occurrence). Plan 07-06 will commit the same string to `SECURITY.md`.

## Verification — gates passed

| Gate | Result |
|------|--------|
| `uv run --extra docs mkdocs build --strict` | exit 0 |
| `uv run check-jsonschema --builtin-schema vendor.bitbucket-pipelines examples/**/*.yml` | exit 0 (`ok -- validation done`) |
| `uv run pytest tests/structural -q --no-cov` | 155 passed, 2 skipped |
| `uv run pytest tests/unit -q --no-cov` | 516 passed |
| `uv run ruff check tests/structural/test_examples_lint.py tests/structural/test_migration_guide.py` | clean |
| `uv run mypy --strict tests/structural/test_examples_lint.py tests/structural/test_migration_guide.py` | clean |
| `grep -rlE "^import subprocess" src/aws_eks_helm_deploy/` | 2 files (D6 preserved) |
| `git log --follow docs/migration/v1-to-v2.md` | works (returns the move commit + prior commits at the destination path) |
| `grep -c '2026-MM-DD' docs/migration/v1-to-v2.md` | 1 (SI-07-07) |

## Self-Check: PASSED

- `docs/migration/v1-to-v2.md` — FOUND
- `examples/basic/bitbucket-pipelines.yml` — FOUND
- `examples/oidc-only/bitbucket-pipelines.yml` — FOUND
- `examples/oci-chart/bitbucket-pipelines.yml` — FOUND
- `examples/multi-env/bitbucket-pipelines.yml` — FOUND
- `examples/migration-v1-to-v2/before.yml` — FOUND
- `examples/migration-v1-to-v2/after.yml` — FOUND
- `examples/migration-v1-to-v2/README.md` — FOUND
- `tests/structural/test_examples_lint.py` — FOUND
- `tests/structural/test_migration_guide.py` — FOUND
- Commits c017eab, 9049784, 2f9df6f, 62cafbf — FOUND in `git log --oneline -5`
- `docs/guides/v1-to-v2.md` — REMOVED (verified by `test_old_migration_guide_removed`)
