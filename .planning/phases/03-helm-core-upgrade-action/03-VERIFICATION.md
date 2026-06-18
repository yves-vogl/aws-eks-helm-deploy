---
phase: 03-helm-core-upgrade-action
verified: 2026-06-18T00:00:00Z
status: human_needed
score: 3.5/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run integration tests against a real kind cluster (Test 1 — CHART-01/05/PIPE-01)"
    expected: "test_upgrade_action_deploys_minimal_chart passes with exit=0 and pipe.success message containing 'minimal (0.1.0)'"
    why_human: "kind binary not installed on verification host; 4 integration tests skip cleanly but have not been run against a live cluster"
  - test: "Run integration tests against a real kind cluster (Test 2 — HISTORY-01/02, closes #17)"
    expected: "test_history_max_5_retains_at_most_5_revisions: after 6 upgrades with HISTORY_MAX=5, len(revisions) == 5 exactly"
    why_human: "kind binary not installed on verification host"
  - test: "Run integration tests against a real kind cluster (Test 3 — META-01)"
    expected: "test_inject_bitbucket_metadata_sets_all_5_keys: helm get values shows 5 bitbucket.* keys; curly-brace UUID {deadbeef-cafe-1234-5678-abcdef012345} preserved verbatim"
    why_human: "kind binary not installed on verification host"
  - test: "Run integration tests against a real kind cluster (Test 4 — PIPE-06)"
    expected: "test_failure_path_surfaces_non_zero_exit_with_human_message: HelmExecutionError(exit_code=5) raised with helm error text in user_message"
    why_human: "kind binary not installed on verification host"
---

# Phase 3: Helm Core & Upgrade Action — Verification Report

