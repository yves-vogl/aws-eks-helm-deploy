---
phase: 4
slug: oidc-chart-source-extensions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Mirrors the shape of `03-VALIDATION.md`. Consumed by `gsd-plan-checker` (gate-keeping) and `gsd-verify-work` (final REQ → green-test mapping).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (inherited) + syrupy 5.3.x (inherited from Phase 3) + pytest-rerunfailures 16.3.x (inherited from Phase 3) + pytest-mock (inherited) + moto 5.2.x `@mock_aws` (inherited; needed by Plan 04-03 for `assume_role_with_web_identity` mocking) |
| **New dev/runtime deps** | **None.** Phase 4 introduces no new Python deps. Cosign 2.6.3 is a **binary** installed in the Dockerfile (Plan 04-07); it is NOT a Python package and does NOT touch `pyproject.toml` / `uv.lock`. |
| **Mocking** | `moto.@mock_aws` for `sts.assume_role_with_web_identity` (Plan 04-03); `pytest-mock`'s `mocker.patch("subprocess.run", ...)` for helm registry/pull + cosign verify subprocess (Plans 04-06, 04-07); `monkeypatch` for env var fixtures (`BITBUCKET_STEP_OIDC_TOKEN`). |
| **Quick run command** | `uv run pytest -q --no-cov` (unit tier, < 12s). |
| **Full suite command** | `uv run pytest && uv run pytest -m integration --no-cov && uv run pytest -m acceptance --no-cov` |
| **Estimated runtime** | unit ~10s (Phase 3 + ~35 new Phase 4 unit tests + moto warmup) · integration ~5-6 min (kind reuse + 3 new integration tests on local `registry:2` + `helm repo` server, each ~30-60s) · acceptance ~60s (unchanged). |

---

## Sampling Rate

- **After every task commit:** `uv run pytest -q --no-cov` (~10s) — verifies the freshly committed module + existing 80+ prior-phase tests stay green.
- **After every plan wave merge:** Full unit suite with `--cov-fail-under=100` gate + (when kind + docker installed) `uv run pytest -m integration --no-cov` for Wave 3.
- **Before `/gsd-verify-work`:** Full unit + integration green AND `uv run mypy --strict src` AND `uv run ruff check src tests` AND `uv run ruff format --check src tests` AND `uv run pre-commit run --all-files` ALL exit 0.
- **Max feedback latency:** < 12s per task commit; < 2 min per wave merge for unit tier; < 6 min for the integration tier on a kind + docker + cosign equipped host.

---

## Per-REQ Traceability

The Plan-Checker reads this table to verify zero REQs are dropped. Each row maps **one** requirement to one or more plans and to the acceptance criterion that gates it.

