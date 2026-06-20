# Phase 5 CONTEXT — Log Masking, Diff, Rollback & Metadata Flip

**Source:** interactive `discuss-phase` run on 2026-06-20. Inputs: ROADMAP Phase 5 entry, REQUIREMENTS.md (SEC-06, PIPE-02..05, META-02..03, MIG-02), Phase 2/3/4 CONTEXT.md, GitHub Issue #16 (closed by this phase), prior decisions from Phase 4 (D3 tempdir-isolation, D5 subprocess-scoping, D8 cosign-pin pattern).

**Downstream:** `gsd-phase-researcher` reads this to know WHAT to investigate; `gsd-planner` reads this to know WHAT decisions are locked, what is deferred, and what the planner-checker must enforce.

---

## Phase boundary (from ROADMAP)

**Goal:** Helm output emitted by the pipe never leaks `Secret` payloads; consumers can preview changes via `ACTION=diff` (or `DRY_RUN=true`) and optionally post the diff as a Bitbucket PR comment; `ACTION=rollback` is safe by default; `INJECT_BITBUCKET_METADATA` defaults to `false` (breaking change) with a loud deprecation warning when v1-style chart usage is detected. Closes #16 and addresses Pitfalls #2 and #3.

**REQs in scope (8):** SEC-06, PIPE-02, PIPE-03, PIPE-04, PIPE-05, META-02, META-03, MIG-02.

**Out of scope (later phases):**
- Cosign verify of the **pipe image itself** + multi-arch + SBOM + SLSA → Phase 6
- Migration guide POLISH + mkdocs site → Phase 7 (this phase only *drafts* the v1→v2 migration section)
- IAM trust-policy doc polish → Phase 7

---

## Canonical refs (MANDATORY for downstream agents)

Every doc uses a full repo-relative path. Researcher and planner MUST read these.

| Ref | Path | Why |
|---|---|---|
| Roadmap (Phase 5 entry) | `.planning/ROADMAP.md` | Goal, 4 SCs, 3 risks |
| Requirements catalog | `.planning/REQUIREMENTS.md` | SEC-06, PIPE-02..05, META-02..03, MIG-02 normative wording |
| Project | `.planning/PROJECT.md` | Core value, decisions table, deferred items |
| Phase 2 CONTEXT | `.planning/phases/02-aws-layer-auth-foundation/02-CONTEXT.md` | structlog conventions, `bind_safe_context`, redact-on-`__repr__` |
| Phase 3 CONTEXT | `.planning/phases/03-helm-core-upgrade-action/03-CONTEXT.md` | `HelmClient` shape, kubeconfig context-manager, error layering (`HelmExecutionError=5`) |
| Phase 4 CONTEXT | `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md` | **D3 tempdir-isolation pattern, D5 subprocess-scoping, D8 cosign-pin pattern — all carry forward verbatim** |
| Phase 4 VERIFICATION | `.planning/phases/04-oidc-chart-source-extensions/04-VERIFICATION.md` | Reference for what "PASS" looks like — Phase 5 verifier follows same shape |
| Existing `helm/client.py` | `src/aws_eks_helm_deploy/helm/client.py` | The only module that may `import subprocess` for helm. New typed methods (`diff`, `rollback`, `history`) land here. |
| Existing `chart/oci.py` | `src/aws_eks_helm_deploy/chart/oci.py` | Only other module with subprocess (cosign) — D5 scope unchanged |
| Existing `errors.py` | `src/aws_eks_helm_deploy/errors.py` | `HelmExecutionError=5`, `ChartResolutionError=4`. New `PrCommentError` or reuse — researcher decides. |
| Existing `actions/upgrade.py` | `src/aws_eks_helm_deploy/actions/upgrade.py` | Integration site for `SAFE_UPGRADE` flag wiring + redactor output capture |
| Settings | `src/aws_eks_helm_deploy/settings.py` | New env-var fields land here (see "Settings additions" below) |
| Dockerfile | `Dockerfile` | Multi-stage; new `helm-diff-fetch` stage mirrors `cosign-fetch` (Phase 4 D8) |
| Pitfalls log | `.planning/PITFALLS.md` (if exists) or inline references in ROADMAP | TS-9 (secret leak), Pitfall #2 (bitbucket-values stealth-coupling), Pitfall #3 (no-wait + rollback) |
| Issue #16 (metadata flip) | `https://github.com/yves-vogl/aws-eks-helm-deploy/issues/16` | Closed by this phase. Use `gh issue view 16` to read. |
| helm-diff plugin upstream | `https://github.com/databus23/helm-diff/releases/tag/v3.10.0` | Tarball + SHA256 source for D2 Dockerfile pin (researcher resolves exact patch version) |
| Bitbucket REST API — PR comments | `https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/#api-repositories-workspace-repo-slug-pullrequests-pull-request-id-comments-get` | API contract for D3 idempotent posting |
| bitbucket-pipes-toolkit | `https://bitbucketpipes.atlassian.net/wiki/spaces/BPT/overview` (or PyPI) | Project convention for Bitbucket HTTP — no NIH (CLAUDE.md global rule) |

