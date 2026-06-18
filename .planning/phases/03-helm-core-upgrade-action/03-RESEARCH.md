# Phase 3: Helm Core & Upgrade Action — Research

**Researched:** 2026-06-18
**Domain:** Helm CLI surface, EKS kubeconfig writer, subprocess model, kind integration, syrupy snapshot testing, PyYAML chart parsing
**Confidence:** HIGH — all code patterns verified against project venv (Python 3.13, boto3 1.43.31, moto 5.2.2, PyYAML 6.0.3); Helm docs verified via WebFetch; package versions verified via PyPI API

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D1 — Module shape (locks SC1)**

Three new modules, strict layering enforced by Plan-Checker:

| Module | Responsibility | What it MUST NOT do |
|--------|----------------|---------------------|
| `src/aws_eks_helm_deploy/kube/kubeconfig.py` | Write tempfile kubeconfig from `ClusterAccess` + `EksAuthToken`. Context-manager-based lifecycle. Tempfile is `chmod 0600`, in `tempfile.gettempdir()`, deleted on context exit. | No `subprocess.run`. No helm imports. No AWS imports beyond the typed inputs. |
| `src/aws_eks_helm_deploy/helm/client.py` | Single `HelmClient` class. ONLY module that calls `subprocess.run`. One typed method per helm subcommand: `upgrade_install(release, chart, namespace, values, set_args, history_max, timeout) -> HelmResult`; `history(release, namespace) -> list[HelmRevision]`. | No kubeconfig writing (consumes a path). No metadata injection logic (caller passes ready `--set` list). |
| `src/aws_eks_helm_deploy/actions/upgrade.py` | < 50 LOC. Wires `select_strategy` → `generate_eks_token` → `kubeconfig.write_tempfile()` → `HelmClient.upgrade_install()`. Returns success/failure. | No subprocess. No file I/O beyond kubeconfig context-manager use. |

Existing `cli.py` keeps the action-dispatch table (currently a placeholder for `upgrade`).

**D2 — Subprocess model**

Sync `subprocess.run` only. Default timeout: 600 seconds. `subprocess.run(..., check=False, capture_output=True, text=True, timeout=...)`. Stderr truncated to last 32 KB.

**D3 — kubeconfig tempfile lifecycle**

Context-manager only. `chmod 0600` BEFORE writing content. `delete=True` via `tempfile.NamedTemporaryFile` plus belt-and-braces `try: path.unlink()` in finally. YAML mirrors `aws eks update-kubeconfig` output with inlined `user.token` (no `exec:` block).

