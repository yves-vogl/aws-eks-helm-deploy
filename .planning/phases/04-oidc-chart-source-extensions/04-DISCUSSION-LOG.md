# Phase 4: OIDC & Chart Source Extensions — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `04-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 04 — oidc-chart-source-extensions
**Areas discussed:** Auth-precedence semantics, OIDC strategy shape, ChartSource Protocol refactor, IAM trust-policy template, Cosign verify model, tempdir lifecycle, workflow + PR strategy
**Mode:** auto-mode (no interactive AskUserQuestion) — locked decisions pre-supplied by Yves in chat 2026-06-18

---

## Auth precedence semantics

| Option | Description | Selected |
|--------|-------------|----------|
| OIDC wins deterministically (ROADMAP SC1 as written) | When both static keys and OIDC token present, OIDC wins. Pipe-specific override of botocore defaults. | |
| Mirror boto3 default credential resolver chain 1:1 | Static keys (env) beat web-identity, matching AWS CLI behavior. Principle of least surprise for AWS-native engineers. | ✓ |

**User's choice:** Mirror botocore default chain. Recorded as deliberate ROADMAP revision; planner must edit ROADMAP.md + REQUIREMENTS.md AUTH-04 in the first wave, atomic with auth code.
**Notes:** Compromise UX mitigation: on startup, when static keys win AND `BITBUCKET_STEP_OIDC_TOKEN` is also present, emit a one-time WARN log so the consumer knows their OIDC token is being ignored. Resolver chain order ships verbatim in v2 docs (Phase 7).

---

## OIDC strategy shape

| Option | Description | Selected |
|--------|-------------|----------|
| `OidcWebIdentityStrategy` as new module under `auth/oidc.py`, satisfies existing AuthStrategy Protocol via structural typing | Mirror Phase 2's `StaticKeysStrategy` / `AssumeRoleStrategy` shape | ✓ |
| Wrap boto3's built-in `AssumeRoleWithWebIdentityCredentialFetcher` | Reuse upstream provider class verbatim | |