**No external ADRs exist outside `.planning/` for Phase 5.** The five locked decisions below ARE the canonical record.

---

## Locked decisions

### D1 — Redaction strategy: YAML-parse-then-redact (SEC-06)

**Decision:** A new module `src/aws_eks_helm_deploy/helm/redact.py` exposes `redact_helm_output(text: str) -> str`. Implementation:

1. Try `yaml.safe_load_all(text)` — multi-doc safe.
2. For each loaded doc where `doc.get("kind") == "Secret"`: replace `data` and `stringData` blocks with the literal sentinel string `"<redacted>"` (not a dict). Other fields untouched.
3. Re-dump via `yaml.safe_dump_all(docs, sort_keys=False)`.
4. **Stream-type-aware passthrough:** if `yaml.safe_load_all()` raises `YAMLError` (e.g., helm wrote a non-YAML error message to stderr), return the input unchanged. The redactor is a content filter, not a parser of last resort.

**Wiring:**
- `HelmClient` captures every stdout AND stderr stream from `subprocess.run()` and routes through `redact_helm_output` before returning to caller. New API: `HelmClient` constructors accept an optional `redactor: Callable[[str], str] = redact_helm_output` for testability.
- structlog: existing `bind_safe_context` (per Phase 2 CONTEXT) already redacts structured kwargs at the logger boundary. The new `redact_helm_output` handles the **raw text payload** that flows separately into PR comments and stdout. Both layers stay independent — defense in depth.
- PR-comment poster (D3) MUST pipe the diff text through `redact_helm_output` before issuing the API call.

**Scope:** only `kind: Secret` rendered manifests. `--set key=secret_value` echoes by helm itself fall under structlog's `bind_safe_context` (already in place). The redactor does NOT try to detect arbitrary inline secrets — out of scope, would be a security theater.

**Tests:** unit fuzz test with randomized chart fixtures emitting Secret manifests (per ROADMAP R1). Acceptance: NO secret bytes appear in any captured output stream from any `HelmClient` method.

**Locks:** SEC-06.

---

### D2 — helm-diff 3.10 plugin: build-time bundle (PIPE-02)

**Decision:** A new multi-stage Dockerfile stage `helm-diff-fetch` mirrors the Phase 4 `cosign-fetch` pattern (D8) verbatim:

1. `ARG HELM_DIFF_VERSION=3.10.0` (RESOLVED by 05-RESEARCH.md — only 3.10.x release; SHA256 linux-amd64 = `a7875d4656b327b0b7f792f25a70f714801e402eb199ddd0f2df06a063e6bede`).
2. Download `helm-diff-linux-amd64.tgz` from `https://github.com/databus23/helm-diff/releases/download/v${HELM_DIFF_VERSION}/helm-diff-linux-amd64.tgz`.
3. Verify SHA256 via upstream checksum file `helm-diff_${HELM_DIFF_VERSION}_checksums.txt` (upstream provides this; preferred over committed checksum).
4. Extract — `tar -xzf` produces a top-level `diff/` directory containing `plugin.yaml`, `bin/diff`, `LICENSE`, `README.md`.
5. Runtime stage: `COPY --from=helm-diff-fetch /tmp/diff /home/pipe/.local/share/helm/plugins/diff`. helm picks it up automatically via plugin discovery.

