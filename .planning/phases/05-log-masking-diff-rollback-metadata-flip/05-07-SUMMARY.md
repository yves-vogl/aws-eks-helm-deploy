---
phase: 05-log-masking-diff-rollback-metadata-flip
plan: "07"
subsystem: docs
tags: [migration-guide, breaking-changes, meta-02, mig-02, pipe-02, pipe-03, pipe-04, pipe-05]
dependency_graph:
  requires: [05-01, 05-03, 05-05, 05-06]
  provides: [docs/guides/v1-to-v2.md]
  affects: []
tech_stack:
  added: []
  patterns: [plain-markdown-draft, no-mkdocs-extensions]
key_files:
  created:
    - docs/guides/v1-to-v2.md
  modified: []
decisions:
  - "Guide is plain Markdown (no mkdocs-material admonitions) so it renders on any renderer; Phase 7 wraps with mkdocs polish"
  - "Tri-state INJECT_BITBUCKET_METADATA documented as table: true/false/unset with distinct behaviour per row"
  - "Both WARN event names documented verbatim (meta.bitbucket_values_detected_without_opt_in, mig.v1_env_var_detected) so grep-driven support lookups hit the guide"
metrics:
  duration: "< 10 minutes"
  completed: "2026-06-20"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 05 Plan 07: Migration Guide Draft (v1-to-v2.md) Summary

**One-liner:** Plain-Markdown migration guide covering all Phase 5 breaking changes and new
workflows — META-02 default flip, MIG-02 env-var re-syntax, PIPE-02/03 diff + PR-comment,
PIPE-04/05 rollback + SAFE_UPGRADE — with v1/v2 before-after examples and both WARN event
names documented verbatim.

## Tasks

| # | Name | Status | Commit |
|---|------|--------|--------|
| 1 | Draft docs/guides/v1-to-v2.md | Complete | eab3709 |

## Artifact: docs/guides/v1-to-v2.md

- **Line count:** 363 (well above the 80-line minimum)
- **H2 headings:** 8
  - Breaking changes at a glance
  - INJECT_BITBUCKET_METADATA — the headline breaking change (META-02)
  - SET and VALUES env var syntax (MIG-02)
  - ACTION=diff — preview changes (PIPE-02/03)
  - ACTION=rollback + SAFE_UPGRADE — safe rollback only (PIPE-04/05)
  - New v2 environment variables
  - Quick migration checklist
  - Phase 7 will expand this guide
- **Fenced code blocks:** 14 (yaml pipeline snippets, text error/WARN examples)
- **H3 subsections:** 8 (detection WARN, before/after, v1 syntax, v2 syntax, startup WARN, basic diff, PR comment, deploying, rollback)

## WARN event name coverage (verbatim)

- `meta.bitbucket_values_detected_without_opt_in` — confirmed present (META-03 detection WARN section)
- `mig.v1_env_var_detected` — confirmed present (SET/VALUES startup WARN section)

## Quality gates passed

| Gate | Result |
|------|--------|
| `test -f docs/guides/v1-to-v2.md` | PASS |
| `wc -l` ≥ 80 | PASS (363 lines) |
| `grep INJECT_BITBUCKET_METADATA` ≥ 1 | PASS (13 hits) |
| `grep 'pipe:safe-upgrade'` ≥ 1 | PASS (4 hits) |
| `grep 'static keys win'` ≥ 1 | PASS |
| `grep meta.bitbucket_values_detected_without_opt_in` | PASS |
| `grep mig.v1_env_var_detected` | PASS |
| `grep 'ghcr.io/yves-vogl/aws-eks-helm-deploy'` ≥ 1 | PASS (8 hits) |
| `grep 'docs/guides/oidc-setup.md'` ≥ 1 | PASS (2 hits) |
| No mkdocs-material admonitions (`!!! `) | PASS |
| No real-looking `BITBUCKET_TOKEN` literal (`ATBB...`) | PASS |
| pre-commit hooks (ruff, mypy, gitleaks, pytest) | PASS |

## Deviations from plan

None — plan executed exactly as written.

## Known Stubs

None — this is a pure documentation file with no backend wiring required.

## Threat Flags

None — documentation file introduces no new trust boundaries or security-relevant surface.

## Self-Check: PASSED

- `docs/guides/v1-to-v2.md` exists: FOUND
- Commit `eab3709` exists: FOUND