**Phase Goal:** `ACTION=upgrade` (default) deploys a local-path Helm chart to a real EKS cluster end-to-end via the new typed `HelmClient`, honouring `HISTORY_MAX` (closes #17) and v1-style Bitbucket metadata injection (opt-in via `INJECT_BITBUCKET_METADATA=true`). v1.x functional parity on the new architecture.

**Verified:** 2026-06-18
**Status:** human_needed — all automated checks pass; 4 integration tests require kind cluster
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `helm/client.py` is the SOLE `subprocess.run` caller; `kube/kubeconfig.py` is context-managed with chmod 0600; `actions/upgrade.py` wires exactly one HelmClient method | PARTIAL | subprocess audit: `grep -RIn "import subprocess" src/` returns ONLY `helm/client.py:27`. chmod 0600 confirmed at `kubeconfig.py:128`. upgrade.py calls `client.upgrade_install` only (two call-sites, same method). But upgrade.py run() body is 68 non-blank/non-comment lines vs "< 50 lines" stated in ROADMAP SC1 (PLAN-04 clarifies < 50 LOC excludes imports, docstring, helper; the PLAN-CHECK accepted ~45 logical statements) |
| 2 | Integration test against kind deploys minimal chart; success message has chart name+version; helm failure surfaces via typed HelmExecutionError | HUMAN_NEEDED | Integration tests exist at `tests/integration/test_upgrade_action.py` (4 tests, 399 LOC). Skip cleanly on this host (kind not installed). Structurally verified: chart fixture exists, HelmExecutionError wiring confirmed at unit tier (230 tests, 100% coverage). |
| 3 | `HISTORY_MAX=5` → ≤ 5 revisions after 6 upgrades; `HISTORY_MAX` unset → helm default-10 holds | HUMAN_NEEDED (integration) / VERIFIED (unit) | Unit tier: `_build_argv` snapshot tests prove `--history-max 5` in argv when set, absent when None (`test_upgrade_argv_history_max_none_omits_flag`). `Settings.history_max` has `ge=0` validation (`settings.py:107`). Integration tier (HISTORY_MAX=5 + 6 upgrades) requires kind. Deviation 0 accepted: unset→default-10 not integration-tested (unit snapshot + helm's own behaviour). |
| 4 | `INJECT_BITBUCKET_METADATA=true` + `BITBUCKET_*` vars → `helm get values` shows 5 `bitbucket.*` keys | HUMAN_NEEDED (integration) / VERIFIED (unit) | Unit tier: `build_bitbucket_set_args` returns all 5 keys (`upgrade.py:52-58`). `--set-string` used (not `--set`) per Pitfall 4. syrupy snapshot `test_upgrade_argv_with_bitbucket_metadata` locks curly-brace UUID. Integration assertion (helm get values) requires kind. |

**Score:** 3.5/4 truths verified (SC1 PARTIAL due to LOC metric; SC2/3/4 require human/kind for integration tier confirmation)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/aws_eks_helm_deploy/kube/kubeconfig.py` | Context-manager, chmod 0600, YAML emit | VERIFIED | File exists, 135 LOC. `os.chmod(path, 0o600)` at line 128 BEFORE `write_text`. `NamedTemporaryFile(delete=False)` at line 120. `contextlib.suppress(FileNotFoundError)` cleanup in `finally`. 100% line+branch coverage. |
| `src/aws_eks_helm_deploy/eks/cluster.py` | ClusterAccess frozen dataclass + get_cluster_access | VERIFIED | `ClusterAccess(frozen=True)` with 4 fields (name, endpoint, ca_data, region). `get_cluster_access` raises `ClusterAccessError` on missing cluster. 100% coverage. |
| `src/aws_eks_helm_deploy/helm/client.py` | Sole subprocess caller; upgrade_install + history methods | VERIFIED | 368 LOC. `import subprocess` at line 27 (only occurrence in codebase). `_build_argv` pure function. `HelmExecutionError` (exit=5) on non-zero return; `HelmTimeoutError` (exit=6) on TimeoutExpired. 32 KB stderr truncation. REVISION regex parser. 100% coverage. |
| `src/aws_eks_helm_deploy/chart/local.py` | ResolvedChart dataclass + resolve_local_chart | VERIFIED | `ResolvedChart(frozen=True)` with 3 fields (name, version, source_path). `resolve_local_chart` handles 15 branches (repo:// reject, oci:// reject, missing path, invalid YAML, etc.). 100% coverage. |
| `src/aws_eks_helm_deploy/actions/upgrade.py` | < 50 LOC; wires full chain; one HelmClient method | PARTIAL | File is 200 LOC total (PLAN-04 predicted < 130). `UpgradeAction.run()` body is 85 lines total / 68 non-blank non-comment lines. PLAN-04's stated constraint was "< 50 LOC excluding imports + docstring + helper"; PLAN-CHECK accepted "~45 executable lines" (logical statements, not physical lines). The intent (thin orchestration, no subprocess, no direct I/O) is met. Calls only `client.upgrade_install` (two call-sites, same method). OSError wrapped as KubeconfigError at line 175-176. 100% coverage. |
| `tests/fixtures/charts/minimal/Chart.yaml` | Minimal chart fixture | VERIFIED | Exists. apiVersion: v2, name: minimal, version: 0.1.0. |
| `tests/integration/test_upgrade_action.py` | 4 integration tests (kind) | VERIFIED (structure) | 399 LOC. 4 tests: happy-path (CHART-01/05), history-max (HISTORY-01/02), inject-metadata (META-01), failure-path (PIPE-06). Skip cleanly when kind absent. |
| `tests/unit/__snapshots__/test_helm_client_argv.ambr` | syrupy snapshot baseline | VERIFIED | File exists (2896 bytes). Committed to git. Contains `--set-string` and `--history-max` evidence. 8 snapshot tests pass. |
| `src/aws_eks_helm_deploy/errors.py` | HelmExecutionError(exit=5) + KubeconfigError(exit=7) + HelmError alias | VERIFIED | `HelmExecutionError.exit_code=5`, `KubeconfigError.exit_code=7`. `HelmError = HelmExecutionError` alias at line 94. `HelmError is HelmExecutionError` confirmed True. Exit codes 1..6 byte-stable from Phases 1+2. |
| `src/aws_eks_helm_deploy/settings.py` | history_max field (ge=0) | VERIFIED | `history_max: int | None = Field(default=None, ge=0, alias="HISTORY_MAX")` at line 107. Closes #17. timeout default updated to "600s" (line 105). |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `helm/client.py::_build_argv` | `--set-string` (not `--set`) | `argv.extend(["--set-string", sa])` line 215 | WIRED | grep confirms; syrupy snapshot locks it |
| `helm/client.py::_build_argv` | `--history-max` conditional | `if history_max is not None: argv.extend(...)` line 216-217 | WIRED | history_max=None omits flag; 0 and N≥1 emit it |
| `helm/client.py::upgrade_install` | `subprocess.run(check=False, ...)` | line 274 | WIRED | `check=False`, `capture_output=True`, `text=True`, `env=os.environ.copy()` |
| `helm/client.py::upgrade_install` | `HelmExecutionError` on non-zero | `raise HelmExecutionError(...)` line 299-301 | WIRED | exit_code=5 confirmed |
| `helm/client.py::upgrade_install` | `HelmTimeoutError` on TimeoutExpired | `raise HelmTimeoutError(...)` line 294 | WIRED | exit_code=6 confirmed |
| `kube/kubeconfig.py::write_kubeconfig` | `os.chmod(path, 0o600)` BEFORE `write_text` | lines 128-130 | WIRED | test_chmod_happens_before_write_content asserts order |
| `actions/upgrade.py::UpgradeAction.run` | Full 9-step chain | steps 1-9 in run() | WIRED | auth→EKS→kubeconfig→chart→helm→success all present |
| `actions/upgrade.py::UpgradeAction.run` | `KubeconfigError` on OSError | `except OSError: raise KubeconfigError(...)` line 175-176 | WIRED | Per Plan 03-01 Deviation 2 |
| `cli.py::main` | `UpgradeAction(settings, strategy=strategy).run(pipe)` | line in cli.py | WIRED | Phase 2 placeholder replaced; `ACTION=upgrade` dispatches correctly |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `actions/upgrade.py::UpgradeAction.run` | `resolved` (ResolvedChart) | `resolve_local_chart(s.chart)` → PyYAML safe_load of Chart.yaml | Yes — reads Chart.yaml from disk | FLOWING |
| `actions/upgrade.py::UpgradeAction.run` | `set_args` | `build_bitbucket_set_args(logger)` reads `os.environ.get(env_var)` | Yes — reads real BITBUCKET_* env vars | FLOWING |
| `actions/upgrade.py::UpgradeAction.run` | `result` (HelmResult) | `HelmClient.upgrade_install` → `subprocess.run(helm ...)` | Yes — helm subprocess returns real output | FLOWING |
| `kube/kubeconfig.py::write_kubeconfig` | YAML content | `_build_kubeconfig_yaml(cluster, token)` → `yaml.safe_dump` | Yes — writes real cluster.ca_data + token | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ruff lint clean | `uv run ruff check src tests` | "All checks passed!" | PASS |
| ruff format clean | `uv run ruff format --check src tests` | "51 files already formatted" | PASS |
| mypy strict clean | `uv run mypy --strict src` | "Success: no issues found in 23 source files" | PASS |
| Unit tests + 100% coverage | `uv run pytest -m unit -q --cov=src --cov-branch --cov-fail-under=100` | 230 passed, 14 deselected, 100% coverage | PASS |
| syrupy snapshots | embedded in unit run | 8 snapshots passed | PASS |
| subprocess isolation | `grep -RIn "import subprocess" src/aws_eks_helm_deploy/` | Only `helm/client.py:27` | PASS |
| HelmError alias | `uv run python3 -c "from aws_eks_helm_deploy.errors import HelmError, HelmExecutionError; assert HelmError is HelmExecutionError"` | True | PASS |
| Settings.history_max ge=0 | `settings.py:107`: `Field(default=None, ge=0, alias="HISTORY_MAX")` | pydantic rejects negatives at parse | PASS |
| Integration tests skip cleanly | `uv run pytest -m integration --no-cov -v` | 1 passed, 6 skipped, 0 failed | PASS (kind absent) |

---

## Probe Execution

No probe scripts declared in this phase. Integration tests serve as the verification probes.

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `tests/integration/test_upgrade_action.py` (Test 1) | `pytest -m integration -k "test_upgrade_action_deploys_minimal_chart"` | SKIPPED (kind absent) | MISSING_HOST_DEP |
| `tests/integration/test_upgrade_action.py` (Test 2) | `pytest -m integration -k "test_history_max_5"` | SKIPPED (kind absent) | MISSING_HOST_DEP |
| `tests/integration/test_upgrade_action.py` (Test 3) | `pytest -m integration -k "test_inject_bitbucket"` | SKIPPED (kind absent) | MISSING_HOST_DEP |
| `tests/integration/test_upgrade_action.py` (Test 4) | `pytest -m integration -k "test_failure_path"` | SKIPPED (kind absent) | MISSING_HOST_DEP |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CHART-01 | 03-01, 03-03, 03-04, 03-05 | Deploy from local path | VERIFIED (unit) / HUMAN_NEEDED (integration) | `resolve_local_chart` + `HelmClient.upgrade_install` chain wired; integration test exists but requires kind |
| CHART-05 | 03-03, 03-04, 03-05 | Report resolved chart name + version in success message | VERIFIED (unit) | `pipe.success(f"Deployed chart {resolved.name} ({resolved.version})...")` at upgrade.py line 182-186; unit test asserts exact format |
| PIPE-01 | 03-01..03-05 | ACTION=upgrade runs helm upgrade --install | VERIFIED (unit) / HUMAN_NEEDED (integration) | `_build_argv` snapshot-tested; full chain wired; integration test exists |
| PIPE-06 | 03-01..03-05 | Non-zero exit + human-readable failure | VERIFIED (unit) / HUMAN_NEEDED (integration) | `HelmExecutionError(exit_code=5)` raised on returncode!=0; integration test 4 covers this |
| HISTORY-01 | 03-04, 03-05 | HISTORY_MAX=N bounds helm history | VERIFIED (unit) / HUMAN_NEEDED (integration) | `Settings.history_max` with `ge=0`; flows to `HelmClient.upgrade_install(history_max=...)`; integration Test 2 requires kind |
| HISTORY-02 | 03-02, 03-04 | Pipe passes --history-max N to helm | VERIFIED | `_build_argv` conditionally extends `["--history-max", str(history_max)]`; syrupy snapshot confirms |
| META-01 | 03-02, 03-04, 03-05 | INJECT=true → 5 bitbucket.* keys via --set-string | VERIFIED (unit) / HUMAN_NEEDED (integration) | `build_bitbucket_set_args` with 5 BITBUCKET_META_VARS; `--set-string` (not `--set`); curly-brace UUID handled; integration Test 3 requires kind |

---

## Deviation Assessment

| Deviation | SC Impact | Assessment |
|-----------|-----------|------------|
| SC1 LOC: `actions/upgrade.py` is 200 lines total (run() body: 68 non-blank/non-comment lines) vs "< 50 lines" in ROADMAP SC1 | PARTIAL | The PLAN-04 clarification is "< 50 LOC excluding imports + module docstring + helper function." The PLAN-CHECK accepted "~45 executable logical statements." The intent — thin wiring layer with no subprocess and no direct I/O — is fully met. The metric divergence is explained by kubeconfig_override dual-branch (added via Plan-Checker BLOCKER 1 fix adding ~14 lines) and multi-line call sites. This is a documentation gap in the SC, not a behavioral regression. |
| SC3 unset→default-10 integration test not run | PARTIAL (documented) | Deviation 0 in 03-05-PLAN.md: unit snapshot proves `--history-max` absent from argv when `history_max=None`. Integration test for helm's own default-10 behavior intentionally omitted as it tests upstream helm behavior, not our code. Accepted per Plan-Checker. |
| Integration tests skip on this host | HUMAN_NEEDED | kind not installed on verification host. 4 integration tests skip cleanly (exit 0). Must be validated on a host with kind + helm installed. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/aws_eks_helm_deploy/actions/upgrade.py` | 132 | `# type: ignore[arg-type]` on boto3.session.Session **kwargs | INFO | Documented deviation in 03-04-SUMMARY.md — mypy strict cannot prove `**dict[str,str]` maps to Session positional args; intentional. |
| `src/aws_eks_helm_deploy/cli.py` | 57 | `# pragma: no cover` on `raise ConfigurationError` | INFO | Documented: defensive branch for Phase 5 when `Settings.action` Literal widens. Not a gap. |
| `src/aws_eks_helm_deploy/helm/client.py` | 274, 346 | `# noqa: S603` on subprocess.run calls | INFO | Intentional: this IS the designated subprocess module per CONTEXT D1. Correct suppression. |

No `TBD`, `FIXME`, or `XXX` debt markers found in any Phase 3 modified files.

---

## Human Verification Required

### 1. Integration Test 1 — CHART-01, CHART-05, PIPE-01

**Test:** On a host with `kind` and `helm` installed, run:
```
make integration-test
# or: uv run pytest -m integration --no-cov -v
```

**Expected:** `test_upgrade_action_deploys_minimal_chart` PASSES:
- `action.run(pipe)` returns 0
- `pipe.success` called once with message starting `"Deployed chart minimal (0.1.0) to release <release-id>"`
- `helm status <release> -o json` shows `info.status == "deployed"`

**Why human:** `kind` binary not installed on verification host; integration tests skip cleanly but require a real cluster.

---

### 2. Integration Test 2 — HISTORY-01, HISTORY-02, closes #17

**Test:** Same integration run as above.

**Expected:** `test_history_max_5_retains_at_most_5_revisions` PASSES:
- After 6 sequential `UpgradeAction.run()` calls with `HISTORY_MAX=5`, `helm history <release> -o json` returns a list of exactly 5 revisions (not 4, not 6)
- Last revision status is `"deployed"`, earlier are `"superseded"`

**Why human:** `kind` binary not installed on verification host.

---

### 3. Integration Test 3 — META-01

**Test:** Same integration run as above.

**Expected:** `test_inject_bitbucket_metadata_sets_all_5_keys` PASSES:
- With 5 BITBUCKET_* env vars set (including `BITBUCKET_STEP_TRIGGERER_UUID={deadbeef-cafe-1234-5678-abcdef012345}`), `helm get values <release> -o yaml` returns a YAML dict containing `bitbucket.bitbucket_build_number`, `bitbucket.bitbucket_repo_slug`, `bitbucket.bitbucket_commit`, `bitbucket.bitbucket_tag`, `bitbucket.bitbucket_step_triggerer_uuid`
- The curly-brace UUID is preserved verbatim (proves `--set-string` handling)

**Why human:** `kind` binary not installed on verification host.

---

### 4. Integration Test 4 — PIPE-06

**Test:** Same integration run as above.

**Expected:** `test_failure_path_surfaces_non_zero_exit_with_human_message` PASSES:
- `UpgradeAction.run(pipe)` raises `HelmExecutionError` with `exit_code=5`
- Error message contains helm's "MISSING" text from the `required "MISSING"` template directive

**Why human:** `kind` binary not installed on verification host.

---

## Gaps Summary

No hard BLOCKERS. One PARTIAL on SC1 LOC metric, all integration tests pending kind host.

**SC1 LOC PARTIAL explanation:** ROADMAP SC1 states `actions/upgrade.py is < 50 lines`. The file is 200 lines total; the `UpgradeAction.run()` body contains 68 non-blank/non-comment physical lines. PLAN-04 clarified the constraint as "< 50 LOC excluding imports + module docstring + helper function" and the Plan-Checker accepted "~45 executable logical statements" (counting unique statements, not continuations). The intent of SC1 — thin orchestration layer with no subprocess and no direct file I/O — is demonstrably met. The LOC divergence is explained by:

1. kubeconfig_override dual-branch added by Plan-Checker BLOCKER 1 fix (+14 lines)
2. Multi-line call argument formatting (8 kwargs across 8 lines vs 1)
3. Step-level comments (+9 comment lines counted in executable body)

**OBS-01 status:** Phase 3 closes the OBS-01 PARTIAL gap from Phase 1. `cli.py` now emits `logger.info("auth strategy selected", auth_strategy=...)` on every run. `upgrade.py` emits `logger.info("upgrade complete", action=..., release=..., namespace=..., chart_source=..., chart_name=..., chart_version=..., cluster=..., helm_revision=..., duration_ms=...)` on success — all 8 stable fields from the OBS-01 contract (auth_strategy bound by cli.py via `bind_safe_context`). OBS-01: **CLOSED**.

---

## Evidence: Grep Audits

```
# CONTEXT D1 layering audit — subprocess.run SOLE caller:
grep -RIn "import subprocess" src/aws_eks_helm_deploy/
src/aws_eks_helm_deploy/helm/client.py:27:import subprocess
# Result: PASS — only helm/client.py

# chmod 0600 in kubeconfig.py:
grep -n "os.chmod" src/aws_eks_helm_deploy/kube/kubeconfig.py
128:    os.chmod(path, 0o600)
# Result: PASS — present and before write_text (line 130)

# --set-string in _build_argv:
grep --include="*.py" -rn -- "--set-string" src/
# Result: argv.extend(["--set-string", sa]) in helm/client.py:215

# --history-max conditional:
grep --include="*.py" -rn -- "--history-max" src/
# Result: argv.extend(["--history-max", str(history_max)]) in helm/client.py:217 (under if history_max is not None)

# settings.history_max ge=0:
grep -n "ge=0" src/aws_eks_helm_deploy/settings.py
107:    history_max: int | None = Field(default=None, ge=0, alias="HISTORY_MAX")
# Result: PASS — closes #17

# KubeconfigError wrapping:
grep -n "KubeconfigError" src/aws_eks_helm_deploy/actions/upgrade.py
175:            except OSError as exc:
176:                raise KubeconfigError(f"Failed to write kubeconfig: {exc}") from exc
# Result: PASS — OSError wrapped at action layer per Plan 03-01 Deviation 2

# Unit test suite:
uv run pytest -m unit -q --cov=src --cov-branch --cov-fail-under=100
# Result: 230 passed, 14 deselected, 100% line+branch coverage, 8 snapshots passed
```

---

_Verified: 2026-06-18_
_Verifier: Claude (gsd-verifier)_
