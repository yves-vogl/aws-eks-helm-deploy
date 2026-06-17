---
phase: 02-aws-layer-auth-foundation
plan: 1
subsystem: aws-eks-token
tags:
  - aws
  - boto3
  - eks
  - sts
  - token
  - presigned-url
  - auth
dependency_graph:
  requires:
    - 01-toolchain-spine (PipeError hierarchy, test infra, boto3/moto already in deps)
  provides:
    - aws_eks_helm_deploy.aws.eks_token.generate_eks_token(session, cluster_name, region) -> str
    - aws_eks_helm_deploy.aws.eks_token.TOKEN_PREFIX
    - aws_eks_helm_deploy.aws.eks_token.K8S_AWS_ID_HEADER
    - aws_eks_helm_deploy.aws.eks_token.URL_TIMEOUT
    - aws_eks_helm_deploy.errors.EksTokenError(PipeError)
  affects:
    - 02-03 (AssumeRoleStrategy produce session that calls generate_eks_token)
    - 02-04 (select_strategy wires generate_eks_token into cli.main)
    - 03-* (kube/kubeconfig.py receives token string)
tech_stack:
  added: []
  patterns:
    - botocore event injection (provide-client-params + before-sign) for x-k8s-aws-id header signing
    - structural-equivalence tests under @mock_aws (moto 5.2.x)
    - botocore.signers.generate_presigned_url as mocker.patch target for error-branch tests
key_files:
  created:
    - src/aws_eks_helm_deploy/aws/__init__.py
    - src/aws_eks_helm_deploy/aws/eks_token.py
    - tests/unit/test_eks_token.py
  modified:
    - src/aws_eks_helm_deploy/errors.py
    - tests/unit/test_errors.py
decisions:
  - "EksTokenError.exit_code=3 shared with ClusterAccessError (both are EKS-reach failures; consumer observability via structlog class name, not exit code)"
  - "Removed defensive if-guards from botocore event closures to achieve 100% branch coverage — guards were unreachable since Params always contains K8S_AWS_ID_HEADER"
  - "Patch target for error-branch tests: botocore.signers.generate_presigned_url (module-level function injected into service subclasses via add_generate_presigned_url, not BaseClient.__dict__)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-17"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
  commits: 3
---

# Phase 02 Plan 01: EKS Token Generator + EksTokenError Summary

**One-liner:** Pure-boto3 EKS bearer token via botocore event injection (x-k8s-aws-id signed into presigned STS GetCallerIdentity URL), with EksTokenError at exit code 3 and 11 structural-equivalence tests at 100% line+branch coverage.

---

## What Was Built

### New Files

**`src/aws_eks_helm_deploy/aws/__init__.py`**
Namespace marker for the aws/ subpackage. Contains module docstring + `from __future__ import annotations`.

**`src/aws_eks_helm_deploy/aws/eks_token.py`** (34 source lines)
- Module-level constants: `TOKEN_PREFIX = "k8s-aws-v1."`, `K8S_AWS_ID_HEADER = "x-k8s-aws-id"`, `URL_TIMEOUT = 60` (all `Final[str/int]`)
- `generate_eks_token(session, cluster_name, region) -> str`: creates regional STS client with `endpoint_url=f"https://sts.{region}.amazonaws.com"` and botocore retry config, registers two event handlers via `sts.meta.events.register()`, calls `generate_presigned_url` with `Params={K8S_AWS_ID_HEADER: cluster_name}`, base64url-encodes without padding, returns `TOKEN_PREFIX + encoded`
- Error handling: `ClientError` → `EksTokenError(f"EKS token generation failed [{code}]: {message}")`, `NoCredentialsError` → `EksTokenError("No AWS credentials available...")`
- Zero awscli imports (AUTH-07 gate verified)

**`tests/unit/test_eks_token.py`** (199 lines)
11 tests under `@mock_aws` and `@pytest.mark.unit`:
1. `test_token_starts_with_v1_prefix`
2. `test_token_contains_no_base64_padding`
3. `test_decoded_url_has_x_amz_expires_60`
4. `test_decoded_url_signs_cluster_name_header`
5. `test_decoded_url_action_is_get_caller_identity`
6. `test_decoded_url_uses_regional_sts_endpoint`
7. `test_different_cluster_names_produce_different_tokens`
8. `test_different_regions_produce_different_endpoints`
9. `test_algorithm_is_sigv4`
10. `test_client_error_raises_eks_token_error`
11. `test_no_credentials_error_raises_eks_token_error`

### Modified Files

**`src/aws_eks_helm_deploy/errors.py`**
- Updated exit-code reference docstring: `3  — ClusterAccessError / EksTokenError (shared)`
- Appended `EksTokenError(PipeError)` with `exit_code = 3`

**`tests/unit/test_errors.py`**
- Added `test_eks_token_error_exit_code` and `test_eks_token_error_custom_exit_code`

