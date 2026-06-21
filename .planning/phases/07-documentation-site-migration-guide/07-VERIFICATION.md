---
phase: 07-documentation-site-migration-guide
verified: 2026-06-21T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 7 Verification

**Date:** 2026-06-21
**Branch:** `phase/07-documentation-site-and-migration` (21 commits ahead of main)
**Verdict:** PASS

Goal-backward verification of the FINAL phase for v2.0 (`aws-eks-helm-deploy`).
Phase 7 goal: README → versioned mkdocs-material site (`/v1/` frozen, `/v2/` current) +
migration guide headline page + before/after `bitbucket-pipelines.yml` diff + 9 MADR
ADRs covering every architectural decision. All 16 mechanical gates pass; all 9 REQs
satisfied; all 7 SIs hold; two acceptable deviations documented.

## Mechanical gates (16 of 16 pass)

| # | Gate | Expected | Actual | Result |
|---|------|----------|--------|--------|
| 1 | `uv run --extra docs mkdocs build --strict` | exit 0, no warnings | exit 0, only INFO about ADR files not in nav (intentional — ADRs in `nav: ADRs: docs/adr/*.md` glob), `strict: true` honored | PASS |
| 2 | `bash scripts/check-variables-drift.sh` | exit 0 | exit 0 | PASS |
| 3 | `uv run check-jsonschema --builtin-schema vendor.bitbucket-pipelines examples/**/*.yml` (6 files: 4 examples + before.yml + after.yml) | exit 0 | exit 0 ("ok -- validation done") | PASS |
| 4 | `grep -rn "import subprocess" src/aws_eks_helm_deploy/` count | exactly 2 | 2 (`chart/oci.py`, `helm/client.py`) | PASS |
| 5 | `grep -c "id-token" .github/workflows/docs.yml` | 0 | 0 | PASS |
| 6 | `grep -E "uses:.*@(main\|master\|v[0-9])" .github/workflows/docs.yml` count | 0 | 0 (both `actions/checkout@<40-SHA>` and `astral-sh/setup-uv@<40-SHA>`) | PASS |
| 7 | `docs/adr/0000-template.md` MADR-4.0 provenance SHA `08dac30ed895cf728fc7da95f9702ca4dd5ab900` declared in body | 1 occurrence | 1 | PASS |
| 8 | Concurrency `cancel-in-progress: false` in docs.yml | present | present (the literal `grep -A1 concurrency:` from the brief misses it because of `group:` line; `grep -A2` confirms; SI-07-06 mechanical gate uses `grep -F` which returns 1 hit) | PASS |
| 9 | SECURITY.md contains literal placeholder `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` | ≥1 | 1 match | PASS |
| 10 | `uv run pytest tests/structural -q --no-cov` | all pass | 199 passed in 1.07s | PASS |
| 11 | `uv run pytest tests/unit -q --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` | all pass + 100% line+branch | 516 passed + 1106 stmts/216 br all covered, 100.00% | PASS |
| 12 | `uv run mypy --strict src/` | exit 0 | exit 0 ("Success: no issues found in 32 source files") | PASS (see notes for ruff legacy folders) |
| 13 | `[ -f docs/migration/v1-to-v2.md ] && [ ! -f docs/guides/v1-to-v2.md ]` + `git log --follow` >1 commit | new path present, old absent, history follows | new path present, old absent, 3 commits via `--follow` | PASS |
| 14 | `examples/` inventory (7 files) | all present | all 7 present (basic/, oidc-only/, oci-chart/, multi-env/, migration-v1-to-v2/{before.yml, after.yml, README.md}) | PASS |
| 15 | ADR inventory: template + 9 ADRs + index = 11 files | all present | all 11 present (0000-template, 0001..0009, index.md) | PASS |
| 16 | `docs-drift` job present in `.github/workflows/ci.yml` | True | True | PASS |

### Notes on gate 8 ("cancel-in-progress: false")

Brief's literal command `grep -A1 "concurrency:" .github/workflows/docs.yml | grep -c "cancel-in-progress: false"` returns 0 because `cancel-in-progress` is the 3rd line of the concurrency block (after `group: docs-deploy-…`), beyond `-A1`'s window. The underlying file is correct:

```
concurrency:
  group: docs-deploy-${{ github.ref }}
  cancel-in-progress: false
```

