---
phase: 7
slug: documentation-site-migration-guide
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-21
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 7 ships docs + ADRs + examples + 1 new CI workflow + 1 extension to ci.yml + 1 new generator script. "Tests" are structural assertions on Markdown / YAML / Python script files plus the docs build itself. Derived from 07-RESEARCH.md "Validation Architecture" + "Security Domain" + RESEARCH Q10 pitfall analysis. Mirrors the Phase 6 VALIDATION.md shape.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 (already configured) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/structural -q --no-cov` |
| **Full suite command** | `uv run pytest tests/ -q --no-cov` |
| **Unit tier (Python-source coverage, MUST stay at 100%)** | `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` |
| **Docs build smoke check** | `uv run mkdocs build --strict --site-dir /tmp/mkdocs-test-site` exits 0 |
| **Examples lint smoke check** | `uv run check-jsonschema --builtin-schema vendor.bitbucket-pipelines examples/**/*.yml` exits 0 |
| **Drift gate smoke check** | `bash scripts/check-variables-drift.sh` exits 0 |
| **Workflow smoke check** | Phase 7 PR's `ci` workflow run passes (the docs-drift extension must be green) |
| **Estimated runtime** | ~10 s structural + ~5 s mkdocs build + ~3 s check-jsonschema |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/structural -q --no-cov` (~10 s)
- **After every wave merge:** `uv run pytest tests/ -q --no-cov` (full suite)
- **Before `/gsd-verify-work`:** Full suite green AND `uv run mypy --strict src/aws_eks_helm_deploy` clean AND `uv run ruff check src/ tests/ scripts/` clean AND `uv run mkdocs build --strict` clean
- **Phase gate:** Phase 7 PR's ci run passes on its own first invocation; the new `docs-drift` job is green; structural tests catch any regression.
- **Max feedback latency:** ~15 s (structural test + mkdocs build tier)

---

## Success Criteria → Plan Mapping (ROADMAP lines 177-183)

| SC | Wording (abbreviated) | Plan(s) | REQ(s) |
|----|-----------------------|---------|--------|
| SC-1 | README is the entry doc (badge row + 60-second quickstart + docs-site / marketplace / migration links) | 07-01 (docs-site link in index hero), 07-06 (badge row + migration link + docs-site link) | DOC-01 |
| SC-2 | mkdocs-material + mike site deployed via `.github/workflows/docs.yml`; `mike list` shows v1 + v2; `/v2/reference/variables.md` is auto-generated; CI fails on drift | 07-01 (mkdocs.yml + nav), 07-03 (settings-doc + drift CI gate), 07-05 (docs.yml deploy workflow), 07-07 (Pages enablement + mike v1 one-shot runbook) | DOC-02 |
| SC-3 | `docs/migration/v1-to-v2.md` documents every breaking change; `examples/migration-v1-to-v2/` ships before/after diff with line-level explanations | 07-04 (move + polish + examples corpus + MIG-03 trio) | DOC-03, MIG-03 |
| SC-4 | `docs/adr/` contains MADR ADRs covering ≥ 7 architectural decisions | 07-02 (9 MADR ADRs + 0000-template.md + index.md) | DOC-04 |
| SC-5 | CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md present + linked from docs site; `examples/` ships ≥ 4 end-to-end snippets | 07-04 (4 example dirs + linked from docs), 07-06 (SECURITY.md polish + CONTRIBUTING / CoC verification) | DOC-05, DOC-06, DOC-07, DOC-08 |

---

## REQ → Plan Coverage Table

