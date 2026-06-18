# Phase 3 CONTEXT — Helm Core & Upgrade Action

**Source:** auto-mode discuss-phase 3, locked decisions only — no interactive gray-area resolution. Inputs: ROADMAP Phase 3 entry, REQUIREMENTS.md, Issue #17 (closed; delivery in Phase 3), Phase 1 + 2 verifier reports.

**Downstream:** `gsd-phase-researcher` reads this to know WHAT to investigate; `gsd-planner` reads this to know WHAT decisions are locked.

## Phase boundary (from ROADMAP)

**Goal:** `ACTION=upgrade` (default) deploys a local-path Helm chart to a real EKS cluster end-to-end via the new typed `HelmClient`, honouring `HISTORY_MAX` and v1-style Bitbucket metadata injection. v1.x functional parity reached on the new architecture. Closes #17.

**REQs in scope (7):** CHART-01, CHART-05, PIPE-01, PIPE-06, HISTORY-01, HISTORY-02, META-01.

**Out of scope (Phase 4+):** repo:// + oci:// chart sources, Cosign verification, diff action, rollback action, log masking deep, opt-in metadata default flip (META-02/03), `--wait`/`--atomic` (SAFE_UPGRADE Phase 5).

## Locked decisions

### D1 — Module shape (locks SC1)

Three new modules, strict layering enforced by Plan-Checker:

| Module | Responsibility | What it MUST NOT do |
|--------|----------------|---------------------|
| `src/aws_eks_helm_deploy/kube/kubeconfig.py` | Write tempfile kubeconfig from `ClusterAccess` + `EksAuthToken`. Context-manager-based lifecycle. Tempfile is `chmod 0600`, in `tempfile.gettempdir()`, deleted on context exit. | No `subprocess.run`. No helm imports. No AWS imports beyond the typed inputs. |
| `src/aws_eks_helm_deploy/helm/client.py` | Single `HelmClient` class. ONLY module that calls `subprocess.run`. One typed method per helm subcommand: `upgrade_install(release, chart, namespace, values, set_args, history_max, timeout) -> HelmResult`; `history(release, namespace) -> list[HelmRevision]`. | No kubeconfig writing (consumes a path). No metadata injection logic (caller passes ready `--set` list). |
| `src/aws_eks_helm_deploy/actions/upgrade.py` | < 50 LOC. Wires `select_strategy` → `generate_eks_token` → `kubeconfig.write_tempfile()` → `HelmClient.upgrade_install()`. Returns success/failure. | No subprocess. No file I/O beyond kubeconfig context-manager use. |

Existing `cli.py` keeps the action-dispatch table (currently a placeholder for `upgrade`).

### D2 — Subprocess model

**Sync `subprocess.run` only.** No async, no concurrent helm calls. The pipe is a one-shot CLI; concurrency would complicate stderr capture and add zero value.

- Default timeout: **600 seconds** per helm invocation (matches Plan 01-02 acceptance-tier default; configurable via `HELM_TIMEOUT` env var). Phase 3 wires the env var; Plan-Checker decides whether to expose it as a public pipe variable now or defer to Phase 5/Phase 7 docs.
- `subprocess.run(..., check=False, capture_output=True, text=True, timeout=...)` — never `check=True`; we map exit codes to typed errors ourselves.
- Stderr capture is the load-bearing input for `HelmExecutionError`. Truncate to last 32 KB if longer (defense against memory blow-up on a chatty Helm error chain).

### D3 — kubeconfig tempfile lifecycle

**Context-manager only.** Public API of `kube/kubeconfig.py`:

```python
@contextmanager
def write_kubeconfig(cluster: ClusterAccess, token: EksAuthToken) -> Iterator[Path]:
    """Yield a Path to a securely-permissioned tempfile kubeconfig.

    The file is deleted on context exit even if the block raises. Permissions
    are 0600. Path is in tempfile.gettempdir() with a randomly-generated name.
    """
```

- File is `delete=True` via `tempfile.NamedTemporaryFile`. Belt-and-braces: also `try: path.unlink() except FileNotFoundError: pass` in the `finally` block.
- Permissions are set via `os.chmod(path, 0o600)` BEFORE writing content (avoid the race where readable content lives at 0644 momentarily).
- YAML structure mirrors `aws eks update-kubeconfig` output — single `clusters/users/contexts` entry, current-context set, no `exec:` block (token is inlined via `user.token`).

### D4 — `HISTORY_MAX` semantics (closes #17)

Lock the wire behaviour Issue #17 asked for:

| `HISTORY_MAX` value | Behaviour |
|---------------------|-----------|
| **unset** | DO NOT pass `--history-max` to helm. Helm's own default (10) applies. Document this as "preserves Helm default" in the variable reference. |
| `HISTORY_MAX=0` | Pass `--history-max 0` to helm. Per Helm docs this means **unlimited** history retention. Document as such. |
| `HISTORY_MAX=N` (N ≥ 1) | Pass `--history-max N`. After upgrade, the cluster's `helm history <release>` returns ≤ N revisions. |
| `HISTORY_MAX=-1` or non-integer | Raise `ConfigurationError` at Settings parse time (pydantic `int` with `ge=0`). Never reaches helm. |

