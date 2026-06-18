---
phase: 04-oidc-chart-source-extensions
type: summary
status: draft
created: 2026-06-18
plans:
  - 04-01
  - 04-02
  - 04-03
  - 04-04
  - 04-05
  - 04-06
  - 04-07
waves: 4
requirements:
  - AUTH-03
  - AUTH-04
  - AUTH-05
  - AUTH-06
  - CHART-02
  - CHART-03
  - CHART-04
closes_issues:
  - 3
  - 7
---

# Phase 4 — OIDC & Chart Source Extensions (Plan Summary)

> Seven atomic plans across four execution waves. Closes #3 (OIDC) and #7 (chart sources). The first plan is a single-commit ROADMAP + REQUIREMENTS revision per CONTEXT D1 + RESEARCH §R1; the remaining six implement OIDC + IAM trust template + ChartSource Protocol + RepoChart + OciChart + Cosign verify + Dockerfile cosign stage.

## Wave timeline

| Wave | Plans (parallelisable) | What lands | Hard dependency |
|------|------------------------|------------|-----------------|
| **1** | **04-01** (atomic precursor — runs first within the wave, see ordering note below) → **04-02**, **04-04**, **04-05** | ROADMAP + REQUIREMENTS revision (D1) · Settings additions + AUTH-06 misconfig errors · IAM trust-policy template + JSON-validity test · `ChartSource` Protocol + `LocalChart` refactor + `select_chart_source` factory | none |
| **2** | **04-03**, **04-06** | `OidcWebIdentityStrategy` + `select_strategy` integration (AUTH-03, AUTH-04 revised) · `RepoChart` + new `HelmClient` `registry`/`pull` methods | 04-02 (settings), 04-05 (Protocol) |
| **3** | **04-07** | `OciChart` + Cosign verify subprocess in `chart/oci.py` + Dockerfile cosign-fetch stage + `registry:2` integration tests | 04-02, 04-05, 04-06 |
| **4** | (verification — handled by `gsd-verify-work`, no new plan) | `04-VERIFICATION.md` checks every REQ → green test | all of 04-01..07 |

### Wave-1 ordering note (Plan-Check obligation per CONTEXT D1 + RESEARCH §R1)

Plans 04-01, 04-02, 04-04, 04-05 are listed as Wave 1 because they have no cross-plan code dependency. **However 04-01 MUST land as the FIRST commit of the phase** — it is the atomic ROADMAP + REQUIREMENTS revision that supersedes ROADMAP SC1 + AUTH-04 wording. The Plan-Checker enforces "doc-edit lands before code in 04-03" by requiring 04-01's commit to land before 04-03's wave. In practice the executor lands 04-01 first, then 04-02 / 04-04 / 04-05 in parallel.

## Per-plan summary

| Plan | Title | Wave | REQs | Key risks mitigated |
|------|-------|------|------|---------------------|
| **04-01** | ROADMAP + REQUIREMENTS revision (D1 precursor) | 1 | AUTH-04 (revised) | R1 (atomic doc-edit before code), R10 (Plan-Checker AUTH-04 verification path) |
| **04-02** | Settings additions + AUTH-06 misconfig errors | 1 | AUTH-06 | R11 (alias consistency), R13 (`SecretStr` for `registry_password`) |
| **04-03** | `OidcWebIdentityStrategy` + `select_strategy` integration | 2 | AUTH-03, AUTH-04 (revised) | R2 (precedence regression), R3 (`botocore.UNSIGNED` import), R10, R11 |
| **04-04** | IAM trust-policy template + JSON-validity unit test | 1 | AUTH-05 | (StringLike erratum from CONTEXT D4) |
| **04-05** | `ChartSource` Protocol + `LocalChart` refactor + `select_chart_source` | 1 | CHART-02 (factory route), CHART-03 (factory route) | (legacy `resolve_local_chart` deletion gate — CONTEXT D3 Plan-Check obligation) |
| **04-06** | `RepoChart` + new `HelmClient` `registry`/`repo`/`pull` methods | 2 | CHART-02 | R4 (`--password-stdin`), R7 (single-subdir discovery) |
| **04-07** | `OciChart` + Cosign verify + Dockerfile cosign-fetch stage | 3 | CHART-03, CHART-04 | R4, R5 (`cosign verify` against ref not tarball), R6 (verify before pull), R7, R8 (tempdir cleanup on cosign failure), R9 (D5 doc-comment override), R12 (Dockerfile stage ordering) |

