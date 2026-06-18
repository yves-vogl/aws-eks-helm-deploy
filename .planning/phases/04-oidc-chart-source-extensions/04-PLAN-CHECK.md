# Phase 4 — Plan-Check Verdict

**Checker:** `gsd-plan-checker` (Opus, goal-backward stance)
**Date:** 2026-06-18
**Subject:** 7 atomic plans (04-01..04-07) + 04-PLAN.md + 04-VALIDATION.md
**Phase goal source:** ROADMAP.md Phase 4 (SC1 wording superseded by CONTEXT D1)

---

## Verdict: **APPROVED**

Plans deliver the phase goal goal-backward. Every Success Criterion has at least one plan that materializes it; every REQ (AUTH-03..06 + CHART-02..04) maps to a covering plan + a testable acceptance gate; every locked decision D1–D8 is honored (including the D4 `StringLike` erratum and the D5 `chart/oci.py` cosign subprocess exception); every R1–R13 risk from RESEARCH.md is mitigated in the named plan with a concrete code-shape and a grep/unit-test enforcement.

**Critical issues:** 0. **Blockers:** 0. **Plan-set is executable as-is.** Two NIT-level observations + one informational deviation acknowledgement are listed below — none block Wave 1.

The planner correctly took the harder of two paths on the helm-client-vs-chart-source layering question (chose RESEARCH §7.4 Option A — new typed `HelmClient` methods rather than inline subprocess in chart-source modules) and explicitly scoped the D5 cosign exception. The 04-01 atomic ROADMAP+REQUIREMENTS precursor commit is correctly enforced as commit #1.

---

## Per-Success-Criterion goal-backward walk

ROADMAP Phase 4 SC1 is post-D1-revision wording: "OIDC strategy ships; static keys win when both present; WARN log surfaces precedence; AUTH-06 misconfigs raise ConfigurationError before AWS call."

| SC | Plans delivering | Acceptance gate | Verdict |
|----|------------------|-----------------|---------|
| **SC1 (revised)** — OIDC strategy + static-keys-win + WARN + AUTH-06 | **04-01** (ROADMAP/REQ revision) + **04-02** (`oidc_audience` field) + **04-03** (OIDC strategy + select_strategy precedence + WARN + AUTH-06) | unit tests `test_select_strategy_static_keys_win_over_oidc_and_emits_warn` + `test_*_without_role_arn_raises_config_error` (5 AUTH-06 branches) + 04-03 line-number grep audit asserting static-keys branch precedes OIDC branch | **PASS** |
| **SC2** — IAM trust-policy template scoped to workspace + repo UUIDs | **04-04** (docs/guides/oidc-setup.md + 5-assertion unit test) | `test_template_has_all_required_placeholders` (5 placeholders), `test_sub_condition_uses_string_like_not_string_equals` (D4 erratum), `test_action_is_assume_role_with_web_identity`, `test_federated_principal_matches_bitbucket_oidc_issuer_pattern` | **PASS** |
| **SC3** — repo:// + oci:// + LocalChart routing via factory | **04-02** (settings) + **04-05** (Protocol + LocalChart + factory) + **04-06** (RepoChart) + **04-07** (OciChart) | `test_select_chart_source_routes_*_prefix_*` + integration tests against local `python -m http.server` (RepoChart) and `registry:2` (OciChart) | **PASS** |
| **SC4** — CHART_VERIFY=true → cosign verify → abort on failure | **04-02** (settings) + **04-07** (cosign subprocess + Dockerfile stage + acceptance test) | `test_resolve_runs_cosign_verify_BEFORE_helm_pull`, `test_resolve_cosign_verify_against_ref_not_tarball`, `test_resolve_cosign_failure_raises_chart_resolution_error_and_cleans_tempdir`, `test_resolve_verify_unconstrained_emits_warn`, acceptance `test_cosign_binary_in_path` | **PASS** |

---

## Per-plan column

