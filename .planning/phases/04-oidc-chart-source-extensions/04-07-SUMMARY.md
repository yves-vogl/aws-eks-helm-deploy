---
phase: 04-oidc-chart-source-extensions
plan: 7
subsystem: chart-sources
tags:
  - oci
  - cosign
  - keyless
  - sigstore
  - helm-registry-login
  - password-stdin
  - subprocess-exception-d5
  - dockerfile-multistage
  - cosign-fetch
  - sha256-checksum
  - secretstr-unwrap
  - tempdir-isolation
  - integration-test
  - acceptance-test
dependency_graph:
  requires:
    - 04-02   # Settings: chart_verify, registry_password (SecretStr)
    - 04-05   # ChartSource Protocol + _parse_chart_yaml helper + factory skeleton
    - 04-06   # HelmClient._run_helm_subcommand helper + RepoChart pattern
  provides:
    - OciChart class (CHART-03 + CHART-04)
    - HelmClient.registry_login + pull_oci (CHART-03)
    - cosign-fetch Dockerfile stage (CHART-04)
  affects:
    - chart/__init__.py (oci:// branch now active, pragma lifted)
    - Dockerfile (new cosign-fetch stage between helm-fetch and runtime)
tech_stack:
  added:
    - cosign 2.6.3 (sigstore/cosign — CNCF Graduated) added to runtime image
  patterns:
    - tempdir context-manager with 4-env-var isolation (RESEARCH §5)
    - method-level pytest-mock for shared-module subprocess patching
    - SHA256 verification via grep + sha256sum -c (Sigstore canonical pattern)
key_files:
  created:
    - src/aws_eks_helm_deploy/chart/oci.py
    - tests/unit/test_chart_oci.py
    - tests/acceptance/test_image_has_cosign.py
  modified:
    - src/aws_eks_helm_deploy/helm/client.py
    - src/aws_eks_helm_deploy/chart/__init__.py
    - Dockerfile
    - tests/unit/test_chart_init_select_source.py
    - tests/unit/test_helm_client_argv.py
    - tests/unit/test_helm_client_run.py
    - tests/unit/__snapshots__/test_helm_client_argv.ambr
    - tests/integration/test_chart_sources.py
decisions:
  - "Method-level mocking (_COSIGN_METHOD_PATCH) for cosign tests: avoids shared-module
    subprocess.run binding conflict when both cosign (oci.py) and helm (client.py) patches
    target the same subprocess module object. Tests needing real _run_cosign_verify behavior
    call the method directly without helm interference."
  - "Cosign failure/timeout tests in resolve() use ChartResolutionError side_effect on
    _run_cosign_verify method mock — same error the real method raises — rather than
    subprocess.CalledProcessError side_effect on subprocess.run (which would be overridden
    by the helm patch)."
  - "exist_ok=True on unpack_dir.mkdir() — required because test harness patches mkdtemp
    to return tmp_path which already has the unpacked/ directory pre-created by _make_chart_dir."
metrics:
  duration: "988s (~16 min)"
  completed: "2026-06-18T14:16:40Z"
  tasks_completed: 2
  files_modified: 11
  tests_added: 57
  coverage: "100% line + branch on chart/oci.py, helm/client.py (all new methods)"
---

# Phase 4 Plan 7: OciChart + Cosign Verify + Dockerfile cosign-fetch Stage Summary

JWT auth with OCI registry login (--password-stdin) + keyless Cosign verify BEFORE helm pull, tempdir-isolated; cosign 2.6.3 binary SHA256-verified in Dockerfile multi-stage build.

## Objective Achieved

Plan 04-07 (Wave 3, Phase 4) is complete. `OciChart` is the final piece closing CHART-03 and CHART-04:

- **CHART-03**: OCI-registry chart source — `helm registry login` + `helm pull oci://` via typed HelmClient methods with full 4-env-var credential isolation.
- **CHART-04**: Optional keyless Cosign signature verification — `cosign verify <oci-ref>` runs BEFORE `helm pull` (R6), against the registry reference not a local tarball (R5), cleans up on failure (R8).

## What Was Built

### Task 04-7-01: HelmClient.registry_login + pull_oci

Two new typed methods on `HelmClient`:

- `registry_login(host, username, password, env)` — password via `input=` to subprocess, NEVER in argv (`--password-stdin`, R4). Bypasses `_run_helm_subcommand` to support `input=`.
- `pull_oci(reference, destination, untar_dir, version, env)` — `helm pull oci://<ref> --untar --untar-dir` via `_run_helm_subcommand`.

Both raise `ChartResolutionError` on failure (exit_code=4). Three new syrupy snapshot tests + 10 new subprocess-mocked tests. `helm/client.py` 100% coverage.

**Commits:**
- `e8d4656` — feat(04-07): add HelmClient.registry_login + pull_oci typed methods

### Task 04-7-02: OciChart + cosign + Dockerfile + tests

**`src/aws_eks_helm_deploy/chart/oci.py`** (NEW, ~200 LOC):
- `OciChart` class satisfying `ChartSource` Protocol structurally.
- `resolve()` context-manager: mkdtemp → 4-env-var isolation → optional registry_login → optional cosign verify → helm pull oci:// → single-subdir discovery → Chart.yaml parse → yield ResolvedChart → finally rmtree.
- `_run_helm_registry_login`: SINGLE `.get_secret_value()` unwrap site (R13).
- `_run_cosign_verify`: `subprocess.run` for cosign — CONTEXT D5 scoped exception. WARN log `chart.verify.unconstrained_identity` when verify=True without identity/issuer constraints.

**`src/aws_eks_helm_deploy/chart/__init__.py`** (MODIFIED):
- Lifted `# pragma: no cover  # Plan 04-07 lifts this pragma` on oci:// branch.
- Removed `# type: ignore` from `_build_oci_chart`. 
- Updated module docstring.

**`Dockerfile`** (MODIFIED):
- `ARG COSIGN_VERSION=2.6.3` added at top.
- New `cosign-fetch` stage between `helm-fetch` (line 39) and `runtime` (line 89). SHA256 verified via `grep "  cosign-linux-amd64$" cosign_checksums.txt | sha256sum -c` (Sigstore canonical pattern, RESEARCH §6).
- `COPY --from=cosign-fetch /cosign /usr/local/bin/cosign` in runtime stage.

**Tests:**
- `tests/unit/test_chart_oci.py` (NEW, 17 tests): all branches covered including R4/R5/R6/R7/R8/R13 structural invariants.
- `tests/unit/test_chart_init_select_source.py`: OCI test unskipped + expanded.
- `tests/integration/test_chart_sources.py`: `oci_registry` fixture + `test_oci_chart_pulls_from_local_registry_2` + cosign placeholder (Deviation 1).
- `tests/acceptance/test_image_has_cosign.py` (NEW): asserts `cosign version` works in runtime image.

**Commits:**
- `c85bc7d` — feat(04-07): add OciChart + cosign verify + Dockerfile cosign-fetch stage + tests

## Structural Invariant Verification

| Invariant | Check | Status |
|-----------|-------|--------|
| R4: --password-stdin (NOT --password) | `grep -F "--password-stdin" helm/client.py` | PASS |
| R4: no positional --password | `! grep -E "\-\-password [^s]" helm/client.py` | PASS |
| R5: cosign verify against OCI ref | argv contains `self._reference`, not tarball path | PASS |
| R6: cosign BEFORE helm pull | line 149 < line 152 in oci.py | PASS |
| R8: cleanup on cosign failure | `finally: shutil.rmtree(tmpdir, ignore_errors=True)` | PASS |
| R13: single SecretStr unwrap | `get_secret_value()` called exactly once in src/ | PASS |
| D5: exactly 2 subprocess imports | helm/client.py + chart/oci.py | PASS |
| R12: Dockerfile stage ordering | helm-fetch(39) < cosign-fetch(67) < runtime(89) | PASS |
| Pragma lifted | `! grep "Plan 04-07 lifts this pragma" chart/__init__.py` | PASS |
| skip-marker removed | `test_select_chart_source_routes_oci_prefix_to_oci_chart` active | PASS |

## Coverage Results

| File | Line | Branch |
|------|------|--------|
| `chart/oci.py` | 100% | 100% |
| `helm/client.py` | 100% | 100% |
| `chart/__init__.py` | 100% | 100% |
| Full unit suite TOTAL | 100% | 100% |

**Test counts:** 340 unit tests pass (18 deselected = integration/acceptance tiers). Integration tests skip cleanly when docker/helm unavailable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] exist_ok=True on unpack_dir.mkdir()**
- **Found during:** Task 04-7-02 test execution.
- **Issue:** `OciChart.resolve()` called `unpack_dir.mkdir()` without `exist_ok=True`. Test harness patches `tempfile.mkdtemp` to return `tmp_path` and pre-creates the `unpacked/` directory — causing `FileExistsError`.
- **Fix:** Added `exist_ok=True` to `unpack_dir.mkdir(exist_ok=True)`.
- **Files modified:** `src/aws_eks_helm_deploy/chart/oci.py`
- **Commit:** c85bc7d