Test obligations (integration tier): 6 sequential upgrades with `HISTORY_MAX=5` → `helm history` shows exactly 5 revisions. With `HISTORY_MAX` unset → default-10 behaviour holds.

Plan-Check Warning to flag: **rollback coupling.** Phase 5 ships rollback (`PIPE-04`); if `HISTORY_MAX < REVISION + 1` rollback breaks. Phase 3 does NOT enforce this (rollback doesn't exist yet) but the variable-reference docs must mention the relationship as a forward note.

### D5 — Bitbucket metadata injection (META-01 only; META-02/03 defer)

Phase 3 implements META-01 explicitly: when `INJECT_BITBUCKET_METADATA=true`, inject all 5 keys via repeated `--set` flags:

```
--set bitbucket.bitbucket_build_number=$BITBUCKET_BUILD_NUMBER
--set bitbucket.bitbucket_repo_slug=$BITBUCKET_REPO_SLUG
--set bitbucket.bitbucket_commit=$BITBUCKET_COMMIT
--set bitbucket.bitbucket_tag=$BITBUCKET_TAG
--set bitbucket.bitbucket_step_triggerer_uuid=$BITBUCKET_STEP_TRIGGERER_UUID
```

**Phase 3 default behaviour** when `INJECT_BITBUCKET_METADATA` is unset or `false`: **no injection.** This is the v2 future state per META-02. Phase 5 adds the deprecation warning (META-03) — Phase 3 does NOT emit the warning yet.

**Missing env vars:** if `INJECT=true` but a specific `BITBUCKET_*` var is missing, omit only that `--set` flag (don't fail). Log a structlog `warn` with `missing_metadata_key=<key>`.

**Why not v1 parity by default in Phase 3:** ROADMAP Phase 3 SC4 explicitly says "When `INJECT_BITBUCKET_METADATA=true`" — the success criterion only covers the opt-in case. META-02 + META-03 are explicitly Phase 5 scope (in `## v2 (Deferred) Requirements`'s ordering and the breaking-change note "(Closes #16; breaking change vs v1.x.)"). v1 parity for INJECT defaults is achieved via the explicit opt-in.

### D6 — Local-path chart resolution (CHART-01 only; repo:// + oci:// defer)

Phase 3 supports `CHART=<local-path>` only — absolute or relative to repo root. Detection: anything not starting with `repo://` or `oci://` is treated as a local path; non-existent path → `ChartResolutionError(exit_code=4)` (matches Phase 2's `EksTokenError` exit_code = 3 family).

A new typed value object **CHART-namespace**:

```python
@dataclass(frozen=True)
class ResolvedChart:
    name: str          # extracted from Chart.yaml or fallback to dir name
    version: str       # extracted from Chart.yaml; "" if missing (warn)
    source_path: Path  # absolute path to the local chart dir
```

`HelmClient.upgrade_install` accepts a `ResolvedChart` (not raw path) so Phase 4's `RepoChart` / `OciChart` can implement the same dataclass with different fields without re-typing the client. Phase 4 will rename `ResolvedChart` to a `ChartSource` Protocol.

### D7 — Success message (CHART-05)

After successful `helm upgrade --install`, emit (via `pipe_io.success`):

```
Deployed chart {chart.name} ({chart.version}) to release {release} in namespace {namespace} on cluster {cluster.name}
```

Also structlog `info` with structured keys: `action=upgrade`, `release`, `namespace`, `chart_source`, `chart_name`, `chart_version`, `cluster`, `auth_strategy` (already bound from Phase 2 `cli.py`), `helm_revision` (parsed from helm stdout), `duration_ms`. Closes OBS-01 with full Phase 1 stable-fields contract.

### D8 — Error mapping (PIPE-06)

Every failure path returns non-zero exit code AND surfaces via `pipe.fail()` with a single-line human message. Errors:

| Error | exit_code | Trigger |
|-------|-----------|---------|
| `ConfigurationError` (existing) | 2 | Settings parse failure, missing required env vars |
| `AwsAuthError` (existing) | 1 | auth strategy `get_credentials()` raises |
| `EksTokenError` (existing) | 3 | `generate_eks_token` raises |
| `ChartResolutionError` (new) | 4 | Local path missing, Chart.yaml absent/unparseable |
| `KubeconfigError` (new) | 5 | Tempfile write fails (disk full, permissions) |
| `HelmExecutionError` (new) | 6 | `helm upgrade` non-zero exit; carries truncated stderr |
| `HelmTimeoutError` (new) | 7 | `subprocess.TimeoutExpired` raised |

The single-line message format: `{error_type}: {short_description} ({remediation_hint})`. Example: `HelmExecutionError: helm upgrade returned 1 — check stderr above for chart rendering error`.

### D9 — argv snapshot tests with `syrupy` (mitigates ROADMAP Risk 1)

Plan must add `syrupy` to `[dependency-groups].dev`. Snapshot tests on `HelmClient._build_argv()` (the argv-construction pure function) prevent the v1.x regression of "subprocess.run timeout edge case crept back in". Snapshots live in `tests/unit/__snapshots__/`.

### D10 — kind integration (mitigates ROADMAP Risk 2)

Phase 3 brings kind from "wired but skipped" (Phase 1) to "actually exercised". Integration tier MUST:

1. Bring up a kind cluster (with kind node image cached per Plan 01-02 patterns)
2. Apply a minimal in-repo test chart at `tests/fixtures/charts/minimal/` (Chart.yaml + templates/configmap.yaml)
3. Run `actions/upgrade.py` against the kind cluster with `STATIC_KEYS` auth (moto-backed STS still gives a valid token for kube-apiserver; if not, switch to a kind-side static token + skip the EKS path)
4. Assert: `helm history <release>` after 6 upgrades with `HISTORY_MAX=5` returns 5
5. Assert: `helm get values <release>` after `INJECT_BITBUCKET_METADATA=true` upgrade shows all 5 `bitbucket.*` keys

**Open question for researcher:** does kind's kube-apiserver accept the moto-presigned-URL EKS token? If not, the integration test needs a different auth shim. Researcher's task to confirm.

Skip + xfail policy: if kind isn't on host, `pytest.skip` cleanly (already wired). If kind is on host but the test fails, that's a real failure — no auto-skip.

### D11 — pre-commit + CI gate stays as-is

No changes to `.pre-commit-config.yaml` or `.github/workflows/ci.yml` for this phase except potentially adding `kind` setup to a future CI matrix (Phase 6 scope per CI-01). Phase 3 keeps integration tier opt-in via `make integration-test`.

### D12 — `helm-diff` plugin NOT used in Phase 3

The Dockerfile ships `helm-diff` 3.10.0 (from Phase 1 Plan 01-03) but Phase 3 does NOT invoke it. Phase 5 ships `ACTION=diff` (`PIPE-02`).

## What the researcher needs to investigate

- **EKS token + kind kube-apiserver compatibility** (D10 open question)
- **helm upgrade --install stderr structure** — what to truncate, what to surface, parsing of "Error: " prefix
- **helm upgrade exit codes** — does Helm distinguish "chart render failure" from "k8s API failure" by exit code? (Likely no — both 1; both go to `HelmExecutionError`.)
- **`helm-diff` version compat with Helm 3.18.6** — already verified in Plan 01-03 but re-confirm
- **Chart.yaml parsing** — use PyYAML (already in pyproject.toml types-PyYAML)? Or `helm show chart` and parse stdout? Recommend stdlib YAML for the simple case; defer `helm show chart` to Phase 4 when repo:// + oci:// need it
- **syrupy** as a snapshot-test library — version pin, integration with pytest, gitignore for snapshot files

## Decisions NOT taken (defer to research / plan-checker)

- **Plan breakdown** — researcher proposes (Section J template from Phase 2), planner finalizes. Likely 4 plans: kubeconfig writer (W1) + HelmClient (W1, parallel) → actions/upgrade.py (W2) → integration test + chart fixture (W3).
- **Whether HELM_TIMEOUT becomes a public pipe variable** — planner decides based on whether existing v1 docs already document it (if yes, keep; if no, internal env-only and document in Phase 7).
- **Whether `ResolvedChart` becomes a Protocol in Phase 3** vs Phase 4 — defer to planner. My recommendation: keep `ResolvedChart` as concrete dataclass in Phase 3; Phase 4 refactors to Protocol when repo:// / oci:// sources arrive.

## Deferred ideas surfaced during analysis (not in scope)

- **`--atomic` / `--wait` flags** → Phase 5 (`PIPE-05` / SAFE_UPGRADE)
- **`helm diff` action + PR comment posting** → Phase 5 (`PIPE-02` / `PIPE-03`)
- **`helm rollback` action** → Phase 5 (`PIPE-04`)
- **Repo + OCI chart sources** → Phase 4 (`CHART-02` / `CHART-03`)
- **Cosign signature verification of charts** → Phase 4 (`CHART-04`)
- **Deprecation-warning loud log for missing INJECT** → Phase 5 (`META-03`)
- **HISTORY_MAX vs REVISION compatibility warning at upgrade time** → Phase 5 (when rollback exists)

## Acknowledged risks (carry into planner)

- **R1 — kind flakiness on CI**: cache node image; retry cluster creation up to 3 times; `pytest-rerunfailures`. (ROADMAP risk; mitigation already documented.)
- **R2 — argv regression**: covered by D9 (syrupy snapshots).
- **R3 — rollback coupling with HISTORY_MAX**: D4 forward-doc; full check lands Phase 5.
- **R4 — kubeconfig token leak via process listing**: tempfile path is in argv (`--kubeconfig /tmp/xxx`); the path itself is non-sensitive. Token is in the FILE not argv. Document that `ps ax` won't leak token.