## Documents written by this planner

- `.planning/phases/04-oidc-chart-source-extensions/04-PLAN.md` — this file.
- `.planning/phases/04-oidc-chart-source-extensions/04-01-PLAN.md` through `04-07-PLAN.md` — atomic per-plan files.
- `.planning/phases/04-oidc-chart-source-extensions/04-VALIDATION.md` — REQ → plan → acceptance-criterion traceability table (consumed by `gsd-plan-checker` and `gsd-verify-work`).

## Documented deviations from CONTEXT D7 granularity guidance

D7 suggests 5–7 atomic plans. This planner ships **seven** — at the upper end of the suggestion — for these reasons:

1. **04-01 is split off from 04-03** so the ROADMAP + REQUIREMENTS doc-edit lands as its own commit (Plan-Check obligation per CONTEXT D1 + RESEARCH §R1).
2. **04-04 is independent** (IAM template + unit test only — no code dependency on auth/oidc.py); it can land in parallel within Wave 1.
3. **04-05 (refactor) and 04-06 (RepoChart) are split** so the `select_chart_source` factory + `LocalChart` refactor lands cleanly before `RepoChart` adds new `HelmClient` methods. Combining them risked a 5-file plan that violates the 2–3 task budget per plan.
4. **04-07 (OciChart + Cosign + Dockerfile) is a single plan** because the three sub-components are tightly coupled — `OciChart.resolve()` calls `subprocess.run` for both `helm pull` and `cosign verify`, and the Dockerfile stage is what ships the cosign binary to runtime. Splitting them would create a phase where OciChart code exists without the binary it depends on, blocking integration tests.

## Plan-Checker handoff

The Plan-Checker (`gsd-plan-checker`) should verify (also captured in `04-VALIDATION.md`):

1. **04-01 lands as commit #1** of the phase. The doc-edit is NOT deferred into 04-03's commit.
2. **AUTH-04 verification path** uses the **revised** wording from D1 (static keys win + WARN log), NOT the original ROADMAP SC1 ("OIDC wins"). See R10.
3. **`select_strategy` OIDC branch is AFTER the static-keys branch** in 04-03 — R2.
4. **`botocore.UNSIGNED` is imported and threaded** in `OidcWebIdentityStrategy.get_credentials` — R3.
5. **`chart/local.py::resolve_local_chart` (legacy function) is REMOVED** before the phase PR closes — CONTEXT D3 Plan-Check obligation.
6. **`subprocess.run` for cosign lives in `chart/oci.py`**, NOT `helm/client.py` — R9 / CONTEXT D5 scoped exception.
7. **`HelmClient` gains `registry_login`, `pull_oci`, `repo_add`, `repo_update`, `pull_repo`** methods (Option A in RESEARCH §7.4 — chosen for the Phase 3 invariant) — 04-06.
8. **`--password-stdin` (not `--password <value>`)** for `helm registry login` — R4.
9. **`registry_password: SecretStr | None`** in `settings.py` — R13. `get_secret_value()` is the only unwrap site (in 04-07's `OciChart.__init__` → `_run_helm_registry_login`).
10. **`cosign verify` runs against the OCI ref**, not the pulled tarball — R5.
11. **`cosign verify` runs BEFORE `helm pull`** — R6.
12. **Single-subdir discovery for `helm pull --untar`** — R7. Hardcoded paths forbidden.
13. **Dockerfile cosign-fetch stage lives BETWEEN `helm-fetch` and `runtime`** — R12.
14. **IAM trust-policy `sub` condition uses `StringLike`** (NOT `StringEquals`) — CONTEXT D4 erratum / RESEARCH §2 correction.

If any of these 14 obligations is missing in the per-plan files, the Plan-Checker MUST flag it before the executor begins Wave 1.
