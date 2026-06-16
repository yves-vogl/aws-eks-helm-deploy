# Pitfalls Research

**Domain:** Bitbucket Pipelines Pipe — Helm-to-EKS deployment with AWS OIDC, OCI charts, Cosign signing, multi-arch images, and GitHub-Actions release pipeline (v1→v2 modernization of an existing public Pipe)
**Researched:** 2026-06-16
**Confidence:** HIGH (drawn from current upstream docs, known issue trackers, and lived patterns; AWS STS now validates IdP claims as of 2026-01)

Pitfalls below are scoped to **this** modernization. Severity is judged against the v2 Core Value promise: "ship a Bitbucket Pipelines deployment to AWS EKS from a clean repository in under five minutes — without committing static AWS credentials and without surprises at upgrade time." Anything that breaks that promise — or breaks an existing v1.x pinned consumer's understanding of how to upgrade — is critical.

## Critical Pitfalls

### Pitfall 1: Bitbucket OIDC `aud` claim mismatch and STS trust policy under-constrained

**What goes wrong:**
The Bitbucket OIDC token (`BITBUCKET_STEP_OIDC_TOKEN`) is exchanged for AWS credentials via `sts:AssumeRoleWithWebIdentity`. If the IAM OIDC provider's `ClientIDList` does not contain the exact Bitbucket audience (`api.bitbucket.org/2.0/workspaces/{WORKSPACE}/pipelines-config/identity/oidc`) or if the IAM role trust policy does not constrain `token.actions.bitbucket.org:sub` to a specific repository / step / branch, the pipe either (a) fails opaquely with `InvalidIdentityToken: Incorrect token audience` (Core Value broken: "under five minutes" turns into a half-day STS-debugging detour), or (b) succeeds and silently allows **any** Bitbucket workspace to assume the role — a privilege-escalation hand-grenade for consumers.

The pitfall is worse for this pipe specifically because we publish it as a **shared component** used by external workspaces — every consumer copy-pastes the trust policy from our docs, so a sloppy default propagates 9+ times.

**Why it happens:**
- AWS STS uses the `azp` (authorized party) claim as the audience when both `aud` and `azp` are present — but Bitbucket only emits `aud`, so people don't notice this gotcha until they switch providers.
- Multiple audiences in one JWT are not supported by AWS STS at all.
- The Atlassian docs show a permissive trust policy (`StringLike: "*"`) as an "intro" example, and people ship that to production.
- v1.x had no OIDC at all, so there is no existing user mental model to fall back on — we are setting the precedent.

**How to avoid:**
- Document **exactly one** trust-policy template that pins all three: `aud` (Bitbucket workspace audience URL), `sub` (`{workspace_uuid}:{repo_uuid}:{step_uuid}` or at minimum repo-scoped), and optionally a branch condition.
- Ship a `examples/oidc-trust-policy.json` with placeholder UUIDs and **no wildcards**.
- In the pipe, validate the token shape before calling STS: assert `aud` is non-empty and is a single string (not a list). Fail with an actionable error: `OIDC token aud is "X" — verify your AWS IAM OIDC provider's ClientIDList contains exactly this string`.
- Surface the AWS error verbatim in the pipe output (do not swallow `InvalidIdentityToken`) but prefix with a remediation hint pointing at the docs URL.
- Test against AWS STS's January 2026 IdP-claim validation feature — confirm our claim shape passes the new path.

**Warning signs:**
- Anyone in a code review proposing `"Condition": { "StringLike": { "...:sub": "*" } }` — instant block.
- Consumer issues with `InvalidIdentityToken` filed in the first week post-release.
- Trust-policy examples in the docs that contain `"*"` anywhere except as an explicit placeholder marker like `<WORKSPACE_UUID>`.

**Phase to address:**
Phase: **AWS OIDC / IRSA implementation**. This is the highest-blast-radius pitfall in v2 because it is both a security primitive and a documentation deliverable, and the docs ship to consumers we do not control.

---

### Pitfall 2: `INJECT_BITBUCKET_METADATA` default flip silently breaks existing pinned consumers who upgrade