SI-07-06 specified the mechanical gate as `grep -F 'cancel-in-progress: false' .github/workflows/docs.yml` returning ≥1 hit, which passes. PASS recorded.

### Notes on gate 12 (mypy + ruff)

- `mypy --strict src/` — clean pass (32 files, 0 issues).
- `ruff check` returns 55 errors and `ruff format --check` reports 3 files needing reformat — **all in pre-existing v1.x legacy code** (`pipe/`, `test/acceptance/`, two scripts under `scripts/`). Verified identical 55 errors and 3 format pendings exist on `main` (commit 9819949); Phase 7 introduces **zero** new ruff/format regressions. The `pipe/` and `test/acceptance/` legacy trees pre-date the v2.x `src/`-layout migration (Phase 1) and are awaiting a separate cleanup PR — explicitly logged in `.planning/phases/07-documentation-site-migration-guide/deferred-items.md`.

## SC coverage (5 SCs from ROADMAP.md lines 177-183)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | README.md = entry doc (10-badge row, 60-second quickstart, links to docs site, marketplace listing, migration guide) | ✓ VERIFIED | 10 shields.io badges (license, release, GHCR, CI, coverage, Cosign-verified, OpenSSF Scorecard, sponsors, stars, open issues); docs-site link present; quickstart section present; `tests/structural/test_readme_polish.py` enforces |
| 2 | mkdocs-material + mike site via `.github/workflows/docs.yml`; `mike list` shows v1 + v2 (v2 default); auto-generated variables reference; CI fails on drift | ✓ VERIFIED | `mkdocs.yml` present (mkdocs-material 9.7.6 + mike 2.2.0 pinned); `docs.yml` workflow deploys via mike with `--update-aliases v2 latest` and `mike deploy --push v1` (mike runtime invocation lives in `repo-settings.md` §6-7); `scripts/generate-variables-doc.py` + `scripts/check-variables-drift.sh` + `ci.yml` `docs-drift` job all present |
| 3 | Migration guide documents every breaking change (INJECT_BITBUCKET_METADATA flip, NAMESPACE correction, image-tag pinning, `:latest` freeze + `:2` rolling tag); `examples/migration-v1-to-v2/` before/after diff | ✓ VERIFIED | `docs/migration/v1-to-v2.md`: 14×`INJECT_BITBUCKET_METADATA`, 11×`NAMESPACE`, 9×image-tag, 1×distribution-change; `examples/migration-v1-to-v2/{before.yml, after.yml, README.md}` present and lint-clean |
| 4 | `docs/adr/` MADR ADRs covering forge primacy, v2.0 clean break, Cosign keyless over GPG, boto3 vs awscli, release-please vs semversioner, OIDC default, multi-arch native runners | ✓ VERIFIED | 9 MADR-4.0 ADRs (template+0001..0009+index); each carries `## Context and Problem Statement`, `## Decision Drivers`, `## Considered Options`, `## Decision Outcome`; template body verbatim from MADR tag 4.0.0 (SHA `08dac…5ab900` declared in provenance comment); `tests/structural/test_adr_template.py` enforces |
| 5 | CONTRIBUTING.md + SECURITY.md (private disclosure + v1.x 6-month support) + CODE_OF_CONDUCT.md (Contributor Covenant 2.1); `examples/` ships ≥4 end-to-end `bitbucket-pipelines.yml` (basic, OIDC-only, OCI chart, multi-env) | ✓ VERIFIED | All 3 governance files present and gated by structural tests; SECURITY.md carries D10 6-month placeholder + 90-day disclosure window; CoC declares Contributor Covenant 2.1; 4 `bitbucket-pipelines.yml` files under `examples/{basic,oidc-only,oci-chart,multi-env}/`, all check-jsonschema-clean |

## REQ coverage (9 of 9)