**User's choice:** New module satisfying the existing Protocol — consistent with Phase 2 patterns, easier to unit-test with moto + pytest-mock without monkey-patching botocore internals.
**Notes:** `OIDC_AUDIENCE` is NOT passed to `AssumeRoleWithWebIdentity` (audience lives inside the JWT `aud` claim — STS validates against the OIDC provider's JWKS). The pipe consumes `OIDC_AUDIENCE` only for (a) traceability log line, (b) IAM trust-policy template rendering. Missing `OIDC_AUDIENCE` with an OIDC token present is a `ConfigurationError`.

---

## ChartSource refactor

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `ResolvedChart` as a concrete dataclass, add `repo_url` + `oci_ref` as new optional fields | Minimal refactor; route-by-prefix logic stays in `actions/upgrade.py` | |
| Promote ResolvedChart's resolver into a `ChartSource` Protocol; concrete `LocalChart` / `RepoChart` / `OciChart` implementations | Symmetric to AuthStrategy Protocol shape; each source owns its tempdir lifecycle | ✓ |

**User's choice:** Protocol refactor. `ResolvedChart` becomes a value-object (the yielded type); resolvers become Protocol implementations.
**Notes:** Existing `resolve_local_chart(chart_spec)` function is removed before PR closes — no dual public APIs for the same job. Plan-Checker enforces.

---

## Tempdir + registry-credential lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| `@contextmanager` + `tempfile.TemporaryDirectory(prefix=...)` mirroring `kube/kubeconfig.py` exactly | Canonical pattern in this codebase; reviewers (human + tool) match on visual shape | ✓ |
| Manual `try/finally` with `tempfile.mkdtemp` + `shutil.rmtree` in callers | Slightly more flexible but invites cleanup-on-exception bugs | |

**User's choice:** Mirror `kube/kubeconfig.py`. Each ChartSource implementation owns its tempdir end-to-end.
**Notes:** OCI registry credential isolation: `HELM_REGISTRY_CONFIG` points at a tempfile inside the chart tempdir. No leak into `~/.docker/config.json` or `~/.config/helm/registry/config.json`. ROADMAP Phase 4 Risks call this out explicitly.

---

## Cosign verification model

| Option | Description | Selected |
|--------|-------------|----------|
| Sigstore keyless with Rekor transparency-log anchor, NO PUBKEY config | `CHART_VERIFY=true` invokes `cosign verify <oci-ref>` after pull, before action layer | ✓ |
| Public-key-based verify (consumer provides `COSIGN_PUBKEY`) | Simpler trust model but rejects modern keyless signing flows | |
| Hybrid (keyless OR pubkey, env-var-driven) | Two code paths, more surface area | |

**User's choice:** Keyless only. `CHART_VERIFY=true` requires `CHART=oci://…`; on `repo://` or local it is a `ConfigurationError`. Cosign binary installed in Dockerfile mirroring the existing `helm-fetch` builder stage. Failed verify → `ChartResolutionError` (exit 4).
**Notes:** OPEN architectural detail — identity constraints (`--certificate-identity-regexp`, `--certificate-oidc-issuer`) need researcher resolution. Without identity constraints, cosign verify only proves signature validity, not signer identity. Documented as open question #3 in CONTEXT.md for the researcher to answer.

---

## IAM trust-policy template

| Option | Description | Selected |
|--------|-------------|----------|
| Ship JSON template with placeholders + Terraform companion at `docs/guides/oidc-setup.md` (drafted in Phase 4, polished Phase 7) | Direct copy-paste for consumers; uniform shape across customers | ✓ |
| Defer to Phase 7 entirely | Closes #3 incompletely (AUTH-05 requires trust template now) | |

**User's choice:** Draft now, polish in Phase 7. Unit test asserts JSON validity + presence of `<OIDC_AUDIENCE>`, `<BITBUCKET_WORKSPACE_UUID>`, `<BITBUCKET_REPO_UUID>` placeholders.
**Notes:** Bitbucket OIDC provider URL has changed historically (twice) — researcher must cite the current canonical form against live Bitbucket Pipelines OIDC docs.

---

## Workflow + PR strategy

| Option | Description | Selected |
|--------|-------------|----------|
| discuss → plan (Opus) → plan-check → execute (Sonnet, wave-by-wave) → verifier → single PR | Same pattern as Phase 2 + Phase 3, proven | ✓ |
| Two PRs (auth-only first, then chart sources) | Smaller blast radius per PR, but breaks the closes-#3-and-#7 atomicity | |

**User's choice:** Single PR, mirroring Phase 2 + Phase 3. Branch `phase/04-oidc-chart-sources` already created.
**Notes:** PR title pattern: `phase(04): OIDC & Chart Source Extensions — OidcWebIdentityStrategy + ChartSource Protocol + Cosign verify (closes #3, #7)`. CHANGELOG via `.changes/next-release/` semversioner JSON.

---

## Claude's Discretion

- Plan granularity (5–7 atomic plans suggested in CONTEXT.md D7) — `gsd-planner` decides final count; `gsd-plan-checker` ratifies.
- Researcher's 6 open questions — left for the researcher to answer with citations, not pre-decided here.
- Exact env-var names for cosign identity constraints (Open Question #3) — researcher recommends; planner ratifies.

## Deferred Ideas

- Air-gapped Cosign verify (no Rekor reachability) → v2.1+.
- `CHART_VERIFY=true` on `repo://` charts → v2.1+ (helm-repo index format doesn't carry Sigstore signature path).
- Cosign identity constraint env vars — researcher resolves whether they ship in Phase 4 or as WARN-only.
- `aws-vault` integration → v2.1+ (already deferred in REQUIREMENTS.md AUTH-NEXT-02).
- AWS Pod Identity for self-hosted runners → v2.1+ (AUTH-NEXT-01).
- mkdocs-material guide polish (`docs/guides/oidc-setup.md`) → Phase 7.

---

*Discussion captured 2026-06-18 in auto-mode (no AskUserQuestion). Source of locked decisions: Yves' chat message pre-supplied at phase start. CONTEXT.md is the canonical downstream-consumed artifact; this log is for human audit.*