**⚠ RESEARCH CORRECTION (2026-06-20):** Earlier CONTEXT wording said `COPY --from=helm-diff-fetch /diff /root/.local/share/helm/plugins/helm-diff/`. Both segments were wrong:
- Path: runtime user is `pipe` (per Dockerfile `USER pipe` + `HELM_PLUGINS=/home/pipe/.local/share/helm/plugins`), NOT `root`.
- Plugin directory name: per upstream `plugin.yaml` `name: "diff"`, the plugin folder MUST be named `diff`, NOT `helm-diff`. helm uses the directory name as the subcommand alias.

**Secondary benefit:** the runtime stage previously needed `git` + `curl` in `apt-get install` to support `helm plugin install`. With the fetch stage, those packages are no longer required at runtime — researcher recommends removing them from the runtime apt-get install + the purge step.

**Why not runtime-install:** offline pipelines (air-gapped, internal artifact registries) break; cold-start budget grows; pin is non-reproducible.

**Cold-start budget:** must stay under 10s (Phase 4 budget). Researcher benchmarks in CI; if helm-diff bundle blows the budget, fallback option is split-stage download cached at base-image rebuild time — but expectation is bundle stays under 5 MB compressed.

**Locks:** PIPE-02.

---

### D3 — PR-comment posting: single-comment-per-PR + 4xx-tolerant (PIPE-03)

**Decision:** A new module `src/aws_eks_helm_deploy/bitbucket/pr_comment.py`. Posting is **idempotent per PR**:

1. Pre-flight: `GET /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments` (pagination respected — researcher decides if 100 comments/page is enough for v2.0).
2. Search response for the marker `<!-- aws-eks-helm-deploy:diff -->` inside any comment body.
3. If found: `PUT /2.0/.../comments/{comment_id}` to replace. If not found: `POST /2.0/.../comments`.
4. Comment body format: marker on line 1; H2 header with release name + revision; fenced code block with the **redacted** diff (passed through `redact_helm_output` — D1 wiring).

**4xx/5xx handling (R2 mitigation):**
- All Bitbucket API error paths route through `bitbucket/pr_comment.py::_sanitize_response_body(body: str) -> str` which strips any occurrence of `BITBUCKET_TOKEN` value and any header line matching `^[Aa]uthorization:`.
- API errors emit `logger.warning("bitbucket.pr_comment.api_error", status=resp.status_code, body=_sanitize_response_body(resp.text))` and **return** — the upgrade/diff action succeeds. PR-comment posting is observability, not critical path.
- Integration test asserts an injected 401 response surfaces no token bytes in the captured log (per ROADMAP R2).

**HTTP client:** stdlib `urllib.request`. **⚠ RESEARCH CORRECTION (2026-06-20):** `bitbucket-pipes-toolkit` 6.2.0 does NOT expose a PR-comments wrapper. Its `HttpRequestsHandler.make_session_request` calls `fail()` on HTTP errors — that hard-fails the pipe on 4xx/5xx, directly violating D3's "4xx-tolerant, warning-only" contract. `urllib.request` is the correct choice here: zero-weight stdlib (no NIH violation per global CLAUDE.md — stdlib counts as standard), full control over error handling, easy to scrub tokens. Pattern in 05-RESEARCH.md "bitbucket-pipes-toolkit API surface" section.

**`BITBUCKET_PR_ID` source:** read from `os.environ` directly (NOT a `Settings` field). Mirrors the existing `BITBUCKET_BUILD_NUMBER` / `BITBUCKET_META_VARS` pattern in `actions/upgrade.py`. Locked unilaterally to close the open question from 05-RESEARCH.md.