---

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check src tests` | PASS (0 errors) |
| `ruff format --check src tests` | PASS (0 files would reformat) |
| `mypy --strict src` | PASS (9 source files, 0 issues) |
| `pytest -q` (unit tier, 100% gate) | PASS (65 passed, 100% line+branch) |
| `grep -RIn 'import awscli' src/` | PASS (0 lines — AUTH-07 gate) |
| No awscli import in runtime code | CONFIRMED — only docstring references |

### Coverage on eks_token.py

```
Name                                       Stmts   Miss Branch BrPart  Cover
-------------------------------------------------------------------------
src/aws_eks_helm_deploy/aws/eks_token.py      32      0      0      0   100%
```

**100% line + 100% branch.**

### NoCredentialsError branch exercised

YES — `test_no_credentials_error_raises_eks_token_error` patches `botocore.signers.generate_presigned_url` to raise `botocore.exceptions.NoCredentialsError()`.

### type: ignore comments in eks_token.py

NONE — the `request: Any` parameter annotation in `_inject_header` (typed as `Any` per botocore's event system design) allows direct `.headers` access without a `type: ignore`. The `# noqa: ANN401` suppression on `request: Any` and `**kwargs: Any` is used instead (acknowledged per RESEARCH Section A).

### Package versions at execution time

| Package | Version |
|---------|---------|
| boto3 | 1.43.31 |
| botocore | 1.43.31 |
| moto | 5.2.2 |
| pytest-mock | 3.15.1 |

### awscli audit grep

```bash
grep -RIn "import awscli" src/
# Returns: (empty — 0 lines)
```

AUTH-07 confirmed: no `import awscli` or `from awscli` statements in `src/`.

---

## Deviations from Plan

### Deviation 1 (Documented in Plan): ROADMAP SC2 byte-equal → structural equivalence

As documented in `02-01-PLAN.md <deviations>` and `02-RESEARCH.md Section A`, the ROADMAP's "byte-equal golden test" is structurally impossible. Implemented as structural-equivalence testing of 7 token properties. This is the intended approach per upstream `aws-iam-authenticator` test suite.

### Deviation 2 (Documented in Plan): EksTokenError.exit_code = 3 shared with ClusterAccessError

As documented in `02-01-PLAN.md <deviations>`. Consumer observability is provided by the typed exception class name emitted via structlog.

### Deviation 3 (Auto-fix, Rule 1): Removed defensive if-guards from event closures

**Found during:** Task 02-1-02 coverage check
**Issue:** The awscli-matching pattern uses `if K8S_AWS_ID_HEADER in params:` and `if "value" in _header_store:` defensive guards. These guards are never False in our implementation (we always pass the header in Params) and made branch coverage impossible to achieve to 100%.
**Fix:** Removed both if-guards. The closures now always execute their body, which is correct since `generate_presigned_url` is always called with `{K8S_AWS_ID_HEADER: cluster_name}` in `Params`.
**Impact:** Zero behavior change — the guards were unreachable in all code paths. The closure dict pattern is preserved; only the unreachable False branches are removed.
**Commit:** 15c917b

### Deviation 4 (Auto-fix, Rule 1): Patch target for error-branch tests

**Found during:** Task 02-1-02 test execution
**Issue:** The plan suggested `mocker.patch("botocore.client.BaseClient.generate_presigned_url", ...)`. At runtime, `botocore.client.BaseClient` does NOT have `generate_presigned_url` in its `__dict__` — it is dynamically injected into service-specific subclasses (e.g., `botocore.client.STS`) via `botocore.signers.add_generate_presigned_url` during client creation.
**Fix:** Used `mocker.patch("botocore.signers.generate_presigned_url", ...)` instead — this patches the module-level function that botocore injects. This is the stable injection point that works under `@mock_aws`.
**Impact:** Functionally equivalent — both approaches intercept the same code path. No change to test semantics.
**Commit:** 15c917b

---

## Known Stubs

None — per `02-01-PLAN.md <known_stubs>`. The module ships at its final Phase 2 behavior.

---

## Threat Flags

No new security surface beyond the plan's documented threat model. The `generate_eks_token` function does not introduce any network endpoints, auth paths, or file access patterns beyond what T-02-01-01 through T-02-01-SC already enumerate.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `src/aws_eks_helm_deploy/aws/__init__.py` exists | FOUND |
| `src/aws_eks_helm_deploy/aws/eks_token.py` exists | FOUND |
| `tests/unit/test_eks_token.py` exists | FOUND |
| Commit `ed4cff1` (Task 02-1-01) exists | FOUND |
| Commit `15c917b` (Task 02-1-02) exists | FOUND |
| `generate_eks_token` importable | OK |
| `EksTokenError("x").exit_code == 3` | OK |