**2. [Rule 1 - Bug] Shared subprocess.run module binding conflict**
- **Found during:** Task 04-7-02 test execution — cosign mock call_count=0 despite patching `oci.subprocess.run`.
- **Issue:** `import subprocess` in both `oci.py` and `client.py` binds to the same module object. Patching `oci.subprocess.run` and `client.subprocess.run` both target the same `subprocess.run` attribute — the second patch (helm) overrides the first (cosign) silently.
- **Fix:** Rewrote cosign tests to use method-level mocking (`OciChart._run_cosign_verify` mock) for tests that need helm + cosign isolation. Tests needing real `_run_cosign_verify` behavior call the method directly without a helm patch. Two additional direct unit tests (`test_run_cosign_verify_called_process_error`, `test_run_cosign_verify_timeout`) test the subprocess-level error mapping without any helm interference.
- **Files modified:** `tests/unit/test_chart_oci.py`
- **Commit:** c85bc7d

### Documented Plan Deviations (pre-planned)

**Deviation 1: Cosign integration test is SKIPPED PLACEHOLDER** — Per plan, ships as `pytest.skip("Cosign-signed chart fixture requires OIDC token; Phase 6 / v2.1 will automate")`. The cosign verify code path is 100% covered at the unit tier via method-level mocking.