| Plan | Wave | REQs covered | Risks addressed | Verdict | Notes |
|------|------|--------------|-----------------|---------|-------|
| **04-01** | 1 (first commit) | AUTH-04 (revised) | R1, R10 | **APPROVED** | Atomic doc-edit; whitelist limits to .planning/ROADMAP.md + .planning/REQUIREMENTS.md; load-bearing greps (`static keys win`, `auth.precedence.static_keys_won_over_oidc`, `2026-06-18 revision`) enforced in `<verify>`; existing `OIDC wins deterministically` negatively grep'd. |
| **04-02** | 1 | AUTH-03, AUTH-06, CHART-02, CHART-03, CHART-04 (env-var surface) | R11, R13 | **APPROVED** | 8 fields incl. `registry_password: SecretStr \| None` (R13). Deviation 2 (AUTH-06 raises live in 04-03, not in Settings) is correctly justified. Coverage gate 100% line + branch. |
| **04-03** | 2 | AUTH-03, AUTH-04 (revised), AUTH-06 | R2, R3, R10, R11 | **APPROVED** | OIDC branch AFTER static-keys (R2 line-number grep audit); `from botocore import UNSIGNED` threaded into `signature_version=UNSIGNED` (R3 positive grep + negative `Audience=` grep); WARN log emit site enforced (R10); 8 new unit tests cover all 7 branches in select_strategy. |
| **04-04** | 1 | AUTH-05 | (D4 erratum) | **APPROVED** | Ships `StringLike` for `sub` (D4 erratum honored); 5 placeholders byte-stable; Terraform companion correctly deferred to Phase 7. |
| **04-05** | 1 | CHART-02, CHART-03 (factory) | (D3 legacy deletion) | **APPROVED** | Protocol + LocalChart class + factory; `resolve_local_chart` REMOVED gate enforced by `! grep -RIn 'resolve_local_chart' src/ tests/`; `# pragma: no cover` + `pytest.mark.skip` markers for 04-06/04-07 lifts are explicitly tagged. |
| **04-06** | 2 | CHART-02 | R4 (carries forward), R7 | **APPROVED** | RepoChart routes through new `HelmClient.repo_add/repo_update/pull_repo` (Phase 3 D1 preserved); env-isolation env vars (HELM_REPOSITORY_CONFIG/CACHE); single-subdir discovery (R7); tempdir cleanup on exception; lifts 04-05's repo pragma + unskips repo test; integration test gates on `helm` binary presence. |
| **04-07** | 3 | CHART-03, CHART-04 | R4, R5, R6, R7, R8, R9, R12, R13 | **APPROVED** | All 8 risks addressed: `--password-stdin` (R4); cosign verify against OCI ref not tarball (R5); cosign verify BEFORE helm pull (R6); single-subdir discovery (R7); tempdir cleanup in `finally` even on cosign failure (R8); `subprocess.run` for cosign in `chart/oci.py` with explicit D5 callout (R9); Dockerfile `cosign-fetch` stage BETWEEN `helm-fetch` and `runtime` with SHA256 `grep \| sha256sum -c` (R12); single `.get_secret_value()` unwrap site (R13). Acceptance test verifies cosign binary in /usr/local/bin/. |

---

## Per-REQ row (covered? testable? gate adequate?)

| REQ | Covered? | Testable? | Gate adequate? | Notes |
|-----|----------|-----------|----------------|-------|
| **AUTH-03** | ✅ 04-02 + 04-03 | ✅ moto `@mock_aws` for STS | ✅ | `test_get_credentials_happy_path_under_mock_aws` exercises happy path; `test_select_strategy_returns_oidc_when_token_and_role_arn_and_audience_set` covers routing. |
| **AUTH-04 (revised)** | ✅ 04-01 + 04-03 | ✅ structlog capture_logs | ✅ | Verifier-path uses REVISED wording per R10. `test_select_strategy_static_keys_win_over_oidc_and_emits_warn` asserts both the precedence AND the WARN log emit. |
| **AUTH-05** | ✅ 04-04 | ✅ JSON-parse + 5 structural assertions | ✅ | `sub` under `StringLike` enforced as a positive assertion AND a negative assertion (the latter catches reverts). |
| **AUTH-06** | ✅ 04-02 surface + 04-03 raise logic | ✅ pytest.raises | ✅ | 3 misconfig branches each have a dedicated test; the existing Phase-2 `ROLE_ARN`-without-creds message is extended to mention OIDC. |
| **CHART-02** | ✅ 04-02 + 04-05 + 04-06 | ✅ subprocess-mocked unit + local-HTTP integration | ✅ | Integration test spins up `python -m http.server` + `helm repo index`; skips cleanly when helm absent. |
| **CHART-03** | ✅ 04-02 + 04-05 + 04-07 | ✅ subprocess-mocked unit + registry:2 integration | ✅ | 4-env-var isolation asserted; `--password-stdin` enforced positively AND `--password ` enforced negatively. |
| **CHART-04** | ✅ 04-02 + 04-07 | ✅ subprocess-mocked unit + acceptance + gated integration | ✅ | Verify-before-pull, verify-against-ref, tempdir-cleanup-on-cosign-failure, unconstrained-identity-WARN all have dedicated tests. Acceptance test for binary presence runs against built image. |