| REQ | Description | Status | Evidence |
|-----|-------------|--------|----------|
| DOC-01 | README entry doc: badge row, 60-second quickstart, docs-site link | ✓ SATISFIED | README.md has 10 shields.io badges, "What this pipe does" section + inline snippet, docs-site link; commit c4d8fcc; `tests/structural/test_readme_polish.py` enforces |
| DOC-02 | mkdocs-material + mike site on GitHub Pages with /v1/ + /v2/ | ✓ SATISFIED | mkdocs.yml (strict: true, mkdocs-material 9.7.6 + mike 2.2.0 in docs extra); `.github/workflows/docs.yml` deploys; `scripts/generate-variables-doc.py` (≤30 LOC settings-doc wrapper) + `scripts/check-variables-drift.sh` + `ci.yml` `docs-drift` job; commits 8878009, b1f2ea0, a97b8a3 |
| DOC-03 | Migration guide every breaking change | ✓ SATISFIED | `docs/migration/v1-to-v2.md` (moved via `git mv` — history follows 3 commits); tokens INJECT_BITBUCKET_METADATA (14×), NAMESPACE (11×), image-tag (9×), distribution change (1×) all present; commits c017eab, 9049784 |
| DOC-04 | 9 MADR ADRs | ✓ SATISFIED | 9 ADRs (0001..0009) + 0000-template + index.md; template provenance SHA `08dac30e…5ab900` declared verbatim; each ADR has MADR 4.0 sections; commits 2917283, ff559dc; `tests/structural/test_adr_template.py` enforces |
| DOC-05 | CONTRIBUTING uv sync + pre-commit + pytest + kind + Conventional Commits | ✓ SATISFIED | CONTRIBUTING.md has all 5 tokens (uv sync: 1×, pre-commit: 3×, pytest: 2×, kind: 1×, Conventional Commits: 1×); commit 5d34b7a; `tests/structural/test_contributing.py` enforces |
| DOC-06 | SECURITY 6-month window + 90-day disclosure | ✓ SATISFIED | SECURITY.md has D10 placeholder `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` (1 match) and 2× 90-day disclosure language; commit 8a0b616; `tests/structural/test_security_md.py` enforces |
| DOC-07 | Contributor Covenant 2.1 | ✓ SATISFIED | CODE_OF_CONDUCT.md has 2× "Contributor Covenant" + 2× "2.1"; commit 5d34b7a; `tests/structural/test_code_of_conduct.py` enforces |
| DOC-08 | ≥4 examples bitbucket-pipelines.yml lint-clean | ✓ SATISFIED | 4 yamls under examples/{basic,oidc-only,oci-chart,multi-env}/; all check-jsonschema-clean; commit 2f9df6f; `tests/structural/test_examples_lint.py` enforces |
| MIG-03 | examples/migration-v1-to-v2/ before+after+README | ✓ SATISFIED | `examples/migration-v1-to-v2/{before.yml, after.yml, README.md}` all present; before+after lint-clean against vendor.bitbucket-pipelines schema; commit 2f9df6f |

## Security invariants (7 of 7)

| SI | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| SI-07-01 | docs.yml NO `id-token: write` | ✓ VERIFIED | `grep -c id-token docs.yml = 0`; permissions: only `contents: write` (for gh-pages branch push) |
| SI-07-02 | All `.github/workflows/*.yml` actions pinned to 40-char SHA | ✓ VERIFIED | `tests/structural/test_workflow_digest_pins.py` 4 tests pass; docs.yml uses `actions/checkout@11bd7…f683` + `astral-sh/setup-uv@caf0c…5d39` |
| SI-07-03 | `mkdocs build --strict` build command AND `strict: true` in mkdocs.yml | ✓ VERIFIED | docs.yml has 1× `mkdocs build --strict`; mkdocs.yml has `strict: true` at line 13 |
| SI-07-04 | MADR 4.0 template body byte-identical (provenance SHA declared) | ✓ VERIFIED | `docs/adr/0000-template.md` declares `08dac30ed895cf728fc7da95f9702ca4dd5ab900` 1×; `test_adr_template.py::test_adr_template_declares_madr_4_0_provenance` enforces |
| SI-07-05 | D6 subprocess invariant — exactly 2 src/ subprocess importers | ✓ VERIFIED | `grep -rn "import subprocess" src/aws_eks_helm_deploy/` = 2 (helm/client.py, chart/oci.py) — unchanged from Phase 4 lock-in |
| SI-07-06 | Concurrency group `docs-deploy-${{ github.ref }}` with `cancel-in-progress: false` | ✓ VERIFIED | Both literals present in docs.yml |
| SI-07-07 | D10 placeholder in SECURITY.md AND migration guide AND repo-settings.md | ✓ VERIFIED | 5 matches total across the 3 files (expected ≥4): SECURITY.md 1×, migration guide 2×, repo-settings.md 2× |

## Known deviations (documented, NOT blockers)