**What goes wrong:**
v1.x unconditionally injects Bitbucket metadata as Helm values (`bitbucket.bitbucket_build_number`, etc.). v2 flips this to opt-in (`INJECT_BITBUCKET_METADATA: false` default — see issue #16). Any consumer who:
1. Has a Helm chart with a values schema (`values.schema.json`) that **requires** these fields, OR
2. References `.Values.bitbucket.bitbucket_build_number` in a template,

will experience a **silent template failure or `nil` deref** on first run of v2. The pipe exits non-zero with a Helm error, but the root cause ("v2 stopped injecting metadata you depended on") is invisible — Helm just says "field bitbucket not found in values".

This is the migration-pitfall most likely to generate angry GitHub issues in the first 48 hours.

**Why it happens:**
- v1.x users built mental models around "this just happens" for three years.
- Changelogs and migration guides are skimmed; defaults are not.
- The v1→v2 image lives on a new tag (`:2.0.0`) but consumers who use `:latest` (we cannot stop them) get the change without reading anything.

**How to avoid:**
- The pipe must **detect** the upgrade scenario: if no `INJECT_BITBUCKET_METADATA` is set explicitly AND we can detect that the chart's existing values (from `helm get values <release>`) contain a `bitbucket.*` key, emit a **prominent warning** before deploying: `WARNING: v1.x injected Bitbucket metadata by default; v2 does not. Set INJECT_BITBUCKET_METADATA: true to preserve v1 behavior. This deploy will proceed WITHOUT metadata.`
- Do **not** auto-fallback to v1 behavior — that defeats the breaking change. Just make the silence audible.
- Pin `:latest` to v1.3.0 forever (do not move it to v2). Document this in the README upgrade section. v2 consumers must opt in with `:2`, `:2.0`, or `:2.0.0`.
- Migration guide must list `INJECT_BITBUCKET_METADATA` in the **first** "Breaking Changes" table row with a concrete `bitbucket-pipelines.yml` before/after diff.
- Acceptance test: invoke the pipe with no env vars and assert the warning fires when a prior release contained `bitbucket.*` keys.

**Warning signs:**
- Migration guide draft that lists the change but does not show a diff.
- No release-note assertion in the test suite.
- Any code path that defaults `INJECT_BITBUCKET_METADATA` to `true` "for compatibility" — instant block; defeats the entire feature.

**Phase to address:**
Phase: **Opt-in Bitbucket metadata injection (issue #16)** plus **Migration guide v1→v2**. Cross-cutting; both phases must explicitly reference this pitfall in their done criteria.

---

### Pitfall 3: Helm `--atomic` + `--wait` rollback breaks when previous release did not also use `--wait`

**What goes wrong:**
v1.x exposes `--wait` and `--timeout` as optional. If a consumer runs revision N **without** `--wait`, and revision N+1 **with** `--atomic`, Helm's auto-rollback target (revision N) is itself in a state Helm believes is "deployed" but Kubernetes never actually converged. The rollback then either (a) completes instantly to a still-broken state (worst case — production traffic on a half-deployed release), or (b) fails with `another operation (install/upgrade/rollback) is in progress` and leaves the release locked.

`--history-max` (issue #17) compounds this: if the consumer sets `HISTORY_MAX: 3` and has been deploying nightly, the only `--wait`-clean revision available for rollback may have already been pruned. Rollback then targets a dirty revision and silently degrades.

**Why it happens:**
- `--atomic` implies `--wait` only for the **current** upgrade, not retroactively for the history.
- Helm's "deployed" status reflects the last `helm upgrade` exit, not actual Kubernetes reconciliation.
- `--cleanup-on-fail` is off by default; partial resources from a failed install remain and clash with the rollback's create-or-replace logic.
- Users mix `--wait true` and `--wait false` invocations without realizing Helm history is now poisoned.

**How to avoid:**
- v2 should make `--wait` and `--atomic` either **both on** or **both off**, controlled by a single `SAFE_UPGRADE: true` (default) flag. Internally this maps to `--atomic --wait --cleanup-on-fail --timeout {TIMEOUT}`. Document that opting out (`SAFE_UPGRADE: false`) is for advanced users only.
- When `ACTION=rollback` is invoked, refuse to roll back to a revision whose `helm status <release> --revision <n>` shows resources not in `deployed` phase. Surface: `Cannot rollback: revision 4 was deployed without --wait and its resource state is indeterminate. Pass FORCE_ROLLBACK=true to proceed anyway.`
- For `HISTORY_MAX`: enforce a minimum of 5 (warn if consumer sets less than 5), and document that low history defeats safe rollback.
- Bundle `helm-diff` (already planned for `DRY_RUN`) and use it pre-rollback to show the consumer what the rollback will actually change — surfaces "rolling back to a broken state" before it happens.

**Warning signs:**
- Pipe code that exposes `--wait` and `--atomic` as independent toggles without coupling.
- `HISTORY_MAX` defaulting below 5.
- Rollback path with no pre-flight resource-status check.
- Integration tests on `kind`/`k3d` that never exercise a rollback after a `--no-wait` upgrade.

**Phase to address:**
Phase: **Rollback subcommand** + **History pruning (issue #17)**. These two ship together or not at all; treat as a single workstream.

---

### Pitfall 4: Cosign keyless signing tied to GitHub Actions OIDC + transparency log breaks under three predictable failure modes

**What goes wrong:**
Three coupled failure modes that each kill the release pipeline silently or annoyingly:

1. **Missing `id-token: write` permission.** The workflow inherits the repo default token permissions; if `permissions:` is set at job level for anything else, `id-token: write` is dropped and the Fulcio cert request fails with `error getting signer: getting key from Fulcio: getting key: invalid character '<' looking for beginning of value` (an HTML error page parsed as JSON — opaque).
2. **Rekor write succeeds, verify-time Rekor read fails.** Downstream consumers running `cosign verify` against the public Rekor endpoint experience verification failures during Sigstore outages — and there is no offline fallback unless we publish a **signed Rekor bundle** alongside the image (`--bundle` flag during signing, `--offline` flag during verify).
3. **Private image signing requires `--force`** on cosign versions prior to 1.4 (we will be on a much newer version, but consumer docs that copy-paste from blog posts may hit the old behavior). More relevant for us: the signing workflow must explicitly disable Docker Hub rate limit-induced `manifest unknown` retries that look like signing failures.

Cross-cutting: Fulcio certificates are valid for ~10 minutes. If the signing step runs after a long buildx step, the cert can expire mid-sign with a confusing error.

**Why it happens:**
- `permissions:` in GitHub Actions is a known footgun — once you set any permission at job level, everything else defaults to `none`.
- Public Sigstore infra has had outages (documented); teams treat it as if it had Google-level uptime.
- Cert expiry during long jobs is undocumented in most cosign tutorials.

**How to avoid:**
- Workflow template: when setting `permissions:`, set them at the **workflow** level explicitly with `id-token: write` and `contents: write` and `packages: write`, and never override at job level for signing jobs. Add a comment in the workflow file warning maintainers about the inheritance footgun.
- Always sign with `--bundle <path>` and publish the bundle as a GitHub Release asset **and** as an OCI attestation alongside the image. Document the offline-verify path for consumers.
- Sign **immediately after push** — separate job for buildx (no signing), separate job for sign-and-push-attestation (cosign only). Each job is short, so cert expiry is a non-issue.
- Pin `cosign` version explicitly in the workflow (not `@latest`).
- Verify signatures in CI on **every** PR — catches "we forgot to sign" and "the workflow lost id-token permission" before release.

**Warning signs:**
- A workflow file with `id-token: write` set at job level but the job depends on artefacts from another job that did not have it.
- No verification step in CI — only signing.
- Cosign step that runs >5 minutes after `buildx` push.
- Docs that tell consumers to verify against `rekor.sigstore.dev` directly without an offline-bundle fallback.

**Phase to address:**
Phase: **Supply-chain modernization** (Cosign + SBOM + Trivy gate). Verification-in-CI must be a sub-task, not "we'll add it later."

---

### Pitfall 5: Multi-arch image build under QEMU silently produces working `amd64` and broken `arm64` because the Python wheel mismatch is invisible until runtime

**What goes wrong:**
`docker buildx build --platform linux/amd64,linux/arm64 -t ...` on a GitHub Actions `ubuntu-latest` runner uses QEMU emulation for the non-native arch. Three things go wrong:

1. **Build time explodes** for `arm64` (20+ minutes for any C-extension Python package — `cryptography`, `MarkupSafe`, `PyYAML` C bindings). The CI job hits the 6-hour limit on a bad day, or just makes every release slow enough that engineers stop releasing.
2. **`musl` + `alpine` + `arm64` + Python C extensions = wheel cache misses**. Many wheels exist for `manylinux_2_28_aarch64` but not for `musllinux_1_2_aarch64`. The build silently falls back to compiling from source; some C extensions fail to find ARM-specific headers and the build emits a "no wheel, compiling..." warning that nobody reads.
3. **Base-image arch mismatch.** If `FROM python:3-alpine` resolves a manifest-list, fine. If it resolves a single-arch image (older custom bases, or a typo'd tag), buildx silently uses the same arch for both targets and the `arm64` image is actually an `amd64` binary tagged `arm64`. It works in `docker run` on a Mac (Rosetta), fails on EKS Graviton with `exec format error`.

For v2 specifically, the pipe runs **inside a Bitbucket Pipelines runner** which is **always `amd64`** today, so the consumer never sees the bug — but Apple Silicon developers pulling the image locally hit it immediately. The bug report will say "image won't run on my Mac" and we will assume Docker Desktop weirdness.

**Why it happens:**
- QEMU is the default, transparent, and slow. Nobody notices until release N+3.
- `alpine` is chosen for image size (15 MB vs 120 MB Debian slim) without measuring the build-time tradeoff for our specific deps.
- The base-image-not-a-manifest-list gotcha is buried in buildx docs.

**How to avoid:**
- Use `docker/setup-buildx-action` + `docker/build-push-action@v6` with `platforms: linux/amd64,linux/arm64`, **and** verify the resulting manifest list explicitly post-push: `docker buildx imagetools inspect $IMAGE | grep -E 'linux/(amd64|arm64)'` as a CI assertion. Fail the job if either arch is missing.
- Switch to **native ARM runners** for the `arm64` build. GitHub Actions offers `ubuntu-24.04-arm` runners; use a matrix strategy with one job per arch on native hardware, then `docker buildx imagetools create` to fuse the manifest list. Eliminates QEMU entirely.
- Pin the base image by **digest**, not tag (`python:3.12-alpine@sha256:...`), so the manifest-list-vs-single-arch behavior is locked at the digest level. Renovate/Dependabot updates the digest.
- Smoke test on **both** arches in CI: pull the image on an `arm64` runner and run `/opt/pipe/pipe.py --help`. Catches "wrong-arch binary at right-arch tag" instantly.
- Measure build time: if `arm64` build > 10 minutes, the CI flow has degraded and we missed a wheel availability change — add a build-duration assertion.

**Warning signs:**
- Single-job buildx with `--platform linux/amd64,linux/arm64` and no post-build manifest assertion.
- Base image referenced by tag only (`python:3-alpine`) rather than tag-and-digest.
- Build logs containing `building wheel for cryptography (PEP 517)` — means QEMU cross-compile is happening; switch to native runners.
- No `arm64` smoke test in CI.

**Phase to address:**
Phase: **Multi-arch image build** + **GitHub Actions release pipeline**. The native-runners decision should be made before the buildx workflow is written.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `awscli` for one transient command "just to unblock release" | No need to rewrite `eks.get_token` path now | Drags `awscli ~1.32` back into the image, contradicts the Key Decision in PROJECT.md, breaks the latency Constraint, eats 120 MB | Never. Cited as a Key Decision; reversal requires an ADR. |
| Stub `--bundle` cosign output, "we'll wire offline verify later" | Sign workflow ships earlier | Consumers cannot verify during Sigstore outages, undermines the whole supply-chain Phase | Never — verification is a deliverable of the same phase. |
| Skip `kind`/`k3d` integration tests, rely on acceptance tests only | Faster CI | Helm-rollback pitfalls (Pitfall 3) cannot be reproduced; acceptance tests mock Helm | Never for v2.0 — 100% coverage + integration are validated requirements. |
| Default `HISTORY_MAX` to Helm's stock 10 without warning if consumer overrides below 5 | Matches Helm defaults exactly | Reintroduces Pitfall 3 (rollback to pruned revision) | Acceptable if consumer warning fires on `< 5`. |
| Ship v2.0 with `:latest` pointing to v2 | "Modern" tag hygiene | Breaks every consumer using `:latest`; contradicts the "v1.x pinned image keeps working forever" promise | Never. `:latest` stays at v1.3.0 indefinitely until a v2 adoption signal exists. |
| Use `BaseException` subclasses for one more release "to minimize diff" | Smaller initial refactor PR | Catches `KeyboardInterrupt` and `SystemExit`, blocks Ctrl-C in local dev, listed explicitly as a v1.x bug to fix | Never in v2. Listed in Active requirements. |
| Bundle `helm-diff` plugin "later" (after MVP) | Faster MVP | Breaks DRY_RUN feature; Pitfall 3 mitigation depends on diff visibility | Acceptable only if `DRY_RUN` is also deferred — they ship together. |
| Skip signed-commit enforcement on `main` "while the team is small" | Faster contribution onboarding | Listed as a hard maintainer constraint (`commit.gpgsign=true`); violation = norm erosion | Never. Maintainer constraint. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Bitbucket OIDC → AWS STS | Wildcard `sub` in trust policy | Pin `sub` to repo+step UUIDs; provide a fillable template (see Pitfall 1) |
| EKS `get-token` via boto3 | Use stale `aws-iam-authenticator` token format (`v1alpha1`) | Emit `client.authentication.k8s.io/v1beta1` (current EKS-supported version); regenerate token per `helm` call, do not cache across `--wait` window |
| OCI chart registry login | `helm registry login` once, assume creds persist across pipe invocations | The pipe runs in a fresh container per step; always login at the start, parameterize `REPO_URL` + `REPO_USERNAME` + `REPO_PASSWORD` and validate they are set when `CHART` starts with `oci://` or `repo://` |
| `ghcr.io` vs Docker Hub auth in CI | Reuse `DOCKERHUB_TOKEN` for both registries | `ghcr.io` uses `GITHUB_TOKEN` with `packages: write`; Docker Hub uses a separate PAT. Two distinct `docker login` steps in the release workflow, each gated on the registry being targeted. |
| Bitbucket Pipes Toolkit env schema | Loose schema (`required: false` everywhere) | Use `pipes_toolkit` schema with `type` and `required` set per variable; validate at startup and surface a single consolidated error message, not N stack traces |
| Helm OCI charts pulled through a proxy | Assume `helm pull oci://` honors `HTTPS_PROXY` | Helm OCI client honors `HTTPS_PROXY` only since 3.13; pin Helm version in image and document the minimum |
| Cosign + private Docker Hub repo | Forget `--force` for keyless signing of private images on older cosign | Pin cosign ≥ 2.x in workflow; document that `--force` is no longer required |
| AWS session tags in OIDC trust | Forget `sts:TagSession` in the role's trust policy | Include `sts:TagSession` only if the pipe actually tags sessions; otherwise omit explicitly (least privilege) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full `awscli` install in the image | Cold pipe start > 60s (Constraint violation) | `boto3`-only EKS token generation (Key Decision) | Already broken at v1.x baseline; v2 fixes |
| QEMU-emulated ARM build | CI release jobs > 20 minutes | Native ARM runners + matrix | When wheels for new deps stop covering musllinux/arm64 |
| Acceptance test rebuilds image per test | CI > 10 minutes per push | Build once per CI run, share via `actions/cache` or registry tag | At ≥ 5 acceptance tests; current acceptance suite already trends here |
| Helm `--history-max` set to default 10 with daily deploys | After 10 days, all rollback targets are post-breakage | Document min `HISTORY_MAX: 5` and pair with `--atomic --wait --cleanup-on-fail` | Within 2 weeks of adoption by a daily-deploy consumer |
| Rekor verify on every pull in consumer's CI | Every `cosign verify` makes a network call to public Rekor | Offline `--bundle` published alongside image | During Sigstore outages or in air-gapped consumer environments |
| `helm upgrade --wait` with `--timeout 5m` on slow EKS pull | Pipe times out before pod is healthy because image pull is slow | Allow `TIMEOUT` ≥ 10m default; document interaction with EKS node-image-prefetch | Consumers with private ECR + cold nodes |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trust policy with wildcard `sub` or no `aud` constraint | Any Bitbucket workspace can assume the role | Pinned template + docs reviewed by a security-minded reviewer; CI script that fails the docs build if `"*"` appears in trust-policy examples |
| Logging `BITBUCKET_STEP_OIDC_TOKEN` or `AWS_SESSION_TOKEN` on error | Token exposure in public CI logs | Centralized log scrubber that redacts known secret env-var names; test that scrubber covers OIDC token specifically |
| Static AWS keys remain the documented "easy path" in v2 README | New consumers adopt the insecure path | OIDC is the **first** auth example in the README; static keys are explicitly labelled "legacy fallback — prefer OIDC" |
| Docker image signed but SBOM not signed | Supply chain claim is incomplete | Sign SBOM as an OCI attestation with cosign; consumers verify both |
| `pip-audit`/Trivy as informational only | CVEs ship to consumers | Both are CI **gates** (Validated requirement); failing scan blocks release-please from creating the release PR merge |
| Auto-merge enabled on Dependabot major bumps without integration test gate | A bad major bump ships to consumers automatically | Auto-merge only when **both** unit AND `kind`/`k3d` integration tests pass; major bumps additionally require Trivy clean |
| Forget to set `pull_request_target` worries on Cosign signing workflow | Forks can mint OIDC tokens with workflow's identity | Sign only on `push` to `main` and `release` events, never `pull_request_target` |
| `helm` charts pulled from arbitrary OCI registry without verification | Tampered chart deploys to EKS | Document `cosign verify` for charts where the publisher signs them; not a v2 hard requirement but called out in docs |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cryptic `helm` errors passed through verbatim | Consumer cannot tell pipe-error from helm-error | Prefix all pipe-emitted errors with `[aws-eks-helm-deploy]`; pass through helm stderr but bracket it `--- helm stderr ---` / `--- end helm stderr ---` |
| Migration guide buried under docs root | Consumers miss it during upgrade | Link from the README's "Upgrading from v1.x" section as the **first** post-install heading |
| `DRY_RUN: true` outputs a 3000-line `helm diff` and breaks Bitbucket log limits | Consumer cannot scroll the diff | Cap diff output at N kB and link to a downloadable artefact attached as a pipe output variable |
| `ACTION=rollback` without `REVISION` rolls back to "previous" by default | Consumer accidentally rolls back the wrong release | Make `REVISION` mandatory when `ACTION=rollback`; refuse to default |
| `INJECT_BITBUCKET_METADATA: false` default in v2 with no warning on first run after v1.x | Silent template failure (Pitfall 2) | Smart-detect prior-release dependency on `bitbucket.*` keys and warn (see Pitfall 2) |
| OCI chart `CHART_VERSION` accepting non-pinned semver ranges (`^1.2.0`) | Reproducibility lost | Reject anything but a fully-pinned version; document the rationale (production deployments must be reproducible) |
| Pipe outputs nothing on success | Consumer cannot verify what changed | Always emit: release name, revision number, app version, namespace, and (if `DRY_RUN`) the diff |

## "Looks Done But Isn't" Checklist

- [ ] **AWS OIDC**: Token validation step in pipe — verify `aud` claim shape; do not rely on STS to surface the error. Test: invoke with a hand-rolled JWT whose `aud` is an array; assert pipe-side rejection.
- [ ] **OCI chart support**: `helm registry login` is called before any `helm pull oci://`; `CHART_VERSION` is mandatory when `CHART` starts with `oci://`. Test: integration test pulling a real chart from `ghcr.io`.
- [ ] **Multi-arch image**: Post-build `docker buildx imagetools inspect` assertion in CI that both `linux/amd64` and `linux/arm64` manifests exist. Test: CI step that fails if either is missing.
- [ ] **Cosign signing**: Signature **and** SBOM attestation **and** Rekor bundle published per release. Test: a verification job in the same workflow runs `cosign verify --offline --bundle` against the freshly-signed image.
- [ ] **Migration guide**: Every breaking-change row has a before/after `bitbucket-pipelines.yml` diff. Test: docs-build script greps for `INJECT_BITBUCKET_METADATA`, `NAMESPACE`, and any renamed env var; fails if any are missing from the migration guide.
- [ ] **Rollback subcommand**: Pre-flight check that the target revision was deployed with `--wait` (status check). Test: integration test on `kind` that rolls back to a `--no-wait` revision and asserts pipe refuses unless `FORCE_ROLLBACK=true`.
- [ ] **`release-please` setup**: Conventional-commit footers (`BREAKING-CHANGE:`) bump major; squash-merge enforced on PR; release PR auto-updates as commits land. Test: a dry-run PR that lands a `feat!:` commit and verifies the release-please PR proposes a major bump.
- [ ] **OCI image labels**: All OCI annotations populated (`org.opencontainers.image.source`, `revision`, `licenses`, `description`, `version`, `created`). Test: `docker buildx imagetools inspect --raw | jq` assertion in CI.
- [ ] **`boto3`-only EKS token**: No `awscli` in `pyproject.toml` final lockfile. Test: lockfile audit step in CI greps for `awscli` and fails.
- [ ] **`helm-diff` plugin bundled**: `DRY_RUN` path works without network access to plugin registry. Test: integration test runs `DRY_RUN: true` with no internet (kind cluster + offline) and asserts diff is emitted.
- [ ] **Trivy/Grype gate**: Vulnerability scan is a **blocking** CI step, not informational. Test: an intentionally vulnerable PR fails the gate (one-time fixture).
- [ ] **`:latest` tag policy**: A documentation note **and** a release-workflow guard that prevents `:latest` from being pushed to v2 images.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| OIDC trust policy too permissive (Pitfall 1) | LOW (security incident pending) | Patch docs immediately; consumers re-deploy with corrected trust policy; rotate any AWS role that was abused (review CloudTrail for unexpected `AssumeRoleWithWebIdentity` events) |
| Metadata-injection default silently broke consumers (Pitfall 2) | MEDIUM | Hotfix release v2.0.1 with a louder warning **and** a one-page upgrade troubleshooting doc; pin a Discord/issue triage for 1 week |
| Helm rollback corrupted a release (Pitfall 3) | HIGH (production outage) | Manual `helm history` review; `kubectl apply -f` last-known-good manifests from backup; document the recovery as a runbook |
| Cosign verify failing due to Sigstore outage (Pitfall 4) | LOW | Publish offline bundle alongside every release; consumer docs link to `cosign verify --offline --bundle` recipe |
| `arm64` image is actually `amd64` (Pitfall 5) | LOW | Republish v2.0.x with fixed buildx workflow; add the inspect-manifest CI gate as a regression test |
| `release-please` PR went off the rails (force-pushed a wrong version) | MEDIUM | Revert the version-bump commit on `main`; manually craft the next release PR; ensure branch protection blocks force-push to `main` going forward |
| Dependabot auto-merged a broken major bump | MEDIUM | Revert PR, pin dependency, file an issue against the dep; review auto-merge criteria |
| Static AWS keys still in use after v2 ships | LOW (security debt) | Migration guide emphasizes OIDC; static-keys-path emits a deprecation log line (not a hard break in v2.0; flagged for v2.1 removal) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. OIDC `aud`/`sub` misconfiguration | AWS OIDC / IRSA implementation | Pipe-side `aud` validation unit test; docs build greps for `"*"` in trust-policy examples |
| 2. `INJECT_BITBUCKET_METADATA` silent break | Opt-in metadata injection (issue #16) + Migration guide | Integration test asserts warning fires when prior release had `bitbucket.*` keys |
| 3. Helm rollback on non-`--wait` revision | Rollback subcommand + History pruning (issue #17) | `kind`/`k3d` integration test rolls back to a `--no-wait` revision and asserts refusal |
| 4. Cosign / GitHub Actions OIDC failure modes | Supply-chain modernization (Cosign + SBOM + Trivy) | Workflow has a verify step on every PR; `--bundle` published per release |
| 5. Multi-arch QEMU silent breakage | Multi-arch image build + GitHub Actions release pipeline | Post-build `imagetools inspect` assertion; `arm64` runner smoke test |
| Bitbucket Pipes Toolkit env-schema loose | Modernization baseline (schema + pyproject) | Strict schema validation at pipe start with consolidated error |
| `awscli` import fragility | Modernization baseline (`boto3`-only EKS token) | Lockfile audit step; unit tests cover token generation against moto |
| `ghcr.io` vs Docker Hub auth divergence | GitHub Actions release pipeline | Separate `docker login` steps; release fails fast if either secret is missing |
| OCI chart auth | Helm repository and OCI chart support (issue #7) | Integration test pulls signed chart from `ghcr.io` |
| `release-please` mis-bumps version | GitHub Actions release pipeline | Branch protection on `main` (signed commits, no force-push); release-please config reviewed; `BREAKING-CHANGE:` footer convention documented in `CONTRIBUTING.md` |
| Acceptance tests rebuild image per test | Test-suite migration | Cache built image across acceptance tests via OCI tag |
| `:latest` tag drift | Distribution modernization | Release workflow refuses to push `:latest` for v2 images |

## Sources

- [Bitbucket OIDC with AWS (Towards The Cloud)](https://towardsthecloud.com/blog/aws-cdk-openid-connect-bitbucket) — `aud` claim shape and trust policy structure
- [Atlassian: Deploy on AWS using Bitbucket Pipelines OpenID Connect](https://support.atlassian.com/bitbucket-cloud/docs/deploy-on-aws-using-bitbucket-pipelines-openid-connect/) — official audience URL format
- [AWS STS now supports validation of IdP-specific claims (2026-01)](https://aws.amazon.com/about-aws/whats-new/2026/01/aws-sts-supports-validation-identity-provider-claims) — recent STS behavior change relevant to OIDC trust policies
- [Helm issue #9490 — ideal flags for upgrade/rollback failure handling](https://github.com/helm/helm/issues/9490) — community pattern for `--atomic` + `--wait` + `--cleanup-on-fail`
- [Helm upgrade docs](https://helm.sh/docs/v3/helm/helm_upgrade/) — `--history-max`, `--atomic`, `--wait` semantics
- [Handling failed Helm upgrade due to another operation in progress](https://www.kristhecodingunicorn.com/post/helm-upgrade-failure-another-operation-in-progress/) — locked-release recovery
- [Sigstore Cosign Keyless Signing with GitHub Actions OIDC: Complete Guide (QC Securing)](https://www.qcecuring.com/blog/sigstore-cosign-keyless-github-actions) — `id-token: write` and Rekor specifics
- [Sign Your Container Images with Cosign, GitHub Actions and GHCR (DEV.to / Christian Dennig)](https://dev.to/n3wt0n/sign-your-container-images-with-cosign-github-actions-and-github-container-registry-3mni) — workflow permission inheritance footgun
- [Faster Docker builds for Arm without emulation (Depot)](https://depot.dev/blog/docker-arm) — QEMU vs native ARM runners performance gap
- [Alpine Python Docker: Multi-Arch Buildx Manifests 2025](https://www.johal.in/alpine-python-docker-multi-arch-buildx-manifests-2025/) — Python-on-Alpine wheel availability
- [Docker multi-platform builds docs](https://docs.docker.com/build/building/multi-platform/) — manifest-list base-image pitfall
- [release-please documentation](https://github.com/googleapis/release-please) — `BREAKING-CHANGE:` footer and squash-merge convention
- [release-please-action](https://github.com/googleapis/release-please-action) — GitHub Actions integration patterns
- [aws-iam-authenticator (kubernetes-sigs)](https://github.com/kubernetes-sigs/aws-iam-authenticator) — EKS token format and `v1beta1` requirement
- [boto3 credentials docs](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html) — `AssumeRoleWithWebIdentity` caching and refresh
- [Helm OCI Registry Integration (DeepWiki)](https://deepwiki.com/helm/helm/6.2-oci-registry-integration) — OCI chart pull / login semantics
- Existing v1.x source: `pipe/{pipe.py, schema.py, eks/, helm/}` — `BaseException`, `awscli.customizations.eks.get_token`, no `--wait`/`--atomic` coupling, `NAMESPACE` default inconsistency

---
*Pitfalls research for: Bitbucket Pipelines Pipe (Helm-to-EKS) v2.0 modernization*
*Researched: 2026-06-16*
