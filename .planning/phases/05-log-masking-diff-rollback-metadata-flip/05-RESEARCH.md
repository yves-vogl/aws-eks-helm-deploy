# Phase 5 RESEARCH — Log Masking, Diff, Rollback & Metadata Flip

**Researched:** 2026-06-20
**Domain:** Python (PyYAML, structlog, stdlib urllib), Helm CLI (history, diff, rollback), Bitbucket REST API (PR comments), Dockerfile multi-stage bundling
**Confidence:** HIGH

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D1** — Redaction: `helm/redact.py`, `redact_helm_output(text) -> str`, `yaml.safe_load_all` + Secret-kind filter + `yaml.safe_dump_all(sort_keys=False)`; YAMLError passthrough; wired into every `HelmClient` stdout/stderr capture; PR-comment poster must also pipe through redactor.
- **D2** — helm-diff 3.10 plugin: new Dockerfile stage `helm-diff-fetch`, mirrors `cosign-fetch` (Phase 4 D8) verbatim; SHA256-verified download; extracted plugin files `COPY`d to `$HELM_PLUGINS/diff/`.
- **D3** — PR-comment posting: `bitbucket/pr_comment.py`; single-comment-per-PR marker `<!-- aws-eks-helm-deploy:diff -->`; GET→PUT (update) or POST (new); 4xx-tolerant with `_sanitize_response_body` stripping BITBUCKET_TOKEN literal; errors surface as `logger.warning`, not as hard failure.
- **D4** — META detection: static grep of `${chart_dir}/values.yaml` for `r"^\s*bitbucket\s*:"`; WARN once when match and `inject_bitbucket_metadata is None`; `Settings.inject_bitbucket_metadata: bool | None = None`.
- **D5** — Rollback safety: `HelmClient.history()` pre-flight; refuse rollback to revision not deployed with `--wait` (detected via `description` field containing "wait" substring — see schema below); `Settings.safe_upgrade: bool = False` adds `--wait --atomic` to upgrade argv.
- **D6** — Module discipline: `import subprocess` stays at EXACTLY 2 files (`helm/client.py`, `chart/oci.py`). New methods land in `HelmClient`. No subprocess in `redact.py`, `bitbucket/pr_comment.py`, or any new module.

### Claude's Discretion

- None beyond what is settled in D1–D6.

### Deferred Ideas (OUT OF SCOPE)

- Template-scan for `bitbucket.*` references (richer META-03 detection) — deferred to v2.1
- `PrCommentError` dedicated exception class — deferred; D3 uses warning-only path
- Append-comment mode (audit-trail per run) — deferred
- Bitbucket Data Center / Server (self-hosted) support — deferred
- helm-diff `--output json` for structured PR comments — deferred to Phase 7

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEC-06 | Helm output masks `kind: Secret` manifests — replaces `data`/`stringData` with `<redacted>` | D1: `yaml.safe_load_all` + kind filter + `safe_dump_all(sort_keys=False)` confirmed working; YAMLError passthrough confirmed |
| PIPE-02 | `ACTION=diff` or `DRY_RUN=true` runs `helm diff upgrade` via bundled helm-diff plugin | D2: `helm-diff-fetch` stage; SHA256=`a7875d4656...` (linux-amd64); plugin extracted from tgz to `$HELM_PLUGINS/diff/` |
| PIPE-03 | diff posted as Bitbucket PR comment when `POST_DIFF_AS_COMMENT=true` and in PR context | D3: toolkit has no PR-comment wrapper; use `HttpRequestsHandler.make_session_request` or stdlib `urllib.request`; Bitbucket REST API `/2.0/.../pullrequests/{id}/comments` |
| PIPE-04 | `ACTION=rollback` + `REVISION=<n>` runs `helm rollback <release> <revision>` | D5: `HelmClient.history()` already implemented; new `HelmClient.rollback()` method needed |
| PIPE-05 | `SAFE_UPGRADE=true` adds `--wait --atomic`; pre-flight checks history before rollback | D5: `description` field in `helm history -o json` is the detection signal |
| META-02 | `INJECT_BITBUCKET_METADATA` defaults to `None`/`false` (breaking change) | Settings field type change: `bool = False` → `bool | None = None`; CONTEXT D4 |
| META-03 | Loud one-time WARN when `values.yaml` references `bitbucket:` without explicit opt-in | D4: static grep `r"^\s*bitbucket\s*:"` confirmed; one-time WARN event name confirmed |
| MIG-02 | Startup WARN if v1 env vars `SET`/`VALUES` detected (unconditional, not gated) | `os.environ` scan; `logger.warning("mig.v1_env_var_detected", name="SET")` |

---

## Domain Map

The four sub-features wire together as follows:

**Redactor (D1)** is the foundational primitive. It is implemented in `helm/redact.py` and injected into `HelmClient` as an optional callable (default `redact_helm_output`). Every method on `HelmClient` that captures stdout/stderr (currently `upgrade_install`, `history`; new: `diff`, `rollback`) routes text through the redactor before returning. The PR-comment poster (D3) also applies the redactor to the diff text before posting. This creates defense-in-depth: even if the caller forgets to redact, the HelmClient boundary handles it.

**DiffAction (PIPE-02/03)** adds `actions/diff.py` (mirrors `upgrade.py` structure). It calls a new `HelmClient.diff(release, chart, namespace, ...)` method that invokes `helm diff upgrade`. If `post_diff_as_comment=True` and `BITBUCKET_PR_ID` is set, it calls `bitbucket/pr_comment.py`. The diff text is passed through the redactor before both stdout emission and PR-comment posting.

**RollbackAction (PIPE-04/05)** adds `actions/rollback.py`. It calls `HelmClient.history()` (already implemented in Phase 4) for pre-flight, then new `HelmClient.rollback(release, revision, namespace)`. The `SAFE_UPGRADE` wiring lands in `upgrade.py` (adds `--wait --atomic` to `_build_argv`).

**Metadata Flip (META-02/03/MIG-02)** modifies `settings.py` (type change + new fields), `actions/upgrade.py` (D4 static grep after chart resolution, before helm upgrade), and a startup hook in `cli.py` (MIG-02 v1 env-var scan).

The `Dockerfile` gains one new stage (`helm-diff-fetch`) placed between `cosign-fetch` and `runtime`, and the runtime stage drops the `helm plugin install` step in favour of `COPY --from=helm-diff-fetch`.

---

## Source-of-Truth Resolutions

### helm-diff 3.10

- **Exact pinned version:** `3.10.0` [VERIFIED: github.com/databus23/helm-diff releases via gh CLI]
- **Release date:** 2025-02-04
- **Release URL:** `https://github.com/databus23/helm-diff/releases/tag/v3.10.0`
- **Only 3.10.x release:** There is exactly one release in the 3.10.x series. The next release after 3.10.0 was 3.11.0. REQUIREMENTS.md IMAGE-02 says "3.10.x" — pin to `3.10.0`.
- **Tarball download URL (linux/amd64):** `https://github.com/databus23/helm-diff/releases/download/v3.10.0/helm-diff-linux-amd64.tgz`
- **SHA256 source:** `https://github.com/databus23/helm-diff/releases/download/v3.10.0/helm-diff_3.10.0_checksums.txt` (upstream checksum file exists — use preferred approach per D2)
- **SHA256 (linux-amd64):** `a7875d4656b327b0b7f792f25a70f714801e402eb199ddd0f2df06a063e6bede` [VERIFIED: downloaded and confirmed]
- **Tarball contents:** extracts to `diff/` directory with `diff/plugin.yaml`, `diff/bin/diff` (pre-built amd64 ELF), `diff/LICENSE`, `diff/README.md`
- **Plugin name (from plugin.yaml):** `name: "diff"` — the helm plugin command is `helm diff`, and the plugin directory MUST be named `diff`, NOT `helm-diff`
- **Plugin path in container:** `$HELM_PLUGINS/diff/` where `HELM_PLUGINS=/home/pipe/.local/share/helm/plugins` (per Dockerfile line 112)
- **Dockerfile already pins `HELM_DIFF_VERSION=3.10.0`** — D2 changes HOW it's installed (separate fetch stage), not the version

**Dockerfile D2 implementation pattern:**

```dockerfile
# ── Stage 2.7: helm-diff plugin fetch ────────────────────────────────────────
FROM debian:bookworm-slim@${DEBIAN_BASE_DIGEST} AS helm-diff-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG HELM_DIFF_VERSION

RUN curl -fsSL \
      "https://github.com/databus23/helm-diff/releases/download/v${HELM_DIFF_VERSION}/helm-diff-linux-amd64.tgz" \
      -o "/tmp/helm-diff-linux-amd64.tgz" \
    && curl -fsSL \
      "https://github.com/databus23/helm-diff/releases/download/v${HELM_DIFF_VERSION}/helm-diff_${HELM_DIFF_VERSION}_checksums.txt" \
      -o "/tmp/helm-diff_checksums.txt" \
    && cd /tmp \
    && grep "  helm-diff-linux-amd64.tgz$" helm-diff_checksums.txt | sha256sum -c \
    && tar -xzf helm-diff-linux-amd64.tgz \
    && rm helm-diff-linux-amd64.tgz helm-diff_checksums.txt

# Runtime stage copies the extracted 'diff/' directory to the pipe user's plugin path
# COPY --from=helm-diff-fetch /tmp/diff /home/pipe/.local/share/helm/plugins/diff
```

**D2 CONTRADICTION to surface (does NOT block locking, but planner must correct):** The CONTEXT.md D2 text says `COPY --from=helm-diff-fetch /diff /root/.local/share/helm/plugins/helm-diff/`. Both path segments are wrong:
1. Should be `/home/pipe`, not `/root` (Dockerfile runs as USER pipe with `HELM_PLUGINS=/home/pipe/...`)
2. Plugin directory name must be `diff`, not `helm-diff` (per `plugin.yaml name: "diff"`)