---

## Per-locked-decision row

| Decision | Implementable as planned? | Gaps? | Notes |
|----------|---------------------------|-------|-------|
| **D1** — Auth precedence mirrors botocore chain (ROADMAP revision) | ✅ | None | 04-01 ships the atomic doc-edit; 04-03 ships the runtime mirror; R10 verifier-path note is honored in VALIDATION.md. |
| **D2** — OidcWebIdentityStrategy shape | ✅ | None | Constructor signature matches verbatim; `Audience=` NOT passed to STS (CONTEXT D2 explicit note honored via negative grep `! grep -E "Audience\s*="`). |
| **D3** — ChartSource Protocol + LocalChart/RepoChart/OciChart | ✅ | None | Module layout matches D3 table; legacy `resolve_local_chart` deletion gate enforced. |
| **D4** — Bitbucket IAM trust-policy template | ✅ | None | StringLike erratum honored. Placeholder fidelity gate (CONTEXT D4 obligation) enforced via 5 positive greps. |
| **D5** — Cosign keyless verify with Rekor anchor | ✅ | None | Subprocess scoped to chart/oci.py with explicit module-docstring callout. `# noqa: S603` comment annotates the scoped exception. |
| **D6** — Tempdir context-manager pattern | ✅ | None | Both RepoChart and OciChart mirror `kube/kubeconfig.py`'s `mkdtemp + try/yield/finally(rmtree)` shape verbatim. 4-env-var isolation in OciChart (RESEARCH §5 belt-and-braces). |
| **D7** — 5-7 atomic plans + workflow shape | ✅ | None | 7 plans ships at upper end; deviation rationale (split off 04-01 + independent 04-04 + factory-vs-impl split for 04-05/06) is documented in 04-PLAN.md. |
| **D8** — Single PR at phase end | ✅ | None | No deviation; branch `phase/04-oidc-chart-sources` already created. |

---

## Wave timeline validation

| Wave | Plans | Inter-wave dependencies | Verdict |
|------|-------|-------------------------|---------|
| **1** | 04-01 (first within wave) → 04-02, 04-04, 04-05 parallel | none | ✅ 04-01 doc-edit, 04-02 settings.py, 04-04 docs/guides/, 04-05 chart/ + actions/upgrade.py — zero file overlap. |
| **2** | 04-03, 04-06 parallel | 04-03 depends on 04-02 (`settings.oidc_audience`); 04-06 depends on 04-02 (`settings.repo_url`) + 04-05 (Protocol + factory pragma) | ✅ Both correctly declare `depends_on: [04-02]` / `depends_on: [04-02, 04-05]`. No cycles. |
| **3** | 04-07 | 04-07 depends on 04-02, 04-05, 04-06 (HelmClient extension pattern + `_run_helm_subcommand` helper) | ✅ Hard depends correctly declared. 04-06 must land first so the helm/client.py extension shape is in place for 04-07 to mirror. |
| **4** | verification (gsd-verify-work) | all of 04-01..07 | ✅ Standard. |

**Wave-N can start with wave-(N-1) artifacts only:** confirmed. 04-03 (Wave 2) only reads `Settings.oidc_audience` (from 04-02 in Wave 1). 04-06 (Wave 2) reads `chart/base.py::ChartSource` + `chart/__init__.py::select_chart_source` pragma block (both from 04-05 in Wave 1). 04-07 (Wave 3) reads helm/client.py extension shape from 04-06 (Wave 2). No backward-edge dependency.

**Strict ordering enforcement on `helm/client.py`:** both 04-06 and 04-07 modify this file. 04-06 lands first (Wave 2) — adds `repo_add/repo_update/pull_repo` + the `_run_helm_subcommand` helper. 04-07 lands second (Wave 3) — appends `registry_login/pull_oci` on top + scopes the cosign exception to `chart/oci.py` (NOT `helm/client.py`). No merge conflict by construction.

---

## Threat / invariant cross-check