**Deviation 2: no ConfigurationError for CHART_VERIFY=true + non-oci CHART** — Per plan, this check is deferred to Phase 5. The silent-ignore path keeps the factory simple.

**Deviation 3: Regexp cosign env vars not shipped** — v2.1+ work.

**Deviation 4: TOCTOU window between cosign verify and helm pull** — Documented in T-04-07-04; mitigation is to pin `--version`.

**Deviation 5: subprocess in chart/oci.py is deliberate D5 exception** — Acknowledged by Plan-Checker; verified by `import subprocess` appearing in exactly 2 src/ files.

## Known Stubs

- `test_oci_chart_verify_against_signed_test_chart` — SKIPPED PLACEHOLDER (Deviation 1). The test body calls `pytest.skip(...)` because signing requires OIDC token. Phase 6 / v2.1 will automate this.
- `HelmClient(kubeconfig_path=tmpdir / "unused-kubeconfig.yaml")` — inherited Deviation 2 pattern from Plan 04-06; OCI ops don't need a kubeconfig, but the constructor requires a Path.

## Threat Surface Scan

No new threat surfaces beyond those in the plan's `<threat_model>`:
- All new network operations are via helm + cosign subprocesses (CHART-03/CHART-04 scope).
- No new Python-level HTTP client, no new auth paths, no schema changes.
- T-04-07-01 through T-04-07-SC mitigations all implemented per threat register.

## Phase 4 Closure

This plan closes:
- **CHART-03** (OCI registry chart source) — fully operational.
- **CHART-04** (Cosign keyless verification) — fully operational at unit tier; acceptance test confirms binary in image; integration tier is opt-in.

Together with Plans 04-01..04-06, Phase 4 closes:
- **AUTH-04** (OIDC Web Identity) — Plan 04-01..04-03
- **CHART-01** (LocalChart) — Plan 04-05
- **CHART-02** (RepoChart) — Plan 04-06
- **CHART-03** + **CHART-04** (OciChart + Cosign) — this plan

## Self-Check: PASSED

- `src/aws_eks_helm_deploy/chart/oci.py` — EXISTS
- `src/aws_eks_helm_deploy/helm/client.py` — MODIFIED (registry_login + pull_oci)
- `src/aws_eks_helm_deploy/chart/__init__.py` — MODIFIED (pragma lifted)
- `Dockerfile` — MODIFIED (cosign-fetch stage)
- `tests/unit/test_chart_oci.py` — EXISTS (17 tests)
- `tests/acceptance/test_image_has_cosign.py` — EXISTS
- Commits e8d4656 and c85bc7d — VERIFIED in git log
- 340 unit tests pass, 100% coverage — VERIFIED