The planner must use `COPY --from=helm-diff-fetch /tmp/diff /home/pipe/.local/share/helm/plugins/diff` (or adjust for the actual extract path in the fetch stage).

Also: the current runtime stage installs helm-diff via `helm plugin install` (which requires `git` + `curl`). Switching to the fetch stage eliminates the need for those packages in the runtime stage's `apt-get install`, allowing removal of the purge step. This is a secondary benefit of D2.

---

### helm history --output json schema

The schema is confirmed by existing tests in `tests/unit/test_helm_client_run.py` (Phase 4 work — `HelmClient.history()` is **already implemented** in `helm/client.py:316–371`).

**Confirmed JSON shape:**
```json
[
  {
    "revision": 1,
    "updated": "2026-01-01T00:00:00Z",
    "status": "superseded",
    "chart": "minimal-0.1.0",
    "app_version": "",
    "description": "Install"
  },
  {
    "revision": 2,
    "updated": "2026-01-02T00:00:00Z",
    "status": "deployed",
    "chart": "minimal-0.1.0",
    "app_version": "1.0",
    "description": "Upgrade complete"
  }
]
```

**Field names:** `revision` (int), `updated` (ISO8601 string), `status` (string), `chart` (string), `app_version` (string), `description` (string). [VERIFIED: from existing test fixtures + helm CLI docs]

**HelmRevision dataclass (already defined in `helm/client.py:129–143`):**
```python
@dataclasses.dataclass(frozen=True)
class HelmRevision:
    revision: int
    status: str
    chart: str
    description: str
    # NOTE: `updated` and `app_version` are intentionally omitted (not needed for rollback logic)
```

**How `--wait` is recorded:** Helm writes the description field differently based on how the release was deployed:
- Without `--wait`: `"Install complete"`, `"Upgrade complete"`
- With `--wait --atomic`: `"Install complete"` or `"Upgrade complete"` — the description text does NOT reliably encode `--wait` status in helm 3.x

**CRITICAL FINDING on D5 `--wait` detection:** The `description` field does NOT reliably indicate whether `--wait` was used. Helm 3.x does not record deployment flags in history. The D5 CONTEXT says "detected via description parsing" — this is not implementable as described. See "Contradictions to surface" section below.

**Recommended approach (confirmed reliable alternative):**
Use a Helm Release annotation. When `SAFE_UPGRADE=true`, pass `--set-string safe_upgrade_marker=true` and read the annotation back via `helm get metadata <release>`. But this pollutes chart values.

**Better alternative:** Store the fact in a Kubernetes annotation on the release secret:
```bash
helm upgrade ... --set-string-from-file ...
```
This is also complex.

**Simplest reliable approach:** Add a Helm chart annotation via `--description "safe-upgrade"` (helm upgrade accepts `--description`). Then parse `description` for the substring `"safe-upgrade"`. This IS reliable because our pipe sets the description explicitly. [ASSUMED — helm upgrade --description flag behavior]

**Fallback per D5:** If description-based detection is unreliable, the plan should include a task to add `--description "safe-upgrade"` to the `HelmClient.upgrade_install()` argv when `safe_upgrade=True`, and detect in history by `revision.description.startswith("safe-upgrade")` or contains the substring. The `HelmRevision.description` field is already captured.

---

### bitbucket-pipes-toolkit API surface

**Installed version in project:** `6.2.0` [VERIFIED: `uv run python -c "import importlib.metadata; print(importlib.metadata.version('bitbucket-pipes-toolkit'))"`]

**API audit for PR comments:**

The toolkit does NOT expose a PR-comment wrapper. `BitbucketApiRepositoriesPipelines` has only:
- `get_last_build_number(workspace, repo_slug)`
- `get_logs_from_step(workspace, repo_slug, build_number, uuid) -> str`
- `get_steps_uuid(workspace, repo_slug, build_number)`

`HttpRequestsHandler.make_session_request(method, url, ...)` is a general-purpose `requests.Session` wrapper with retry and timeout. It calls `fail()` on errors, NOT raises — this behaviour is incompatible with D3's 4xx-tolerant warning-only requirement.

**Recommendation for D3 HTTP client:** Use **`urllib.request`** (stdlib). Rationale:
- `bitbucket-pipes-toolkit` has no PR-comment methods
- `HttpRequestsHandler.make_session_request` calls `fail()` on errors — hard-fails the pipe on any network error. This violates D3's "4xx-tolerant, emit warning, continue" contract
- `requests` IS available as a transitive dep (via toolkit), but using it directly adds an implicit dep without a declared constraint — a smell
- `urllib.request` is zero-weight stdlib, needs no new imports, and gives full control over error handling
- No NIH violation: stdlib counts as standard per CLAUDE.md global rule