**Idempotency edge:** if two concurrent pipe runs race for the same PR, last write wins. Acceptable — PR-comment is best-effort UX, not a transaction.

**Locks:** PIPE-03.

---

### D4 — META-02/03 detection: static grep of resolved chart's values.yaml

**Decision:** After chart resolution (any `ChartSource.resolve()` exits) and BEFORE `helm upgrade --install`:

1. Read `${chart_dir}/values.yaml` once.
2. Apply regex `r"^\s*bitbucket\s*:"` (line-anchored, top-level-or-indented). Also match `r"\.Values\.bitbucket\."` inside any `.yaml` / `.yml` template file under `${chart_dir}/templates/` — researcher decides whether template scan is worth it (Phase 5 starts with `values.yaml` only; template scan is a follow-up if false negatives surface in dogfooding).
3. If a match exists AND `Settings.inject_bitbucket_metadata` is `None` (unset, not `False`): emit `logger.warning("meta.bitbucket_values_detected_without_opt_in", chart=...)` ONCE per run.
4. If `Settings.inject_bitbucket_metadata is True`: inject the `bitbucket.*` values (parity with v1.x behaviour gated behind explicit opt-in).
5. If `Settings.inject_bitbucket_metadata is False`: do nothing, no warning.

**Why static grep, not helm-template-then-search:** double helm-call (template + upgrade) doubles cold-start; static grep covers the 95% case (charts that declare `bitbucket:` in values.yaml). False negatives (charts that conjure `.Values.bitbucket.*` from go-template defaults) are acceptable at v2.0 launch — the migration guide tells consumers to opt in explicitly anyway.

**META-02 default flip:** `Settings.inject_bitbucket_metadata: bool | None = None` (env var `INJECT_BITBUCKET_METADATA`). When `None` or `False`, the v1-era `bitbucket.*` keys are NOT injected. Breaking change, called out in release notes + migration guide.

**MIG-02 v1 env-var detector:** at startup, scan `os.environ` for the v1-era names `SET`, `VALUES`. If either is set, emit `logger.warning("mig.v1_env_var_detected", name="SET")` once per startup. Detection is unconditional — not gated by any setting.

**Locks:** META-02, META-03, MIG-02.

---

### D5 — Rollback safety + SAFE_UPGRADE wiring (PIPE-04, PIPE-05) — pre-locked, no discussion

**Decision:** Mechanical. Locked without interactive discussion because the design follows the same patterns as Phase 3/4. **⚠ RESEARCH-CORRECTED 2026-06-20** — see correction below D5 step 3.

1. `Settings.safe_upgrade: bool = False` (env `SAFE_UPGRADE`).
2. When `Settings.safe_upgrade is True`: `actions/upgrade.py` adds `--wait`, `--atomic`, AND `--description "pipe:safe-upgrade"` to the helm-upgrade argv. The `--description` flag is the safety marker (helm persists it in release history, retrievable on rollback).
3. `ACTION=rollback` + `REVISION=<n>`:
   - Pre-flight: `HelmClient.history(release, max=20) -> list[HelmRevision]` is **already implemented from Phase 4** (`helm/client.py:316–371`) — Phase 5 reuses it, does NOT add a new history method.
   - For the target revision, read `description` and check substring `"pipe:safe-upgrade"`.
   - If absent: raise `ChartResolutionError("Refusing rollback to revision <n> — not deployed with SAFE_UPGRADE=true. Re-deploy with SAFE_UPGRADE=true first.")` BEFORE invoking `helm rollback`.
   - Otherwise: new typed method `HelmClient.rollback(release, revision, namespace)` invokes `helm rollback <release> <revision>`.
4. `ACTION=rollback` is permitted regardless of `SAFE_UPGRADE` on the current run — the safety check is on the **target revision's history**, not on the current run's setting. ROADMAP SC3 wording confirms this.