| Req ID | Behavior | Plan(s) | Test Type | Automated Command |
|--------|----------|---------|-----------|-------------------|
| DOC-01 | README badge row + 60s quickstart + docs-site link | 07-01, 07-06 | structural | `uv run pytest tests/structural/test_readme_polish.py -x` |
| DOC-02 | mkdocs-material + mike site builds strict-clean | 07-01, 07-03, 07-05 | structural | `uv run pytest tests/structural/test_mkdocs_build.py tests/structural/test_variables_doc_generator.py tests/structural/test_docs_yml_structure.py -x` |
| DOC-03 | Migration guide covers every breaking change | 07-04 | structural | `uv run pytest tests/structural/test_migration_guide.py -x` |
| DOC-04 | 9 MADR ADRs + 0000-template byte-identical to upstream | 07-02 | structural | `uv run pytest tests/structural/test_adr_template.py -x` |
| DOC-05 | CONTRIBUTING.md documents uv/pre-commit/pytest/kind | 07-06 | structural | `uv run pytest tests/structural/test_contributing.py -x` |
| DOC-06 | SECURITY.md has 6-month placeholder + 90-day flow | 07-06 | structural | `uv run pytest tests/structural/test_security_md.py -x` |
| DOC-07 | CODE_OF_CONDUCT.md references Contributor Covenant 2.1 | 07-06 | structural | `uv run pytest tests/structural/test_code_of_conduct.py -x` |
| DOC-08 | examples/{basic,oidc-only,oci-chart,multi-env}/bitbucket-pipelines.yml lint-clean | 07-04 | structural | `uv run pytest tests/structural/test_examples_lint.py -x` |
| MIG-03 | examples/migration-v1-to-v2/{before,after,README} ship | 07-04 | structural | `uv run pytest tests/structural/test_examples_lint.py::test_migration_dir_has_before_after_readme -x` |

**Coverage:** 9/9 REQs (DOC-01..08 + MIG-03) — each mapped to ≥ 1 plan and ≥ 1 structural test. Zero unmapped REQs.

---

## Per-Task Verification Map

