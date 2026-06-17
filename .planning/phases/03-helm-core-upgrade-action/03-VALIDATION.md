---
phase: 3
slug: helm-core-upgrade-action
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Mirrors the shape of `02-VALIDATION.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (inherited from Phase 1) + syrupy 5.3.x (NEW — Plan 03-02) + pytest-rerunfailures 16.3.x (NEW — Plan 03-02) |
| **Mocking** | pytest-mock for subprocess.run + boto3 patching; moto 5.2.x `@mock_aws` for EKS describe_cluster (Plan 03-01); syrupy snapshot fixture for argv assertions (Plan 03-02); structlog.testing.capture_logs for structlog warning assertions (Plan 03-03 + 03-04) |
| **Config file** | `pyproject.toml` — Phase 3 modifies `[dependency-groups].dev` to add syrupy + pytest-rerunfailures (Plan 03-02); modifies `Settings` to add `history_max` + update `timeout` default (Plan 03-04). `--cov-fail-under=100` gate UNCHANGED. |
| **Quick run command** | `uv run pytest -q --no-cov` (unit tier, no gate; < 10s including moto warmup + structlog config) |
| **Full suite command** | `uv run pytest && uv run pytest -m integration --no-cov && uv run pytest -m acceptance --no-cov` |
| **Estimated runtime** | unit ~8s (existing 50+ tests + ~30 new Phase 3 tests) · integration ~4-5 min (kind cluster reuse + 4 new integration tests, each ~30-60s) · acceptance ~60s (unchanged) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q --no-cov` (~8s; unit tier, no gate) — verifies the freshly committed module + existing 50+ prior-phase tests stay green.
- **After every plan wave merge:** Run the full unit suite: `uv run pytest` (with the 100% gate) + (when kind installed) `uv run pytest -m integration --no-cov` for Wave 4.
- **Before `/gsd-verify-work`:** Full unit suite green AND `uv run mypy --strict src` AND `uv run ruff check src tests` AND `uv run ruff format --check src tests` AND `uv run pre-commit run --all-files` ALL exit 0.
- **Max feedback latency:** < 10s per task commit (unit-tier quick run); < 2 min per wave merge (full unit + the gate); < 5 min for the integration tier on a kind-equipped host.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirements | SC | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|--------------|----|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-1-01 | 03-01 | 1 | PIPE-06 | SC1 | T-03-01-04 | KubeconfigError(exit_code=7) added without renumbering existing 1..6; eks/ + kube/ packages importable | unit | `uv run pytest -m unit -q tests/unit/test_errors.py --no-cov` | ❌ W0 | ⬜ pending |
| 03-1-02 | 03-01 | 1 | PIPE-01, PIPE-06 | SC1 | T-03-01-05, T-03-01-06 | ClusterAccess immutable + ca_data verbatim passthrough (Pitfall 1); ClusterAccessError surfaces public AWS error codes only | unit | `uv run pytest -m unit -q tests/unit/test_eks_cluster.py --cov=aws_eks_helm_deploy.eks.cluster --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 03-1-03 | 03-01 | 1 | PIPE-01 | SC1 | T-03-01-01, T-03-01-02, T-03-01-03, T-03-01-04 | chmod 0600 BEFORE write_text (Pitfall 2 — call-order asserted); ca_data verbatim (Pitfall 1); cleanup on exception; FileNotFoundError suppression in finally | unit | `uv run pytest -m unit -q tests/unit/test_kubeconfig.py --cov=aws_eks_helm_deploy.kube.kubeconfig --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 03-2-01 | 03-02 | 1 | PIPE-06 | SC1, SC2 | T-03-02-SC | syrupy + pytest-rerunfailures dev deps installed and importable; HelmExecutionError canonical name at exit_code=5 with HelmError alias preserved | unit | `uv lock && uv sync && uv run python -c "import syrupy; import pytest_rerunfailures" && uv run pytest -m unit -q tests/unit/test_errors.py --no-cov` | ❌ W0 | ⬜ pending |
| 03-2-02 | 03-02 | 1 | PIPE-01, HISTORY-02, META-01 | SC1, SC4 | T-03-02-01, T-03-02-04 | --set-string used for ALL set_args (corrections #4 + Pitfall 4); --history-max emitted only when history_max is not None; argv snapshot baseline committed to git | unit (syrupy) | `uv run pytest -m unit -q tests/unit/test_helm_client_argv.py --no-cov` | ❌ W0 | ⬜ pending |
| 03-2-03 | 03-02 | 1 | PIPE-01, PIPE-06 | SC1, SC2 | T-03-02-02, T-03-02-03, T-03-02-05 | subprocess.run with check=False; HelmExecutionError(exit=5) on returncode!=0; HelmTimeoutError(exit=6) on TimeoutExpired; 32 KB stderr truncation on success AND failure paths; subprocess is the SOLE subprocess.run call site in src/ | unit | `uv run pytest -m unit -q tests/unit/test_helm_client_run.py tests/unit/test_helm_client_argv.py --cov=aws_eks_helm_deploy.helm.client --cov-branch --cov-fail-under=100 --no-header && grep -RIn "import subprocess" src/aws_eks_helm_deploy/ \| awk 'END{exit NR==1?0:1}'` | ❌ W0 | ⬜ pending |
| 03-3-01 | 03-03 | 2 | CHART-01, CHART-05 | SC1, SC2 | T-03-03-01, T-03-03-02, T-03-03-04 | yaml.safe_load exclusively (NEVER yaml.load — code-execution pitfall); repo:// + oci:// rejected with ChartResolutionError(exit=4); name/version fallbacks + apiVersion v1 warn (non-fatal) | unit | `uv run pytest -m unit -q tests/unit/test_chart_local.py --cov=aws_eks_helm_deploy.chart.local --cov-branch --cov-fail-under=100 --no-header && grep -RIn "yaml\\.load[^_]" src/ \| awk 'NR>0{exit 1}'` | ❌ W0 | ⬜ pending |
| 03-4-01 | 03-04 | 3 | HISTORY-01 | SC3 | T-03-04-02 | Settings.history_max ge=0 validator rejects negative integers at parse time; Settings.timeout default updated to "600s" per corrections #5 | unit | `uv run pytest -m unit -q tests/unit/test_settings.py --cov=aws_eks_helm_deploy.settings --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 03-4-02 | 03-04 | 3 | CHART-01, CHART-05, PIPE-01, PIPE-06, HISTORY-02, META-01 | SC1, SC2, SC3, SC4 | T-03-04-01, T-03-04-03, T-03-04-04, T-03-04-06 | UpgradeAction orchestrates 9-step chain via typed primitives only; OSError → KubeconfigError(exit=7) wrap; CHART-05 success message verbatim; OBS-01 9-field structlog info; META-01 opt-in with 5 BITBUCKET vars + missing-var warns; subprocess NOT imported by upgrade.py | unit | `uv run pytest -m unit -q tests/unit/test_upgrade_action.py --cov=aws_eks_helm_deploy.actions.upgrade --cov-branch --cov-fail-under=100 --no-header && grep -c "import subprocess" src/aws_eks_helm_deploy/actions/upgrade.py \| awk '$1==0{exit 0} $1!=0{exit 1}'` | ❌ W0 | ⬜ pending |
| 03-4-03 | 03-04 | 3 | CHART-01, CHART-05, PIPE-01, PIPE-06 | SC1, SC2 | T-03-04-07 | cli.py dispatches ACTION=upgrade to UpgradeAction(settings, strategy=strategy); passes the already-selected strategy (auth selection happens once); PipeError → pipe.fail + exit_code; unexpected → 99 | unit | `uv run pytest -m unit -q tests/unit/test_cli.py --cov=aws_eks_helm_deploy.cli --cov-branch --cov-fail-under=100 --no-header && uv run pytest -q` | ❌ W0 | ⬜ pending |
| 03-5-01 | 03-05 | 4 | CHART-01 | SC2 | (delegated to T-03-03-*) | Minimal chart fixture renders both with and without .Values.bitbucket guards | fixture | `test -f tests/fixtures/charts/minimal/Chart.yaml && uv run python -c "import yaml; assert yaml.safe_load(open('tests/fixtures/charts/minimal/Chart.yaml'))['name'] == 'minimal'"` | ❌ W0 | ⬜ pending |
| 03-5-02 | 03-05 | 4 | CHART-01 (prerequisite) | SC2 | T-03-05-01, T-03-05-03 | kind_kubeconfig fixture extracts admin kubeconfig via `kind get kubeconfig`; tempfile chmod 0600; skips cleanly on subprocess failure | fixture | `uv run python -c "import ast; tree = ast.parse(open('tests/integration/conftest.py').read()); fixtures = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert 'kind_kubeconfig' in fixtures"` | ❌ W0 | ⬜ pending |
| 03-5-03 | 03-05 | 4 | CHART-01, CHART-05, PIPE-01, PIPE-06, HISTORY-01, HISTORY-02, META-01 | SC2, SC3, SC4 | T-03-05-02, T-03-05-03, T-03-05-04 | Integration tests use kind admin kubeconfig path (NOT EKS token — corrections #7); all 4 tests carry @pytest.mark.flaky(reruns=3, reruns_delay=5) per ROADMAP Risk 2 | integration | `uv run pytest -m integration -q --collect-only tests/integration/test_upgrade_action.py --no-cov && (uv run pytest -m integration -q tests/integration/test_upgrade_action.py --no-cov \|\| echo "SKIPPED — kind not installed")` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave dependency notes:**
- **Wave 1 (parallel):** 03-01 + 03-02 — both modify `errors.py` and `tests/unit/test_errors.py`; file-overlap resolution per each plan's `dependencies_on_prior_plans` section. Recommended order: 03-01 appends KubeconfigError first; 03-02 renames HelmError → HelmExecutionError second (trivial rebase).
- **Wave 2:** 03-03 depends on Wave 1 (errors stable; helm.client TYPE_CHECKING forward reference resolves once chart.local lands). 03-03 modifies ONLY `chart/*` + `tests/unit/test_chart_local.py` — no overlap with 03-01/03-02.
- **Wave 3:** 03-04 depends on ALL of Wave 1 + Wave 2 (Composition root). Modifies settings.py + cli.py + creates actions/upgrade.py + test files for each. Single plan in the wave — no parallel conflict.
- **Wave 4:** 03-05 depends on ALL prior waves (consumes UpgradeAction's `kubeconfig_override` scaffold from 03-04 + HelmClient from 03-02 + ResolvedChart from 03-03 indirectly via UpgradeAction).

**Strict ordering enforcement:**
- 03-04 Task 03-4-03 (cli.py wire-in) modifies `cli.py` — this is the same file Phase 2 Plan 02-04 extended. The Phase 2 placeholder `pipe.success(...)` is REMOVED in favor of `UpgradeAction(settings, strategy=strategy).run(pipe)`.
- 03-04 Task 03-4-03 also modifies `tests/unit/test_cli.py` — the Phase 2 placeholder assertion is REPLACED with UpgradeAction-dispatch assertions. Existing select_strategy + bind_safe_context Phase 2 tests UNCHANGED.
- 03-02 RENAMES `HelmError` → `HelmExecutionError` + alias. Any existing Phase 1 imports continue to resolve (alias). Plan-Checker MUST grep `grep -RIn "HelmError" src tests` after merge: expected occurrences are (a) the renamed class in errors.py, (b) the alias line in errors.py, (c) any test that asserts the alias identity.

---

## Wave 0 Requirements

All Phase 3 test infrastructure builds on Phase 1 + Phase 2 + Plans 03-01..04 foundation. New files created BEFORE tests can be exercised:

- [ ] `src/aws_eks_helm_deploy/eks/__init__.py` (Plan 03-01, Task 03-1-01) — required before `test_eks_cluster.py` can import.
- [ ] `src/aws_eks_helm_deploy/eks/cluster.py` (Plan 03-01, Task 03-1-02) — `ClusterAccess` + `get_cluster_access`.
- [ ] `src/aws_eks_helm_deploy/kube/__init__.py` (Plan 03-01, Task 03-1-01) — required before `test_kubeconfig.py` can import.
- [ ] `src/aws_eks_helm_deploy/kube/kubeconfig.py` (Plan 03-01, Task 03-1-03) — `write_kubeconfig` context manager.
- [ ] `src/aws_eks_helm_deploy/errors.py` (Plans 03-01 + 03-02) — `KubeconfigError` (new, exit_code=7) + `HelmExecutionError` (renamed from HelmError, exit_code=5) + `HelmError = HelmExecutionError` alias.
- [ ] `src/aws_eks_helm_deploy/helm/__init__.py` (Plan 03-02, Task 03-2-01) — required before helm.client tests.
- [ ] `src/aws_eks_helm_deploy/helm/client.py` (Plan 03-02, Task 03-2-02) — `HelmClient`, `HelmResult`, `HelmRevision`, constants, helpers.
- [ ] `src/aws_eks_helm_deploy/chart/__init__.py` (Plan 03-03, Task 03-3-01) — required before chart tests.
- [ ] `src/aws_eks_helm_deploy/chart/local.py` (Plan 03-03, Task 03-3-01) — `ResolvedChart` + `resolve_local_chart`.
- [ ] `src/aws_eks_helm_deploy/actions/__init__.py` (Plan 03-04, Task 03-4-02) — required before upgrade-action tests.
- [ ] `src/aws_eks_helm_deploy/actions/upgrade.py` (Plan 03-04, Task 03-4-02) — `UpgradeAction` + `build_bitbucket_set_args` + `BITBUCKET_META_VARS`.
- [ ] `src/aws_eks_helm_deploy/settings.py` (extended by Plan 03-04, Task 03-4-01) — `history_max` field + `timeout` default updated.
- [ ] `src/aws_eks_helm_deploy/cli.py` (extended by Plan 03-04, Task 03-4-03) — dispatch ACTION=upgrade to UpgradeAction.
- [ ] `tests/unit/test_eks_cluster.py` (Plan 03-01, Task 03-1-02) — 7 tests under @mock_aws.
- [ ] `tests/unit/test_kubeconfig.py` (Plan 03-01, Task 03-1-03) — 13 tests including the FileNotFoundError suppression branch.
- [ ] `tests/unit/test_errors.py` (modified by Plans 03-01 + 03-02) — appends KubeconfigError + HelmExecutionError + alias-identity tests.
- [ ] `tests/unit/test_helm_client_argv.py` (Plan 03-02, Task 03-2-02) — 8 syrupy snapshot tests.
- [ ] `tests/unit/test_helm_client_run.py` (Plan 03-02, Task 03-2-03) — 18+ subprocess-mocked tests.
- [ ] `tests/unit/__snapshots__/test_helm_client_argv.ambr` (Plan 03-02, Task 03-2-02) — syrupy snapshot baseline (committed to git, NOT in .gitignore).
- [ ] `tests/unit/test_chart_local.py` (Plan 03-03, Task 03-3-01) — 15+ tests covering all 15 branches.
- [ ] `tests/unit/test_settings.py` (extended by Plan 03-04, Task 03-4-01) — 6 new tests.
- [ ] `tests/unit/test_upgrade_action.py` (Plan 03-04, Task 03-4-02) — 20+ tests.
- [ ] `tests/unit/test_cli.py` (extended by Plan 03-04, Task 03-4-03) — placeholder replaced + 4 new dispatch tests.
- [ ] `tests/fixtures/charts/minimal/Chart.yaml` (Plan 03-05, Task 03-5-01) — minimal chart manifest.
- [ ] `tests/fixtures/charts/minimal/templates/configmap.yaml` (Plan 03-05, Task 03-5-01) — chart template.
- [ ] `tests/integration/conftest.py` (modified by Plan 03-05, Task 03-5-02) — adds `kind_kubeconfig` fixture.
- [ ] `tests/integration/test_upgrade_action.py` (Plan 03-05, Task 03-5-03) — 4+ integration tests.
- [ ] Framework additions: `uv add --group dev "syrupy~=5.3" "pytest-rerunfailures~=16.3"` — Plan 03-02 Task 03-2-01.

Existing Phase 1 + Phase 2 infrastructure REUSED (no new files):
- `tests/conftest.py` (auto-mark hook from Phase 1).
- `tests/integration/conftest.py::kind_cluster` (Phase 1 session fixture, REUSED in Plan 03-05; sibling fixture `kind_kubeconfig` added).
- `tests/acceptance/conftest.py::built_image` (NOT reused in Phase 3 — acceptance tier is unchanged; Phase 1's three acceptance tests still pass).
- `pyproject.toml` `[tool.pytest.ini_options].addopts` already has `--cov-fail-under=100` — Phase 3 inherits the gate.

When all source files in 03-01..04 have merged AND their corresponding test files exist AND `pytest -q` exits 0 at 100% coverage, the Phase 3 validation contract is fully active (unit tier). Integration tier activates when kind is installed locally; CI gating ships in Phase 6.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CONTEXT D1 layering — `helm/client.py` is the SOLE `subprocess.run` call site | PIPE-01 | A unit test asserting "no other module calls subprocess.run" is structurally a code-grep; surfaced here as the canonical gate. | `grep -RIn "import subprocess" src/aws_eks_helm_deploy/` returns ONLY the line in `src/aws_eks_helm_deploy/helm/client.py`. Expected: EXACTLY ONE matching file. |
| CONTEXT D1 layering — `actions/upgrade.py` does NOT import subprocess | PIPE-01 | Same grep-audit pattern. | `grep -c "import subprocess" src/aws_eks_helm_deploy/actions/upgrade.py` returns 0. |
| CONTEXT D1 layering — `kube/kubeconfig.py` does NOT import subprocess or helm | PIPE-01 | Same grep-audit pattern. | `grep -c "import subprocess\\|import helm\\|from aws_eks_helm_deploy.helm" src/aws_eks_helm_deploy/kube/kubeconfig.py` returns 0. |
| syrupy snapshot baseline committed to git | PIPE-01 / HISTORY-02 / META-01 | Snapshot file must NOT be in .gitignore per CONTEXT D9 + RESEARCH Section D. Existence + non-ignore status checked. | `test -f tests/unit/__snapshots__/test_helm_client_argv.ambr` AND `git check-ignore tests/unit/__snapshots__/test_helm_client_argv.ambr` exits non-zero (file is tracked). |
| RESEARCH Pitfall 1 — ca_data passed through verbatim | PIPE-01 | Asserted by `test_get_cluster_access_ca_data_passed_through_verbatim` unit test (Plan 03-01); manual verification only if unit test is removed. | Read `src/aws_eks_helm_deploy/eks/cluster.py`; confirm NO `base64.b64decode` or similar on `cluster["certificateAuthority"]["data"]`. |
| RESEARCH Pitfall 2 — chmod 0600 BEFORE write_text in kubeconfig writer | PIPE-01 | Asserted by `test_chmod_happens_before_write_content` call-order test (Plan 03-01); structural verification by code read. | Read `src/aws_eks_helm_deploy/kube/kubeconfig.py`; confirm `os.chmod(path, 0o600)` line appears BEFORE `path.write_text(...)` line in the function body. |
| Phase 3 OBS-01 stable-fields contract closure | CHART-05 | The 9-field structlog `info` event is unit-tested via structlog.testing.capture_logs in `test_run_emits_structlog_info_with_all_obs01_fields` (Plan 03-04). Production smoke happens in Phase 7. | `LOG_FORMAT=json uv run python -m aws_eks_helm_deploy 2>&1 \| python -c "import sys, json; line = next(l for l in sys.stdin if 'upgrade complete' in l); data = json.loads(line); assert all(k in data for k in ['action', 'release', 'namespace', 'chart_source', 'chart_name', 'chart_version', 'cluster', 'auth_strategy', 'helm_revision', 'duration_ms'])"` — requires a full env setup; integration tier covers the contract end-to-end. |
| Integration test on kind (Plan 03-05) | CHART-01, CHART-05, PIPE-01, PIPE-06, HISTORY-01, HISTORY-02, META-01 | Requires kind + docker + helm locally; CI gating lands in Phase 6 (CI-01). | `uv run pytest -m integration -q --no-cov tests/integration/test_upgrade_action.py` — all 4 tests pass when kind is installed; skip cleanly when absent. |
| RESEARCH corrections #7 — kind does NOT accept EKS bearer tokens | (kind tier scope only) | Architectural fact — verified by code-read of `tests/integration/test_upgrade_action.py` (uses `kubeconfig_override=kind_kubeconfig`, NOT the EKS-token path). | `grep -c "kubeconfig_override" tests/integration/test_upgrade_action.py` >= 4 (one per integration test). |
| Existing exit codes 1..6 byte-stable after Phase 3 | PIPE-06 | Plan 03-01 + 03-02 both modify errors.py; Plan-Checker verifies the exit-code reference. | `grep -E "exit_code = [1-7]" src/aws_eks_helm_deploy/errors.py` lists the codes in order: 1 (PipeError/ConfigurationError), 2 (AuthenticationError), 3 (ClusterAccessError), 4 (ChartResolutionError), 5 (HelmError/HelmExecutionError), 6 (HelmTimeoutError), 3 (EksTokenError — Phase 2 shared with ClusterAccessError), 7 (KubeconfigError — NEW Plan 03-01). NO renumbering of 1..6. |

*All other phase behaviors have automated verification.*

---

## ROADMAP / RESEARCH / CONTEXT Deviation Surface

This phase ships SEVENTEEN documented deviations from the ROADMAP / CONTEXT / RESEARCH wording. They are intentional and surfaced here so the phase-checker / plan-checker can verify them up-front:

### Plan 03-01 (3 deviations)

1. **`KubeconfigError.exit_code = 7`** (NOT 5 as CONTEXT D8 cites). CONTEXT D8 collides with existing `HelmError=5`. Per RESEARCH Section L Recommendation 1: preserve 1..6, add new errors with non-colliding integers. See `03-01-PLAN.md <deviations>`.
2. **`write_kubeconfig` does NOT raise `KubeconfigError` directly** — wraps as `KubeconfigError` happens at the action layer (Plan 03-04). Separation: writer = primitive, action = error context.
3. **`_build_kubeconfig_yaml` is private** (no public re-export) — minimal public surface for Phase 3.

### Plan 03-02 (5 deviations)

1. **syrupy `~= 5.3`** (NOT 4.7 as CONTEXT D9 cites) — corrections #1; current latest is 5.3.2 under `syrupy-project` org.
2. **pytest-rerunfailures `~= 16.3`** (NOT 14.0 as CONTEXT cites) — corrections #2; current latest is 16.3.
3. **`HelmError` rename → `HelmExecutionError`** at exit_code=5 unchanged + `HelmError = HelmExecutionError` alias for backward compat. Per RESEARCH Section L.
4. **stderr truncation uses char slicing** (not byte slicing) — approximation acceptable since helm stderr is ASCII-dominant.
5. **HELM_TIMEOUT NOT added as new Settings field** — corrections #5 + RESEARCH Open Question 1; reuse existing `Settings.timeout`.

### Plan 03-03 (4 deviations)

1. **`ResolvedChart` is concrete dataclass** (NOT Protocol) — RESEARCH Open Question 2; Phase 4 refactors to Protocol when repo:// + oci:// land.
2. **`resolve_local_chart(chart_spec: str, repo_root: pathlib.Path | None = None)`** signature (NOT RESEARCH Section H's `parse_chart_yaml(chart_path: Path)`) — `chart_spec` matches the env-var shape; `repo_root` for testability.
3. **Empty Chart.yaml raises `ChartResolutionError`** — explicit `if data is None` check; better UX than the implicit AttributeError.
4. **Non-mapping Chart.yaml raises `ChartResolutionError`** — `isinstance(data, dict)` defensive check.

### Plan 03-04 (5 deviations)

1. **`UpgradeAction.__init__(strategy: AuthStrategy | None = None)` kwarg** — prevents double `select_strategy` call (cli.py + action both selecting); idiomatic constructor injection.
2. **`os.environ` read INSIDE `build_bitbucket_set_args`** (not via Settings) — documented exception mirroring `auth/__init__.py::_derive_session_name`; BITBUCKET_* are platform-supplied.
3. **`# pragma: no cover` on cli.py `else: raise ConfigurationError` branch** — defensive scaffold for Phase 5's wider action Literal; currently unreachable.
4. **`--history-max 0` passed through to helm** — Pitfall 3 + CONTEXT D4; 0 means UNLIMITED per helm semantics.
5. **META-02 + META-03 NOT implemented** — Phase 5 scope per CONTEXT D5. META-02 already accidentally satisfied by `inject_bitbucket_metadata=False` default from Phase 1.

### Plan 03-05 (5 deviations)

1. **kind cluster name REUSES `test-pipe-integration`** (NOT CONTEXT D10's suggested `kind-phase3`) — reuses existing Phase 1 `kind_cluster` fixture; saves session startup time.
2. **Tests use kind admin kubeconfig** (NOT the EKS token path) — corrections #7; kind does NOT accept k8s-aws-v1.* bearer tokens.
3. **Test 2 asserts EXACTLY 5 revisions** (NOT ≤ 5) — stricter assertion catches both over-retention AND over-aggressive pruning.
4. **`PipeIO` mocked with `MagicMock(spec=PipeIO)`** — avoids bitbucket-pipes-toolkit `Pipe(pipe_metadata=..., schema=...)` boot complexity in integration tests.
5. **Test 4 (failure path) asserts via `pytest.raises(HelmExecutionError)`** (NOT through cli.main's pipe.fail) — orthogonal to the integration scope; cli.py error mapping is unit-tested in Plan 03-04.

The phase-checker / phase-verifier MUST acknowledge these deviations before flagging them as gaps in `03-VERIFICATION.md`.

---

## Coverage Roll-Up

Phase 3 adds the following modules; all MUST hit 100% line + 100% branch by the end of the phase (per the active `--cov-fail-under=100` gate from Phase 1):

| Module | Owner Plan | Coverage Target | Branch Coverage Note |
|--------|------------|------------------|----------------------|
| `src/aws_eks_helm_deploy/eks/__init__.py` | 03-01 | 100% (trivial) | No branches. |
| `src/aws_eks_helm_deploy/eks/cluster.py` | 03-01 | 100% line + 100% branch | ClientError branch + happy path. |
| `src/aws_eks_helm_deploy/kube/__init__.py` | 03-01 | 100% (trivial) | No branches. |
| `src/aws_eks_helm_deploy/kube/kubeconfig.py` | 03-01 | 100% line + 100% branch | The `FileNotFoundError` suppression branch in `finally` AND the cleanup-on-exception branch both exercised. |
| `src/aws_eks_helm_deploy/helm/__init__.py` | 03-02 | 100% (trivial) | No branches. |
| `src/aws_eks_helm_deploy/helm/client.py` | 03-02 | 100% line + 100% branch | All `_build_argv` branches (history_max present + absent, --set-string loop, --values loop) + all `upgrade_install` branches (success + non-zero + TimeoutExpired + truncate + revision-present + revision-absent) + all `history` branches + all `_parse_timeout` branches + all `_truncate_stderr` branches. |
| `src/aws_eks_helm_deploy/chart/__init__.py` | 03-03 | 100% (trivial) | No branches. |
| `src/aws_eks_helm_deploy/chart/local.py` | 03-03 | 100% line + 100% branch | All 15 branches enumerated in Plan 03-03 behavior. |
| `src/aws_eks_helm_deploy/actions/__init__.py` | 03-04 | 100% (trivial) | No branches. |
| `src/aws_eks_helm_deploy/actions/upgrade.py` | 03-04 | 100% line + 100% branch | All 3 required-env-var early-check branches + INJECT True/False + 5 BITBUCKET var present/missing pairs (10 branches across multiple tests) + OSError → KubeconfigError wrap + each typed-error propagation path + success path. |
| `src/aws_eks_helm_deploy/cli.py` | extended by 03-04 | 100% line + 100% branch | New `if settings.action == "upgrade": UpgradeAction(...).run(pipe)` branch + the `# pragma: no cover` defensive `else: raise ConfigurationError` (forward scaffold for Phase 5). |
| `src/aws_eks_helm_deploy/errors.py` | extended by 03-01 + 03-02 | 100% (existing 100% + new `KubeconfigError` class + `HelmExecutionError` renamed class + `HelmError` alias line) | All new classes tested in `test_errors.py`; alias-identity test asserts `HelmError is HelmExecutionError`. |
| `src/aws_eks_helm_deploy/settings.py` | extended by 03-04 | 100% (existing 100% + new `history_max` field + the ge=0 validator branch) | `test_history_max_rejects_negative_integer` exercises the ge=0 ValidationError branch; `test_history_max_accepts_zero` + `test_history_max_default_is_none` exercise the success branches. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify OR documented Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (13 tasks across 5 plans, every task has an automated verify; integration tier (Task 03-5-03) has a runtime gate that auto-skips when kind absent — still automated, just conditional)
- [ ] Wave 0 covers all MISSING references (see Wave 0 Requirements above)
- [ ] No watch-mode flags (no `--watch`, no `pytest-watch`)
- [ ] Feedback latency < 10s per task quick-run (verified locally: existing Phase 1+2 ~5s + ~30 new Phase 3 unit tests ~3s + structlog/moto warmup ~1s)
- [ ] All seventeen documented deviations are surfaced to the phase-checker (this file's "ROADMAP / RESEARCH / CONTEXT Deviation Surface" section)
- [ ] `nyquist_compliant: true` to be set after Wave 4 lands and the full unit + integration suites pass (integration tier requires kind on host)

**Approval:** pending
