# Phase 4 CONTEXT — OIDC & Chart Source Extensions

**Source:** auto-mode `discuss-phase` run on 2026-06-18 with 4 locked decisions pre-supplied by the user. No interactive gray-area resolution. Inputs: ROADMAP Phase 4 entry, REQUIREMENTS.md (AUTH-03..06, CHART-02..04), Phase 2 + Phase 3 CONTEXT.md, GitHub Issues #3 and #7 (both closed by this phase).

**Downstream:** `gsd-phase-researcher` reads this to know WHAT to investigate; `gsd-planner` reads this to know WHAT decisions are locked, what is deferred, and what the planner-checker must enforce.

## Phase boundary (from ROADMAP)

**Goal:** Consumers can authenticate to AWS via Bitbucket Pipelines OIDC (zero static keys) and pull Helm charts from Helm repositories or OCI registries, with optional Cosign signature verification on OCI charts. v1.x has none of this — v2.0 ships it on the new typed Protocols. Closes issues #3 and #7.

**REQs in scope (7):** AUTH-03, AUTH-04, AUTH-05, AUTH-06, CHART-02, CHART-03, CHART-04.

**Out of scope (later phases):**
- Log masking + diff action + rollback + metadata default flip → Phase 5
- Cosign verify of the **pipe image itself** + multi-arch + SBOM + SLSA → Phase 6
- IAM trust-policy doc polish + mkdocs site + migration guide → Phase 7
- `aws-vault` integration → v2.1+ (REQUIREMENTS.md AUTH-NEXT-02)

---

## Canonical refs (MANDATORY for downstream agents)

Every doc referenced below uses a full repo-relative path. The researcher and planner MUST read these — they encode either the prior-phase contract, a locked decision, or an upstream spec that overrides the ROADMAP claim.

| Ref | Path | Why |
|---|---|---|
| Roadmap (Phase 4 entry) | `.planning/ROADMAP.md` | Goal, success criteria, risks. **See ROADMAP REVISION below — SC1 wording is superseded by D1.** |
| Requirements catalog | `.planning/REQUIREMENTS.md` | AUTH-03..06 + CHART-02..04 normative wording |
| Project | `.planning/PROJECT.md` | Core value, decisions table, deferred items |
| Phase 2 CONTEXT | `.planning/phases/02-aws-layer-auth-foundation/02-CONTEXT.md` | `AuthStrategy` Protocol shape, `AwsCredentials`, mask-on-`__repr__`, `select_strategy` composition root |
| Phase 3 CONTEXT | `.planning/phases/03-helm-core-upgrade-action/03-CONTEXT.md` | `HelmClient` shape, kubeconfig context-manager pattern, subprocess model, error layering |
| Phase 3 PLAN-CHECK | `.planning/phases/03-helm-core-upgrade-action/03-PLAN-CHECK.md` | Plan-Checker stance on module-boundary discipline — applies again here |
| Existing `auth/__init__.py` | `src/aws_eks_helm_deploy/auth/__init__.py` | Already has TODO marker `# Phase 4: insert OIDC check here`; `select_strategy` is the integration site |
| Existing `auth/base.py` | `src/aws_eks_helm_deploy/auth/base.py` | `AuthStrategy` Protocol (structural) — OIDC strategy must satisfy it without inheritance |
| Existing `auth/assume_role.py` | `src/aws_eks_helm_deploy/auth/assume_role.py` | Reference shape for a composed strategy; `OidcWebIdentityStrategy` may compose differently — researcher decides |
| Existing `chart/local.py` | `src/aws_eks_helm_deploy/chart/local.py` | `ResolvedChart` is the current concrete type — to be refactored per D3 |
| Existing `kube/kubeconfig.py` | `src/aws_eks_helm_deploy/kube/kubeconfig.py` | **Canonical tempfile context-manager pattern** — `RepoChart` + `OciChart` MUST mirror this shape (D3) |
| Existing `helm/client.py` | `src/aws_eks_helm_deploy/helm/client.py` | Only module that calls `subprocess.run`; new helm subcommands (`repo add`, `pull`, `registry login`) belong here |
| Existing `errors.py` | `src/aws_eks_helm_deploy/errors.py` | Exception hierarchy + exit-code map. `AuthenticationError=2`, `ChartResolutionError=4`. New OIDC + verify failures reuse these codes. |
| Settings | `src/aws_eks_helm_deploy/settings.py` | Env-var aliasing pattern; new vars added here: `OIDC_AUDIENCE`, `REPO_URL`, `CHART_VERSION`, `REGISTRY_USERNAME`, `REGISTRY_PASSWORD`, `CHART_VERIFY` |
| Dockerfile | `Dockerfile` | Multi-stage; `helm-fetch` already adds helm + helm-diff. `cosign` must be added in the same builder pattern. |
| Issue #3 (OIDC) | `https://github.com/yves-vogl/aws-eks-helm-deploy/issues/3` | Closed by this phase — context for "why OIDC matters". Use `gh issue view 3` to read. |
| Issue #7 (chart sources) | `https://github.com/yves-vogl/aws-eks-helm-deploy/issues/7` | Closed by this phase. Use `gh issue view 7` to read. |