| REQ | Source wording (post-D1 revision where applicable) | Plans covering | Gating acceptance criterion | Test that proves it |
|-----|-----------------------------------------------------|-----------------|------------------------------|----------------------|
| **AUTH-03** | M authenticates via Bitbucket Pipelines OIDC by setting only `OIDC_AUDIENCE` + `ROLE_ARN`; pipe exchanges `BITBUCKET_STEP_OIDC_TOKEN` for STS credentials via `AssumeRoleWithWebIdentity`. (Closes #3.) | **04-02** (env-var surface), **04-03** (`OidcWebIdentityStrategy` + integration) | `select_strategy(settings_with_oidc_only)` returns `OidcWebIdentityStrategy`; `get_credentials()` calls `sts.assume_role_with_web_identity` exactly once under `@mock_aws` and returns a populated `AwsCredentials` with `session_token` + `expiration`. | `tests/unit/test_auth_oidc.py::test_get_credentials_happy_path_under_mock_aws` (Plan 04-03) + `tests/unit/test_auth_init_select_strategy.py::test_select_strategy_returns_oidc_when_token_and_role_arn_set` (Plan 04-03) |
| **AUTH-04** (revised per D1) | Strategy selection follows the boto3 / AWS CLI default credential resolver chain; when both static keys AND an OIDC token are present, **static keys win** — same behaviour as the AWS CLI itself; a one-time WARN log surfaces when this happens. | **04-01** (ROADMAP + REQUIREMENTS edit), **04-03** (`select_strategy` precedence) | `select_strategy(settings_with_BOTH_static_keys_AND_oidc_token)` returns `StaticKeysStrategy` (NOT `OidcWebIdentityStrategy`) AND emits `auth.precedence.static_keys_won_over_oidc` WARN log exactly once. | `tests/unit/test_auth_init_select_strategy.py::test_select_strategy_static_keys_win_over_oidc_and_emits_warn` (Plan 04-03) |
| **AUTH-05** | Pipe ships a documented AWS IAM trust-policy template scoped to `BITBUCKET_WORKSPACE_UUID` + `BITBUCKET_REPO_UUID` so consumers cannot accidentally configure a permissive policy. (Pitfall #1.) | **04-04** | `docs/guides/oidc-setup.md` contains a fenced ```jsonc block parseable as valid JSON; the policy has the 5 required placeholders (`<ACCOUNT_ID>`, `<WORKSPACE>`, `<OIDC_AUDIENCE>`, `<BITBUCKET_WORKSPACE_UUID>`, `<BITBUCKET_REPO_UUID>`); the `sub` condition lives under `StringLike` (NOT `StringEquals`) per RESEARCH §2 erratum; the Action is `sts:AssumeRoleWithWebIdentity`; the Federated principal matches the Bitbucket OIDC issuer pattern. | `tests/unit/test_iam_trust_policy_template.py::test_template_has_required_placeholders_and_string_like` (Plan 04-04) |
| **AUTH-06** | Pipe rejects misconfigurations explicitly (e.g. `ROLE_ARN` set without any base credentials, `OIDC_AUDIENCE` without `ROLE_ARN`, `BITBUCKET_STEP_OIDC_TOKEN` without `ROLE_ARN`) with a clear error message before contacting AWS. | **04-02** (settings + initial error wording), **04-03** (`select_strategy` validation branches) | `select_strategy(settings_oidc_audience_without_role_arn)` raises `ConfigurationError` with `"OIDC requires ROLE_ARN"` substring; same for `settings_oidc_token_without_role_arn`; existing `ROLE_ARN`-without-base-creds error message is extended to mention OIDC as an alternative. | `tests/unit/test_auth_init_select_strategy.py::test_oidc_audience_without_role_arn_raises_config_error` + `::test_oidc_token_without_role_arn_raises_config_error` + `::test_role_arn_without_base_creds_message_mentions_oidc` (all Plan 04-03) |
| **CHART-02** | M deploys a chart from a Helm repo by setting `CHART=repo://<repo>/<chart>`, `REPO_URL=<url>`, optional `CHART_VERSION=<version>`. (Closes #7.) | **04-02** (settings: `REPO_URL`, `CHART_VERSION`), **04-05** (factory routing), **04-06** (`RepoChart` impl + `HelmClient.repo_add/repo_update/pull_repo`) | `select_chart_source(settings_with_repo_chart)` returns `RepoChart`; under subprocess mocking, `RepoChart.resolve()` invokes `helm repo add` + `helm repo update` + `helm pull` with the correct argv + env (`HELM_REPOSITORY_CONFIG` + `HELM_REPOSITORY_CACHE` pointing at the tempdir); yields a `ResolvedChart` whose `source_path` is inside the tempdir; cleans the tempdir on context exit (incl. on exception). | `tests/unit/test_chart_repo.py::test_resolve_invokes_helm_repo_add_update_pull_with_isolated_env` + `::test_resolve_cleans_tempdir_on_exception` + `tests/unit/test_chart_init_select_source.py::test_select_chart_source_routes_repo_prefix_to_repo_chart` (Plans 04-05, 04-06) + integration: `tests/integration/test_chart_sources.py::test_repo_chart_resolves_real_chart_via_local_http_repo` (Plan 04-06) |
| **CHART-03** | M deploys a chart from an OCI registry by setting `CHART=oci://<registry>/<chart>` with optional `CHART_VERSION` + optional `REGISTRY_USERNAME` + `REGISTRY_PASSWORD`. | **04-02** (settings: `REGISTRY_USERNAME`, `REGISTRY_PASSWORD`), **04-05** (factory routing), **04-07** (`OciChart` impl + Dockerfile cosign stage) | `select_chart_source(settings_with_oci_chart)` returns `OciChart`; under subprocess mocking, `OciChart.resolve()` invokes `helm registry login --password-stdin` (when creds set) then `helm pull oci://…` with the correct argv + env (`HELM_REGISTRY_CONFIG` + `DOCKER_CONFIG` + `HELM_REPOSITORY_CONFIG` + `HELM_REPOSITORY_CACHE` all pointing at the tempdir); cleans the tempdir on context exit. | `tests/unit/test_chart_oci.py::test_resolve_invokes_helm_pull_oci_with_isolated_env` + `::test_resolve_runs_registry_login_with_password_stdin_when_creds_set` + `::test_resolve_cleans_tempdir_on_exception` + `tests/unit/test_chart_init_select_source.py::test_select_chart_source_routes_oci_prefix_to_oci_chart` (Plans 04-05, 04-07) + integration: `tests/integration/test_chart_sources.py::test_oci_chart_pulls_from_local_registry_2` (Plan 04-07, gated by `registry:2` container fixture) |
| **CHART-04** | M can verify an OCI chart signature by setting `CHART_VERIFY=true` (Cosign verification of the chart artifact); failure aborts the upgrade. | **04-02** (settings: `CHART_VERIFY`, `CHART_VERIFY_CERTIFICATE_IDENTITY`, `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER`), **04-07** (Cosign verify subprocess + Dockerfile cosign stage) | When `CHART_VERIFY=true`, `OciChart.resolve()` invokes `cosign verify <oci-ref>` BEFORE `helm pull`; on non-zero cosign returncode the tempdir is cleaned AND `ChartResolutionError` is raised (exit_code=4); when both `CHART_VERIFY_CERTIFICATE_IDENTITY` + `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER` are set, cosign is invoked with `--certificate-identity <id> --certificate-oidc-issuer <url>`; when `CHART_VERIFY=true` is set without either constraint, a `chart.verify.unconstrained_identity` WARN log is emitted; the Dockerfile bundles `cosign` 2.6.3 in `/usr/local/bin/cosign`. | `tests/unit/test_chart_oci.py::test_resolve_runs_cosign_verify_before_helm_pull_when_verify_true` + `::test_resolve_passes_certificate_identity_and_oidc_issuer_flags_when_set` + `::test_resolve_emits_unconstrained_identity_warn_when_no_constraint_set` + `::test_resolve_raises_chart_resolution_error_on_cosign_non_zero` + acceptance: `tests/acceptance/test_image_has_cosign.py::test_cosign_binary_in_path` (Plan 04-07) + integration (gated): `tests/integration/test_chart_sources.py::test_oci_chart_verify_against_signed_test_chart` (Plan 04-07, `@pytest.mark.skipif(shutil.which('cosign') is None)`) |

**Coverage sanity check:** 7 REQs → 7 rows above. Every REQ in scope has at least one plan and at least one test. ✓

---

## Per-Task Verification Map

| Task ID | Plan | Wave | REQs | SC | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|------|----|------------|------------------|-----------|-------------------|-------------|--------|
| 04-1-01 | 04-01 | 1 | AUTH-04 (revised) | SC1 | (doc-edit) | ROADMAP + REQUIREMENTS wording mirrors botocore chain order; atomic with the OIDC code in 04-03 | doc | `grep -F "static keys win" .planning/ROADMAP.md && grep -F "static keys win" .planning/REQUIREMENTS.md` | ❌ W0 | ⬜ pending |
| 04-2-01 | 04-02 | 1 | AUTH-03, AUTH-06, CHART-02, CHART-03, CHART-04 | SC1, SC3, SC4 | T-04-02-01 (R13 — `SecretStr` for password) | New env vars added to `Settings`; `registry_password: SecretStr \| None` (NOT str); existing fields unchanged | unit | `uv run pytest -m unit -q tests/unit/test_settings.py --cov=aws_eks_helm_deploy.settings --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 04-3-01 | 04-03 | 2 | AUTH-03, AUTH-04 (revised), AUTH-06 | SC1 | T-04-03-01..04 | `OidcWebIdentityStrategy` satisfies `AuthStrategy` Protocol structurally; uses `botocore.UNSIGNED` (R3); `select_strategy` OIDC branch AFTER static-keys branch (R2); WARN log on static-keys-win-over-oidc | unit | `uv run pytest -m unit -q tests/unit/test_auth_oidc.py tests/unit/test_auth_init_select_strategy.py --cov=aws_eks_helm_deploy.auth.oidc --cov=aws_eks_helm_deploy.auth --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 04-4-01 | 04-04 | 1 | AUTH-05 | SC2 | T-04-04-01 (IAM doc) | Trust-policy template has 5 placeholders + `sub` under `StringLike` (RESEARCH §2 correction) + Action is `sts:AssumeRoleWithWebIdentity` + Federated principal matches Bitbucket OIDC issuer pattern | unit | `uv run pytest -m unit -q tests/unit/test_iam_trust_policy_template.py --no-cov` | ❌ W0 | ⬜ pending |
| 04-5-01 | 04-05 | 1 | CHART-02, CHART-03 (factory routing) | SC3 | T-04-05-01 (legacy fn removal) | `ChartSource` Protocol + `ResolvedChart` in `chart/base.py`; `LocalChart` class with `.resolve()` context-manager; legacy `resolve_local_chart` removed BEFORE PR; `select_chart_source` factory; `actions/upgrade.py` wired to factory; all Phase 3 tests still green | unit | `uv run pytest -m unit -q tests/unit/test_chart_base.py tests/unit/test_chart_local.py tests/unit/test_chart_init_select_source.py tests/unit/test_upgrade_action.py --cov=aws_eks_helm_deploy.chart --cov=aws_eks_helm_deploy.actions.upgrade --cov-branch --cov-fail-under=100 --no-header && grep -c "resolve_local_chart" src/aws_eks_helm_deploy/ -r \| awk -F: '$2!=0{exit 1}END{exit 0}'` | ❌ W0 | ⬜ pending |
| 04-6-01 | 04-06 | 2 | CHART-02 | SC3 | T-04-06-01 (helm/client.py invariant scope), T-04-06-02 (tempdir cleanup), T-04-06-03 (env isolation) | `RepoChart` mirrors `kube/kubeconfig.py` context-manager pattern; subprocess invocation goes through `HelmClient.repo_add/repo_update/pull_repo` (NEW typed methods — preserves Phase 3 D1 invariant); env vars `HELM_REPOSITORY_CONFIG` + `HELM_REPOSITORY_CACHE` point at tempdir; cleanup on exit even on exception; single-subdir discovery per RESEARCH §4 | unit + integration | `uv run pytest -m unit -q tests/unit/test_chart_repo.py tests/unit/test_helm_client_argv.py tests/unit/test_helm_client_run.py --cov=aws_eks_helm_deploy.chart.repo --cov=aws_eks_helm_deploy.helm.client --cov-branch --cov-fail-under=100 --no-header && (uv run pytest -m integration -q tests/integration/test_chart_sources.py::test_repo_chart_resolves_real_chart_via_local_http_repo --no-cov \|\| echo "SKIPPED — kind/docker absent")` | ❌ W0 | ⬜ pending |
| 04-7-01 | 04-07 | 3 | CHART-03, CHART-04 | SC4 | T-04-07-01 (R4 password-stdin), T-04-07-02 (R5 verify against ref), T-04-07-03 (R6 verify before pull), T-04-07-04 (R8 tempdir on cosign failure), T-04-07-05 (R9 D5 doc override), T-04-07-06 (R12 Dockerfile stage order) | `OciChart` mirrors `RepoChart` pattern + cosign verify + 4-env-var isolation (`HELM_REGISTRY_CONFIG`, `DOCKER_CONFIG`, `HELM_REPOSITORY_CONFIG`, `HELM_REPOSITORY_CACHE`); `helm registry login --password-stdin` (R4); cosign verify against OCI ref BEFORE helm pull (R5+R6); tempdir cleanup on cosign failure (R8); subprocess for cosign lives in `chart/oci.py` (R9 / D5 scoped override); Dockerfile `cosign-fetch` stage between `helm-fetch` and `runtime` with SHA256 + grep filter (R12) | unit + integration + acceptance | `uv run pytest -m unit -q tests/unit/test_chart_oci.py tests/unit/test_helm_client_argv.py --cov=aws_eks_helm_deploy.chart.oci --cov=aws_eks_helm_deploy.helm.client --cov-branch --cov-fail-under=100 --no-header && (uv run pytest -m integration -q tests/integration/test_chart_sources.py --no-cov \|\| echo "SKIPPED — docker/cosign absent") && (uv run pytest -m acceptance -q tests/acceptance/test_image_has_cosign.py --no-cov \|\| echo "SKIPPED — image not built")` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave dependency notes:**

- **Wave 1 (parallel; 04-01 lands FIRST within the wave):**
  - 04-01 — `ROADMAP.md` + `REQUIREMENTS.md` only; no code.
  - 04-02 — `settings.py` only.
  - 04-04 — `docs/guides/oidc-setup.md` + `tests/unit/test_iam_trust_policy_template.py` only. Independent of all other plans.
  - 04-05 — `chart/base.py`, `chart/local.py`, `chart/__init__.py`, `actions/upgrade.py`. Touches `chart/__init__.py` + `chart/local.py` — no overlap with 04-02 / 04-04 / 04-01.
- **Wave 2:**
  - 04-03 — `auth/oidc.py` (new), `auth/__init__.py` (extends), `tests/unit/test_auth_oidc.py` (new), `tests/unit/test_auth_init_select_strategy.py` (extends Phase 2). Depends on 04-02 (`oidc_audience` setting).
  - 04-06 — `chart/repo.py` (new), `helm/client.py` (adds `repo_add/repo_update/pull_repo`), `tests/unit/test_chart_repo.py` (new), `tests/unit/test_helm_client_argv.py` + `__snapshots__/test_helm_client_argv.ambr` (extends; new snapshots committed), `tests/integration/test_chart_sources.py` (new). Depends on 04-02 (settings) + 04-05 (Protocol).
- **Wave 3:**
  - 04-07 — `chart/oci.py` (new), `helm/client.py` (adds `registry_login`, `pull_oci`), `Dockerfile` (cosign-fetch stage), `tests/unit/test_chart_oci.py` (new), `tests/unit/test_helm_client_argv.py` + snapshot file (extends), `tests/integration/test_chart_sources.py` (extends from 04-06), `tests/acceptance/test_image_has_cosign.py` (new). Depends on 04-02, 04-05, 04-06.

**Strict ordering enforcement:**

- 04-01 lands as **commit #1**. The Plan-Checker rejects any phase plan-set where 04-03 is merged before 04-01 (R1 / R10).
- 04-06 and 04-07 both modify `helm/client.py` (adding new typed methods) AND `tests/unit/test_helm_client_argv.py` + the syrupy snapshot file. Recommended landing order: 04-06 first (Wave 2), 04-07 second (Wave 3); 04-07's commit appends new methods + new snapshot entries without touching 04-06's adds.
- 04-05 imports `ChartSource` from `chart/base.py` into `actions/upgrade.py`. Plan 04-06 / 04-07 do NOT touch `actions/upgrade.py` — they only ship new chart modules consumed via the factory.

---

## Wave 0 Requirements

All Phase 4 test infrastructure builds on Phase 1 + Phase 2 + Phase 3 + Plans 04-01..05 foundation. New files created BEFORE tests can be exercised:

- [ ] `.planning/ROADMAP.md` (Plan 04-01) — Phase 4 SC1 + AUTH-04 wording revised.
- [ ] `.planning/REQUIREMENTS.md` (Plan 04-01) — AUTH-04 row + traceability cross-reference.
- [ ] `src/aws_eks_helm_deploy/settings.py` (Plan 04-02) — 8 new env-var fields.
- [ ] `src/aws_eks_helm_deploy/auth/oidc.py` (Plan 04-03) — `OidcWebIdentityStrategy`.
- [ ] `src/aws_eks_helm_deploy/auth/__init__.py` (Plan 04-03) — `select_strategy` extended with OIDC branch.
- [ ] `docs/guides/oidc-setup.md` (Plan 04-04) — IAM trust-policy template.
- [ ] `src/aws_eks_helm_deploy/chart/base.py` (Plan 04-05) — `ChartSource` Protocol + `ResolvedChart`.
- [ ] `src/aws_eks_helm_deploy/chart/local.py` (Plan 04-05) — refactored to `LocalChart` class; legacy `resolve_local_chart` REMOVED.
- [ ] `src/aws_eks_helm_deploy/chart/__init__.py` (Plan 04-05) — `select_chart_source` factory + re-exports.
- [ ] `src/aws_eks_helm_deploy/actions/upgrade.py` (Plan 04-05) — wired to `select_chart_source`.
- [ ] `src/aws_eks_helm_deploy/chart/repo.py` (Plan 04-06) — `RepoChart`.
- [ ] `src/aws_eks_helm_deploy/helm/client.py` (Plans 04-06, 04-07) — new typed methods `repo_add`, `repo_update`, `pull_repo`, `registry_login`, `pull_oci`.
- [ ] `src/aws_eks_helm_deploy/chart/oci.py` (Plan 04-07) — `OciChart` + cosign verify subprocess.
- [ ] `Dockerfile` (Plan 04-07) — `cosign-fetch` stage between `helm-fetch` and `runtime`.
- [ ] `tests/unit/test_settings.py` (extended by Plan 04-02) — 8 new tests.
- [ ] `tests/unit/test_auth_oidc.py` (Plan 04-03) — 8+ tests.
- [ ] `tests/unit/test_auth_init_select_strategy.py` (extended by Plan 04-03) — 6+ new tests around OIDC precedence + WARN log + misconfig errors.
- [ ] `tests/unit/test_iam_trust_policy_template.py` (Plan 04-04) — 5 assertions.
- [ ] `tests/unit/test_chart_base.py` (Plan 04-05) — Protocol + ResolvedChart shape tests.
- [ ] `tests/unit/test_chart_local.py` (modified by Plan 04-05) — switches to `LocalChart` class tests.
- [ ] `tests/unit/test_chart_init_select_source.py` (Plan 04-05) — factory routing tests.
- [ ] `tests/unit/test_chart_repo.py` (Plan 04-06) — 8+ tests under subprocess mocking.
- [ ] `tests/unit/test_chart_oci.py` (Plan 04-07) — 10+ tests under subprocess mocking.
- [ ] `tests/unit/test_helm_client_argv.py` (extended by Plans 04-06, 04-07) — new snapshot tests for `repo_add/repo_update/pull_repo/registry_login/pull_oci` argv.
- [ ] `tests/unit/__snapshots__/test_helm_client_argv.ambr` (extended by Plans 04-06, 04-07) — new snapshot entries committed to git.
- [ ] `tests/unit/test_helm_client_run.py` (extended by Plans 04-06, 04-07) — subprocess-mocked tests for new typed methods.
- [ ] `tests/unit/test_upgrade_action.py` (extended by Plan 04-05) — replaces direct `resolve_local_chart` calls with `select_chart_source` calls.
- [ ] `tests/integration/test_chart_sources.py` (Plans 04-06, 04-07) — 3+ integration tests against local `helm repo` + `registry:2` containers.
- [ ] `tests/acceptance/test_image_has_cosign.py` (Plan 04-07) — `docker run --entrypoint /bin/sh image -c "which cosign && cosign version"` exits 0.

Existing infrastructure REUSED (no new files):

- `tests/conftest.py` (auto-mark hook).
- `tests/integration/conftest.py::kind_cluster` + `kind_kubeconfig` (Phase 3).
- `pyproject.toml` `[tool.pytest.ini_options].addopts` already has `--cov-fail-under=100`.

When all source files in 04-01..07 have merged AND their corresponding test files exist AND `pytest -q` exits 0 at 100% coverage, the Phase 4 validation contract is fully active (unit tier). Integration tier activates when kind + docker + cosign are installed locally.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CONTEXT D1 + RESEARCH §R9 — `subprocess.run` for cosign lives in `chart/oci.py`, NOT in `helm/client.py` | CHART-04 | Architectural exception to Phase 3 D1 invariant — scoped to non-helm binaries. Plan-Checker MUST acknowledge this is intentional. | `grep -RIn "subprocess\.run" src/aws_eks_helm_deploy/` shows entries in `helm/client.py` (helm sub-commands only) AND `chart/oci.py` (cosign only). NO other module shells out. |
| RESEARCH §R5 — cosign verify against OCI ref, not pulled tarball | CHART-04 | Architectural fact. | Read `src/aws_eks_helm_deploy/chart/oci.py`; confirm `cosign verify` argv contains `{registry}/{chart}:{tag}` style ref or `oci://…` ref — NOT a `<tmpdir>/<chart>.tgz` path. |
| RESEARCH §R6 — cosign verify runs BEFORE helm pull | CHART-04 | Architectural ordering. | Read `src/aws_eks_helm_deploy/chart/oci.py::resolve`; confirm `_run_cosign_verify()` is called BEFORE `_run_helm_pull()` in the body. |
| RESEARCH §R12 — Dockerfile stage ordering | CHART-04 | Docker build-time fact. | `docker buildx build --target runtime .` succeeds; `docker image inspect <image> --format '{{ .Config.Cmd }}'` shows `cosign` in `/usr/local/bin/`; the `cosign-fetch` stage appears in `Dockerfile` between `helm-fetch` (~ line 38) and `runtime` (~ line 64). |
| Legacy `resolve_local_chart` function REMOVED before PR closes | CHART-02 / CHART-03 (factory) | CONTEXT D3 Plan-Check obligation; deletion gate. | `grep -RIn "resolve_local_chart" src/ tests/` returns ZERO matches (the symbol is fully removed). |
| AUTH-04 verifier reads REVISED wording, not original | AUTH-04 | R10 — Plan-Checker pointer. | `gsd-verify-work` for Phase 4 asserts `select_strategy` returns `StaticKeysStrategy` when both env vars + OIDC token are set — NOT the inverse. |
| Cosign 2.6.3 binary pinned + SHA256 verified at build time | CHART-04 | Supply-chain integrity check. | Read `Dockerfile`; confirm `ARG COSIGN_VERSION=2.6.3` AND `grep "  cosign-linux-amd64$" cosign_checksums.txt \| sha256sum -c` in the `cosign-fetch` stage. |
| `--password-stdin` for `helm registry login` | CHART-03 | R4 — process-listing leak prevention. | `grep -RIn "helm.*registry.*login\|registry_login" src/aws_eks_helm_deploy/` shows `--password-stdin` in the argv list; NEVER `--password <value>`. |

*All other phase behaviors have automated verification.*

---

## Documented Deviations Surface

This phase ships the following deviations from CONTEXT / ROADMAP. They are intentional and surfaced here so `gsd-plan-checker` and `gsd-verify-work` acknowledge them up-front.

### CONTEXT-level deviations (acknowledged but UPHELD)

1. **D1 — ROADMAP SC1 + AUTH-04 wording deliberately superseded.** Plan 04-01 ships the revision; 04-VERIFICATION.md will assert the revised wording, not the original.
2. **D4 erratum — `sub` condition under `StringLike`, NOT `StringEquals`.** CONTEXT D4's JSON sketch had `StringEquals` for the `sub` key; RESEARCH §2 confirms IAM only treats `*` as a wildcard under `StringLike`. Plan 04-04 ships the corrected template.
3. **D5 doc-comment override — cosign subprocess lives in `chart/oci.py`, NOT `helm/client.py`.** Plan-Checker MUST NOT flag this as a layering violation; the Phase 3 invariant is scoped to **helm** sub-commands only.
4. **D7 granularity — 7 plans (upper end of the 5–7 suggestion).** Justification in `04-PLAN.md` § "Documented deviations from CONTEXT D7 granularity guidance".

### RESEARCH-level deviations (option A chosen over option B)

5. **HelmClient extension chosen over inline subprocess in chart-source modules** (RESEARCH §7.4 Option A vs Option B). New typed methods on `HelmClient`: `repo_add`, `repo_update`, `pull_repo`, `registry_login`, `pull_oci`. Rationale: preserves the Phase 3 D1 invariant ("helm/client.py is the SOLE subprocess caller for helm commands"); the cost of two extra typed methods + their snapshot/run tests is small compared to the consistency gain. Cosign is the documented exception (D5).

### Plan-level deviations

6. **04-02 `registry_password: SecretStr` (NOT str)** — R13 mitigation. The single `.get_secret_value()` unwrap site lives in 04-07's `OciChart._run_helm_registry_login`.
7. **04-03 `os.environ.get("BITBUCKET_STEP_OIDC_TOKEN")` outside `settings.py`** — RESEARCH §7.2 documented exception, mirroring Phase 2's `BITBUCKET_PIPELINE_UUID` / `BITBUCKET_BUILD_NUMBER` reads in `_derive_session_name`. The token MUST NOT enter `Settings` because (a) it tempts callers to `repr(settings)` and leak the token; (b) it bypasses pydantic's masking.
8. **04-04 `docs/guides/oidc-setup.md` is drafted, not polished** — full polish + `mkdocs` integration ships in Phase 7.
9. **04-04 Terraform companion snippet is DEFERRED to Phase 7** — CONTEXT D4 explicitly allows deferring this if Phase 4 is heavy; this planner defers to keep 04-04's scope at "one IAM template + one unit test".
10. **04-07 regexp variants of cosign env vars are RESERVED but not shipped** — RESEARCH §3 documents `CHART_VERIFY_CERTIFICATE_IDENTITY_REGEXP` and `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER_REGEXP` as v2.1+ work because cosign's own env-var support for the regexp variants is undocumented.

The phase-checker / phase-verifier MUST acknowledge these ten deviations before flagging them as gaps in `04-VERIFICATION.md`.

---

## Coverage Roll-Up

Phase 4 adds the following modules; all MUST hit 100% line + 100% branch by the end of the phase (per the active `--cov-fail-under=100` gate inherited from Phase 1):

| Module | Owner Plan | Coverage Target | Branch Coverage Note |
|--------|------------|------------------|----------------------|
| `src/aws_eks_helm_deploy/settings.py` | extended by 04-02 | 100% line + 100% branch | 8 new fields; trivial — pydantic Field defaults are pure assignment. |
| `src/aws_eks_helm_deploy/auth/oidc.py` | 04-03 | 100% line + 100% branch | Happy path (`@mock_aws`) + `ClientError` branch. |
| `src/aws_eks_helm_deploy/auth/__init__.py` | extended by 04-03 | 100% line + 100% branch | Pre-existing branches + new OIDC branch + WARN-log branch + AUTH-06 `ConfigurationError` branches (audience-without-role-arn, token-without-role-arn). |
| `src/aws_eks_helm_deploy/chart/base.py` | 04-05 | 100% (trivial — Protocol + frozen dataclass) | No runtime branches. |
| `src/aws_eks_helm_deploy/chart/local.py` | refactored by 04-05 | 100% line + 100% branch | Inherits Phase 3's coverage; `LocalChart.resolve()` is degenerate context-manager (yields existing path, no cleanup); legacy `resolve_local_chart` REMOVED. |
| `src/aws_eks_helm_deploy/chart/__init__.py` | extended by 04-05 | 100% line + 100% branch | `select_chart_source` factory: `oci://`, `repo://`, else → local branches + the `repo://` parse-error branch + the `repo://`-without-`REPO_URL` branch. |
| `src/aws_eks_helm_deploy/actions/upgrade.py` | extended by 04-05 | 100% line + 100% branch | Pre-existing coverage; new `select_chart_source(settings)` call replaces `resolve_local_chart(settings.chart)`. Tests in `test_upgrade_action.py` updated to mock the factory. |
| `src/aws_eks_helm_deploy/chart/repo.py` | 04-06 | 100% line + 100% branch | Happy path + version-set branch + version-unset branch + tempdir-cleanup-on-exception branch + non-zero-helm-returncode branch + missing-subdir-after-untar branch. |
| `src/aws_eks_helm_deploy/chart/oci.py` | 04-07 | 100% line + 100% branch | Happy path + verify=True branch + verify=False branch + registry-login-with-creds branch + registry-login-without-creds branch + identity-constraint-present branch + identity-constraint-absent + WARN-log branch + cosign-failure-cleans-tempdir branch + helm-pull-failure branch + missing-subdir-after-untar branch. |
| `src/aws_eks_helm_deploy/helm/client.py` | extended by 04-06, 04-07 | 100% line + 100% branch | Pre-existing coverage; new methods `repo_add`, `repo_update`, `pull_repo`, `registry_login`, `pull_oci` each tested for happy + non-zero-returncode + TimeoutExpired branches. Snapshot tests for argv. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify OR documented Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (7 plans × 1-2 tasks each; every task has an automated verify; integration tier auto-skips when fixtures absent).
- [ ] Wave 0 covers all MISSING references (see Wave 0 Requirements above).
- [ ] No watch-mode flags (no `--watch`, no `pytest-watch`).
- [ ] Feedback latency < 12s per task quick-run.
- [ ] All ten documented deviations are surfaced to the phase-checker (this file's "Documented Deviations Surface" section).
- [ ] `nyquist_compliant: true` to be set after Wave 3 lands and the full unit + integration suites pass (integration tier requires docker on host).

**Approval:** pending Plan-Checker review (`gsd-plan-checker`).