*Populated by planner using suggested skeleton. Docs/Markdown additions use grep-based acceptance_criteria; Python helpers (`scripts/generate-variables-doc.py`) and YAML workflow modifications use pytest assertions in `tests/structural/`.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|----------|-----------|-------------------|-------------|--------|
| 07-01-1 | 01 | 1 | DOC-02 | SI-07-03 | pyproject.toml docs extra pins mkdocs-material 9.7.6 + mike 2.2.0; structural tests ship | structural | `uv run pytest tests/structural/test_mkdocs_build.py tests/structural/test_readme_polish.py -x` | ❌ W0 | ⬜ pending |
| 07-01-2 | 01 | 1 | DOC-02 SC-1 | SI-07-03 | mkdocs.yml + docs/index.md + nav skeleton + 4 stubs; `mkdocs build --strict` exits 0 | structural | `uv run mkdocs build --strict --site-dir /tmp/mkdocs-test-site` | ❌ W0 | ⬜ pending |
| 07-01-3 | 01 | 1 | DOC-02 | — | Full suite green; coverage gate holds | unit + structural | `uv run pytest tests/unit tests/structural --cov-fail-under=100` | ❌ W0 | ⬜ pending |
| 07-02-1 | 02 | 1 | DOC-04 | SI-07-04 | 0000-template.md ships verbatim from MADR 4.0 tag (blob SHA `08dac30...`) | structural | `uv run pytest tests/structural/test_adr_template.py::test_adr_template_declares_madr_4_0_provenance -x` | ❌ W0 | ⬜ pending |
| 07-02-2 | 02 | 1 | DOC-04 | — | 9 ADRs ship with MADR sections | structural | `uv run pytest tests/structural/test_adr_template.py::test_all_nine_adrs_exist tests/structural/test_adr_template.py::test_each_adr_has_madr_sections -x` | ❌ W0 | ⬜ pending |
| 07-02-3 | 02 | 1 | DOC-04 | — | docs/adr/index.md lists all 9 ADRs | structural | `uv run pytest tests/structural/test_adr_template.py::test_adr_index_exists_and_lists_all_nine -x` | ❌ W0 | ⬜ pending |
| 07-03-1 | 03 | 2 | DOC-02 SC-2 | T-07-V10 | settings-doc 4.3.2 pinned; wrapper ≤30 LOC; correct settings path (C1) | structural | `uv run pytest tests/structural/test_variables_doc_generator.py::test_generator_script_is_under_30_loc tests/structural/test_variables_doc_generator.py::test_generator_references_corrected_settings_path -x` | ❌ W0 | ⬜ pending |
| 07-03-2 | 03 | 2 | DOC-02 SC-2 | T-07-V5 | drift gate script runs + exits 0 + D5 banner present | structural | `bash scripts/check-variables-drift.sh && uv run pytest tests/structural/test_variables_doc_generator.py::test_drift_gate_exits_zero -x` | ❌ W0 | ⬜ pending |
| 07-03-3 | 03 | 2 | DOC-02 SC-2 | SI-07-01 | ci.yml 8th docs-drift job, no id-token, SHA pins clean | structural | `uv run pytest tests/structural/test_ci_yml_structure.py::test_docs_drift_job_present tests/structural/test_workflow_digest_pins.py -x` | ❌ W0 | ⬜ pending |
| 07-04-1 | 04 | 2 | DOC-03 | SI-07-07 | git mv preserves history; D10 placeholder + all breaking-change tokens present; `mkdocs --strict` green | structural | `uv run pytest tests/structural/test_migration_guide.py -x && uv run mkdocs build --strict` | ❌ W0 | ⬜ pending |
| 07-04-2 | 04 | 2 | DOC-08, MIG-03 | T-07-V5 | examples corpus ships; 5 dirs + 6 yml + README | structural | `uv run pytest tests/structural/test_examples_lint.py::test_all_required_example_subdirs_exist tests/structural/test_examples_lint.py::test_migration_dir_has_before_after_readme -x` | ❌ W0 | ⬜ pending |
| 07-04-3 | 04 | 2 | DOC-08, MIG-03 | T-07-V5 | check-jsonschema 0.37.3 lint-clean against every example yml | structural | `uv run pytest tests/structural/test_examples_lint.py::test_examples_yamls_lint_clean_via_check_jsonschema -x` | ❌ W0 | ⬜ pending |
| 07-05-1 | 05 | 2 | DOC-02 SC-1, SC-3 | SI-07-01, SI-07-02, SI-07-06 | docs.yml ships with concurrency, no id-token, SHA pins, strict build, mike deploy | structural | `uv run pytest tests/structural/test_docs_yml_structure.py -x` | ❌ W0 | ⬜ pending |
| 07-05-2 | 05 | 2 | DOC-02 SC-1 | SI-07-02 | All workflow uses: lines 40-char SHA pinned (Phase 6 carry-forward) | structural | `uv run pytest tests/structural/test_workflow_digest_pins.py -x` | ❌ W0 | ⬜ pending |
| 07-06-1 | 06 | 3 | DOC-01 | T-07-V14 | README has 10 badges (7 existing + 3 additive); docs-site link + migration link | structural | `uv run pytest tests/structural/test_readme_polish.py -x` | ❌ W0 | ⬜ pending |
| 07-06-2 | 06 | 3 | DOC-06 | SI-07-07 | SECURITY.md has D10 6-month placeholder verbatim + unchanged 90-day disclosure flow | structural | `uv run pytest tests/structural/test_security_md.py -x` | ❌ W0 | ⬜ pending |
| 07-06-3 | 06 | 3 | DOC-05, DOC-07 | — | CONTRIBUTING.md + CODE_OF_CONDUCT.md verification (no edit if already correct) | structural | `uv run pytest tests/structural/test_contributing.py tests/structural/test_code_of_conduct.py -x` | ❌ W0 | ⬜ pending |
| 07-07-1 | 07 | 4 | DOC-01..08, MIG-03 | SI-07-07 | docs/admin/repo-settings.md sections 5-9 + sections 1-4 byte-identical | structural | `uv run pytest tests/structural/test_repo_settings_runbook.py -x` | ❌ W0 | ⬜ pending |
| 07-07-2 | 07 | 4 | (cross-REQ) | — | PR template extended with v2.0.0 maintainer checklist | structural | `uv run pytest tests/structural/test_governance_files.py::test_pr_template_has_maintainer_checklist_for_v2_release_ceremony -x` | ❌ W0 | ⬜ pending |
| 07-07-3 | 07 | 4 | (cross-REQ) | — | Maintainer checkpoint approval (D11 release ceremony scope) | manual | Reply `approved` to the checkpoint | manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Phase 7 EXTENDS the existing `tests/structural/` directory (created in Phase 6). Wave 0 files to create (all new):