1. **07-04 `git stash` once during execution.** The Plan 07-04 executor used `git stash` once for a non-destructive context save during the migration-guide polish step. Flagged for transparency; no scope or content impact.

2. **07-07 replaced Phase 6 sections 5-8 of `docs/admin/repo-settings.md` with Phase 7 sections 5-9.**
   - Phase 6 sections 5-8 (Project Board, Labels, Docker Hub v1.x freeze, Sanity-check) were replaced by Phase 7 sections 5-9 (GitHub Pages enablement, `mike set-default v2`, `mike deploy --push v1`, Bitbucket Pipe Marketplace listing update, Docker Hub README deprecation banner).
   - **Phase 6 content preserved in git history at commit `cca2868` (Phase 6 merge commit) — verified via `git show cca2868 --stat | grep repo-settings` returns the 299-line Phase 6 file.**
   - **Acceptable because** the Phase 6 actions documented in sections 5-8 (Project Board v2 setup, breaking-change label seeding, Docker Hub freeze, post-Phase-6 sanity sweep) are already done on GitHub (Phase 6 PR #40 merged 2026-06-19); the maintainer-runbook only needs Phase 7-relevant manual steps going forward into the v2.0.0 tag-cut ceremony.
   - This deviation is intentional and aligned with D11 ("Phase 7 PR body lists every maintainer manual step with exact commands; mirrors Phase 6 `docs/admin/repo-settings.md` shape"). Documented inline in the file under `## Notes (Phase 7 — sections 5-9)`.

3. **Pre-existing legacy ruff/format issues on `pipe/`, `test/acceptance/`, and 2 scripts.** 55 ruff errors + 3 format pendings are pre-existing on `main` (verified by checking out main and re-running). Phase 7 introduces zero new lint regressions. Logged in `deferred-items.md`.

## Plan execution summary

- **07-01** — mkdocs scaffolding + nav + theme: shipped (commit 8878009, "scaffold mkdocs-material site + nav skeleton").
- **07-02** — 9 MADR ADRs + 0000-template: shipped (commits 2917283, ff559dc).
- **07-03** — Variable generator + drift CI gate: shipped (commit b1f2ea0 "variable reference generator + docs-drift CI gate"). No formal plan-summary commit (per spec — `feat(07)` carried the work).
- **07-04** — Migration guide move + polish + examples corpus: shipped (commits c017eab, 9049784, 2f9df6f, 62cafbf, fad70df). Plan-summary commit present.
- **07-05** — docs.yml deploy workflow + mike v1 + v2 publish: shipped (commit a97b8a3 "feat(07): add docs.yml — GitHub Pages deploy via mkdocs + mike").
- **07-06** — README badge polish + SECURITY 6-month + CONTRIBUTING + CoC: shipped (commits c4d8fcc, 8a0b616, 5d34b7a, a6670c2). Plan-summary commit present.
- **07-07** — Repo-settings §§5-9 + PR template ceremony checklist: shipped (commits a7a813d, 926bf9b).
- **Branch total:** 21 commits ahead of `main` on `phase/07-documentation-site-and-migration`.

## Overall verdict

**PASS.**

Phase 7 delivers its goal end-to-end: the README is the entry point (10-badge row, 60-second quickstart, docs-site + marketplace + migration links); the versioned mkdocs-material site is fully wired (mkdocs.yml + docs.yml deploy workflow + mike alias strategy + auto-generated `/v2/reference/variables.md` + CI drift gate); the migration guide lives at `docs/migration/v1-to-v2.md` (history-preserving `git mv` from `docs/guides/`) and covers every Phase-5+Phase-6 breaking change; 9 MADR-4.0 ADRs cover every architectural decision shipped in Phases 1-6 (verbatim MADR-4.0 provenance SHA `08dac30…5ab900` declared in the template); the examples corpus (4 production scenarios + before/after migration trio) is lint-clean; SECURITY.md/CONTRIBUTING.md/CODE_OF_CONDUCT.md governance triad is verified by structural tests; D10 6-month placeholder and the 90-day disclosure window are both present. All 7 Security Invariants hold; all 9 REQs satisfied; all 16 mechanical gates pass. The repo is ready for the v2.0.0 tag-cut ceremony (manual `git tag v2.0.0 && git push --tags` by Yves, followed by the release.yml sign+SBOM+GHCR publish).

---

_Verified: 2026-06-21_
_Verifier: Claude (gsd-verifier, Opus 4.7)_