**`urllib.request` pattern for D3:**
```python
import json
import urllib.request
import urllib.error

def _api_request(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)
```

---

### PyYAML behavior verification

[VERIFIED: executed in project venv via `uv run python`]

1. **`yaml.safe_load_all(text)` returns a generator of docs.** Each `---` separator produces one doc. Calling `list()` on it materializes all docs. Safe for multi-doc helm output.

2. **`yaml.safe_dump_all(docs, sort_keys=False)` preserves:**
   - Document count: YES — emits one YAML document per item in the list
   - Document order: YES — items processed in list order
   - Key order within each doc: YES — Python 3.7+ dicts are insertion-ordered; `sort_keys=False` preserves that order

3. **Edge cases confirmed:**
   - `None` docs (empty `---`) are emitted as `--- null\n...\n` — acceptable passthrough
   - Empty doc separator (`---\n---\n`) parses to `[None, None]` and re-dumps as `null\n--- null\n...\n`
   - Non-YAML helm output (e.g., `"Release \"my-release\" has been upgraded. Happy Helming!\nNAME: my-release\n..."`) raises `yaml.scanner.ScannerError` → caught as `YAMLError` → passthrough (correct D1 behaviour)

4. **Separator format:** `yaml.safe_dump_all` uses `---` separator between documents. The first document does NOT have a leading `---`. This matches how helm renders multi-doc manifests.

5. **Redaction confirmed working:**
   ```python
   # Secret kind: data + stringData replaced with '<redacted>' string
   # Other kinds: unchanged
   # Non-YAML input: returned unchanged (YAMLError passthrough)
   ```
   Verified with a multi-doc input containing `kind: Secret` + `kind: ConfigMap`.

6. **`sort_keys=False` vs `sort_keys=True`:** With `sort_keys=False`, keys appear in Python dict insertion order. Since `yaml.safe_load_all` preserves the original YAML key order into a Python dict (Python 3.7+), round-tripping a YAML doc with `safe_load_all` + `safe_dump_all(sort_keys=False)` preserves key order. **No custom dumper needed.**

---

### Existing Secret-emitting fixture

**Finding:** NO Secret-emitting chart fixture exists in the test suite. [VERIFIED: `find tests -name "*secret*"` and `grep -rn "kind: Secret" tests/` both returned empty]

The only test fixture chart is `tests/fixtures/charts/minimal/` which emits a `ConfigMap` only. The `templates/configmap.yaml` renders `bitbucket.*` values conditionally but is not a `kind: Secret`.

**Recommendation:** Create `tests/fixtures/charts/secret-emitting/` as a minimal chart with one template emitting a `kind: Secret`. Suggested structure:
```
tests/fixtures/charts/secret-emitting/
├── Chart.yaml           # name: secret-emitting, version: 0.1.0
└── templates/
    └── secret.yaml      # kind: Secret, data: {password: "dGVzdA=="}
```

This fixture supports the D1 fuzz test (unit tier) and integration redaction tests without importing external charts.

---

## Codebase State Inventory (Phase 5 starting conditions)

| Item | Current State | Phase 5 Change |
|------|--------------|----------------|
| `settings.py :: action` | `Literal["upgrade"]` | Widen to `Literal["upgrade", "diff", "rollback"]` |
| `settings.py :: inject_bitbucket_metadata` | `bool = False` | Change to `bool \| None = None` |
| `cli.py` dispatch | Only handles `"upgrade"`; has `# pragma: no cover` on else branch | Add `"diff"` and `"rollback"` branches; remove pragma |
| `HelmClient.history()` | **Already implemented** in Phase 4 (`helm/client.py:316–371`) | No change needed; used by D5 pre-flight |
| `HelmRevision` dataclass | **Already defined** in Phase 4 (`helm/client.py:129–143`) | No change needed |
| subprocess import count | **Exactly 2 files** (`helm/client.py`, `chart/oci.py`) | Must remain 2 after Phase 5 |
| `PyYAML` dep | Already in `pyproject.toml` (`PyYAML ~= 6.0`) | No new dep needed for `helm/redact.py` |
| `bitbucket-pipes-toolkit` dep | Already in `pyproject.toml` (`~= 6.2`) | No new dep; D3 uses urllib.request from stdlib |
| Dockerfile helm-diff install | `helm plugin install` in runtime stage (needs git+curl) | Replace with `helm-diff-fetch` stage + `COPY --from` |
| `bitbucket/` module package | Does NOT exist | Create `src/aws_eks_helm_deploy/bitbucket/__init__.py` + `pr_comment.py` |
| `actions/diff.py` | Does NOT exist | Create |
| `actions/rollback.py` | Does NOT exist | Create |
| `helm/redact.py` | Does NOT exist | Create |

---

## Contradictions to Surface

**CONTRADICTION 1 (D2 — Dockerfile path):** `05-CONTEXT.md` D2 says:
> `COPY --from=helm-diff-fetch /diff /root/.local/share/helm/plugins/helm-diff/`