**⚠ RESEARCH CORRECTION (2026-06-20):** Earlier D5 text said "detected via `description` column (helm includes flags like `Install/Upgrade complete`)". Research verified that helm 3.x does NOT record `--wait` status in the history `description` field. The description is just `"Install complete"` / `"Upgrade complete"` regardless of `--wait`. Workaround: the pipe explicitly sets `--description "pipe:safe-upgrade"` on upgrade when `safe_upgrade=True`, and detects by substring `"pipe:safe-upgrade"` in `HelmRevision.description` on rollback pre-flight.

**Side effect of the workaround:** users cannot combine `SAFE_UPGRADE=true` with a custom `--description`. The pipe owns the description field when `safe_upgrade=True`. This is documented in the v1→v2 migration guide; combining with a custom description is deferred to v2.1+ (would require append-semantics, complicating substring detection).

**Why this is safe to lock without further discussion:** the contract is dictated by ROADMAP SC3 + Pitfall #3; the only research-driven change is the marker mechanism (description vs nonexistent --wait field). No new design choice for the user.

**Locks:** PIPE-04, PIPE-05.

---

### D6 — Module boundary discipline (carry-forward from Phase 4 D5)

**Decision:** Phase 4's D5 scope holds verbatim. `import subprocess` remains restricted to exactly two files: `helm/client.py` and `chart/oci.py`.

- New helm subcommands (`helm diff upgrade`, `helm rollback`, `helm history`, `helm plugin list`) → new typed methods on `HelmClient`. No subprocess imports anywhere else.
- `helm/redact.py`: pure Python (`yaml`, `re`). No subprocess.
- `bitbucket/pr_comment.py`: HTTP via `bitbucket-pipes-toolkit` or stdlib `urllib.request`. No subprocess (no `curl` shell-out).
- CI gate (Phase 4 mechanical gate) extended: `grep '^import subprocess' src/aws_eks_helm_deploy/` MUST still return exactly 2 files at end of Phase 5.

**Locks:** the architectural invariant from Phase 4 — not a Phase 5 REQ directly, but plan-checker enforces it.

---

## Settings additions (Phase 5)

| Env var | Settings field | Type | Default | REQ |
|---|---|---|---|---|
| `POST_DIFF_AS_COMMENT` | `post_diff_as_comment` | `bool` | `False` | PIPE-03 |
| `BITBUCKET_TOKEN` | `bitbucket_token` | `SecretStr | None` | `None` | PIPE-03 |
| `SAFE_UPGRADE` | `safe_upgrade` | `bool` | `False` | PIPE-05 |
| `INJECT_BITBUCKET_METADATA` | `inject_bitbucket_metadata` | `bool | None` | `None` | META-02/03 |
| `REVISION` | `revision` | `int | None` | `None` | PIPE-04 |

(`ACTION=diff` and `ACTION=rollback` use the existing `Settings.action` field — researcher confirms it accepts the new enum values.)

---

## Deferred ideas

- **Template-scan for `bitbucket.*` references** (richer META-03 detection): deferred to v2.1 if dogfooding surfaces false negatives. Static grep wins on simplicity.
- **PrCommentError dedicated exception class:** D3 says reuse warning-only path; if a future requirement asks for fail-on-comment-error semantics, introduce the class then.
- **Append-comment mode** (audit-trail per run): deferred. Single-comment-per-PR is simpler UX for diff iteration on a PR.
- **Bitbucket Data Center / Server (self-hosted) support:** Phase 5 targets Bitbucket Cloud only (the workspace REST API). Self-hosted users get the diff in stdout, not as PR comment. Deferred to v2.1+.
- **helm-diff `--output json` for structured PR comments:** Phase 5 ships plain text in fenced block. JSON-output → richer GitHub-style file collapsibles is a Phase 7 docs-site refinement.

---

## Scope creep redirects

None encountered during this discussion. User selected the four scoped gray areas; no out-of-phase suggestions surfaced.

---

## Out of scope

