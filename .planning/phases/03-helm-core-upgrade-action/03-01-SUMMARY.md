---
phase: 03-helm-core-upgrade-action
plan: 1
subsystem: eks-kubeconfig-layer
tags:
  - eks
  - kubeconfig
  - boto3
  - moto
  - tempfile
  - dataclass
  - context-manager
dependency_graph:
  requires:
    - phase: 01-toolchain-spine
      provides: errors.py PipeError hierarchy (exit codes 1..6)
    - phase: 02-aws-layer-auth-foundation
      provides: AwsCredentials dataclass style reference; generate_eks_token token-string contract
  provides:
    - aws_eks_helm_deploy.eks.cluster.ClusterAccess (frozen dataclass, 4 fields)
    - aws_eks_helm_deploy.eks.cluster.get_cluster_access(session, cluster_name, region)
    - aws_eks_helm_deploy.kube.kubeconfig.write_kubeconfig(cluster, token) -> Iterator[Path]
    - aws_eks_helm_deploy.errors.KubeconfigError(PipeError, exit_code=7)
  affects:
    - 03-02-PLAN.md: shares errors.py (appends HelmExecutionError after this plan's KubeconfigError=7)
    - 03-04-PLAN.md: consumes get_cluster_access + write_kubeconfig in actions/upgrade.py
tech_stack:
  added:
    - types-PyYAML (dev dep, type stubs for PyYAML — aligns local mypy with pre-commit mypy env)
  patterns:
    - frozen dataclass value object (ClusterAccess mirrors AwsCredentials shape)
    - @contextmanager generator with try/finally cleanup
    - contextlib.suppress(FileNotFoundError) for belt-and-braces unlink
    - os.chmod before write_text (T-03-01 race-window mitigation)
    - @mock_aws for boto3 EKS unit testing without real AWS
key_files:
  created:
    - src/aws_eks_helm_deploy/eks/__init__.py
    - src/aws_eks_helm_deploy/eks/cluster.py
    - src/aws_eks_helm_deploy/kube/__init__.py
    - src/aws_eks_helm_deploy/kube/kubeconfig.py
    - tests/unit/test_eks_cluster.py
    - tests/unit/test_kubeconfig.py
  modified:
    - src/aws_eks_helm_deploy/errors.py (appended KubeconfigError + header docstring entry)
    - tests/unit/test_errors.py (appended two KubeconfigError tests + import)
    - pyproject.toml (added types-PyYAML to dev dependency group)
    - uv.lock (updated for types-PyYAML)
decisions:
  - "KubeconfigError exit_code=7 (not 5 as CONTEXT D8 stated): 5 is already HelmError; per RESEARCH Section L preserve 1..6, assign next free integer"
  - "write_kubeconfig does not raise KubeconfigError directly: writer is a primitive; error typing happens in actions/upgrade.py where call-site context (cluster, release) is available"
  - "Private _build_kubeconfig_yaml helper: keeps public surface minimal (one function), testable in isolation for Phase 4/5 snapshot tests"
  - "Added types-PyYAML to pyproject.toml dev deps: pre-commit mypy env already had it (types-PyYAML in additional_dependencies); local venv must match to avoid false unused-ignore errors"
  - "contextlib.suppress(FileNotFoundError) instead of try/except/pass: SIM105 ruff rule; semantically identical, satisfies coverage branch for suppression path"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 4
---

# Phase 03 Plan 01: EKS Cluster Access + kubeconfig Writer Summary

**One-liner:** `ClusterAccess` frozen dataclass + `get_cluster_access` boto3 wrapper + `write_kubeconfig` chmod-0600 context manager + `KubeconfigError(exit_code=7)` — the complete kubeconfig layer for Plan 03-04 to wire.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 03-1-01 | KubeconfigError + eks/kube package markers | 7a23d98 | errors.py, eks/__init__.py, kube/__init__.py, test_errors.py |
| 03-1-02 | ClusterAccess + get_cluster_access() | 9f05d1b | eks/cluster.py, test_eks_cluster.py |
| 03-1-03 | write_kubeconfig() context manager | ea5ad2e | kube/kubeconfig.py, test_kubeconfig.py, pyproject.toml |

## Coverage Results

| Module | Line Coverage | Branch Coverage |
|--------|--------------|----------------|
| `src/aws_eks_helm_deploy/eks/cluster.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/kube/kubeconfig.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/eks/__init__.py` | 100% | 100% |
| `src/aws_eks_helm_deploy/kube/__init__.py` | 100% | 100% |
| TOTAL (all 17 source files) | 100% | 100% |

**Full suite:** 145 tests passed, 10 deselected (integration/acceptance tier), 0 failed.

## FileNotFoundError Branch Verification

Yes — `test_unlink_suppresses_file_not_found` exercises the `contextlib.suppress(FileNotFoundError)` path by calling `p.unlink()` inside the `with write_kubeconfig(...)` block and asserting no exception propagates on context exit. The branch is confirmed covered at 100%.

## chmod-before-write Ordering Verification

Yes — `test_chmod_happens_before_write_content` patches `aws_eks_helm_deploy.kube.kubeconfig.os.chmod` and `pathlib.Path.write_text` via `mocker.patch`. A shared `call_order: list[str]` list is populated by both side effects. The test asserts `call_order.index("chmod") < call_order.index("write_text")`.

## type: ignore Comments

Zero `# type: ignore` comments landed in `eks/cluster.py` or `kube/kubeconfig.py`. The only type-ignore that was attempted — `# type: ignore[import-untyped]` for PyYAML — was removed and replaced by adding `types-PyYAML` to dev dependencies. This aligned the local `uv run mypy --strict src` environment with the pre-commit mypy hook (which already had `types-PyYAML` in `additional_dependencies`).

## Package Versions at Execution Time

| Package | Version |
|---------|---------|
| boto3 | 1.43.31 |
| moto | 5.2.2 |
| PyYAML | 6.0.3 |
| types-PyYAML | 6.0.12.20260518 |

## Exit Code Byte-Stability Audit

```
grep -n "exit_code = " src/aws_eks_helm_deploy/errors.py
27:            self.exit_code = exit_code   # PipeError.__init__ override
38:    exit_code = 1                         # ConfigurationError (UNCHANGED)
44:    exit_code = 2                         # AuthenticationError (UNCHANGED)
50:    exit_code = 3                         # ClusterAccessError (UNCHANGED)
56:    exit_code = 4                         # ChartResolutionError (UNCHANGED)
62:    exit_code = 5                         # HelmError (UNCHANGED)
68:    exit_code = 6                         # HelmTimeoutError (UNCHANGED)
80:    exit_code = 3                         # EksTokenError (UNCHANGED, shared with ClusterAccessError)
86:    exit_code = 7                         # KubeconfigError (NEW — this plan)
```

Exit codes 1..6 are byte-stable. `EksTokenError` retains exit_code=3 (shared). `KubeconfigError` takes 7 (next free integer per RESEARCH Section L Recommendation 1).

## Deviations from Plan

### Deviation 1 (planned): KubeconfigError.exit_code = 7 (not 5)

- **Origin:** CONTEXT D8 cited exit_code=5 for KubeconfigError.
- **Reality:** exit_code=5 is already taken by `HelmError` from Phase 1.
- **Resolution:** Per RESEARCH Section L Recommendation 1 — keep existing 1..6 unchanged; assign KubeconfigError=7.
- **Traceability:** Documented in PLAN.md `<deviations>` section, pre-planned before execution.

### Deviation 2 (planned): write_kubeconfig does not raise KubeconfigError

- **Origin:** CONTEXT D3 implied the kubeconfig writer is the natural place to raise KubeconfigError.
- **Resolution:** Writer stays as a primitive — `OSError`/`PermissionError` propagate. The action layer (Plan 03-04's `actions/upgrade.py`) wraps with `try: ... except OSError: raise KubeconfigError(...)`.
- **Rationale:** Better testability; error context (cluster name, release) is available at the action layer.
- **Traceability:** Documented in PLAN.md `<deviations>` section, pre-planned before execution.

### Deviation 3 (planned): Private _build_kubeconfig_yaml helper

- **Origin:** RESEARCH Section B showed the YAML build inline in write_kubeconfig.
- **Resolution:** Factored to private `_build_kubeconfig_yaml` to keep the context manager body clean. Not in `__all__`.
- **Traceability:** Documented in PLAN.md `<deviations>` section, pre-planned before execution.

### Deviation 4 (auto-fix, Rule 2): Added types-PyYAML dev dependency

- **Found during:** Task 03-1-03 commit (pre-commit mypy hook failed with "Unused type: ignore" error).
- **Issue:** The pre-commit mypy env already had `types-PyYAML` (in `.pre-commit-config.yaml` `additional_dependencies`), but the local venv did not. Attempting `# type: ignore[import-untyped]` on the yaml import made pre-commit mypy error (unused ignore), while removing it made local mypy error (import-untyped). The environments were misaligned.
- **Fix:** Added `"types-PyYAML"` to `[dependency-groups].dev` in `pyproject.toml`; ran `uv sync`; removed the `# type: ignore` comment. Both environments now agree.
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** ea5ad2e

### Deviation 5 (auto-fix, Rule 1): contextlib.suppress instead of try-except-pass

- **Found during:** Task 03-1-03 commit (ruff SIM105 — "use contextlib.suppress instead of try-except-pass").
- **Fix:** Replaced `try: path.unlink() except FileNotFoundError: pass` with `with contextlib.suppress(FileNotFoundError): path.unlink()`. Semantically identical; satisfies SIM105.
- **Coverage note:** `contextlib.suppress(FileNotFoundError)` suppresses the exception; the `test_unlink_suppresses_file_not_found` test still exercises this path at 100% branch coverage.
- **Files modified:** `kube/kubeconfig.py`
- **Commit:** ea5ad2e

## Known Stubs

- `KubeconfigError` is introduced but not raised in this plan. The actual `raise KubeconfigError(...)` call lives in Plan 03-04's `actions/upgrade.py`. This is intentional per Deviation 2.
- `eks/__init__.py` and `kube/__init__.py` have no re-exports. Minimal namespace markers only.

## Threat Flags

No new security-relevant surface beyond what the PLAN.md threat model already documents (T-03-01 through T-03-06). The implemented mitigations are:
- T-03-01: `os.chmod(path, 0o600)` before `write_text` — verified by `test_chmod_happens_before_write_content`.
- T-03-01-04: `contextlib.suppress(FileNotFoundError)` cleanup in `finally` — verified by `test_file_deleted_on_context_exit_exception` and `test_unlink_suppresses_file_not_found`.
- T-03-01-05: ca_data verbatim passthrough — verified by `test_ca_data_passed_through_verbatim` (both modules).

## Self-Check: PASSED

All created files exist on disk. All task commits (7a23d98, 9f05d1b, ea5ad2e) exist in git history. Full test suite at 100% coverage.