This is wrong on two counts verified by direct inspection:
1. `/root/` should be `/home/pipe/` — the Dockerfile uses USER pipe with `HELM_PLUGINS=/home/pipe/.local/share/helm/plugins`
2. `helm-diff` should be `diff` — the plugin's `plugin.yaml` declares `name: "diff"` and the tgz extracts to `diff/`

**Correct COPY directive:**
```dockerfile
COPY --from=helm-diff-fetch /tmp/diff /home/pipe/.local/share/helm/plugins/diff
```

Severity: MEDIUM. If not corrected, `helm diff` will silently not work in the container. The planner must use the corrected path.

---

**CONTRADICTION 2 (D5 — `--wait` detection via `description` field):** `05-CONTEXT.md` D5 says:
> "If the target revision was NOT deployed with `--wait`: raise `ChartResolutionError`..."
> "For each `Revision` we read... the `description` column (helm includes flags like `Install/Upgrade complete` — researcher confirms `--wait`-tracking via either `description` parsing or a deterministic side-channel like `helm get metadata`)"

**Research finding:** Helm 3.x does NOT record `--wait` or `--atomic` flags in the `description` field of history entries. Standard descriptions are `"Install complete"`, `"Upgrade complete"`, `"Rollback to 3"` — none of these encode `--wait` semantics. [ASSUMED based on helm source code knowledge; no running cluster available to verify live, but consistent with helm documentation and test fixtures in the codebase]

**Recommended resolution:** When `SAFE_UPGRADE=true`, explicitly pass `--description "pipe:safe-upgrade"` to `helm upgrade --install`. Then in `HelmClient.history()`, the revision's `description` will contain `"pipe:safe-upgrade"`. The pre-flight check is `"pipe:safe-upgrade" in revision.description`.

This pattern:
- Is reliable and deterministic (pipe controls the description)
- Requires no external metadata store or annotation lookup
- Requires a small addition to `_build_argv`: when `safe_upgrade=True`, append `["--description", "pipe:safe-upgrade"]`
- Works with existing `HelmRevision.description` field (already captured)

**Action for planner:** Add a task in 05-05 to:
1. Add `--description "pipe:safe-upgrade"` to `_build_argv` when `safe_upgrade=True`
2. Pre-flight check: `"pipe:safe-upgrade" in revision.description`