- **Cosign verify of the pipe image itself** → Phase 6 (release pipeline + supply chain).
- **Multi-arch image (arm64 + amd64)** → Phase 6.
- **SBOM generation + Syft/SPDX** → Phase 6.
- **Migration guide POLISH + mkdocs site** → Phase 7 (this phase only drafts the v1→v2 migration section under `docs/guides/v1-to-v2.md`).
- **IAM trust-policy doc polish** → Phase 7 (drafted in Phase 4).
- **`aws-vault` integration, AWS Pod Identity for self-hosted runners** → v2.1+ deferred (REQUIREMENTS.md `AUTH-NEXT-*`).

---

## Notes for the researcher (resolved by 05-RESEARCH.md)

All 5 notes resolved. Summary (full evidence in 05-RESEARCH.md):

1. **`helm history --output json` schema** → CONFIRMED. `HelmRevision` dataclass already exists from Phase 4 (`helm/client.py:129–143`). `description` field is `"Install complete"` / `"Upgrade complete"`, does NOT encode `--wait`. → drives D5 correction above.
2. **helm-diff 3.10** → CONFIRMED. Pin `3.10.0`, SHA256 `a7875d4656b327b0b7f792f25a70f714801e402eb199ddd0f2df06a063e6bede`, upstream checksum file exists. → drives D2 correction above.
3. **bitbucket-pipes-toolkit** → CONFIRMED no PR-comment wrapper; `HttpRequestsHandler.make_session_request` hard-fails on errors. → drives D3 correction above (stdlib `urllib.request`).
4. **PyYAML `safe_dump_all(sort_keys=False)`** → CONFIRMED preserves doc count + doc order + key order (Python 3.7+ dicts insertion-ordered). No custom dumper.
5. **Secret-emitting fixture chart** → DOES NOT EXIST. Must be created in Wave 0: `tests/fixtures/charts/secret-emitting/` (Chart.yaml + templates/secret.yaml). Researcher provides minimal template.

---

## Notes for the planner

- **5 plan-size guidance:** 4 conceptually independent features but tightly sequenced — SEC-06 redactor is precondition for PIPE-03. Suggested plan breakdown:
  - 05-01 Settings field additions (5 new fields) — atomic precursor
  - 05-02 SEC-06 redactor (`helm/redact.py` + HelmClient wiring + fuzz test) — UNBLOCKS 03
  - 05-03 PIPE-02 + Dockerfile helm-diff-fetch stage + ActionDiff
  - 05-04 PIPE-03 PR-comment poster (depends 02 + 03)
  - 05-05 PIPE-04 + PIPE-05 rollback + SAFE_UPGRADE wiring + HelmClient.history typed method
  - 05-06 META-02 + META-03 + MIG-02 detection + warnings
  - 05-07 (optional) Migration guide draft `docs/guides/v1-to-v2.md`
- **Wave structure:** 05-01 must precede 05-02..06. 05-04 must follow 05-02 (needs redactor). 05-03/05/06 can wave-parallelize with 05-02 if Settings is split correctly. 05-07 is doc-only, can land last.
- **Plan-checker invariants to enforce:**
  - `grep '^import subprocess'` still returns exactly 2 files at end of phase.
  - `redact_helm_output` is called by every `HelmClient` method that captures stdout/stderr (grep audit).
  - No `BITBUCKET_TOKEN` literal appears anywhere in the source tree (gitleaks + manual grep).
  - Settings defaults match the table above verbatim.

---

## Discussion summary (for human audit)

Four gray areas presented; user selected all four recommended options:

1. **Redaction (D1):** YAML-parse-then-redact (multi-doc safe_load_all) + stream-type-aware passthrough.
2. **helm-diff plugin (D2):** Build-time bundle in Dockerfile, multi-stage mirroring Phase 4 cosign-fetch pattern.
3. **PR-comment posting (D3):** Single-comment-per-PR via marker, 4xx-tolerant with token-scrubbed WARN.
4. **META detection (D4):** Static grep of resolved chart's `values.yaml`, one-time WARN when match without opt-in.

Plus D5 (rollback safety) pre-locked mechanically and D6 (module discipline) carried forward from Phase 4 D5.
