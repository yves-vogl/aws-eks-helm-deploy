---
phase: 07-documentation-site-migration-guide
plan: 02
title: ADR archive — 9 MADR 4.0 ADRs + verbatim 0000-template
status: complete
date: 2026-06-21
duration_minutes: ~25
commit: 2917283
requirements: [DOC-04]
requirements_addressed: [DOC-04]
files_created:
  - docs/adr/0000-template.md
  - docs/adr/0001-github-primary-forge.md
  - docs/adr/0002-v2-clean-break.md
  - docs/adr/0003-cosign-keyless-over-gpg.md
  - docs/adr/0004-boto3-only-over-awscli.md
  - docs/adr/0005-release-please-over-semversioner.md
  - docs/adr/0006-oidc-default-precedence.md
  - docs/adr/0007-multi-arch-native-runners.md
  - docs/adr/0008-mkdocs-material-now-zensical-later.md
  - docs/adr/0009-src-layout-no-compat-shims.md
  - tests/structural/test_adr_template.py
files_modified:
  - docs/adr/index.md
provides:
  - "MADR 4.0 ADR archive (template + 9 authored ADRs)"
  - "Structural test asserting MADR provenance + 9-ADR presence + section structure"
  - "Curated index page wired into mkdocs nav"
key_decisions:
  - "Cross-phase CONTEXT.md links use github.com blob URLs (not relative .planning/ paths) because .planning is outside docs_dir and mkdocs --strict rejects them."
  - "All three plan tasks (template+test, 9 ADRs, index rewrite) collapsed into one commit because the structural test asserts on the index and 9-ADR outputs; staging Task 1 alone left the pre-commit hook with 3 expected-red tests, blocking the commit."
---

# Phase 7 Plan 02: ADR archive Summary

Ship the v2.0 architecture-decision record archive: 9 MADR 4.0 ADRs covering every architectural decision shipped across Phases 1-6, plus the canonical MADR 4.0 template vendored verbatim at the upstream blob SHA. Closes DOC-04.

## What shipped

### docs/adr/0000-template.md

- **Upstream provenance:** MADR tag `4.0.0`, `template/adr-template.md`, blob SHA `08dac30ed895cf728fc7da95f9702ca4dd5ab900`, released 2024-09-17, license CC0-1.0.
- **On-disk layout:** 4-line provenance comment + 1 blank line + verbatim upstream body. Total 79 lines (74 upstream body lines + 5 prepended).
- **Body byte-identity:** `tail -n +6 docs/adr/0000-template.md | diff - /tmp/madr-4.0-template.md` → empty (clean diff).
- **Reproducibility:** `curl -fsSL https://raw.githubusercontent.com/adr/madr/4.0.0/template/adr-template.md | git hash-object --stdin` → `08dac30ed895cf728fc7da95f9702ca4dd5ab900`.

### Nine MADR 4.0 ADRs (0001..0009)

| # | Title | Decision outcome (1 line) |
|---|-------|---------------------------|
| 0001 | GitHub primary forge | Move primary to GitHub; keep Bitbucket Marketplace listing pointing at Docker Hub v1.3.0 frozen image for v1.x compat. |
| 0002 | v2.x clean break | No runtime compat shim; v1.x frozen on Docker Hub at v1.3.0, v2.x publishes to GHCR, migration documented. |
| 0003 | Cosign keyless | Cosign keyless (OIDC → Fulcio → Rekor) with `--bundle` for offline verify; no long-lived keys. |
| 0004 | boto3-only EKS auth | ~40 lines of Python over `boto3.client('sts').generate_presigned_url` replaces bundled `awscli`; ~120 MB image weight reclaimed; stays inside D6 subprocess invariant. |
| 0005 | release-please | release-please-action v4 (`release-type: python`) replaces semversioner; release-PR model + Conventional Commits enforce semver mechanically. |
| 0006 | OIDC default precedence | Static AWS keys win over OIDC when both are present, matching `botocore` default credential chain; one-shot WARN log `auth.precedence.static_keys_won_over_oidc` surfaces the precedence. |
| 0007 | Multi-arch native runners | Two native runners (`ubuntu-24.04` + `ubuntu-24.04-arm`) + `docker buildx imagetools create` fan-in; never QEMU (silent broken-arm64 risk). |
| 0008 | mkdocs-material now, Zensical later | mkdocs-material 9.7.6 ships v2.0; Zensical migration tracked as DOC-NEXT-01 for v2.1+ (maintenance-mode critical fixes through Nov 2026). |
| 0009 | src-layout, no v1 compat shims | `src/aws_eks_helm_deploy/` layout; no `aws_eks_helm_deploy.v1` shim namespace (v1 was a shell pipe, no Python API existed). |

Every ADR has front-matter (`status: accepted`, `date: 2026-06-21`, `decision-makers: yves-vogl`, `consulted`, `informed`) and the canonical MADR section order: Context → Decision Drivers → Considered Options → Decision Outcome (with `### Consequences` sub-section) → Pros and Cons of the Options → More Information.