Severity: HIGH — without this resolution, D5 pre-flight is unimplementable as described.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Secret payload masking | Python lib (`helm/redact.py`) | `HelmClient` wiring | Pure text transform; no subprocess |
| helm diff argv | `HelmClient` (subprocess tier) | `actions/diff.py` (orchestration) | D6: subprocess only in client.py |
| PR-comment POST/PUT | `bitbucket/pr_comment.py` (HTTP tier) | `actions/diff.py` (caller) | Separate module; no subprocess |
| Rollback pre-flight | `HelmClient.history()` (already exists) | `actions/rollback.py` | Reuses existing typed method |
| `--wait --atomic` wiring | `HelmClient._build_argv()` | `actions/upgrade.py` | argv construction in client |
| META detection (values.yaml grep) | `actions/upgrade.py` | filesystem read | Plain file read; not in settings |
| MIG-02 startup scan | `cli.py` (startup hook) | — | One-time at startup before dispatch |
| Action dispatch | `cli.py` | `settings.py` (action Literal) | cli.py already has Phase 5 comment |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1 (unit tier runs by default via `addopts = "-m 'unit'"`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit -q --no-cov` |
| Full suite command | `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SEC-06 | `redact_helm_output` masks Secret data/stringData | unit | `uv run pytest tests/unit/test_helm_redact.py -x` | ❌ Wave 0 |
| SEC-06 | Non-YAML input passes through unchanged | unit | same | ❌ Wave 0 |
| SEC-06 | Multi-doc YAML: only Secret docs redacted | unit | same | ❌ Wave 0 |
| SEC-06 | `HelmClient.upgrade_install` stdout/stderr through redactor | unit (mock) | `uv run pytest tests/unit/test_helm_client_run.py -x` | ✅ (extend) |
| PIPE-02 | `HelmClient.diff()` builds correct argv | unit | `uv run pytest tests/unit/test_helm_client_argv.py -x` | ✅ (extend) |
| PIPE-02 | `DiffAction.run()` happy path | unit (mock) | `uv run pytest tests/unit/test_diff_action.py -x` | ❌ Wave 0 |
| PIPE-03 | PR-comment POST when no existing comment | unit (mock urllib) | `uv run pytest tests/unit/test_pr_comment.py -x` | ❌ Wave 0 |
| PIPE-03 | PR-comment PUT when marker comment found | unit (mock urllib) | same | ❌ Wave 0 |
| PIPE-03 | 401 response: no token in log output | unit (mock urllib) | same | ❌ Wave 0 |
| PIPE-04 | `HelmClient.rollback()` argv correct | unit | `uv run pytest tests/unit/test_helm_client_argv.py -x` | ✅ (extend) |
| PIPE-05 | Pre-flight: safe-upgrade revision passes | unit (mock history) | `uv run pytest tests/unit/test_rollback_action.py -x` | ❌ Wave 0 |
| PIPE-05 | Pre-flight: non-safe revision raises ChartResolutionError | unit (mock history) | same | ❌ Wave 0 |
| META-02 | `Settings.inject_bitbucket_metadata` default is `None` | unit | `uv run pytest tests/unit/test_settings.py -x` | ✅ (extend) |
| META-03 | WARN emitted when values.yaml has `bitbucket:` + setting is None | unit | `uv run pytest tests/unit/test_upgrade_action.py -x` | ✅ (extend) |
| MIG-02 | WARN on `SET` env var at startup | unit | `uv run pytest tests/unit/test_cli.py -x` | ✅ (extend) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit -q --no-cov`
- **Per wave merge:** `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_helm_redact.py` — covers SEC-06 (new module)
- [ ] `tests/unit/test_diff_action.py` — covers PIPE-02/03
- [ ] `tests/unit/test_pr_comment.py` — covers PIPE-03
- [ ] `tests/unit/test_rollback_action.py` — covers PIPE-04/05
- [ ] `tests/fixtures/charts/secret-emitting/` — fixture chart for SEC-06 tests

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `yaml.safe_load_all` (not `yaml.load`); `int()` coercion for revision |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| BITBUCKET_TOKEN leak in logs | Info Disclosure | `_sanitize_response_body` strips token literal; `bind_safe_context` rejects credential keys |
| Secret YAML in diff PR comment | Info Disclosure | `redact_helm_output()` applied before POST/PUT |
| YAML bomb / billion-laughs | DoS | `yaml.safe_load_all` uses SafeLoader which disallows aliases expansion attacks |
| Token in argv / env vars | Info Disclosure | D6: no subprocess in `bitbucket/pr_comment.py`; token passed as HTTP header only |

### Security invariants the plan-checker must enforce:

1. `grep -rn "BITBUCKET_TOKEN" src/` returns NO literal string occurrences (only `Settings.bitbucket_token` field reference)
2. `grep '^import subprocess' src/aws_eks_helm_deploy/` returns EXACTLY 2 files
3. `yaml.safe_load` (not `yaml.load`) is used in `redact.py`
4. `_sanitize_response_body` strips both the token value AND `Authorization:` header lines

---

## Risks Beyond ROADMAP R1–R3

**R4 — helm plugin missing `install-binary.sh`:** The helm-diff tgz does NOT include the `install-binary.sh` hook script that `plugin.yaml hooks.install` references. Helm only runs `install` hooks during `helm plugin install`, NOT during plugin loading from disk. So the `COPY --from=helm-diff-fetch` approach correctly bypasses this hook. **Risk:** if a future helm version validates plugin hooks at load time, the build will break. Mitigation: add `helm diff version` smoke test in runtime stage (already present in Dockerfile line 127) to fail the build early.

**R5 — `yaml.safe_dump_all` null-doc separator:** When helm output contains empty `---` separators, `safe_load_all` produces `None` items and `safe_dump_all` re-emits them as `null\n--- null\n...\n`. This changes whitespace vs. the original input. Since the redactor output is used for display (PR comments, logs) not re-parsing, this is cosmetic and acceptable. **Risk:** if the diff output is fed to helm again (e.g., from a recorded test), the format change may cause test fragility. Mitigation: snapshot tests for the redactor output; accept the format change.

**R6 — settings type change `bool → bool | None` breaks 100 % coverage in existing tests:** `tests/unit/test_settings.py` has `test_inject_bitbucket_metadata_default_is_false` (likely). When the type changes to `None`, the test assertion `assert s.inject_bitbucket_metadata == False` becomes `assert s.inject_bitbucket_metadata is None`. Planner must include a task to update the existing test. [ASSUMED: exact test name — grep will confirm in plan execution]

**R7 — `DRY_RUN=true` + `ACTION=upgrade` shortcut:** REQUIREMENTS PIPE-02 says `ACTION=diff` OR `DRY_RUN=true` activates diff mode. Current settings.py has `dry_run: bool = False`. When `dry_run=True` and `action="upgrade"`, cli.py must route to DiffAction, NOT UpgradeAction. This routing logic is not explicitly stated in D1–D6. The planner must add a task in 05-01 (Settings) or 05-03 (DiffAction wiring) to define this routing logic. Suggestion: `if settings.action == "diff" or settings.dry_run: return DiffAction(...).run(pipe)`.

**R8 — ACTION=diff needs `chart` + `release_name` + `cluster_name` like upgrade:** DiffAction must validate the same required fields as UpgradeAction. The planner should reuse the same field guards from `upgrade.py` (copy-paste + same error messages) or extract a shared `_require_cluster_chart_release(settings)` helper.

---

## Plan-by-Plan Suggestion

### Wave 1 (sequential — each unblocks the next)

**05-01: Settings field additions** [WAVE 1 — precursor]
- Requirements: META-02, PIPE-03, PIPE-04, PIPE-05
- Key files: `settings.py`, `tests/unit/test_settings.py`
- Tasks: (a) widen `action` Literal to `["upgrade", "diff", "rollback"]`; (b) change `inject_bitbucket_metadata: bool = False` → `bool | None = None`; (c) add 4 new fields (`post_diff_as_comment`, `bitbucket_token: SecretStr | None`, `safe_upgrade`, `revision: int | None`); (d) update existing settings tests
- Complexity: **small** (pure pydantic field changes)
- Note: `BITBUCKET_TOKEN` as `SecretStr` prevents repr leak; consistent with `registry_password` pattern

**05-02: SEC-06 redactor** [WAVE 1 — unblocks 05-03, 05-04]
- Requirements: SEC-06
- Key files: `src/aws_eks_helm_deploy/helm/redact.py` (new), `helm/client.py` (wiring), `tests/unit/test_helm_redact.py` (new), `tests/unit/test_helm_client_run.py` (extend), `tests/fixtures/charts/secret-emitting/` (new)
- Tasks: (a) create `redact.py`; (b) add `redactor` parameter to `HelmClient.__init__`; (c) route `upgrade_install` stdout+stderr through redactor; (d) route `history` stdout through redactor; (e) unit tests (happy path, YAMLError passthrough, multi-doc, fuzz)
- Complexity: **medium** (new module + 2 wiring points + test coverage at 100%)

### Wave 2 (can parallelize 05-03 + 05-05 + 05-06 after wave 1 complete)

**05-03: PIPE-02 + Dockerfile helm-diff-fetch stage + DiffAction** [WAVE 2]
- Requirements: PIPE-02
- Key files: `Dockerfile` (new stage), `helm/client.py` (new `diff()` method + `_build_diff_argv()`), `actions/diff.py` (new), `cli.py` (dispatch wiring), `tests/unit/test_helm_client_argv.py` (extend), `tests/unit/test_diff_action.py` (new)
- Tasks: (a) add `helm-diff-fetch` Dockerfile stage with SHA256 verify; (b) remove `helm plugin install` from runtime stage + purge curl/git apt section; (c) add `COPY --from=helm-diff-fetch`; (d) add `HelmClient.diff()` + `_build_diff_argv()`; (e) create `DiffAction`; (f) wire `ACTION=diff` and `DRY_RUN=true` in `cli.py`
- Complexity: **large** (multi-file: Dockerfile + 2 source + 2 test files)

**05-04: PIPE-03 PR-comment poster** [WAVE 2 — depends on 05-02 (redactor)]
- Requirements: PIPE-03
- Key files: `src/aws_eks_helm_deploy/bitbucket/__init__.py` (new), `bitbucket/pr_comment.py` (new), `actions/diff.py` (extend), `tests/unit/test_pr_comment.py` (new)
- Tasks: (a) create `bitbucket/` package; (b) implement `post_diff_comment(workspace, repo_slug, pr_id, diff_text, token)` with GET+PUT/POST idempotency + marker; (c) implement `_sanitize_response_body`; (d) wire into `DiffAction.run()` when `post_diff_as_comment=True` and `BITBUCKET_PR_ID` is set; (e) unit tests: happy path, idempotent update, 401 handling (no token in log)
- Complexity: **medium**

**05-05: PIPE-04 + PIPE-05 rollback + SAFE_UPGRADE** [WAVE 2]
- Requirements: PIPE-04, PIPE-05
- Key files: `helm/client.py` (new `rollback()` + `_build_rollback_argv()` + `_build_argv` safe_upgrade addition + `--description` for safe-upgrade marker), `actions/rollback.py` (new), `cli.py` (dispatch), `tests/unit/test_helm_client_argv.py` (extend), `tests/unit/test_rollback_action.py` (new), `settings.py` (already done in 05-01)
- Tasks: (a) add `--wait --atomic` to `_build_argv` when `safe_upgrade=True`; (b) add `--description "pipe:safe-upgrade"` to `_build_argv` when `safe_upgrade=True` (CONTRADICTION 2 resolution); (c) implement `HelmClient.rollback()`; (d) implement `RollbackAction` with pre-flight; (e) unit tests
- Complexity: **medium**

**05-06: META-02 + META-03 + MIG-02** [WAVE 2]
- Requirements: META-02, META-03, MIG-02
- Key files: `actions/upgrade.py` (D4 grep wiring), `cli.py` (MIG-02 startup scan), `settings.py` (already in 05-01: `inject_bitbucket_metadata` type change), `tests/unit/test_upgrade_action.py` (extend), `tests/unit/test_cli.py` (extend)
- Tasks: (a) add `_check_bitbucket_values_yaml(chart_dir)` to upgrade.py (pure file-read + regex); (b) call it after chart resolution, before helm upgrade; (c) add MIG-02 v1 env scan to cli.py startup; (d) update existing `inject_bitbucket_metadata`-related tests for `None` default
- Complexity: **small–medium**

### Wave 3 (doc only)

**05-07: Migration guide draft** [WAVE 3 — doc only]
- Requirements: MIG-02 (partial)
- Key files: `docs/guides/v1-to-v2.md` (new)
- Tasks: (a) document `INJECT_BITBUCKET_METADATA` breaking change; (b) document `ACTION=diff/rollback`; (c) document `SET`/`VALUES` env var renames
- Complexity: **small**

---

## Recommendation for the Planner

The two highest-risk areas requiring extra acceptance-criteria sharpness are:

1. **05-03 Dockerfile change (D2):** The existing runtime stage uses `helm plugin install` which requires `git` + `curl` + network access. The new `helm-diff-fetch` stage eliminates this. The planner must write explicit acceptance criteria: (a) the runtime stage's `apt-get install` list no longer includes `git` and `curl`; (b) the `apt-get purge` step is removed; (c) `helm diff version` in a container built from the new Dockerfile still exits 0; (d) `COPY --from=helm-diff-fetch` uses the corrected path `/home/pipe/.local/share/helm/plugins/diff` (not the path in D2 CONTEXT text). If the planner copies the D2 CONTEXT path verbatim, the build will produce a container where `helm diff` silently fails.

2. **05-05 D5 rollback pre-flight (CONTRADICTION 2):** The plan MUST include a task to add `--description "pipe:safe-upgrade"` to upgrade argv (in `_build_argv`) when `safe_upgrade=True`. Without this, the pre-flight check has no reliable signal to detect safe-upgraded revisions. The acceptance criterion is: "given a release with 2 revisions where rev 1 was `safe_upgrade=False` and rev 2 was `safe_upgrade=True`, `ACTION=rollback REVISION=1` raises `ChartResolutionError` and `ACTION=rollback REVISION=2` succeeds".

3. **100 % coverage across all 7 plans:** Each plan that touches `cli.py` must account for the `# pragma: no cover` line currently on the `else` branch of `if settings.action == "upgrade"`. Once Phase 5 adds `"diff"` and `"rollback"` branches, the else branch remains but the pragma must be re-evaluated — if there are now exactly 3 handled actions and pydantic enforces the Literal, the else is unreachable and the pragma is justified. The plan-checker should grep for `pragma: no cover` on the else branch and confirm it is still sound.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Helm 3.x does NOT record `--wait` flag in `description` field of `helm history -o json` | D5 contradiction | If wrong and helm DOES record it, the `--description "pipe:safe-upgrade"` workaround is unnecessary but harmless |
| A2 | `helm plugin install` creates the plugin dir named `diff` (matching `plugin.yaml name`) | D2 | If wrong (dir named `helm-diff`), the COPY destination must be `plugins/helm-diff` not `plugins/diff` — but tgz extraction is deterministic and shows `diff/` |
| A3 | `requests` lib from `bitbucket-pipes-toolkit` transitive dep is available at runtime | D3 note | Available (verified in dev env), but not a declared direct dep — stdlib `urllib.request` avoids this ambiguity |
| A4 | `--description` flag is accepted by `helm upgrade --install` | D5 resolution | helm 3.x does support `--description` — [ASSUMED from training knowledge; no running helm to verify] |

---

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `helm/client.py`, `settings.py`, `actions/upgrade.py`, `cli.py`, `Dockerfile`, `pyproject.toml`, `tests/unit/test_helm_client_run.py` — all read directly this session
- `gh release list/view/download` against `databus23/helm-diff` — version list, checksums, tgz structure all verified by direct download
- `uv run python` interactive verification of `yaml.safe_load_all`, `yaml.safe_dump_all(sort_keys=False)`, redaction pattern, `bitbucket_pipes_toolkit` API surface

### Secondary (MEDIUM confidence)
- `bitbucket-pipes-toolkit` 6.2.0 API — inspected via `inspect.getsource` in project venv; confirmed no PR-comment wrapper exists

### Tertiary (LOW confidence — marked ASSUMED)
- helm `--description` flag support — training knowledge; not verified against running helm binary (not available in this env)
- helm `description` field encoding of `--wait` status — training knowledge; consistent with test fixtures in codebase

---

## Metadata

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (30 days; helm-diff and toolkit are stable)

**Confidence breakdown:**
- Standard stack: HIGH — all deps already in pyproject.toml; no new packages needed
- Architecture: HIGH — D1–D6 fully verified against codebase; all wiring points confirmed
- Pitfalls: HIGH — two contradictions in CONTEXT.md surfaced with evidence
- D5 `--wait` detection: LOW → resolved to HIGH via `--description` workaround
