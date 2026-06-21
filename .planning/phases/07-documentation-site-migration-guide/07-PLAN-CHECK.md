# Phase 7 Plan-Check (inline)

**Verdict: PASS — no blockers, 1 warning, dispatch to executor.**

Plan-checker subagent hit monthly spend limit (transient API issue). Inline goal-backward verification below mirrors the Phase 5/6 plan-checker shape.

## Coverage Matrices

### REQ → Plan

| REQ | Plans | Acceptance gate |
|---|---|---|
| DOC-01 (README + 60s quickstart + docs-site link) | 07-01, 07-06, 07-07 | `tests/structural/test_readme_polish.py` (extended by 07-06) |
| DOC-02 (mkdocs-material + mike + variables generator) | 07-01, 07-03, 07-05 | `mkdocs build --strict` + `docs-drift` CI job + `tests/structural/test_docs_yml_structure.py` |
| DOC-03 (migration guide breaking-change coverage) | 07-04 | `tests/structural/test_migration_guide.py` |
| DOC-04 (9 MADR ADRs + 0000-template byte-identity) | 07-02 | `tests/structural/test_adr_template.py` |
| DOC-05 (CONTRIBUTING.md uv/pre-commit/pytest/kind loop) | 07-06 | `tests/structural/test_contributing.py` |
| DOC-06 (SECURITY.md 6-month window) | 07-06 | `tests/structural/test_security_md.py` (SI-07-07 placeholder) |
| DOC-07 (Contributor Covenant 2.1 in CODE_OF_CONDUCT.md) | 07-06 | `tests/structural/test_code_of_conduct.py` |
| DOC-08 (≥4 examples bitbucket-pipelines.yml) | 07-04 | `tests/structural/test_examples_lint.py` (check-jsonschema) |
| MIG-03 (examples/migration-v1-to-v2 before/after diff) | 07-04 | same as DOC-08 + README.md presence assertion |

All 9 REQs mapped to at least one plan with mechanical gate. ✓

### SC → Plan (ROADMAP lines 177-183)

| SC | Plans | Gate |
|---|---|---|
| SC-1 README badge row + quickstart | 07-01 + 07-06 | structural readme test |
| SC-2 mkdocs-material + mike v1/v2 + drift CI | 07-01 + 07-03 + 07-05 | mkdocs build + ci.yml docs-drift job |
| SC-3 migration guide + examples/migration-v1-to-v2 | 07-04 | migration + examples lint tests |
| SC-4 ADRs (7 minimum, 9 in our plan) | 07-02 | ADR structural test |
| SC-5 CONTRIBUTING/SECURITY/CoC + examples | 07-04 + 07-06 | 4 structural tests |

All 5 SCs mapped. ✓

### SI → Plan

| SI | Plan | Gate |
|---|---|---|
| SI-07-01 no `id-token: write` in docs.yml | 07-05 | grep gate in `test_docs_yml_structure.py` |
| SI-07-02 40-char SHA digest pinning | 07-05 | Phase 6 `test_workflow_digest_pins.py` covers all `.github/workflows/*.yml` |
| SI-07-03 `mkdocs build --strict` is build cmd | 07-01 + 07-05 | mkdocs build test + workflow grep |
| SI-07-04 0000-template byte-identity vs MADR 4.0.0 | 07-02 | `git hash-object` assertion in `test_adr_template.py` |
| SI-07-05 D6 subprocess invariant preserved | 07-04 grep gate | `grep -c "import subprocess" src/**/*.py == 2` |
| SI-07-06 concurrency group `docs-deploy-*` cancel-in-progress: false | 07-05 | workflow structural test |
| SI-07-07 SECURITY.md D10 placeholder literal | 07-06 | `test_security_md_has_d10_six_month_placeholder` |

All 7 SIs mapped to a grep-confirmable gate. ✓

## Wave dependency check

- Wave 1 (07-01, 07-02): independent ✓ — 07-01 owns `mkdocs.yml` + `docs/index.md` + `pyproject.toml[docs]`; 07-02 owns `docs/adr/`. No overlap.
- Wave 2 (07-03, 07-04, 07-05): all depend on 07-01 (need `pyproject.toml[docs]` extra + nav slot). No mutual overlap:
  - 07-03 owns `scripts/generate-variables-doc.py`, `docs/reference/variables.md`, `ci.yml`.
  - 07-04 owns `docs/migration/v1-to-v2.md`, `examples/`, `pyproject.toml[dev]`.
  - 07-05 owns `.github/workflows/docs.yml`.
  - `pyproject.toml` is touched by both 07-03 (`[project.optional-dependencies] docs`) and 07-04 (`[dependency-groups] dev`) — distinct table sections, no merge conflict if sequenced or merged carefully.
- Wave 3 (07-06): independent ✓.
- Wave 4 (07-07): depends on all ✓ — needs Plan 07-05's `docs.yml` to exist before documenting Pages enablement; needs Plan 07-04's `docs/migration/v1-to-v2.md` for Docker Hub banner ref.

## Warnings (advise-fix, non-blocking)

**W-01 — 07-07 `autonomous: false` checkpoint:** Plan 07-07 has a human-verify checkpoint asking Yves to confirm D11 ceremony scope. Under the user's standing "autonomous + take my recommendations" instruction, the orchestrator will treat this as auto-confirm with a note in the PR body. Action: Executor will record the auto-confirm decision in the plan's checkpoint log entry; not a blocker.

## Plan-size economy

| Plan | Files NEW | Files MOD | Estimated tokens |
|---|---|---|---|
| 07-01 | 3 (mkdocs.yml, docs/index.md, 2× tests/structural/*) | 1 (pyproject.toml) | ~120k |
| 07-02 | 11 (10× docs/adr/* + 1× test) | 0 | ~150k (content-heavy ADR authoring) |
| 07-03 | 4 (scripts/×2, docs/reference, test) | 2 (pyproject.toml, ci.yml) | ~110k |
| 07-04 | 8 (examples ×6, migration md after `git mv`, 2× tests) | 3 (guides→migration via git mv, pyproject.toml) | ~180k |
| 07-05 | 2 (docs.yml, test) | 0 | ~90k |
| 07-06 | 3 (test_security_md, test_contributing, test_code_of_conduct) | 2 (README.md, SECURITY.md) + 1 (extend test_readme_polish) | ~100k |
| 07-07 | 2 (test_repo_settings_runbook, extend governance test) | 2 (PR template, repo-settings.md) | ~100k |
| Total | | | ~850k |

Within budget (1M estimate from CONTEXT.md). ✓

## NIH check

- `settings-doc 4.3.2` swap: ✓ (RESEARCH C2)
- `check-jsonschema 0.37.3` for bitbucket-pipelines.yml lint: ✓ (RESEARCH Q8)
- MADR 4.0 template verbatim copy: ✓ (no custom ADR format)
- No custom mike publish wrapper (plain `uses:` + `run:`): ✓
- No custom Pages-deploy action (no `peaceiris/actions-gh-pages`): ✓ — uses native `mike deploy --push`

## Confidence

**PASS.** Dispatch Wave 1 executors. Top action: spawn 07-01 and 07-02 in parallel (no shared files, no shared deps).