- [ ] `tests/structural/test_mkdocs_build.py` — DOC-02 SC-1 strict-build gate (Plan 07-01)
- [ ] `tests/structural/test_readme_polish.py` — DOC-01 badge + link gate (Plan 07-01 ships placeholder; Plan 07-06 hardens)
- [ ] `tests/structural/test_adr_template.py` — DOC-04 MADR + 9-ADR gate (Plan 07-02)
- [ ] `tests/structural/test_variables_doc_generator.py` — DOC-02 SC-2 generator + drift gate (Plan 07-03)
- [ ] `tests/structural/test_migration_guide.py` — DOC-03 + SI-07-07 placeholder gate (Plan 07-04)
- [ ] `tests/structural/test_examples_lint.py` — DOC-08 + MIG-03 gate (Plan 07-04)
- [ ] `tests/structural/test_docs_yml_structure.py` — DOC-02 SC-1 + Q10 pitfalls #1/#4/#7 gate (Plan 07-05)
- [ ] `tests/structural/test_security_md.py` — DOC-06 + SI-07-07 gate (Plan 07-06)
- [ ] `tests/structural/test_contributing.py` — DOC-05 gate (Plan 07-06)
- [ ] `tests/structural/test_code_of_conduct.py` — DOC-07 gate (Plan 07-06)
- [ ] `tests/structural/test_repo_settings_runbook.py` — D11 release ceremony gate (Plan 07-07)
- [ ] `scripts/generate-variables-doc.py` — wrapper around `settings-doc 4.3.2` (Plan 07-03)
- [ ] `scripts/check-variables-drift.sh` — CI drift gate (Plan 07-03)
- [ ] `pyproject.toml` — add `[project.optional-dependencies] docs` extra (Plan 07-01 + 07-03) and `check-jsonschema == 0.37.3` to dev group (Plan 07-04)

Plans 07-03 + 07-07 also EXTEND existing files:
- [ ] `.github/workflows/ci.yml` — add 8th `docs-drift` job (Plan 07-03)
- [ ] `tests/structural/test_ci_yml_structure.py` — add `test_docs_drift_job_present` fn (Plan 07-03)
- [ ] `tests/structural/test_governance_files.py` — add `test_pr_template_has_maintainer_checklist_for_v2_release_ceremony` fn (Plan 07-07)
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` — add maintainer-checklist section (Plan 07-07)
- [ ] `docs/admin/repo-settings.md` — add sections 5-9 (Plan 07-07)

---

## Manual-Only Verifications (Out of Band)

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pages enabled with gh-pages source | DOC-02 SC-3 prerequisite | Maintainer-only repo setting (RESEARCH Q6) | Yves runs `gh api repos/yves-vogl/aws-eks-helm-deploy/pages -X POST -f source[branch]=gh-pages -f source[path]=/` (docs/admin/repo-settings.md §5) |
| mike default alias set to v2 | DOC-02 SC-3 | One-shot, not CI-safe (Q10 pitfall #5) | Yves runs `uv run mike set-default v2 --push` from a gh-pages worktree (docs/admin/repo-settings.md §6) |
| v1 frozen snapshot deployed under /v1/ | DOC-02 SC-3 | One-shot, not CI-safe (Q10 pitfall #6) | Yves runs `uv run mike deploy --push v1` from a v1.3.0 checkout (docs/admin/repo-settings.md §7) |
| Bitbucket Pipe Marketplace listing updated | D11 | Web UI only | Yves updates listing at https://bitbucket.org/.../pipe-info (docs/admin/repo-settings.md §8) |
| Docker Hub README banner posted | MIG-01 / D11 | Web UI only | Yves pastes deprecation banner at https://hub.docker.com/.../general (docs/admin/repo-settings.md §9) |
| End-of-support date replaces `2026-MM-DD` placeholder | D10 | Compute = v2.0.0 release date + 6 months | After tag-cut, Yves opens a follow-up PR replacing the placeholder in SECURITY.md + docs/migration/v1-to-v2.md + docs/admin/repo-settings.md §7+§9 |
| Live docs site responds at the canonical URL | DOC-02 SC-3 | Real network check | `curl -sf https://yves-vogl.github.io/aws-eks-helm-deploy/ | head -10` after Pages enabled |
| OpenSSF Scorecard score ≥ 8/10 | (Phase 6 carry-forward) | Live API | `curl https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy` |

Plan 07-07 ships `docs/admin/repo-settings.md` sections 5-9 with EXACT `gh api` / `mike` commands.

---

## Security Domain (from 07-RESEARCH.md)