**No external doc artifacts (ADRs, design docs) exist outside `.planning/` for Phase 4.** The four locked decisions below ARE the canonical record.

---

## Locked decisions

### D1 — Auth strategy precedence mirrors botocore default chain (ROADMAP REVISION)

**Decision:** The `AuthStrategy` resolver implemented in `auth/__init__.py::select_strategy()` reflects the **boto3 / AWS CLI default credential resolver chain order, 1:1**. We do not invent our own precedence.

**Concrete order** (per `botocore.credentials.create_credential_resolver` defaults — researcher must verify against the pinned `boto3` version):

1. Environment variables (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` ± `AWS_SESSION_TOKEN`) → **`StaticKeysStrategy`** wins here.
2. (Subsequent botocore providers like shared-credentials / assume-role / SSO are **not in scope** for the pipe — the pipe is a one-shot CLI in a CI container, no shared file present.)
3. `AssumeRoleWithWebIdentity` provider (env var `AWS_WEB_IDENTITY_TOKEN_FILE`, or our typed equivalent `BITBUCKET_STEP_OIDC_TOKEN` + `OIDC_AUDIENCE` + `ROLE_ARN`) → **`OidcWebIdentityStrategy`**.
4. (Instance Metadata is not reachable in Bitbucket Pipelines — out of scope.)

**Consequence (intentional):** When both `AWS_ACCESS_KEY_ID`+`AWS_SECRET_ACCESS_KEY` AND `BITBUCKET_STEP_OIDC_TOKEN` are present, **static keys win**. This contradicts ROADMAP Phase 4 Success Criterion 1 ("when both ... are present, OIDC wins deterministically") and AUTH-04 ("OIDC wins").

**⚠ ROADMAP REVISION (deliberate, recorded 2026-06-18):**
- ROADMAP SC1 + AUTH-04 wording is **superseded** by D1.
- New normative wording for AUTH-04: *"Strategy selection follows the boto3/AWS CLI default credential resolver chain; when both static keys and an OIDC token are present, static keys win — same behavior as the AWS CLI itself."*
- ROADMAP.md is updated by this phase's execution (one-line note + link to this CONTEXT.md). REQUIREMENTS.md AUTH-04 is updated likewise.
- The resolver chain (full ordered list) is also surfaced verbatim in the Phase 7 v2 docs site (`docs/guides/auth-resolver-chain.md` — drafted in Phase 4, polished in Phase 7).

**Why we chose this:** Pipe users debugging "why isn't my OIDC token used?" should be able to consult AWS CLI behavior as the canonical reference instead of memorizing a pipe-specific override. **Principle of least surprise** for any AWS-native engineer.

**Mitigation for the gotcha** (consumers who set both and expect OIDC to win): on startup, if `select_strategy()` returns `StaticKeysStrategy` AND `BITBUCKET_STEP_OIDC_TOKEN` is also present in `os.environ`, emit a **one-time WARN log** (`auth.precedence.static_keys_won_over_oidc`) telling the consumer their OIDC token is being ignored because static keys are set. Defensive UX, zero behavior change.

**Auth misconfig errors (AUTH-06):** before any AWS API call:
- `OIDC_AUDIENCE` set without `ROLE_ARN` → `ConfigurationError` ("OIDC requires ROLE_ARN to assume").
- `BITBUCKET_STEP_OIDC_TOKEN` present without `ROLE_ARN` → `ConfigurationError` (same message).
- `ROLE_ARN` set with neither static keys nor an OIDC token → already raised by Phase 2's `select_strategy` (`"ROLE_ARN requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY"`); Phase 4 updates the message to mention OIDC as an alternative.

**Locks:** AUTH-03, AUTH-04 (revised), AUTH-06.

**Plan-Check obligation:** the planner emits an explicit ROADMAP+REQUIREMENTS edit task as part of Phase 4 plans, NOT as a verifier afterthought. Single commit, atomic with the auth implementation.

---

### D2 — `OidcWebIdentityStrategy` shape

**Decision:** New module `src/aws_eks_helm_deploy/auth/oidc.py`. Exports `OidcWebIdentityStrategy` satisfying the existing `AuthStrategy` Protocol from `auth/base.py` — structural typing, no inheritance.

**Constructor signature** (researcher confirms against the boto3 version pinned in `pyproject.toml`):

```python
class OidcWebIdentityStrategy:
    def __init__(
        self,
        oidc_token: str,             # from BITBUCKET_STEP_OIDC_TOKEN (passed by select_strategy)
        role_arn: str,               # from ROLE_ARN
        audience: str,               # from OIDC_AUDIENCE — NOT used in AssumeRoleWithWebIdentity itself,
                                     # but validated/recorded for traceability + trust-policy alignment
        session_name: str,           # derived via _derive_session_name (existing Phase 2 helper)
        region: str,                 # from AWS_REGION
    ) -> None: ...
    def get_credentials(self) -> AwsCredentials: ...
```

**Implementation pattern:**
- One `boto3.client("sts", region_name=...)` call.
- One `sts.assume_role_with_web_identity(RoleArn=..., RoleSessionName=..., WebIdentityToken=oidc_token, DurationSeconds=...)` call.
- Map the response `Credentials` block to a frozen `AwsCredentials(...)` value object — already defined in `auth/base.py` with the masking `__repr__`.
- On `botocore.exceptions.ClientError` / `BotoCoreError` raise `AuthenticationError(...)` (exit code 2 per existing error map).

**`OIDC_AUDIENCE` semantics:**
- `AssumeRoleWithWebIdentity` itself does not take an `Audience` arg — the audience is encoded **inside** the OIDC JWT (`aud` claim). The pipe does NOT re-validate the JWT (STS does that against the OIDC provider's JWKS).
- `OIDC_AUDIENCE` is consumed by the pipe for two purposes only:
  1. **Traceability / debug log** — emitted at INFO level as part of the auth-start log line.
  2. **Trust-policy template** rendering (D4) — the IAM trust-policy template requires the audience string to be plugged in.
- An OIDC strategy that runs without `OIDC_AUDIENCE` set is a **`ConfigurationError`** (AUTH-06).

**Session name derivation:** the Phase 2 `_derive_session_name(settings)` helper in `auth/__init__.py` already produces an IAM-valid session name from `SESSION_NAME` / `BITBUCKET_PIPELINE_UUID` / `BITBUCKET_BUILD_NUMBER` / `uuid4` fallback. **Reuse as-is.** No new derivation logic.

**Locks:** AUTH-03, AUTH-07 (already satisfied by Phase 2 — OIDC strategy continues to use pure-boto3, no `awscli` re-introduced).

---

### D3 — `ChartSource` Protocol + concrete `LocalChart` / `RepoChart` / `OciChart`

**Decision:** Refactor `src/aws_eks_helm_deploy/chart/` to a typed Protocol with three concrete implementations. The Phase 3 `ResolvedChart` frozen dataclass becomes a concrete `LocalChart` class satisfying the new Protocol.

**Module layout:**

| Module | Responsibility | Phase 3 → Phase 4 delta |
|---|---|---|
| `chart/base.py` | NEW. `ChartSource` Protocol + `ResolvedChart` dataclass (with `name`, `version`, `source_path`). | New file. Protocol exposes one method: `def resolve(self) -> ContextManager[ResolvedChart]`. |
| `chart/local.py` | EXISTING — refactor. The current `resolve_local_chart(chart_spec)` function becomes a `LocalChart(chart_spec, repo_root=None)` class with `.resolve()` context-manager. | The function form remains as a thin shim during the refactor for unit tests; removed before the phase PR closes. |
| `chart/repo.py` | NEW. `RepoChart(name, chart, repo_url, version=None)` — runs `helm repo add` + `helm repo update` + `helm pull <name>/<chart>` to a tempdir, then yields a `ResolvedChart` pointing at the unpacked dir. | New file. |
| `chart/oci.py` | NEW. `OciChart(reference, version=None, registry_username=None, registry_password=None, verify=False)` — runs (optional) `helm registry login`, then `helm pull oci://<reference>` to a tempdir; if `verify=True`, invokes Cosign verify on the pulled artifact BEFORE handing the path back (D5). | New file. |
| `chart/__init__.py` | EXISTING — refactor. Exports `ChartSource`, `ResolvedChart`, `LocalChart`, `RepoChart`, `OciChart`, and a `select_chart_source(settings) -> ChartSource` composition root. | New `select_chart_source` factory; routes by `CHART=` prefix (`oci://` / `repo://` / else → local). |

**`select_chart_source(settings)` decision tree:**

```
if settings.chart.startswith("oci://"):
    return OciChart(
        reference=settings.chart.removeprefix("oci://"),
        version=settings.chart_version,                 # optional
        registry_username=settings.registry_username,   # optional
        registry_password=settings.registry_password,   # optional
        verify=settings.chart_verify,                   # default False
    )
if settings.chart.startswith("repo://"):
    name, _, chart_name = settings.chart.removeprefix("repo://").partition("/")
    if not name or not chart_name:
        raise ConfigurationError("CHART=repo:// must be 'repo://<repo-name>/<chart>'")
    if not settings.repo_url:
        raise ConfigurationError("CHART=repo://… requires REPO_URL")
    return RepoChart(name=name, chart=chart_name, repo_url=settings.repo_url, version=settings.chart_version)
return LocalChart(chart_spec=settings.chart, repo_root=None)
```

**Lifecycle contract (all three implementations):**
- `.resolve()` returns a `ContextManager[ResolvedChart]`. The chart's on-disk presence is valid **only** inside the `with` block.
- Tempdir lifecycle mirrors `kube/kubeconfig.py` (`@contextmanager` + `tempfile.TemporaryDirectory(prefix="aws-eks-helm-deploy-chart-")`) — see "Tempdir context-manager pattern" in D6.
- `LocalChart.resolve()` is a degenerate context-manager that yields the already-on-disk path; nothing is cleaned up.
- `RepoChart` and `OciChart` clean their tempdirs on context exit even if the `with` block raises (`finally` clause).

**`actions/upgrade.py` integration:** the Phase 3 upgrade action becomes:

```python
chart_source = select_chart_source(settings)
with chart_source.resolve() as resolved:                # tempdir scope
    with write_kubeconfig(cluster, token) as kubeconfig_path:
        helm.upgrade_install(release=..., chart=resolved.source_path, ...)
```

The action stays well under the 50-LOC budget set by Phase 3.

**Locks:** CHART-02, CHART-03 (signature), CHART-05 (`resolved.name + .version` already surfaces in the success-message logic — unchanged).

**Plan-Check obligation:** `chart/local.py` legacy `resolve_local_chart` function must be **removed** before the PR closes. The Plan-Checker enforces "no dual public APIs for the same job".

---

### D4 — Bitbucket OIDC IAM trust-policy template

**Decision:** Ship a single documented IAM trust-policy template at `docs/guides/oidc-setup.md` (drafted in Phase 4, polished + linked from the v2 docs site in Phase 7). The template is exposed as a copy-pasteable JSON block with two interpolation points.

**Template shape:**

```jsonc
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc:aud": "<OIDC_AUDIENCE>",
        "api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc:sub": [
          "{<BITBUCKET_WORKSPACE_UUID>}:{<BITBUCKET_REPO_UUID>}:*"
        ]
      }
    }
  }]
}
```

(Exact provider URL and condition keys to be verified by the researcher against current Bitbucket Pipelines OIDC docs — Bitbucket has changed the provider URL format twice historically.)

**Validation:** a unit test parses the template as JSON and asserts:
1. `aud` condition uses the literal placeholder `<OIDC_AUDIENCE>` (must be replaced before applying).
2. `sub` condition references both `<BITBUCKET_WORKSPACE_UUID>` and `<BITBUCKET_REPO_UUID>` placeholders.
3. The action is `sts:AssumeRoleWithWebIdentity`.
4. The provider URL matches a documented Bitbucket OIDC issuer pattern.

**Optional Terraform companion snippet:** a sibling `docs/guides/oidc-setup-terraform.md` (drafted lightly in Phase 4, polished in Phase 7) shows the same trust policy via `aws_iam_role` + `data.tls_certificate` patterns. Defer if Phase 4 is already heavy — gate is "ships in Phase 7 at latest".

**Locks:** AUTH-05.

**Plan-Check obligation:** any deviation from the placeholder names (`<ACCOUNT_ID>`, `<WORKSPACE>`, `<OIDC_AUDIENCE>`, `<BITBUCKET_WORKSPACE_UUID>`, `<BITBUCKET_REPO_UUID>`) is rejected — consumers will grep for these.

---

### D5 — Cosign verification (Sigstore keyless, transparency-log anchor)

**Decision:** `CHART_VERIFY=true` invokes `cosign verify <oci-ref>` after `helm pull` and before handing the chart path to the action layer. **Keyless only** — no `PUBKEY` config var. The Sigstore transparency log (Rekor) is the trust anchor.

**Concrete behavior:**
- `CHART_VERIFY` defaults to `false`. When `true` and `CHART` is NOT `oci://…`, raise `ConfigurationError` ("CHART_VERIFY=true requires CHART=oci://…").
- Cosign binary is installed in the Dockerfile (same multi-stage builder pattern as the existing `helm-fetch` stage). Version pinned via `ARG COSIGN_VERSION=…` + SHA256 checksum verification mirroring the `helm` install.
- The pipe shells out to `cosign verify <oci-ref>` (single typed `subprocess.run` call from `chart/oci.py`). Stderr capture is preserved on failure for the `ChartResolutionError` user message.
- A failed verification raises `ChartResolutionError` (exit code 4 — already in the error map).

**Identity constraints (OPEN — researcher resolves):**
- Cosign keyless verify accepts `--certificate-identity` / `--certificate-identity-regexp` and `--certificate-oidc-issuer` / `--certificate-oidc-issuer-regexp`. Without either, `cosign verify` succeeds for **any** valid Sigstore signature — which is "verified the signature is real" but NOT "verified the signer is who I trust".
- **Researcher must investigate** whether the pipe exposes two new optional env vars (`CHART_VERIFY_CERTIFICATE_IDENTITY_REGEXP`, `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER`) to constrain trust. If yes, when `CHART_VERIFY=true` is set without either constraint var, emit a loud one-time WARN log (`chart.verify.unconstrained_identity`) telling the consumer they are only verifying signature validity, not signer identity. Defensive UX, no behavior change.
- Cosign env vars (`COSIGN_EXPERIMENTAL=1` was required for keyless pre-v2.0 — researcher verifies whether the pinned cosign version needs this; cosign 2.x deprecated it).

**Tlog (transparency log) anchor:** cosign verify checks the entry against Rekor by default; we do not disable it. Air-gapped customers (no Rekor reachability) are explicitly **out of scope** — v2.1+ may add `--insecure-ignore-tlog` if a customer needs it; for now Rekor reachability is a hard requirement of `CHART_VERIFY=true`.

**Locks:** CHART-04.

**Plan-Check obligation:** `subprocess.run` for `cosign verify` lives in `chart/oci.py`, NOT in `helm/client.py`. The "only `helm/client.py` shells out" invariant from Phase 3 D1 is **scoped to helm subcommands**. Cosign is a separate binary; chart-source modules are allowed to shell out to non-helm binaries when the lifecycle (download + verify) is entirely owned by the chart source.

---

### D6 — Tempdir context-manager pattern (mirror `kube/kubeconfig.py`)

**Decision:** Both `RepoChart` and `OciChart` use the **same context-manager-with-cleanup pattern** as `kube/kubeconfig.py`'s `write_kubeconfig` — this is the canonical pattern in this codebase for "filesystem side effect that must be cleaned even on exception".

**Pattern:**

```python
@contextmanager
def resolve(self) -> Iterator[ResolvedChart]:
    tmpdir = tempfile.mkdtemp(prefix="aws-eks-helm-deploy-chart-")
    try:
        # 1. Run `helm pull` / `helm repo add+update+pull` into tmpdir.
        # 2. Discover the unpacked chart dir inside tmpdir (single child dir
        #    after `helm pull --untar`).
        # 3. (OciChart + verify=True only) Run `cosign verify` against the
        #    OCI reference; raise on failure BEFORE yielding.
        # 4. Parse Chart.yaml, build ResolvedChart.
        yield ResolvedChart(name=..., version=..., source_path=...)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

**Why mirror exactly:** the kubeconfig module already encodes the chmod-before-write, finally-cleanup-even-on-raise, and OSError-propagation-not-wrapping patterns. Reviewers (humans and tools) match on visual shape — divergence costs review cycles.

**OCI registry credential isolation:** `helm registry login` writes to a config file. The pipe MUST point this at a tempfile inside the chart tempdir via `HELM_REGISTRY_CONFIG=<tmpdir>/registry-config.json` (ROADMAP Phase 4 Risks mention this explicitly). Cleanup is automatic via the `shutil.rmtree` in the `finally`. No registry creds leak into `~/.docker/config.json` or `~/.config/helm/registry/config.json`.

**Locks:** Implementation contract for D3 and D5.

---

### D7 — Workflow pattern (carries forward from Phase 2 + Phase 3)

**Decision:** Same workflow shape as Phases 2 and 3:

1. `discuss-phase` → this CONTEXT.md (DONE).
2. `plan-phase` (Opus) → atomic per-module PLAN files, VALIDATION.md, Plan-Checker (`gsd-plan-checker`) gate.
3. `execute-phase` (Sonnet, wave-by-wave) — sequential within a wave, parallel where deps allow.
4. `verify-phase` (`gsd-verifier`) → VERIFICATION.md asserting all 7 REQs are exercised by green tests.
5. **One PR** at the end. Title `phase(04): OIDC & Chart Source Extensions — OidcWebIdentityStrategy + ChartSource Protocol + Cosign verify (closes #3, #7)`.

**Plan granularity guidance** (planner decides exact count — likely 5–7 atomic plans):
- 04-01: ROADMAP+REQUIREMENTS revision (D1) + auth misconfig errors (AUTH-06).
- 04-02: `OidcWebIdentityStrategy` (D2) + `select_strategy` integration.
- 04-03: IAM trust-policy template + unit-test JSON validity (D4).
- 04-04: `ChartSource` Protocol + `LocalChart` refactor + `select_chart_source` (D3 module scaffolding).
- 04-05: `RepoChart` implementation + integration test against `helm repo`.
- 04-06: `OciChart` implementation + cosign install in Dockerfile + integration test against `registry:2` (D5, D6).
- 04-07: Settings additions (new env vars) + variable-reference docstring update.

The planner may merge or split — Plan-Checker decides whether the granularity is right.

---

### D8 — PR strategy

**Decision:** **Single PR** at end of Phase 4. Same as Phase 2 / Phase 3. Reasoning: the four locked decisions are tightly coupled (OIDC trust policy + auth precedence revision are one logical change; ChartSource Protocol + RepoChart + OciChart + Cosign are the other; both together close issues #3 + #7 atomically in the changelog).

**Branch:** `phase/04-oidc-chart-sources` (already created on 2026-06-18).

**Closes:** GitHub issues #3 and #7. CHANGELOG entries via `.changes/next-release/` semversioner JSON, mirroring Phase 2 + Phase 3 pattern.

---

## Open questions for researcher

These are the only items the researcher should answer before the planner runs. None of them are blocking — the planner could proceed with defaults — but resolving them lifts plan quality.

1. **botocore default chain order, current version.** Confirm precedence in the pinned `boto3` version (`pyproject.toml`); cite `botocore.credentials.create_credential_resolver`. If the default order changed between boto3 majors, D1 needs a version annotation.
2. **Bitbucket OIDC issuer URL — current canonical form.** Bitbucket has historically had two forms. Cite the live Bitbucket docs page.
3. **Cosign 2.x keyless invocation.** Does the pinned cosign require `COSIGN_EXPERIMENTAL=1`? What is the canonical CLI form (`cosign verify <ref>` vs `cosign verify --certificate-identity-regexp <re> --certificate-oidc-issuer <url> <ref>`)? Recommend env-var names for the two optional identity constraints (D5).
4. **`helm pull oci://`** — does it unpack by default, or is `--untar` required? What is the unpacked directory's name pattern?
5. **`helm registry login` with `HELM_REGISTRY_CONFIG`** — does the env-var override work cleanly, or does helm also read `~/.config/helm/`? Tempfile-isolation contract depends on this.
6. **Cosign binary distribution + SHA256.** Pinning strategy + checksum verification — mirror the existing `helm-fetch` stage in Dockerfile.

---

## Deferred ideas (NOT in scope for Phase 4)

| Idea | Why deferred | Routed to |
|---|---|---|
| Air-gapped Cosign verify (no Rekor reachability) | Vanishing-tail user; complicates Rekor anchor argument | v2.1+ backlog (AUTH-NEXT or new CHART-NEXT) |
| Constraint env vars for cosign keyless identity | Researcher must confirm shape; do NOT block Phase 4 if researcher recommends "ship as WARN-only" | Resolved during D5 research |
| `CHART_VERIFY=true` on `repo://` charts | Helm-repo charts don't carry a Sigstore signature path in the standard helm-repo index format | v2.1+ (separate REQ) |
| Bitbucket OIDC token rotation mid-pipeline | Single one-shot CLI; refresh not needed | Not applicable — out of scope by design |
| AWS Pod Identity for self-hosted runners | Already deferred in REQUIREMENTS.md (AUTH-NEXT-01) | v2.1+ |
| `aws-vault` integration | Already deferred (AUTH-NEXT-02) | v2.1+ |
| Polished mkdocs guides for OIDC + chart sources | Drafted in Phase 4, polished in Phase 7 (`docs/guides/oidc-setup.md`) | Phase 7 |

---

## Summary for downstream agents

**Researcher TODO:** answer the 6 questions in "Open questions for researcher". Produce `04-RESEARCH.md` consumed by the planner.

**Planner TODO:** read this CONTEXT.md + 04-RESEARCH.md + Phase 2 CONTEXT.md + Phase 3 CONTEXT.md. Produce 5–7 atomic PLAN files matching D7 granularity guidance. **First plan MUST be the ROADMAP + REQUIREMENTS revision (D1) — single commit, atomic with the OIDC strategy code change.** Use `gsd-plan-checker` before `/clear`.

**Executor TODO:** wave-by-wave, Sonnet subagents per Plan, **whitelist files per subagent** (see user-global `feedback_orchestrator_role` guidance).

**Verifier TODO:** all 7 REQs (AUTH-03..06, CHART-02..04) must be exercised by green tests; AUTH-04 is verified against the **revised** wording from D1, not the original ROADMAP wording.

---

*Phase 4 CONTEXT.md created 2026-06-18 — locked decisions provided by Yves in chat, no interactive AskUserQuestion run.*