| Invariant / threat | Honored? | Where enforced |
|--------------------|----------|----------------|
| `helm/client.py` is the SOLE module calling `subprocess.run` for HELM commands (Phase 3 D1) | ✅ | 04-06 + 04-07 route all helm subcommands through `HelmClient.*`. RepoChart + OciChart construct a HelmClient with placeholder kubeconfig path. |
| `chart/oci.py` shells out to cosign (D5 scoped exception) | ✅ | 04-07 explicit; threat model + Deviation table both list it; `# noqa: S603` annotates the scoped exception in source. |
| `auth/oidc.py` does NOT shell out (boto3 only) | ✅ | 04-03 plan ships ZERO subprocess imports in auth/oidc.py; AUTH-07 parity maintained. |
| `actions/upgrade.py` stays under ~50 LOC body (Phase 3 invariant) | ✅ | 04-05 task 04-5-03 explicitly preserves; nested `with` block adds 2 lines; no other changes. The 200-line file total is mostly module docstring + class docstring (Phase 3 baseline). |
| 100% line + branch coverage gate | ✅ | Each plan declares `--cov-fail-under=100`; 04-05 documents the `# pragma: no cover` on forward-import OCI/repo branches, lifted by 04-06/07. |

---

## NIT / informational observations (NOT blockers)

1. **NIT — 04-03 `botocore.UNSIGNED` import style.** RESEARCH §7.1 cookbook code shows `signature_version=botocore.UNSIGNED` (dotted attribute access) but the prose says `from botocore import UNSIGNED`. The 04-03 plan correctly enforces the explicit-import form via `grep -F "from botocore import UNSIGNED"` in `<verify>`. No action needed; flagging only because the RESEARCH.md cookbook is mildly inconsistent — execution will follow the 04-03 plan's explicit verify gate.

2. **NIT — 04-03 file blacklist excludes `src/aws_eks_helm_deploy/logging.py`** while the action says to add `from aws_eks_helm_deploy.logging import get_logger`. This is a READ-only import (no modification); the blacklist correctly blocks WRITE; the import works at runtime. No conflict.

3. **Informational — D4 erratum cleanly absorbed.** CONTEXT D4 itself contains the `StringEquals` → `StringLike` correction inline; 04-04 honors the corrected version. Plan-Checker accepts this is NOT a CONTEXT deviation but a CONTEXT erratum-honored. Plan-Checker does NOT count this as a deviation against D4's first JSON sketch.

4. **Informational — file-overlap on `helm/client.py` across 04-06 + 04-07** is by design (additive only, ordered by wave). Snapshot file (`__snapshots__/test_helm_client_argv.ambr`) similarly. Both plans declare it; no conflict.

5. **Informational — Coverage on `chart/__init__.py`** uses `# pragma: no cover` markers in 04-05 with a documented lift path in 04-06 + 04-07. The 100% gate stays active throughout. This is the cleanest of the two alternatives RESEARCH §7.4 sketches.

---

## Fix list

**None.** No `CHANGES REQUESTED`. Plans are executable as-is.

If any of the NIT items become concrete blockers during execution (e.g. 04-03 executor accidentally uses `botocore.UNSIGNED` dotted form and the `<verify>` grep catches it), the executor can resolve inline without re-planning.

---

## Plan-Checker sign-off

- [x] All 4 Phase 4 Success Criteria walk back to a covering plan with a testable gate.
- [x] All 7 REQs covered + testable + gated.
- [x] All 8 locked decisions D1–D8 honored (D4 erratum is the correction CONTEXT itself calls out).
- [x] All 13 risks R1–R13 from RESEARCH.md mitigated with concrete code-shape + enforcement.
- [x] Wave dependencies are acyclic and forward-only; wave-N artifacts are sufficient for wave-(N+1) to start.
- [x] Atomic ROADMAP+REQUIREMENTS revision is enforced as commit #1 (04-01 first in Wave 1; 04-03 cannot pass verifier without 04-01 landed).
- [x] Phase 3 invariants preserved (helm/client.py as sole subprocess caller for HELM commands; actions/upgrade.py body slim; 100% coverage gate active).
- [x] D5 scoped exception (cosign subprocess in chart/oci.py) is explicit, documented, and surfaced to threat model + plan-checker via the VALIDATION.md "Documented Deviations Surface" section.
- [x] AUTH-04 verifier-path uses REVISED wording (R10 — verifier asserts static keys win, NOT "OIDC wins").

**Recommendation:** proceed to `/gsd-execute-phase 4`. Wave 1 may launch immediately (04-01 sequenced first; 04-02 + 04-04 + 04-05 parallel after the doc-edit commit lands).

*Phase 4 PLAN-CHECK signed off 2026-06-18.*