### Applicable ASVS Categories (ASVS Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (CI surface) | `id-token: write` NOT requested in docs.yml; least-privilege `permissions:` block |
| V5 Input Validation | yes (examples + drift) | `check-jsonschema vendor.bitbucket-pipelines` lints `examples/`; drift gate prevents `docs/reference/variables.md` hand-edits |
| V10 Malicious Code | yes (action pins) | every action in `.github/workflows/*.yml` pinned to 40-char SHA; Dependabot keeps them current |
| V14 Configuration | yes (mkdocs / mike / Pages) | `mkdocs build --strict`; mike concurrency group `cancel-in-progress: false`; Pages branch pinned to `gh-pages` |

### Known Threat Patterns

| Threat ID | Pattern | STRIDE | Standard Mitigation |
|-----------|---------|--------|---------------------|
| T-07-V10 | Compromised mkdocs-material / mike / settings-doc / check-jsonschema via mutable tag | Tampering | All deps `==` pinned (RESEARCH Q1, Q2, Q7, Q8); Dependabot pip ecosystem keeps current |
| T-07-V14-PT | Malicious `pull_request_target` in docs.yml | EoP | docs.yml uses `push` + `workflow_dispatch` only; structural test asserts |
| T-07-V14-OIDC | OIDC token write in docs.yml | InfoDisc | `permissions: contents: write` only; NO `id-token: write`; structural test asserts |
| T-07-V14-RACE | mike push non-fast-forward on gh-pages | Repudiation / DoS | `concurrency.cancel-in-progress: false` queues runs (Q10 pitfall #1) |
| T-07-V14-ORDER | mkdocs strict fails because variables.md missing | Tampering | generator step ordered BEFORE strict build (Q10 pitfall #4); structural test asserts |
| T-07-V5-DRIFT | docs/reference/variables.md drifts from settings.py | Tampering | drift gate `bash scripts/check-variables-drift.sh` in ci.yml docs-drift job |
| T-07-V4 | docs site renders user-submitted Markdown | XSS | N/A — docs repo-authored; no user input surface |
| T-07-V4-CC0 | MADR template license incompat | Acceptance | CC0 → Apache-2.0 is compatible (RESEARCH Q10 pitfall #8) |

### Package Legitimacy Audit (RESEARCH §Sources / Don't Hand-Roll table)

| Package | Version | Source | Disposition |
|---------|---------|--------|-------------|
| `mkdocs-material` | 9.7.6 | https://pypi.org/project/mkdocs-material/9.7.6/ (MIT) | OK — verified 2026-06-21 |
| `mike` | 2.2.0 | https://pypi.org/project/mike/2.2.0/ (BSD-3-Clause) | OK — verified 2026-06-21 |
| `settings-doc` | 4.3.2 | https://pypi.org/project/settings-doc/4.3.2/ (MIT) | OK — verified 2026-06-21 |
| `check-jsonschema` | 0.37.3 | https://pypi.org/project/check-jsonschema/0.37.3/ (Apache-2.0) | OK — verified 2026-06-21 |

NONE are `[ASSUMED]` / `[SUS]` / `[SLOP]` — all 4 are well-established (≥ 10k weekly downloads; tracked changelogs; identified PyPI maintainers). No package-legitimacy human checkpoint required.

---

## Security Invariants (Phase 7 verifier MUST enforce)

| ID | Invariant | Mechanical gate |
|----|-----------|-----------------|
| **SI-07-01** | `docs.yml` MUST NOT request `id-token: write` (Phase 6 SI-06-01 carry-forward; PR + push-triggered workflows MUST NOT have OIDC write) | `grep -F 'id-token: write' .github/workflows/docs.yml` returns 0 hits |
| **SI-07-02** | All actions in `docs.yml` (and every workflow under `.github/workflows/`) pinned to 40-char SHA digests | `uv run pytest tests/structural/test_workflow_digest_pins.py -x` exits 0 |
| **SI-07-03** | `mkdocs build --strict` is the build command (fail on warnings) | `grep -F 'mkdocs build --strict' .github/workflows/docs.yml` returns 1 hit AND `grep -F 'strict: true' mkdocs.yml` returns 1 hit |
| **SI-07-04** | `docs/adr/0000-template.md` is verbatim from MADR tag 4.0.0 blob SHA `08dac30ed895cf728fc7da95f9702ca4dd5ab900` | `grep -F '08dac30ed895cf728fc7da95f9702ca4dd5ab900' docs/adr/0000-template.md` returns 1 hit; expected SHA recorded below for verifier reproduction |
| **SI-07-05** | D6 subprocess invariant preserved — exactly 2 `src/` files import subprocess (`helm/client.py`, `chart/oci.py`); Phase 7 introduces ZERO new src/ subprocess callers | `grep -rE '^import subprocess' src/aws_eks_helm_deploy/ \| wc -l` returns 2 |
| **SI-07-06** | Concurrency group `docs-deploy-${{ github.ref }}` with `cancel-in-progress: false` in `.github/workflows/docs.yml` | `grep -F 'docs-deploy-${{ github.ref }}' .github/workflows/docs.yml` returns 1 hit AND `grep -F 'cancel-in-progress: false' .github/workflows/docs.yml` returns 1 hit |
| **SI-07-07** | `SECURITY.md` AND `docs/migration/v1-to-v2.md` AND `docs/admin/repo-settings.md` contain the literal `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` placeholder | `grep -F '2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.' SECURITY.md docs/migration/v1-to-v2.md docs/admin/repo-settings.md \| wc -l` returns ≥ 4 (1+1+2-3) |

### Expected SHA / digest values for verifier reproduction

| Asset | Expected SHA | How verifier reproduces |
|-------|--------------|-------------------------|
| `docs/adr/0000-template.md` body (after the 4-line provenance comment header) | upstream MADR tag 4.0.0 blob SHA `08dac30ed895cf728fc7da95f9702ca4dd5ab900` | `curl -fsSL https://raw.githubusercontent.com/adr/madr/4.0.0/template/adr-template.md \| git hash-object --stdin` returns `08dac30ed895cf728fc7da95f9702ca4dd5ab900`; verifier compares against `tail -n +N docs/adr/0000-template.md \| git hash-object --stdin` (N = number of leading provenance comment lines + 1 blank; documented in 07-02-SUMMARY.md) |
| `actions/checkout@v4.2.2` in docs.yml | `11bd71901bbe5b1630ceea73d27597364c9af683` | `gh api repos/actions/checkout/git/refs/tags/v4.2.2 --jq .object.sha` |
| `astral-sh/setup-uv@v3.2.4` in docs.yml | `caf0cab7a618c569241d31dcd442f54681755d39` | `gh api repos/astral-sh/setup-uv/git/refs/tags/v3.2.4 --jq .object.sha` |

---

## Mechanical Gates Verifier MUST Run

```bash
# 1. mkdocs strict-build green
uv run mkdocs build --strict --site-dir /tmp/mkdocs-test-site

# 2. Drift gate (compares regenerated docs/reference/variables.md against committed)
uv run scripts/generate-variables-doc.py
git diff --exit-code -- docs/reference/variables.md

# (or equivalently:)
bash scripts/check-variables-drift.sh

# 3. Examples lint (SchemaStore vendor.bitbucket-pipelines)
uv run check-jsonschema --builtin-schema vendor.bitbucket-pipelines \
  examples/basic/bitbucket-pipelines.yml \
  examples/oidc-only/bitbucket-pipelines.yml \
  examples/oci-chart/bitbucket-pipelines.yml \
  examples/multi-env/bitbucket-pipelines.yml \
  examples/migration-v1-to-v2/before.yml \
  examples/migration-v1-to-v2/after.yml

# 4. D6 subprocess invariant
grep -rE '^import subprocess' src/aws_eks_helm_deploy/ | wc -l   # MUST equal 2

# 5. ADR template byte-identity
grep -F '08dac30ed895cf728fc7da95f9702ca4dd5ab900' docs/adr/0000-template.md   # MUST return 1
# (For deeper verification, hash the body excluding the provenance comment.)

# 6. GitHub Actions SHA pin reproduction (RESEARCH Q5)
gh api repos/actions/checkout/git/refs/tags/v4.2.2 --jq .object.sha
# Expected: 11bd71901bbe5b1630ceea73d27597364c9af683
gh api repos/astral-sh/setup-uv/git/refs/tags/v3.2.4 --jq .object.sha
# Expected: caf0cab7a618c569241d31dcd442f54681755d39

# 7. SI-07-01 — no id-token in docs.yml
grep -F 'id-token: write' .github/workflows/docs.yml | wc -l   # MUST equal 0

# 8. SI-07-06 — concurrency group with cancel-in-progress: false
grep -F 'docs-deploy-${{ github.ref }}' .github/workflows/docs.yml | wc -l   # MUST equal 1
grep -F 'cancel-in-progress: false' .github/workflows/docs.yml | wc -l   # MUST equal 1

# 9. SI-07-07 — D10 placeholder across 3 files
grep -F '2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.' \
  SECURITY.md docs/migration/v1-to-v2.md docs/admin/repo-settings.md | wc -l   # MUST be >= 4

# 10. Full structural suite + coverage gate
uv run pytest tests/structural -q --no-cov
uv run pytest tests/unit tests/structural --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100
```

---

## Risk Inventory

| Risk ID | Risk | Likelihood | Impact | Mitigation |
|---------|------|------------|--------|------------|
| R-07-1 | mkdocs-material 9.7.6 has a latent bug exposed by mike 2.2.0 | LOW | MED | Strict-mode build catches build-time issues; Phase 7 PR is the smoke test (the PR itself must produce a green docs.yml run on first push to main); fallback: pin minor versions earlier (e.g., 9.7.5) — but pin is research-verified, so unlikely. |
| R-07-2 | Bitbucket SchemaStore vendor.bitbucket-pipelines schema lags Bitbucket platform features | LOW | LOW | check-jsonschema is offline-cacheable; if a schema lag rejects a valid Bitbucket key, suppress per-file or pin to an older schema bundle. Currently no known divergence (RESEARCH Q8). |
| R-07-3 | settings-doc Markdown output differs visibly from the existing README variable-table style | MED | LOW | Docs site is source-of-truth, not README; cosmetic deviation is acceptable. Plan 07-03 SUMMARY notes any deviation. RESEARCH §A3. |
| R-07-4 | `git mv docs/guides/v1-to-v2.md docs/migration/v1-to-v2.md` followed by accidental hand-edit breaks history-preservation | LOW | MED | Plan 07-04 Task 1 documents the exact `git mv` invocation; `git log --follow` verifies post-move. |
| R-07-5 | docs.yml first run fails because Pages was not enabled before merge | MED | LOW | Plan 07-07 Section 5 documents the prerequisite; PR-template checklist surfaces it; if missed, the docs.yml run fails with a clear error and Yves runs `gh api ... pages -X POST` after the fact. |
| R-07-6 | Maintainer forgets to run the post-merge ceremony steps (tag, mike v1, marketplace, Docker Hub) | MED | MED | PR-template maintainer-checklist is the principal mitigation; the structural test asserts the checklist is present in the template before merge. |
| R-07-7 | D10 placeholder is forgotten in the post-tag-cut follow-up PR, leaving a stale `2026-MM-DD` literal in published docs | MED | LOW | SI-07-07 grep gate; Plan 07-07 §Notes explicitly documents the multi-file replacement step; the placeholder string is loud and ungrammatical, increasing user-visible cost of leaving it stale. |

---

## Verifier Bar (mirrors Phase 6 VERIFICATION shape)

Phase 7 verifier MUST assert:

- 5 Success Criteria observable in shipped code (per ROADMAP Phase 7 SC1-SC5)
- 9 REQs covered by docs / examples / workflow / structural tests (DOC-01..08, MIG-03)
- 11 locked decisions D1-D11 honoured (with 2 research-driven corrections C1 + C2 applied)
- 3 ROADMAP risks mitigated (mkdocs-material maintenance, variable-reference drift, missed real-world breaking change)
- 7 plan-checker security invariants enforced (SI-07-01 to SI-07-07 grep gates above)
- 9 manual-only verifications documented in `docs/admin/repo-settings.md` for post-merge maintainer execution
- `tests/structural/` 11 NEW test files + 2 EXTENDED Phase 6 test files all green
- Phase 7 PR's own CI run passes (the new docs-drift job + every Phase 6 job stay green)

---

*Skeleton authored 2026-06-21 by Claude per Phase 7 planning mandate. Per-task rows post-execution-update.*
</content>
</invoke>