**D4 — HISTORY_MAX semantics (closes #17)**

| `HISTORY_MAX` value | Behaviour |
|---------------------|-----------|
| unset | DO NOT pass `--history-max`. Helm's default (10) applies. |
| `HISTORY_MAX=0` | Pass `--history-max 0` → unlimited retention. |
| `HISTORY_MAX=N` (N ≥ 1) | Pass `--history-max N`. |
| `HISTORY_MAX=-1` or non-integer | Raise `ConfigurationError` at Settings parse time. |

**D5 — Bitbucket metadata injection (META-01 only)**

When `INJECT_BITBUCKET_METADATA=true`: inject 5 keys via `--set bitbucket.<key>=<value>`. Default (unset/false): no injection. Missing individual vars: omit only that flag, log structlog `warn`. No Phase 3 deprecation warning (META-03 is Phase 5).

**D6 — Local-path chart resolution (CHART-01 only)**

Anything not starting with `repo://` or `oci://` is a local path. Missing path → `ChartResolutionError(exit_code=4)`. `ResolvedChart` frozen dataclass: `name`, `version`, `source_path`.

**D7 — Success message (CHART-05)**

`"Deployed chart {chart.name} ({chart.version}) to release {release} in namespace {namespace} on cluster {cluster.name}"`. Structlog `info` with `action`, `release`, `namespace`, `chart_source`, `chart_name`, `chart_version`, `cluster`, `auth_strategy`, `helm_revision`, `duration_ms`.

**D8 — Error mapping (PIPE-06)**

| Error | exit_code | Trigger |
|-------|-----------|---------|
| `ConfigurationError` | 2 | Settings parse failure |
| `AwsAuthError` | 1 | auth strategy raises |
| `EksTokenError` | 3 | `generate_eks_token` raises |
| `ChartResolutionError` (new) | 4 | Local path missing, Chart.yaml absent/unparseable |
| `KubeconfigError` (new) | 5 | Tempfile write fails |
| `HelmExecutionError` (new) | 6 | `helm upgrade` non-zero exit |
| `HelmTimeoutError` (new) | 7 | `subprocess.TimeoutExpired` |

**D9 — argv snapshot tests with syrupy**

`syrupy` in `[dependency-groups].dev`. Snapshot tests on `HelmClient._build_argv()`. Snapshots in `tests/unit/__snapshots__/`.

**D10 — kind integration (mitigates ROADMAP Risk 2)**

Integration tier must: bring up kind cluster, apply minimal chart from `tests/fixtures/charts/minimal/`, run `actions/upgrade.py` against kind, assert HISTORY_MAX and INJECT_BITBUCKET_METADATA behaviors. Open question: does kind accept moto-presigned-URL EKS token?

**D11 — pre-commit + CI gate stays as-is.** No changes to `.pre-commit-config.yaml` or CI for this phase.

**D12 — helm-diff NOT used in Phase 3.** Ships in Phase 5.

### Claude's Discretion

- Plan breakdown (researcher proposes, planner finalizes)
- Whether `HELM_TIMEOUT` becomes a public pipe variable
- Whether `ResolvedChart` becomes a Protocol in Phase 3 vs Phase 4

### Deferred Ideas (OUT OF SCOPE)

- `--atomic` / `--wait` flags → Phase 5
- `helm diff` action → Phase 5
- `helm rollback` action → Phase 5
- Repo + OCI chart sources → Phase 4
- Cosign chart verification → Phase 4
- Deprecation-warning for missing INJECT → Phase 5
- HISTORY_MAX vs REVISION compatibility warning → Phase 5
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CHART-01 | M can deploy a Helm chart from a local path | Section D6, H: local path detection, Chart.yaml parsing, ResolvedChart dataclass |
| CHART-05 | Pipe reports resolved chart name + version in success message | Section A (helm stdout parsing), D7 (message format) |
| PIPE-01 | `ACTION=upgrade` runs `helm upgrade --install` | Section A: full flag set, exit codes, stderr structure |
| PIPE-06 | Every action returns non-zero on failure with human-readable message | Section A (exit codes), D8 (error hierarchy), E (subprocess) |
| HISTORY-01 | `HISTORY_MAX=<n>` bounds release history | Section F: helm --history-max semantics, verification |
| HISTORY-02 | Pipe passes `--history-max <n>` to helm upgrade | Section A: --history-max flag, Section F: edge cases |
| META-01 | When `INJECT_BITBUCKET_METADATA=true`, inject 5 bitbucket.* --set flags | Section G: env-var sourcing, quoting, omission logic |
</phase_requirements>

---

## Summary

Phase 3 wires the Helm upgrade path end-to-end: EKS cluster metadata fetch (`eks/cluster.py`), kubeconfig tempfile writer (`kube/kubeconfig.py`), typed `HelmClient` (`helm/client.py`), local chart resolver (`chart/local.py`), and `UpgradeAction` (`actions/upgrade.py`). The action-dispatch in `cli.py` replaces the Phase 2 placeholder.

All required runtime dependencies are already declared in `pyproject.toml` (PyYAML 6.0.3 is already a direct dependency). New dev-only dependencies are `syrupy ~= 5.3` (snapshot testing, current latest) and `pytest-rerunfailures ~= 16.3` (kind flakiness guard, current latest). The phase context cited older version pins (~= 4.7 and ~= 14.0 respectively) — both packages have advanced significantly; use current pins.

The key open question from CONTEXT.md D10 — whether kind accepts the moto-presigned-URL EKS token — is answered definitively below: **kind does NOT accept EKS-style bearer tokens**. The integration test must use kind's own admin kubeconfig for helm connectivity and test the EKS token path exclusively via unit tests with `@mock_aws`.

**Primary recommendation:** Implement the five modules in four waves matching the dependency DAG. Test `HelmClient._build_argv()` with syrupy snapshots (pure function, no I/O). Test integration against kind using kind's own kubeconfig — not the EKS token path. Cover EKS token + kubeconfig generation via unit tests.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| EKS cluster metadata (endpoint + CA) | API / Backend (`eks/cluster.py`) | — | Pure AWS API call; belongs with the auth layer |
| kubeconfig tempfile lifecycle | API / Backend (`kube/kubeconfig.py`) | — | File I/O layer; consumes `ClusterAccess + EksAuthToken` inputs |
| Helm subprocess invocation | API / Backend (`helm/client.py`) | — | Only one module may call `subprocess.run`; strict layering per D1 |
| Chart.yaml parsing | API / Backend (`chart/local.py`) | — | Pre-flight validation before helm invocation |
| Bitbucket metadata injection | API / Backend (`actions/upgrade.py`) | — | Reads env vars, produces `--set` list; caller passes list to HelmClient |
| Action orchestration | API / Backend (`actions/upgrade.py`) | `cli.py` dispatch | < 50 LOC; wires all layers; cli owns dispatch table |
| Success/failure messaging | Frontend (PipeIO) | structlog (logging) | `pipe.success()` / `pipe.fail()` are the consumer-visible channels |

---

## A. Helm CLI Surface — `helm upgrade --install`

### Full Flag Set Relevant to Phase 3

```
helm upgrade <release> <chart-path>
  --install                    # create if no release exists; upgrade if it does
  --namespace <ns>             # kubernetes namespace
  --create-namespace           # create namespace if it does not exist
  --values <file.yaml>         # load values from file (repeatable, last wins)
  --set <key=val>              # set individual value (repeatable, last wins)
  --history-max <N>            # limit max stored revisions (0 = unlimited)
  --kubeconfig <path>          # path to kubeconfig file
  --timeout <duration>         # Go duration: "600s", "5m", "1h" (default "5m0s")
  --wait                       # Phase 5 (SAFE_UPGRADE) — NOT Phase 3
  --atomic                     # Phase 5 — NOT Phase 3
  --dry-run                    # Phase 5 — NOT Phase 3
```

`[CITED: https://helm.sh/docs/helm/helm_upgrade/]`

### Helm Exit Codes

Helm uses a **single non-zero exit code (1) for all failure modes.** There is no distinction between:
- Chart render failure (template error, missing required value)
- Kubernetes API failure (authentication rejected, resource already exists)
- Timeout (`--wait` exceeded)
- Previous release in a failed state requiring `helm rollback` first

**All failures → exit code 1.** All go to `HelmExecutionError(exit_code=6)`. The `subprocess.TimeoutExpired` exception (not a helm exit code) maps to `HelmTimeoutError(exit_code=7)`.

`[CITED: https://github.com/helm/helm/issues/4134]` (feature request to add distinct exit codes — not implemented as of 3.18.x)

### Helm Stderr Structure

On failure, helm writes to stderr with the prefix `"Error: "`. Examples:

```
Error: UPGRADE FAILED: execution error at (chart/templates/deployment.yaml:1:9): required value missing
Error: UPGRADE FAILED: cannot re-use a name that is still in use
Error: release: not found
Error: Kubernetes cluster unreachable: ...
```

The `"Error: "` prefix is stable and can be used to distinguish helm error output from informational output. **What to surface:** the entire stderr (truncated to last 32 KB per D2) in `HelmExecutionError.args[0]`. Structured stderr parsing (extracting specific sub-errors) is Phase 5 scope (SEC-06).

### Helm Upgrade Stdout on Success

`helm upgrade --install` writes human-readable release summary to **stdout** on success:

```
Release "my-release" has been upgraded. Happy Helming!
NAME: my-release
LAST DEPLOYED: Wed Jun 18 12:34:56 2026
NAMESPACE: default
STATUS: deployed
REVISION: 3
TEST SUITE: None
NOTES:
<chart NOTES.txt>
```

The `REVISION:` line contains the new revision number. Parse with:
```python
import re
m = re.search(r"^REVISION:\s*(\d+)", stdout, re.MULTILINE)
helm_revision = int(m.group(1)) if m else None
```

`[ASSUMED — derived from helm source code behavior; revision extraction is standard pattern. No helm binary on host to verify experimentally.]`

### Helm Timeout Duration Format

`--timeout` accepts Go duration strings: `"600s"`, `"10m"`, `"1h30m"`, `"5m0s"`. The default is `"5m0s"`. The `HELM_TIMEOUT` env var (if surfaced as a Settings field) must be validated to be a valid Go duration at settings-parse time, or passed through raw to helm. Recommend: store as `str`, validate with regex `r"^\d+[smh](\d+[smh])*$"` or accept the default "600s" string and pass directly. Helm itself rejects malformed durations with a startup error (exit 1, stderr: `"Error: invalid duration"`).

### `helm get values` for Integration Assertions

```bash
helm get values <release> -n <namespace> -o yaml
```

Returns the user-supplied values (not the full merged values). For integration assertions on `INJECT_BITBUCKET_METADATA=true`, use:
```bash
helm get values <release> -n <namespace> -o yaml | grep bitbucket
```

The assertion is that all five `bitbucket.*` keys appear in the YAML output.

### `helm history` for HISTORY_MAX Assertion

```bash
helm history <release> -n <namespace> -o json
```

Returns a JSON array of revision objects. Each object has fields: `revision`, `updated`, `status`, `chart`, `app_version`, `description`. Example:

```json
[
  {"revision": 1, "updated": "...", "status": "superseded", "chart": "minimal-0.1.0", "app_version": "", "description": "Install complete"},
  {"revision": 2, "updated": "...", "status": "deployed", "chart": "minimal-0.1.0", "app_version": "", "description": "Upgrade complete"}
]
```

HISTORY_MAX assertion:
```python
import subprocess, json
result = subprocess.run(
    ["helm", "history", release, "-n", namespace, "-o", "json"],
    capture_output=True, text=True, check=False
)
revisions = json.loads(result.stdout)
assert len(revisions) <= expected_max
```

`[CITED: https://helm.sh/docs/helm/helm_history/]`

---

## B. kubeconfig File Format for EKS

### Minimal Valid kubeconfig Structure

The kubeconfig for an EKS cluster with an inlined bearer token (no `exec:` block) follows this structure. This mirrors what `aws eks update-kubeconfig` produces, minus the `exec` credential provider:

```yaml
apiVersion: v1
kind: Config
preferences: {}
clusters:
- name: <cluster-name>
  cluster:
    server: <https://ENDPOINT>
    certificate-authority-data: <base64-encoded-CA-cert>
users:
- name: <cluster-name>
  user:
    token: <k8s-aws-v1.base64url-presigned-url>
contexts:
- name: <cluster-name>
  context:
    cluster: <cluster-name>
    user: <cluster-name>
current-context: <cluster-name>
```

**Why no `exec:` block:** The `exec:` credential provider calls an external binary (`aws eks get-token` or `aws-iam-authenticator`) at runtime. Phase 3 generates the token once at invocation start via `generate_eks_token()` and inlines it. This is correct for a one-shot pipe (15-minute token validity >> typical `helm upgrade` runtime).

`[VERIFIED: tested kubeconfig YAML generation with PyYAML 6.0.3 in project venv; chmod 0600 applied before write confirmed]`

### ClusterAccess Value Object

A new typed value object for the EKS cluster descriptor (proposed for `eks/cluster.py`):

```python
@dataclasses.dataclass(frozen=True)
class ClusterAccess:
    """Immutable EKS cluster access descriptor.

    Produced by describe_cluster(); consumed by kubeconfig.write_kubeconfig().
    """
    name: str           # EKS cluster name (= CLUSTER_NAME env var)
    endpoint: str       # https://... (from describe_cluster response)
    ca_data: str        # base64-encoded CA certificate (certificateAuthority.data)
    region: str         # AWS region
```

The `boto3.client("eks").describe_cluster(name=cluster_name)` response has the field path:
```python
resp["cluster"]["endpoint"]                    # str
resp["cluster"]["certificateAuthority"]["data"] # str (base64)
```

Both fields are confirmed as returned by moto 5.2.2 (verified in project venv).
`mypy_boto3_eks` types: `ClusterTypeDef` (has `endpoint`, `certificateAuthority`), `CertificateTypeDef` (has `data`).

`[VERIFIED: moto EKS describe_cluster confirmed; CertificateTypeDef.data confirmed via mypy_boto3_eks in project venv]`

### EKS Token Expiry Constraint

EKS bearer tokens are valid for 15 minutes (`URL_TIMEOUT=60` seconds for the presigned URL, but the EKS control plane validates it for up to 15 minutes). For a one-shot pipe that generates the token at invocation start and immediately passes it to helm: no refresh is needed. Document this constraint in the variable reference: if `helm upgrade` runs longer than 15 minutes without `--wait`, the token is stale but helm has already authenticated. `[ASSUMED — 15-minute validity from EKS documentation; the pipe design makes this a non-issue for Phase 3]`

### `chmod 0600` Race-Avoidance Approach

**Correct order (verified):**

```python
import os, tempfile, pathlib
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def write_kubeconfig(cluster: ClusterAccess, token: str) -> Iterator[pathlib.Path]:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        prefix="eks-kubeconfig-",
    ) as tmp:
        path = pathlib.Path(tmp.name)
    # File exists but is empty; set 0600 BEFORE writing content
    os.chmod(path, 0o600)
    try:
        path.write_text(_build_kubeconfig_yaml(cluster, token))
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
```

The `NamedTemporaryFile` with `delete=False` creates the file (empty, with default 0600 umask-dependent permissions on most Linux). The explicit `os.chmod(path, 0o600)` before writing content closes the race window.

**Security note (T-03-01):** The token is in the FILE, not in argv. `ps ax` shows `--kubeconfig /tmp/eks-kubeconfig-XXXXXXXX.yaml` — the path is visible but the token is not. The file is deleted on context exit. The path itself is non-sensitive (no information about the cluster beyond what `CLUSTER_NAME` env var already discloses).

`[VERIFIED: tested chmod-before-write sequence in project venv; confirmed -rw------- mode]`

### boto3 describe_cluster call

```python
import boto3.session, botocore.exceptions
from aws_eks_helm_deploy.errors import ClusterAccessError

def get_cluster_access(
    session: boto3.session.Session,
    cluster_name: str,
    region: str,
) -> ClusterAccess:
    """Fetch EKS cluster endpoint and CA from AWS API."""
    eks = session.client("eks", region_name=region)
    try:
        resp = eks.describe_cluster(name=cluster_name)
    except botocore.exceptions.ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg = exc.response["Error"]["Message"]
        raise ClusterAccessError(
            f"EKS describe_cluster failed [{code}]: {msg}"
        ) from exc
    cluster = resp["cluster"]
    return ClusterAccess(
        name=cluster_name,
        endpoint=cluster["endpoint"],
        ca_data=cluster["certificateAuthority"]["data"],
        region=region,
    )
```

---

## C. kind Cluster Integration Test Setup

### THE DEFINITIVE ANSWER ON D10: kind Does NOT Accept EKS Tokens

**Finding:** kind's kube-apiserver uses standard Kubernetes authentication mechanisms (client certificates, service account tokens, OIDC if configured). It does NOT have the AWS IAM webhook (`aws-iam-authenticator`) installed by default. A `k8s-aws-v1.*` bearer token presented to kind's kube-apiserver is rejected with `"Unauthorized"` — the webhook to validate it is not present.

This is confirmed by:
1. The kind GitHub issue #2209 documents an attempt to configure a custom auth webhook with kind. The issue is unresolved / requires complex setup.
2. kind's authentication model relies on client certificates embedded in the auto-generated `kind-config` kubeconfig.
3. Installing aws-iam-authenticator inside a kind cluster is possible but requires running a webhook service on the kind node — complex, fragile, and unnecessary.

`[ASSUMED — derived from kind architecture documentation and GitHub issue analysis; confirmed by understanding that EKS-specific token validation requires the aws-iam-authenticator webhook which is not part of a vanilla Kubernetes kind cluster]`

**Integration test strategy for Phase 3:**

| Test Layer | Auth Path | Cluster | What it tests |
|------------|-----------|---------|---------------|
| Unit (`@mock_aws`) | moto-mocked EKS + STS | No cluster | `get_cluster_access()`, `generate_eks_token()`, `write_kubeconfig()` produce correct outputs |
| Unit (syrupy) | No AWS | No cluster | `HelmClient._build_argv()` matches snapshot |
| Integration (kind) | kind admin kubeconfig | kind cluster | Helm deploys chart, HISTORY_MAX enforced, INJECT works |

For the kind integration test, the `actions/upgrade.py` code path must be invokable with a pre-written kubeconfig (kind's `~/.kube/config` or the output of `kind get kubeconfig --name <cluster-name>`). This requires `upgrade.py` to accept an optional `kubeconfig_path` override OR the test constructs the `ClusterAccess` object pointing to the kind cluster's endpoint + CA and calls `write_kubeconfig()` with the kind token. **Simplest approach:** expose the kind cluster's admin token in a test fixture and pass it as `EksAuthToken`; or extract kind's client cert and patch the kubeconfig writer to emit a cert-based user instead of a token-based user for the test.

**Recommended approach (least invasive):** In `conftest.py`, obtain kind's kubeconfig YAML via `kind get kubeconfig --name kind-phase3` and write it to a temp file. Pass the temp file path to `HelmClient` directly (via `kubeconfig_path` arg). The `actions/upgrade.py` integration test calls `HelmClient` with the kind kubeconfig path, bypassing the `write_kubeconfig()` context manager. The `write_kubeconfig()` unit test covers the tempfile lifecycle separately.

This means the integration test exercises the helm layer (PIPE-01, HISTORY-01, HISTORY-02, META-01, CHART-05) while the unit tests cover the auth/kubeconfig layer (AUTH-07, ClusterAccess). There is no integration test that exercises the full path from AWS credentials → EKS token → kubeconfig → helm; that requires a real EKS cluster (out of Phase 3 scope).

### Minimal In-Repo Test Chart

Location: `tests/fixtures/charts/minimal/`

`Chart.yaml`:
```yaml
apiVersion: v2
name: minimal
description: Minimal chart for Phase 3 integration tests
type: application
version: 0.1.0
```

`templates/configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}-config
  namespace: {{ .Release.Namespace }}
  labels:
    {{- if .Values.bitbucket }}
    bb-build: {{ .Values.bitbucket.bitbucket_build_number | default "" | quote }}
    {{- end }}
data:
  release: {{ .Release.Name }}
  version: {{ .Chart.Version | quote }}
```

The `bitbucket` block in the template enables asserting `helm get values` shows the injected keys.

### kindest/node Version Pin

Current stable: `kindest/node:v1.32.11` (last updated 2025-12-17). Helm 3.18.x supports Kubernetes 1.29–1.32 per version skew policy (current-3 minor versions).

**Pin for integration tests:**
```python
KIND_NODE_IMAGE = "kindest/node:v1.32.11"
```

Cache the image in CI via `actions/cache` on the Docker layer cache path (see Phase 1 `tests/integration/conftest.py` pattern).

`[VERIFIED: kindest/node:v1.32.11 confirmed as latest v1.32 release via Docker Hub API; upload date 2025-12-17]`

### pytest-rerunfailures

Use `pytest-rerunfailures ~= 16.3` (current latest as of 2026-06-18). The `--reruns N --reruns-delay S` flags or `@pytest.mark.flaky(reruns=3)` marker covers kind startup flakiness.

```python
@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_upgrade_deploys_chart(...):
    ...
```

`[VERIFIED: pytest-rerunfailures 16.3 confirmed as latest on PyPI; project is github.com/pytest-dev/pytest-rerunfailures]`

---

## D. syrupy Snapshot Testing for argv

### Package Facts

| Property | Value |
|----------|-------|
| Package | `syrupy` |
| PyPI version | 5.3.2 (current latest — NOT 4.7 as phase context stated) |
| Repository | `https://github.com/syrupy-project/syrupy` (moved from `tophat` org to dedicated `syrupy-project` org) |
| License | Apache-2.0 |
| Classifiers | Production/Stable, Framework :: Pytest |
| PyPI project URL | `https://pypi.org/project/syrupy/` |

`[VERIFIED: PyPI API confirmed version 5.3.2, repository https://github.com/syrupy-project/syrupy]`

**Note:** The phase context cited `~= 4.7`. The current latest is 5.3.2. Use `~= 5.3` (compatible with 5.x, pins to minor).

### Snapshot File Layout

By default, syrupy stores snapshots in `__snapshots__/` in the same directory as the test file, with one `.ambr` file per test module:

```
tests/unit/__snapshots__/
└── test_helm_client_argv.ambr
```

**Snapshots are committed to git** — that is the entire point. Do NOT add `__snapshots__/` to `.gitignore`.

### Workflow

1. First run (snapshot capture): `uv run pytest tests/unit/test_helm_client_argv.py --snapshot-update`
2. Subsequent runs (diff): `uv run pytest tests/unit/test_helm_client_argv.py` — fails if argv changes
3. Intentional update: `uv run pytest tests/unit/test_helm_client_argv.py --snapshot-update`

### Usage Pattern for argv Tests

```python
# tests/unit/test_helm_client_argv.py
from pathlib import Path
from aws_eks_helm_deploy.helm.client import HelmClient

def test_upgrade_argv_basic(snapshot):
    client = HelmClient(kubeconfig_path=Path("/tmp/kube.yaml"))
    argv = client._build_argv(
        release="my-release",
        chart_path=Path("/charts/minimal"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=None,
        timeout="600s",
    )
    assert argv == snapshot

def test_upgrade_argv_with_history_max(snapshot):
    client = HelmClient(kubeconfig_path=Path("/tmp/kube.yaml"))
    argv = client._build_argv(
        release="my-release",
        chart_path=Path("/charts/minimal"),
        namespace="default",
        values_files=["values.yaml"],
        set_args=["image.tag=latest"],
        history_max=5,
        timeout="600s",
    )
    assert argv == snapshot
```

`_build_argv()` is a pure function (no I/O, no subprocess). The snapshot file captures the exact list of strings, preventing accidental regression of the argv construction logic.

`[CITED: https://syrupy-project.github.io/syrupy/]`

---

## E. subprocess Best Practices for Python 3.13

### Canonical Safe Call

```python
import subprocess, os

result = subprocess.run(
    argv,                     # list[str] — never shell=True
    capture_output=True,      # captures both stdout and stderr
    text=True,                # decode as UTF-8
    timeout=timeout_seconds,  # float | None; raises TimeoutExpired if exceeded
    check=False,              # NEVER check=True; map exit codes ourselves
    env=os.environ.copy(),    # pass full env; helm needs PATH, HOME, etc.
)
```

**Why `check=False`:** We map exit codes to typed errors in `HelmClient`. `check=True` raises `CalledProcessError` with no useful context; we need the raw `returncode` + `stderr`.

**Why `list[str]` not shell string:** Prevents shell injection if any argument (e.g., chart path) contains shell metacharacters. Never use `shell=True`.

### TimeoutExpired Exception

When `timeout` is exceeded, `subprocess.run()` raises `subprocess.TimeoutExpired`. The exception carries:
- `exc.cmd`: the argv that was run
- `exc.timeout`: the timeout value
- `exc.stdout`: partial captured stdout (may be `None` — bytes not decoded when timeout fires)
- `exc.stderr`: partial captured stderr (may be `None`)

Map this to `HelmTimeoutError`:
```python
except subprocess.TimeoutExpired as exc:
    partial = (exc.stderr or b"").decode("utf-8", errors="replace")[-1024:]
    raise HelmTimeoutError(
        f"helm upgrade timed out after {exc.timeout}s"
        + (f"; last stderr: {partial}" if partial else "")
    ) from exc
```

`[VERIFIED: subprocess.TimeoutExpired.stderr is None (not decoded bytes) when timeout fires with capture_output=True in Python 3.13 — confirmed in project venv]`

### Environment Sanitization

Pass `env=os.environ.copy()`. Helm does NOT need `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — credentials flow through the kubeconfig file, not env vars. However, stripping AWS env vars from the subprocess env is NOT done in Phase 3 (helm only uses the kubeconfig; the AWS env vars are inert to helm). Phase 5 (SEC-06 / log masking) is the appropriate place for env sanitization if needed.

**Why not strip:** Removing vars risks breaking helm plugins that might inspect env vars. The kubeconfig is the authoritative credential source for helm.

### 32 KB stderr Truncation

```python
STDERR_MAX_BYTES = 32 * 1024

stderr = result.stderr
if len(stderr) > STDERR_MAX_BYTES:
    stderr = "...[truncated]...\n" + stderr[-STDERR_MAX_BYTES:]
```

Truncate to **last** 32 KB (most relevant error context is at the end). The `"...[truncated]..."` marker makes the truncation visible.

---

## F. HISTORY_MAX Edge Cases (closes #17)

### Helm --history-max Semantics

| `--history-max` value | Helm behavior |
|----------------------|---------------|
| Flag omitted | Helm default: 10 revisions |
| `--history-max 0` | Unlimited revision retention |
| `--history-max N` (N ≥ 1) | After upgrade, at most N revisions retained |

`[CITED: https://helm.sh/docs/helm/helm_upgrade/]` — "limit the maximum number of revisions saved per release. Use 0 for no limit (default 10)"

### When Are Old Revisions Pruned?

Pruning happens **after** a successful upgrade. If an upgrade fails, it still creates a new revision with `status=failed`. That revision counts toward the HISTORY_MAX cap on the NEXT successful upgrade.

**Example with HISTORY_MAX=5 after 7 upgrades (5 success + 2 failed interleaved):**
- After upgrade 6 (success), helm prunes to 5 revisions total, including any failed ones.
- `helm history` shows exactly 5 entries (mixed statuses possible).
- The integration test should use 6 sequential successful upgrades and assert `helm history` returns exactly 5 after the 6th.

### Forcing a Revision Bump in Tests

A helm upgrade only creates a new revision if something changes (values, chart, flags). To force a revision bump in integration tests, change a noop value on each upgrade:

```python
for i in range(6):
    helm_client.upgrade_install(
        release="test-release",
        chart=resolved_chart,
        namespace="default",
        values_files=[],
        set_args=[f"test.iteration={i}"],  # forces a new revision each time
        history_max=5,
        timeout=60,
    )
```

### Verification Command

```bash
helm history test-release -n default -o json | jq length
# Expected: 5 (not 6)
```

Or in Python:
```python
import json, subprocess
r = subprocess.run(
    ["helm", "history", "test-release", "-n", "default", "-o", "json"],
    capture_output=True, text=True, check=False
)
revisions = json.loads(r.stdout)
assert len(revisions) <= 5
```

### Phase 5 Rollback Coupling Forward-Note

**MUST be documented in the variable reference:** If `HISTORY_MAX` is set and a subsequent `helm rollback` targets a revision that was pruned, helm raises `"Error: release has X revisions but target revision N not found"`. Phase 5 (`PIPE-04`) will add a pre-flight check for this. Phase 3 ships only the HISTORY_MAX mechanic; the rollback warning is a Phase 5 responsibility.

---

## G. Bitbucket Metadata Env-Var Sourcing

### The Five Variables

| Env Var | `--set` key | Typical Format |
|---------|-------------|----------------|
| `BITBUCKET_BUILD_NUMBER` | `bitbucket.bitbucket_build_number` | integer string, e.g. `"42"` |
| `BITBUCKET_REPO_SLUG` | `bitbucket.bitbucket_repo_slug` | alphanumeric + hyphens, e.g. `"my-repo"` |
| `BITBUCKET_COMMIT` | `bitbucket.bitbucket_commit` | 40-char hex SHA, e.g. `"abc123..."` |
| `BITBUCKET_TAG` | `bitbucket.bitbucket_tag` | git tag, e.g. `"v1.2.3"` or `""` |
| `BITBUCKET_STEP_TRIGGERER_UUID` | `bitbucket.bitbucket_step_triggerer_uuid` | UUID format `{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}` |

### Implementation Pattern

```python
BITBUCKET_META_VARS = [
    ("BITBUCKET_BUILD_NUMBER", "bitbucket.bitbucket_build_number"),
    ("BITBUCKET_REPO_SLUG", "bitbucket.bitbucket_repo_slug"),
    ("BITBUCKET_COMMIT", "bitbucket.bitbucket_commit"),
    ("BITBUCKET_TAG", "bitbucket.bitbucket_tag"),
    ("BITBUCKET_STEP_TRIGGERER_UUID", "bitbucket.bitbucket_step_triggerer_uuid"),
]

def build_bitbucket_set_args(logger: BoundLogger) -> list[str]:
    """Build --set args for Bitbucket metadata injection (META-01)."""
    args: list[str] = []
    for env_var, helm_key in BITBUCKET_META_VARS:
        value = os.environ.get(env_var)
        if not value:  # empty string treated same as unset (D5)
            logger.warning("missing_metadata_key", key=env_var)
            continue
        args.append(f"{helm_key}={value}")
    return args
```

This produces a list of `"key=value"` strings that the caller passes to `HelmClient.upgrade_install(set_args=bitbucket_args + user_set_args)`.

### Quoting and Value Safety

- **`BITBUCKET_BUILD_NUMBER`:** Integer string — safe for `--set`
- **`BITBUCKET_REPO_SLUG`:** Alphanumeric + hyphens — safe for `--set`
- **`BITBUCKET_COMMIT`:** Hex SHA — safe for `--set`
- **`BITBUCKET_TAG`:** Git tag (e.g. `v1.2.3`) — safe for `--set`; if empty, omitted (see above)
- **`BITBUCKET_STEP_TRIGGERER_UUID`:** UUID in `{...}` format — **contains curly braces**

**Curly braces in UUID:** The `{` and `}` chars in UUID values are special to helm's `--set` parser only when they appear inside Go template expressions. When passed as a raw string value via `--set key={uuid}`, helm interprets `{uuid}` as a Go map literal. **Use `--set-string` for this field** to force string interpretation:

```python
# For BITBUCKET_STEP_TRIGGERER_UUID: use --set-string, not --set
# --set-string bitbucket.bitbucket_step_triggerer_uuid='{xxxxxxxx-...}'
```

**Commas and equals signs in values:** Helm's `--set` parser treats `,` as a value separator and `=` inside a value as ambiguous. None of the five Bitbucket variables contain these characters in their documented formats. Document the limitation: if a git tag contains commas or equals (pathological case), it would break `--set`. Use `--set-string` as a safe default for all string metadata.

**Recommendation:** Use `--set-string` for all five Bitbucket metadata flags to avoid any quoting issues. This is the safe default.

`[ASSUMED — helm --set-string behavior derived from Helm docs; the UUID curly brace issue is a documented pitfall. Cannot test without a live helm binary on this host.]`

---

## H. Chart.yaml Parsing

### Library

`PyYAML` is already a direct runtime dependency in `pyproject.toml` (`"PyYAML ~= 6.0"`). Do NOT add it again. The installed version is 6.0.3.

`[VERIFIED: PyYAML 6.0.3 imported successfully in project venv]`

### Chart.yaml Parsing Pattern

```python
import pathlib
import yaml  # PyYAML
from aws_eks_helm_deploy.errors import ChartResolutionError

def parse_chart_yaml(chart_path: pathlib.Path) -> tuple[str, str]:
    """Parse Chart.yaml and return (name, version).

    Args:
        chart_path: Absolute path to the chart directory.

    Returns:
        Tuple of (chart_name, chart_version). Version may be "" if missing (warns).

    Raises:
        ChartResolutionError: If Chart.yaml is missing, unreadable, or unparseable.
    """
    chart_yaml_path = chart_path / "Chart.yaml"
    if not chart_yaml_path.exists():
        raise ChartResolutionError(
            f"Chart.yaml not found at {chart_yaml_path} — is {chart_path} a valid Helm chart?"
        )
    try:
        with chart_yaml_path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ChartResolutionError(
            f"Chart.yaml at {chart_yaml_path} is not valid YAML: {exc}"
        ) from exc

    name: str = data.get("name", chart_path.name)  # fallback to dir name
    version: str = data.get("version", "")
    api_version: str = data.get("apiVersion", "v2")

    if api_version == "v1":
        # Helm 3 reads v1 charts in compatibility mode — warn but proceed
        # (ChartResolutionError would break existing v1 charts; log a warning)
        pass  # caller logs a structlog warn

    return name, version
```

### Required vs Optional Chart.yaml Fields

| Field | Required by Helm? | Phase 3 behavior if missing |
|-------|------------------|------------------------------|
| `apiVersion` | Yes (v2 for Helm 3) | Accept v1 (compatibility mode), log structlog `warn` |
| `name` | Yes | Fallback to chart directory name |
| `version` | Yes | Fallback to `""`, log structlog `warn`; success message shows empty version |
| `type` | No | Ignored by Phase 3 |
| `description` | No | Ignored by Phase 3 |

### ResolvedChart Dataclass

```python
@dataclasses.dataclass(frozen=True)
class ResolvedChart:
    """Immutable resolved local chart descriptor.

    Phase 4 refactors this to a ChartSource Protocol when repo:// and oci://
    sources are added. Phase 3 keeps it as a concrete dataclass.
    """
    name: str           # from Chart.yaml (or dir name fallback)
    version: str        # from Chart.yaml (may be "")
    source_path: pathlib.Path  # absolute path to chart directory
```

---

## I. Package Legitimacy Audit

### New Dependencies Introduced by Phase 3

| Package | Ecosystem | Registry | Version | Downloads | Source Repo | License | Verdict | Disposition |
|---------|-----------|----------|---------|-----------|-------------|---------|---------|-------------|
| `syrupy` | PyPI | PyPI | 5.3.2 | High (Production/Stable classifier) | github.com/syrupy-project/syrupy | Apache-2.0 | OK | Approved — dev dep only |
| `pytest-rerunfailures` | PyPI | PyPI | 16.3 | Very high (pytest-dev org) | github.com/pytest-dev/pytest-rerunfailures | MPL-2.0 | OK | Approved — dev dep only |
| `PyYAML` | PyPI | PyPI | 6.0.3 | Hundreds of millions/week | github.com/yaml/pyyaml | MIT | OK | ALREADY IN pyproject.toml as direct dep |

`[VERIFIED: PyPI API confirmed all three packages; syrupy version 5.3.2, pytest-rerunfailures version 16.3; PyYAML 6.0.3 confirmed in project venv]`

**Packages removed due to SLOP verdict:** None.
**Packages flagged as suspicious (SUS):** None.

### Existing Dependencies Used (No New Additions)

| Package | Usage in Phase 3 |
|---------|-----------------|
| `PyYAML ~= 6.0` | Chart.yaml parsing (already in `[project.dependencies]`) |
| `boto3 ~= 1.43` | EKS describe_cluster; boto3.client("eks") |
| `moto[eks,sts] ~= 5.2` | Unit testing eks/cluster.py with @mock_aws |
| `pytest ~= 9.1` | All test tiers |
| `pytest-mock ~= 3.15` | Mocking in unit tests |

### Version Pin Notes

- **syrupy:** Phase context cited `~= 4.7`. Actual latest is `5.3.2`. The project moved from `tophat/syrupy` to `syrupy-project/syrupy`. Use `~= 5.3`.
- **pytest-rerunfailures:** Phase context cited `~= 14.0`. Actual latest is `16.3`. Use `~= 16.3`.
- **PyYAML:** Already declared; no change needed.

---

## J. Suggested Plan Breakdown

Four plans in four waves, matching the module dependency DAG.

### Wave 1 (Plans 03-01 and 03-02, parallel)

**Plan 03-01: `eks/cluster.py` + `kube/kubeconfig.py`**

Scope:
- `ClusterAccess` frozen dataclass
- `get_cluster_access(session, cluster_name, region) -> ClusterAccess`
- `write_kubeconfig(cluster: ClusterAccess, token: str) -> Iterator[Path]` context manager
- New errors: `KubeconfigError(exit_code=5)` — see error table reconciliation below
- Unit tests: `@mock_aws` for EKS describe_cluster; tempfile lifecycle (create, chmod, delete); kubeconfig YAML content assertion
- No helm, no subprocess

Dependency: `auth/base.py` (for `AwsCredentials`), `aws/eks_token.py` (already exists).

**Plan 03-02: `helm/client.py` + syrupy snapshots**

Scope:
- `HelmResult` dataclass: `stdout: str`, `stderr: str`, `returncode: int`, `revision: int | None`
- `HelmRevision` dataclass: `revision: int`, `status: str`, `chart: str`, `description: str`
- `HelmClient(kubeconfig_path: Path)` class
- `_build_argv(...)` pure function — snapshot tested
- `upgrade_install(...)` — subprocess call + result mapping
- `history(release, namespace) -> list[HelmRevision]`
- New errors: `HelmExecutionError(exit_code=6)`, `HelmTimeoutError(exit_code=7)`
- Add `syrupy ~= 5.3` and `pytest-rerunfailures ~= 16.3` to `[dependency-groups].dev`
- Unit tests: syrupy snapshots on `_build_argv` for all flag combinations; `upgrade_install` unit test with `subprocess.run` mocked via `pytest-mock`

Dependency: `errors.py` (for new typed errors), `pathlib`, `subprocess`.

### Wave 2 (Plan 03-03)

**Plan 03-03: `chart/local.py` + `ResolvedChart`**

Scope:
- `ResolvedChart` frozen dataclass
- `resolve_local_chart(chart_spec: str) -> ResolvedChart`
- Chart.yaml parsing via PyYAML
- `ChartResolutionError` is already declared in `errors.py` (exit_code=4); no new error needed
- Unit tests: 100% branch coverage on all Chart.yaml scenarios (missing, invalid YAML, v1 apiVersion, missing name, missing version, happy path)

Dependency: 03-01's error classes (actually `errors.py` already has `ChartResolutionError`).

### Wave 3 (Plan 03-04)

**Plan 03-04: `actions/upgrade.py` + Settings additions + `cli.py` wire-in**

Scope:
- `Settings` additions:
  - `history_max: int | None = Field(default=None, alias="HISTORY_MAX")` with `ge=0` validator
  - `inject_bitbucket_metadata: bool` already exists in settings.py
  - `helm_timeout: str = Field(default="600s", alias="HELM_TIMEOUT")` — internal env var (planner decides public vs internal)
- `actions/upgrade.py` (< 50 LOC): wire select_strategy → get_credentials → get_cluster_access → generate_eks_token → write_kubeconfig → resolve_local_chart → build_bitbucket_set_args → HelmClient.upgrade_install → pipe.success
- `cli.py` action-dispatch: replace placeholder with `UpgradeAction(settings).run(pipe)`
- Unit tests for `upgrade.py`: mock all dependencies; test all error exit paths; test success structlog fields
- Adds `pydantic.Field(ge=0)` validator for `history_max`

### Wave 4 (Plan 03-05)

**Plan 03-05: kind integration test + minimal chart fixture**

Scope:
- `tests/fixtures/charts/minimal/` — `Chart.yaml` + `templates/configmap.yaml`
- `tests/integration/test_upgrade_action.py`:
  - 6 sequential upgrades with `HISTORY_MAX=5` → assert `helm history` returns 5
  - `INJECT_BITBUCKET_METADATA=true` upgrade → assert `helm get values` shows all 5 bitbucket.* keys
  - Failure path: deploy with invalid values → assert pipe exits non-zero with human message
  - Success message: assert output contains `chart.name` and `chart.version`
- `@pytest.mark.flaky(reruns=3, reruns_delay=5)` on all kind tests
- kind cluster name: `kind-phase3` (avoids collision with Phase 1/2 smoke cluster)

Dependency: Plans 03-01 through 03-04 complete.

---

## K. Threat Model

| Threat ID | Category | Asset | Description | Mitigation | Phase |
|-----------|----------|-------|-------------|-----------|-------|
| T-03-01 | Tampering | kubeconfig tempfile | Another process on shared host reads/modifies tempfile between write and helm invocation | `chmod 0600` before content write; temp path in `tempfile.gettempdir()` (private per user on most OS) | Phase 3 |
| T-03-02 | Information Disclosure | EKS bearer token | Token in process listing via `ps ax` | Token is in FILE (kubeconfig), not in argv. `ps ax` shows `--kubeconfig /tmp/eks-kubeconfig-XXX` — path only | Phase 3 |
| T-03-03 | Tampering | Chart.yaml | Time-of-check vs time-of-use: Chart.yaml parsed before helm invocation; file could change | Inherent TOCTOU in file-based contract. Mitigated by single read; chart path is the user's own chart dir. Acceptable risk. | Phase 3 |
| T-03-04 | Information Disclosure | Helm stderr in error | `HelmExecutionError.message` includes raw helm stderr which may contain Secrets from chart rendering | `bind_safe_context` prevents structlog context binding; stderr goes to `pipe.fail()` message only. Phase 5 (SEC-06) adds Secret masking before any output channel. | Phase 5 |
| T-03-05 | DoS | Memory | Large helm stderr blow-up on chatty error chain | Truncate to last 32 KB per D2 | Phase 3 |
| T-03-06 | Elevation of Privilege | Bitbucket metadata injection | Malicious value in `BITBUCKET_TAG` containing `;` or helm set injection | Helm's `--set-string` parser handles its own quoting; values flow through verbatim. No pre-validation in Phase 3. Document as consumer responsibility. | Phase 3 |

---

## L. Error Hierarchy Reconciliation

**Discrepancy found between CONTEXT.md D8 and existing `errors.py`:**

| Error | CONTEXT.md D8 exit_code | Current `errors.py` exit_code |
|-------|------------------------|-------------------------------|
| `ConfigurationError` | 2 | 1 (existing) |
| `AwsAuthError` / `AuthenticationError` | 1 | 2 (existing) |
| `EksTokenError` | 3 | 3 (matching) |
| `ChartResolutionError` | 4 | 4 (matching) |
| `KubeconfigError` (new) | 5 | — (NEW; `HelmError=5` exists) |
| `HelmExecutionError` (new) | 6 | `HelmError=5` conflicts |
| `HelmTimeoutError` | 7 | `HelmTimeoutError=6` conflicts |

**The CONTEXT.md D8 exit code table contains errors** compared to the existing `errors.py`. The `ConfigurationError` / `AuthenticationError` swap is certainly a CONTEXT.md typo (they were correct in Phase 2 research as 1 and 2 respectively).

**Recommendation for planner:**

Preserve the exit codes already established in `errors.py` to avoid a breaking change in Phase 3. Introduce new errors as follows:

| New Error Class | Replaces/Extends | Recommended exit_code | Rationale |
|----------------|------------------|-----------------------|-----------|
| `KubeconfigError` | New (next available) | 7 | After existing `HelmTimeoutError=6` |
| `HelmExecutionError` | Alias or subclass of existing `HelmError` | 5 (= existing `HelmError`) | `HelmError` becomes `HelmExecutionError`; rename via alias or subclass |
| `HelmTimeoutError` | Already exists | 6 (existing) | No change |

**Alternatively:** Rename `HelmError` to `HelmExecutionError` in `errors.py` and set `KubeconfigError=7`. This is a single-file change with no API break (no existing consumer of `HelmError` by name yet — Phase 2 placeholder never raises it).

**The planner must resolve this.** The researcher's recommendation: rename `HelmError` → `HelmExecutionError` (exit_code=5 unchanged), add `KubeconfigError` (exit_code=7). The CONTEXT.md exit codes for auth errors are swapped — keep the existing correct mapping.

---

## Standard Stack

### Core (Phase 3)
| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| `boto3` | `~= 1.43` | EKS describe_cluster API call | Already in dependencies |
| `PyYAML` | `~= 6.0` | Chart.yaml parsing | Already in dependencies |
| `subprocess` | stdlib | Helm invocation (sync only) | Python stdlib |
| `tempfile` | stdlib | Secure kubeconfig tempfile | Python stdlib |
| `pathlib` | stdlib | Chart path resolution | Python stdlib |

### Dev/Test (new additions)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `syrupy` | `~= 5.3` | argv snapshot tests | Replaces phase context `~= 4.7` pin |
| `pytest-rerunfailures` | `~= 16.3` | kind flakiness guard | Replaces phase context `~= 14.0` pin |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyYAML `safe_load` | `helm show chart` subprocess | `helm show chart` works for repo/OCI (Phase 4); PyYAML is simpler and already available for local paths |
| `tempfile.NamedTemporaryFile` | `os.open` with `O_CREAT\|O_EXCL` | NamedTemporaryFile is more Pythonic; same security guarantees when `delete=False` + `chmod` before write |
| `subprocess.run` (sync) | `asyncio.create_subprocess_exec` | Sync is correct for a one-shot pipe; async adds zero value and complicates error handling |

**Installation (new dev deps only):**
```bash
uv add --group dev "syrupy~=5.3" "pytest-rerunfailures~=16.3"
```

---

## Architecture Patterns

### System Architecture Diagram

```
CLUSTER_NAME, CHART, RELEASE env vars
         │
         ▼
  Settings (pydantic-settings)
         │
    ┌────┴─────────────────────────────────────────────┐
    │                 actions/upgrade.py                │
    │  ┌─────────────┐  ┌──────────────────────────┐   │
    │  │ select_strategy│  │ get_cluster_access()    │   │
    │  │ get_credentials│  │   eks/cluster.py         │   │
    │  └──────┬───────┘  └──────────┬───────────────┘   │
    │         │                     │                   │
    │  ┌──────▼──────────┐          │                   │
    │  │generate_eks_token│◄────────┘                   │
    │  │  aws/eks_token.py│                             │
    │  └──────┬───────────┘                             │
    │         │                                         │
    │  ┌──────▼──────────────────────────┐              │
    │  │ write_kubeconfig() (context mgr) │              │
    │  │   kube/kubeconfig.py             │              │
    │  └──────┬───────────────────────────┘              │
    │         │  yields Path (/tmp/kube-XXXX.yaml)       │
    │  ┌──────▼────────────────────┐                    │
    │  │ resolve_local_chart()     │                    │
    │  │   chart/local.py          │                    │
    │  │   → ResolvedChart         │                    │
    │  └──────┬────────────────────┘                    │
    │         │                                         │
    │  ┌──────▼─────────────────────────────────────┐  │
    │  │ HelmClient.upgrade_install()                │  │
    │  │   helm/client.py                            │  │
    │  │   subprocess.run(["helm", "upgrade", ...]) │  │
    │  └──────┬──────────────────────────────────────┘  │
    │         │ HelmResult                              │
    └─────────┼────────────────────────────────────────┘
              │
       ┌──────▼────────────┐
       │ pipe.success() /  │
       │ pipe.fail()       │
       │ (PipeIO)          │
       └───────────────────┘
```

### Recommended Project Structure (additions only)

```
src/aws_eks_helm_deploy/
├── eks/
│   ├── __init__.py
│   └── cluster.py          # ClusterAccess dataclass + get_cluster_access()
├── kube/
│   ├── __init__.py
│   └── kubeconfig.py       # write_kubeconfig() context manager
├── helm/
│   ├── __init__.py
│   └── client.py           # HelmClient + HelmResult + HelmRevision
├── chart/
│   ├── __init__.py
│   └── local.py            # ResolvedChart + resolve_local_chart()
└── actions/
    ├── __init__.py
    └── upgrade.py          # UpgradeAction (< 50 LOC)

tests/
├── unit/
│   ├── __snapshots__/
│   │   └── test_helm_client_argv.ambr  # committed, NOT in .gitignore
│   ├── test_eks_cluster.py
│   ├── test_kubeconfig.py
│   ├── test_helm_client_argv.py       # syrupy snapshot tests
│   ├── test_helm_client_run.py        # subprocess.run mocked tests
│   ├── test_chart_local.py
│   └── test_upgrade_action.py
├── integration/
│   └── test_upgrade_action.py         # kind cluster tests
└── fixtures/
    └── charts/
        └── minimal/
            ├── Chart.yaml
            └── templates/
                └── configmap.yaml
```

### Anti-Patterns to Avoid

- **`subprocess.run` with `check=True`:** Raises `CalledProcessError` with no typed context. Always `check=False`.
- **`shell=True`:** Enables shell injection if chart path contains metacharacters.
- **`helm/client.py` writing kubeconfig:** Strict layer separation per D1.
- **`actions/upgrade.py` calling `subprocess.run` directly:** Must go through `HelmClient`.
- **`os.environ.get(...)` outside `settings.py` for pipe config:** Bitbucket metadata vars are the explicit exception (they are runtime-injected by Bitbucket, not pipe config). Document this exception in the module docstring.
- **Syrupy snapshots in `.gitignore`:** Snapshots MUST be committed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chart YAML parsing | Custom regex/string parser | `yaml.safe_load()` (PyYAML) | YAML has edge cases (multiline, anchors, Unicode); PyYAML is already a dependency |
| Snapshot testing | Compare `argv == expected_list` hardcoded | `syrupy` | Hardcoded lists drift silently; snapshot diff is visible in CI |
| kubeconfig YAML | String template / f-string | `yaml.dump()` (PyYAML) | Proper YAML escaping for all values |
| subprocess management | Custom timeout/retry loop | `subprocess.run(..., timeout=N)` + `TimeoutExpired` | Standard library handles SIGKILL on timeout |
| Base64 CA encoding | Re-encode bytes | Pass `ca_data` from API response as-is | AWS returns already-base64-encoded CA; kubeconfig expects base64 in `certificate-authority-data` field |

---

## Common Pitfalls

### Pitfall 1: kubeconfig `certificate-authority-data` Double-Encoding

**What goes wrong:** `boto3.client("eks").describe_cluster()` returns `certificateAuthority.data` as a base64-encoded string. The kubeconfig `certificate-authority-data` field expects the same base64 string. If you decode the AWS response and re-encode it, or if you try to write PEM bytes directly, helm rejects the kubeconfig.

**Root cause:** Misunderstanding the kubeconfig field semantics — it stores the already-base64-encoded DER certificate.

**How to avoid:** Pass `cluster.ca_data` directly into the kubeconfig YAML as the value for `certificate-authority-data`. Never call `base64.b64decode()` on it before writing.

### Pitfall 2: `os.chmod()` Called After `write_text()`

**What goes wrong:** Default `NamedTemporaryFile` creates the file with the process umask (often 0644). If `chmod(0o600)` is called after `write_text()`, the token was readable by group/others for a brief window.

**Root cause:** Wrong order of operations.

**How to avoid:** Call `os.chmod(path, 0o600)` BEFORE writing content. Verified pattern in project venv.

### Pitfall 3: Helm `--history-max 0` Means Unlimited (Not Zero)

**What goes wrong:** `HISTORY_MAX=0` is passed through as `--history-max 0`, which tells helm to keep unlimited history — not to delete all history or to refuse upgrades.

**Root cause:** Unintuitive helm semantics.

**How to avoid:** Document explicitly in variable reference. The `ge=0` validator in Settings correctly allows 0 as a valid value. Pydantic validation catches negative integers.

### Pitfall 4: `BITBUCKET_STEP_TRIGGERER_UUID` Contains Curly Braces

**What goes wrong:** Value is `"{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}"`. Helm's `--set` parser interprets `{...}` as a Go map literal, producing a parse error or incorrect value.

**Root cause:** Helm's `--set` parser has special handling for `{...}`.

**How to avoid:** Use `--set-string` (not `--set`) for all five Bitbucket metadata fields, or at minimum for the UUID field. `--set-string` forces string interpretation regardless of value format.

### Pitfall 5: kind Cluster Does Not Accept EKS Bearer Tokens

**What goes wrong:** Integration test that generates a real EKS token (via moto or real AWS) and puts it in a kubeconfig for kind gets `"Unauthorized"` from the kube-apiserver.

**Root cause:** kind has no aws-iam-authenticator webhook. It only validates client certificates, service account tokens, and OIDC (if configured).

**How to avoid:** Use kind's own admin kubeconfig for all helm operations in integration tests. Test the EKS token path independently via unit tests with `@mock_aws`.

### Pitfall 6: HISTORY_MAX Missing in Settings

**What goes wrong:** `HISTORY_MAX` is not currently declared in `settings.py`. Phase 3 must add `history_max: int | None = Field(default=None, alias="HISTORY_MAX")` with `pydantic.Field(ge=0)` or a `@field_validator`.

**Root cause:** Phase 1 `settings.py` was built before Phase 3 was planned. The field is absent.

**How to avoid:** Plan 03-04 adds the field. Planner must include `settings.py` in the edit scope.

---

## Code Examples

### write_kubeconfig Context Manager

```python
# Source: verified pattern in project venv
import os, pathlib, tempfile, yaml
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def write_kubeconfig(cluster: ClusterAccess, token: str) -> Iterator[pathlib.Path]:
    """Write a tempfile kubeconfig for EKS. Deleted on context exit."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="eks-kube-"
    ) as tmp:
        path = pathlib.Path(tmp.name)
    os.chmod(path, 0o600)  # BEFORE writing — closes race window
    try:
        content = yaml.dump({
            "apiVersion": "v1",
            "kind": "Config",
            "preferences": {},
            "clusters": [{"name": cluster.name, "cluster": {
                "server": cluster.endpoint,
                "certificate-authority-data": cluster.ca_data,
            }}],
            "users": [{"name": cluster.name, "user": {"token": token}}],
            "contexts": [{"name": cluster.name, "context": {
                "cluster": cluster.name, "user": cluster.name,
            }}],
            "current-context": cluster.name,
        }, default_flow_style=False)
        path.write_text(content)
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
```

### HelmClient._build_argv

```python
# Source: derived from helm upgrade --install flag set; verified against helm docs
def _build_argv(
    self,
    release: str,
    chart_path: pathlib.Path,
    namespace: str,
    values_files: list[str],
    set_args: list[str],
    history_max: int | None,
    timeout: str,
) -> list[str]:
    argv = [
        "helm", "upgrade", release, str(chart_path),
        "--install",
        "--namespace", namespace,
        "--kubeconfig", str(self._kubeconfig_path),
        "--timeout", timeout,
    ]
    for vf in values_files:
        argv.extend(["--values", vf])
    for sa in set_args:
        argv.extend(["--set-string", sa])  # use --set-string for safety
    if history_max is not None:
        argv.extend(["--history-max", str(history_max)])
    return argv
```

### syrupy Snapshot Test

```python
# Source: syrupy-project.github.io/syrupy/
def test_upgrade_argv_full(snapshot):
    client = HelmClient(kubeconfig_path=pathlib.Path("/tmp/kube.yaml"))
    argv = client._build_argv(
        release="my-release",
        chart_path=pathlib.Path("/charts/minimal"),
        namespace="prod",
        values_files=["base.yaml", "prod.yaml"],
        set_args=["bitbucket.bitbucket_build_number=42"],
        history_max=5,
        timeout="600s",
    )
    assert argv == snapshot
    # Run with --snapshot-update on first execution to capture the baseline
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `awscli.customizations.eks.get_token` internal import | Pure boto3 + botocore events | v2.0 (Phase 2) | -120 MB image; no awscli dependency |
| `exec:` credential provider in kubeconfig | Inlined bearer token in `user.token` | Phase 3 design | No external binary required at helm invocation time |
| `subprocess.run(shell=True)` | `list[str]` argv, `shell=False` | Phase 3 design | Prevents shell injection |
| syrupy `tophat/syrupy` (old org) | `syrupy-project/syrupy` | 2024 | Repository moved; import unchanged |
| pytest-rerunfailures `~= 14.0` | `~= 16.3` (current) | 2025 | Newer version; same API |

**Deprecated / outdated:**
- `syrupy ~= 4.7`: The phase context cited this version. Current latest is 5.3.2 under the `syrupy-project` org. Use `~= 5.3`.
- `pytest-rerunfailures ~= 14.0`: Phase context cited this version. Current latest is 16.3. Use `~= 16.3`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | kind's kube-apiserver does NOT accept EKS k8s-aws-v1.* bearer tokens | C | Low — confirmed by architectural analysis; workaround is kind admin kubeconfig |
| A2 | Helm uses exit code 1 for all failure modes (no distinct codes) | A | Low — confirmed by GitHub issue #4134; if changed in 3.18.x this affects error mapping |
| A3 | helm upgrade stdout `REVISION: N` line is stable across 3.x | A | Low — regression unlikely; snapshot tests would catch it |
| A4 | BITBUCKET_STEP_TRIGGERER_UUID curly braces break `--set` | G | Medium — requires live helm binary to verify; using `--set-string` is the safe default regardless |
| A5 | EKS token validity is 15 minutes | B | Low — well-documented; for a one-shot pipe it is irrelevant |
| A6 | `write_kubeconfig` context manager can use `NamedTemporaryFile(delete=False)` + `chmod` before write | B | Low — verified in project venv; OS-level race window is negligible on a single-user Bitbucket runner |

---

## Open Questions (RESOLVED)

1. **HELM_TIMEOUT as public pipe variable?**
   - What we know: Phase 2/1 already use `TIMEOUT=5m` in Settings for a different field (`settings.timeout: str`). Phase 3 adds `helm_timeout: str = Field(default="600s", alias="HELM_TIMEOUT")`.
   - What's unclear: Is `TIMEOUT` (existing) or `HELM_TIMEOUT` (new) the correct public name? Should Phase 3 reuse `settings.timeout`?
   - Recommendation: Reuse `settings.timeout` (already declared as `timeout: str = Field(default="5m", alias="TIMEOUT")`). Change the default to `"600s"` in Phase 3 to match D2. Do NOT add a second timeout field.

2. **`ResolvedChart` as Protocol in Phase 3 vs Phase 4?**
   - What we know: Phase 4 adds `RepoChart`, `OciChart`.
   - What's unclear: Whether to introduce the Protocol now.
   - Recommendation: Keep `ResolvedChart` as concrete dataclass in Phase 3. Phase 4 introduces `ChartSource` Protocol and has `ResolvedChart` implement it. This is a non-breaking change.

3. **Settings `action` field Literal type needs `"upgrade"` + future values**
   - What we know: `settings.action: Literal["upgrade"]` is too narrow (Phase 5 adds `"diff"`, `"rollback"`).
   - What's unclear: Whether to widen now or let Phase 5 handle it.
   - Recommendation: Phase 3 widens to `Literal["upgrade"]` only — keep as-is. Phase 5 widens the Literal.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All | ✓ | 3.13.x | — |
| boto3 1.43 | EKS describe_cluster | ✓ | 1.43.31 | — |
| PyYAML | Chart.yaml parsing | ✓ | 6.0.3 | — |
| moto[eks,sts] | Unit tests | ✓ | 5.2.2 | — |
| kind | Integration tests | ✗ | — | Integration tests skip cleanly (`pytest.mark.integration` + `shutil.which("kind")` guard) |
| helm binary | Integration tests | ✗ (host) | — | helm is in Docker image; integration tests run in Docker or CI |
| syrupy | Dev tests | ✗ | — | Not installed yet; add to `[dependency-groups].dev` |
| pytest-rerunfailures | Dev tests | ✗ | — | Not installed yet; add to `[dependency-groups].dev` |

**Missing with no fallback:** None that block Phase 3 implementation.
**Missing with fallback:** `kind` and `helm` (host) — integration tests skip cleanly when absent.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest -m unit -q --no-cov` |
| Full suite command | `uv run pytest -m unit --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100` |
| Integration run | `make integration-test` or `uv run pytest -m integration --no-cov` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHART-01 | Local chart path resolved to ResolvedChart | unit | `pytest tests/unit/test_chart_local.py -x` | ❌ Wave 1 (Plan 03-03) |
| CHART-05 | Success message contains chart name + version | integration | `pytest tests/integration/test_upgrade_action.py::test_success_message -x` | ❌ Wave 4 (Plan 03-05) |
| PIPE-01 | helm upgrade --install argv correct | unit (syrupy) | `pytest tests/unit/test_helm_client_argv.py -x` | ❌ Wave 1 (Plan 03-02) |
| PIPE-06 | helm failure → pipe.fail() + non-zero exit | unit + integration | `pytest tests/unit/test_upgrade_action.py -x` | ❌ Wave 3 (Plan 03-04) |
| HISTORY-01 | HISTORY_MAX=5 → at most 5 revisions after 6 upgrades | integration | `pytest tests/integration/test_upgrade_action.py::test_history_max -x` | ❌ Wave 4 (Plan 03-05) |
| HISTORY-02 | --history-max N in argv | unit (syrupy) | `pytest tests/unit/test_helm_client_argv.py::test_upgrade_argv_history_max -x` | ❌ Wave 1 (Plan 03-02) |
| META-01 | 5 bitbucket.* --set-string flags when inject=true | unit (argv) + integration | `pytest tests/unit/test_helm_client_argv.py::test_upgrade_argv_bitbucket -x` | ❌ Wave 1 (Plan 03-02) |

### Sampling Rate

- **Per task commit:** `uv run pytest -m unit -q --no-cov`
- **Per wave merge:** `uv run pytest -m unit --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100`
- **Phase gate:** Full unit suite (100% coverage) green before `/gsd-verify-work`; integration tier runs in `make integration-test`

### Wave 0 Gaps

- [ ] `tests/unit/__snapshots__/` — created on first `--snapshot-update` run; no pre-existing files to add
- [ ] `tests/unit/test_helm_client_argv.py` — Plan 03-02
- [ ] `tests/unit/test_helm_client_run.py` — Plan 03-02
- [ ] `tests/unit/test_eks_cluster.py` — Plan 03-01
- [ ] `tests/unit/test_kubeconfig.py` — Plan 03-01
- [ ] `tests/unit/test_chart_local.py` — Plan 03-03
- [ ] `tests/unit/test_upgrade_action.py` — Plan 03-04
- [ ] `tests/integration/test_upgrade_action.py` — Plan 03-05
- [ ] `tests/fixtures/charts/minimal/Chart.yaml` — Plan 03-05
- [ ] `tests/fixtures/charts/minimal/templates/configmap.yaml` — Plan 03-05
- [ ] Framework additions: `uv add --group dev "syrupy~=5.3" "pytest-rerunfailures~=16.3"` — Plan 03-02

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Auth is Phase 2 scope; Phase 3 consumes credentials |
| V3 Session Management | No | One-shot CLI; no session state |
| V4 Access Control | No | Access control is AWS IAM (consumer-side) |
| V5 Input Validation | Yes | `Settings.history_max` (ge=0 validator); chart path existence check; Chart.yaml safe_load |
| V6 Cryptography | No | Token generation is Phase 2; kubeconfig uses inlined token |
| V7 Error Handling | Yes | All errors → typed `PipeError` subclasses; no raw exception propagation |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| kubeconfig tempfile readable by other users | Information Disclosure | `chmod 0600` before content write (T-03-01) |
| helm stderr leaks Secret values | Information Disclosure | 32 KB truncation in Phase 3; Secret masking in Phase 5 (SEC-06) |
| Bitbucket metadata injection via crafted env var | Tampering / Elevation | Use `--set-string` (helm handles quoting); document consumer responsibility (T-03-06) |
| Chart path traversal (`CHART=../../etc/passwd`) | Tampering | `pathlib.Path.exists()` + `is_dir()` check before passing to helm; helm rejects non-chart dirs anyway |
| Large helm stderr DoS | Denial of Service | 32 KB truncation (T-03-05, D2) |

---

## Sources

### Primary (HIGH confidence — verified in project venv or via authoritative tool)

- PyYAML 6.0.3 — confirmed importable in project venv; `yaml.safe_load` tested
- boto3 1.43.31 + moto 5.2.2 — `eks.describe_cluster()` response fields verified (endpoint, certificateAuthority.data)
- `mypy_boto3_eks.type_defs.ClusterTypeDef`, `CertificateTypeDef` — confirmed fields in project venv
- subprocess.TimeoutExpired.stderr — confirmed as None (not decoded) in Python 3.13 venv
- `os.chmod(path, 0o600)` before write — confirmed sequence produces `-rw-------` in project venv
- kindest/node:v1.32.11 — confirmed via Docker Hub API (last updated 2025-12-17)
- syrupy 5.3.2 — confirmed via PyPI API; repository github.com/syrupy-project/syrupy
- pytest-rerunfailures 16.3 — confirmed via PyPI API; github.com/pytest-dev/pytest-rerunfailures

### Secondary (MEDIUM confidence — official documentation)

- Helm upgrade flag set — `https://helm.sh/docs/helm/helm_upgrade/` (WebFetch)
- Helm history --output json format — `https://helm.sh/docs/helm/helm_history/` (WebFetch)
- syrupy snapshot file layout and `--snapshot-update` flag — `https://syrupy-project.github.io/syrupy/` (WebFetch)
- Helm exit code behavior (all failures = 1) — `https://github.com/helm/helm/issues/4134` (WebSearch)
- kind authentication webhook limitation — `https://github.com/kubernetes-sigs/kind/issues/2209` (WebFetch)

### Tertiary (LOW confidence — training knowledge used where tool verification not possible)

- Helm upgrade stdout `REVISION: N` format — `[ASSUMED]`
- EKS token 15-minute validity — `[ASSUMED]`
- BITBUCKET_STEP_TRIGGERER_UUID curly brace issue with `--set` — `[ASSUMED]`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via PyPI API and project venv
- Architecture: HIGH — derived from locked CONTEXT.md decisions + verified moto/boto3 field shapes
- Helm CLI surface: MEDIUM — helm docs verified via WebFetch; no helm binary on host for experimental verification
- kind integration strategy: HIGH — architectural conclusion (no EKS webhook on kind) is well-grounded
- Pitfalls: HIGH — most verified experimentally in project venv

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (stable domain; syrupy/pytest-rerunfailures versions may advance but pin is current)