### docs/adr/index.md

Curated archive landing page replacing the Wave-1 stub from Plan 07-01:
- 9-row table with ADR number, title, and one-line summary.
- Provenance note linking to `0000-template.md` and citing the MADR 4.0 upstream blob SHA.
- "How to add a new ADR" procedure (copy template → fill MADR sections → update index → PR).
- Related references (MADR upstream, REQUIREMENTS.md, phase planning archive).

### tests/structural/test_adr_template.py

7 tests covering:
1. `test_adr_dir_exists` — `docs/adr/` is a directory.
2. `test_adr_template_exists` — `0000-template.md` is a file.
3. `test_adr_template_declares_madr_4_0_provenance` — file contains the literal SHA `08dac30ed895cf728fc7da95f9702ca4dd5ab900`.
4. `test_adr_template_has_madr_4_0_canonical_sections` — file contains the three canonical MADR headings.
5. `test_all_nine_adrs_exist` — frozenset of 9 expected filenames is subset of discovered.
6. `test_each_adr_has_madr_sections` — every authored ADR has the three canonical MADR section headings.
7. `test_adr_index_exists_and_lists_all_nine` — `index.md` links to each of the 9 ADR filename stems and references the MADR SHA.

`uv run ruff check` clean. `uv run mypy --strict` clean. `uv run pytest tests/structural/test_adr_template.py --no-cov` → 7/7 green.

## Verification artifacts

```
$ uv run --extra docs mkdocs build --strict --site-dir /tmp/mkdocs-test-site
INFO    -  Documentation built in 0.22 seconds      # 11 ADR pages reachable, 0 warnings

$ uv run pytest tests/structural/test_adr_template.py --no-cov -q
.......                                                                  [100%]
7 passed in 0.01s

$ ls docs/adr/*.md | wc -l
11                                                  # 1 template + 9 ADRs + 1 index

$ grep -rn "import subprocess" src/
src/aws_eks_helm_deploy/chart/oci.py:42:import subprocess  # CONTEXT D5 scoped exception
src/aws_eks_helm_deploy/helm/client.py:38:import subprocess
# Exactly 2 → D6 invariant preserved
```

## Deviations from Plan

### [Rule 3 — Blocking issue] Cross-phase CONTEXT.md links rewritten as github.com blob URLs

- **Found during:** Task 3 verification (`mkdocs build --strict`).
- **Issue:** ADRs initially used relative paths like `../../.planning/phases/06-.../06-CONTEXT.md` for source citations. `mkdocs --strict` flagged these as broken because `docs_dir: docs` excludes the `.planning/` tree — mkdocs treats unresolved relative links as fatal.
- **Fix:** Rewrote 9 source-citation links across ADRs 0001-0009 to absolute `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/.../0N-CONTEXT.md` URLs, matching the convention already established in ADR-0005 and `docs/adr/index.md` for `CONTRIBUTING.md` / `REQUIREMENTS.md` references.
- **Files modified:** all 9 authored ADRs.
- **Re-verification:** `mkdocs build --strict` → 0 warnings.

### [Plan-tasks combined into one commit] Tasks 1 + 2 + 3 collapsed

- **Found during:** Task 1 commit attempt.
- **Issue:** The structural test from Task 1 asserts on Task 2 (9 ADRs present) and Task 3 (index lists 9 ADRs) outputs. Committing Task 1 alone with the test landed but those outputs absent left the pre-commit hook test suite with 3 expected-red tests — the project's pre-commit hook runs `pytest` and refuses any commit with failing tests.
- **Fix:** Held Task 1's diff in the working tree, completed Tasks 2 and 3, then committed everything together as a single `feat(07)` commit (`2917283`).
- **Impact:** Plan execution unchanged; one commit instead of three is a cosmetic difference. The plan's task boundaries are still visible in the structural test's progression (3 template-side tests, 4 ADR-side tests).

## Cross-references

- DOC-04 closed: REQUIREMENTS.md should mark DOC-04 as `complete`.
- ADR-0006 references AUTH-04 (revised 2026-06-18) — verifier check from Plan 07-07 will assert this cross-reference exists.
- ADR-0008 references DOC-NEXT-01 — Zensical migration backlog for v2.1+.
- Plan 07-04 (migration guide polish) will reference ADR-0002 and ADR-0009 by number; no content dependencies.

## Self-Check: PASSED

- [x] `docs/adr/0000-template.md` exists with MADR 4.0 provenance comment + verbatim body (74 upstream lines, body diff clean).
- [x] All 9 authored ADRs exist with MADR 4.0 structure.
- [x] `docs/adr/index.md` curated archive lists all 9 ADRs and references the MADR SHA.
- [x] `tests/structural/test_adr_template.py` ships with 7 tests, all green.
- [x] `mkdocs build --strict` exits 0 with all 11 ADR pages reachable.
- [x] D6 invariant preserved: `grep -rn "import subprocess" src/` returns exactly 2 lines.
- [x] Commit `2917283` is on `phase/07-documentation-site-and-migration` branch.
