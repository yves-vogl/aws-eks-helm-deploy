# Feature Research

**Domain:** Bitbucket Pipelines Pipe — CI-driven Helm deployment to AWS EKS
**Researched:** 2026-06-16
**Confidence:** HIGH (well-documented competitor space; conclusions cross-verified across Atlassian Pipes, GitHub Actions, Helmfile/Flux/ArgoCD docs)

> **Scope note.** The v2.0 "must-have" list in `PROJECT.md` (AWS OIDC, OCI/repo charts, dry-run, rollback, `HISTORY_MAX`, opt-in metadata injection) is treated as **already decided** and is not re-recommended here. This document covers what the **competitive ecosystem** ships that we should consider on top, plus features we should deliberately exclude.

---

## Competitive Landscape Surveyed

| Tool | Class | Why it matters here |
|------|-------|---------------------|
| `atlassian/aws-eks-kubectl-run` | Bitbucket Pipe | Closest official sibling; sets baseline for Pipe contract conventions |
| `atlassian/aws-ecs-deploy` | Bitbucket Pipe | Atlassian-blessed pattern for AWS deploys (WAIT, FORCE_NEW_DEPLOYMENT, env var naming) |
| `atlassian/aws-lambda-deploy` | Bitbucket Pipe | Same — naming and `DEBUG` conventions |
| `azure/k8s-deploy@v5` | GitHub Action | Most feature-complete equivalent; canary/blue-green strategies, baseline-vs-canary, SMI |
| `deliverybot/helm` | GitHub Action | Helm-specific GHA, `track` for canary, `task=remove` for cleanup, templated values |
| `aws-actions/configure-aws-credentials` | GitHub Action | OIDC reference implementation (retry, custom STS endpoint, masked credentials) |
| `databus23/helm-diff` | Helm plugin | Industry-standard dry-run output, used by Helmfile/Flux |
| `helmfile/helmfile` | Declarative wrapper | Multi-release manifest, `sync`/`apply`/`diff`/`destroy`, environment values layering |
| `fluxcd/helm-controller` | GitOps controller | `valuesFrom` (Secret/ConfigMap), `postRenderers`, `dependsOn`, drift detection |
| `argoproj/argo-cd` | GitOps controller | Renders Helm to manifests + applies; no Helm release ownership |
| `jkroepke/helm-secrets` | Helm plugin | SOPS-encrypted values files; widely expected by security-conscious teams |

---

## Feature Landscape

### Table Stakes (Users Expect These)

These are features where, if they're missing in v2.0 compared to the broader 2026 CI-deploy ecosystem, the Pipe will feel **unmaintained or toyish** next to GHA/Helmfile alternatives. Items already on the v2.0 must-have list are NOT repeated here.

| # | Feature | Why Expected | Complexity | Depends On |
|---|---------|--------------|------------|------------|
| TS-1 | `helm upgrade --atomic` opt-in via `ATOMIC=true` | Default for any production-grade Helm CD pipeline; pairs naturally with `--wait`/`--timeout` which v1 already has. Without it, failed deploys leave half-applied releases. | **S** | — |
| TS-2 | `--wait-for-jobs` opt-in via `WAIT_FOR_JOBS=true` | Required when chart has `pre-install`/`pre-upgrade` hook jobs (DB migrations). Mentioned in every Helm-in-CI best-practices article 2025-2026. | **S** | `WAIT=true` (already in v1) |
| TS-3 | `DEBUG=true` variable that toggles `--debug` on Helm and verbose Pipe logging | Atlassian convention across every official Pipe (`aws-ecs-deploy`, `aws-eks-kubectl-run`, `aws-lambda-deploy`). Users will look for it first when something breaks. | **S** | — |
| TS-4 | Multiple `--values` files (current pipe supports one `VALUES_FILE`; ecosystem expects a list) | Helmfile, Flux, deliverybot/helm, azure/k8s-deploy all support layered values (base + env overrides). Single file forces consumers to pre-merge → friction. | **S** | — |
| TS-5 | `--set-string` and `--set-file` passthrough via `EXTRA_ARGS` or dedicated `SET_STRING` / `SET_FILE` variables | Standard Helm flags; needed for embedding cert PEMs, long tokens, or numeric-looking values that must stay strings. | **S** | — |
| TS-6 | Distinct exit codes for: helm failure vs AWS auth failure vs schema/validation failure | Atlassian Pipe convention; lets consumers use Bitbucket "on failure" steps differently per cause. v1 just bubbles whatever Python exception happens. | **M** | exception-hierarchy refactor (already in modernization baseline) |
| TS-7 | `helm template` pre-flight validation (no cluster needed) when `VALIDATE_ONLY=true` | Cheaper than dry-run, catches schema errors before AWS auth even runs. Helmfile and Flux both do this as a first step. | **S** | — |
| TS-8 | `helm lint` integration on the chart path before install/upgrade | Industry-standard CI step; every Helm-in-CI tutorial 2025-2026 mentions it. | **S** | — |
| TS-9 | Credential masking in logs (AWS keys, STS tokens, OIDC tokens, helm-rendered Secrets) | Bitbucket masks declared secrets but `helm get manifest` and `--debug` output happily print rendered Secret manifests. `aws-actions/configure-aws-credentials` masks by default. Failing to do this is a real CVE class. | **M** | — |
| TS-10 | `KUBECONFIG_OUTPUT_PATH` / explicit kubeconfig artifact path for subsequent pipeline steps | Lets consumers chain a kubectl step after the Pipe without re-authenticating. Pattern used by `aws-actions/configure-aws-credentials` (exposes credentials as outputs). | **S** | — |
| TS-11 | Helm version pinning displayed in pipe output banner | When the bundled Helm changes (skew policy ADR), users need to immediately see which Helm ran. Helmfile/Flux always log this. | **S** | — |
| TS-12 | Multiple chart deployment in a single pipe call via `RELEASE` list — **NO**, deliberately deferred to anti-features (see AF-2) | n/a | n/a | n/a |
| TS-13 | `RELEASE_NAME` validation against DNS-1123 / Helm release-name rules before the call | Helm errors on bad names are cryptic; pre-validating gives a friendly error. Every Helm GHA does this. | **S** | — |
| TS-14 | Cleanup / uninstall mode (`ACTION=uninstall` with `KEEP_HISTORY=true/false`) | deliverybot/helm has `task=remove`; ephemeral preview-env deployments need this. Without it, consumers write a separate step using a different image. | **S** | rollback subcommand work (action dispatch is being introduced anyway) |
| TS-15 | Output variables (`BITBUCKET_PIPE_STORAGE_DIR/output`): release name, revision number, status, manifest path | Bitbucket Pipe Toolkit convention; downstream steps (Slack notify, Datadog event) need these. v1 doesn't emit any. | **S** | bitbucket-pipes-toolkit `set_output` (already a dep) |
| TS-16 | Retry with exponential backoff on STS `AssumeRoleWithWebIdentity` and `eks describe-cluster` | `aws-actions/configure-aws-credentials` retries 12 times by default; AWS APIs throttle in busy accounts. Failure-on-first-throttle looks amateur. | **S** | OIDC work (already in v2.0 scope) |
| TS-17 | Local kubeconfig path override (`KUBECONFIG_PATH=...`) for advanced users who already have one | Helmfile/Flux/deliverybot all support it. Lets consumers re-use a kubeconfig built by a previous Pipe step. | **S** | — |

**Summary — Table stakes additions: 14 features (TS-1..11, TS-13..17), all S/M complexity, no L items.** Nothing here threatens timeline if done as part of the v2.0 cleanup.

---

### Differentiators (Competitive Advantage)

Features that distinguish this Pipe from the rest of the Bitbucket Pipe field and from Helm-deploy GHAs. Each item is annotated with **v2.0 / v2.1+** scope hint.

| # | Feature | Value Proposition | Complexity | v2.0 or later? |
|---|---------|-------------------|------------|----------------|
| D-1 | **Bundled `helm-diff` + automatic Bitbucket PR comment with the diff** when running in a PR pipeline | No competitor Pipe does this. Even Atlassian's own ECS pipe doesn't comment on PRs. Posting `helm diff upgrade` as a Bitbucket PR comment makes this the **only** Pipe that gives reviewers Terraform-style change preview. Massive UX win for the OIDC + PR-preview workflow. | **M** | **v2.0** — `helm-diff` is already bundled for `DRY_RUN`; PR-comment hook via Bitbucket API is incremental |
| D-2 | **Signed pipe image (Cosign keyless) + SBOM attestation verifiable from consumer pipelines** | No other Bitbucket Pipe in the marketplace ships Cosign-signed images with SBOM as of mid-2026. Consumers can add `cosign verify` to their own pipeline as a supply-chain gate. Story: "the only Pipe you can prove came from this repo." | **M** | **v2.0** — already in distribution-modernization scope; emphasize as a differentiator in marketing |
| D-3 | **Native Bitbucket Deployments environment integration** — auto-detect `BITBUCKET_DEPLOYMENT_ENVIRONMENT`, surface release/revision to the Deployments dashboard | v1 ignores it. Other Pipes barely use it. Tying Helm release name + revision to Bitbucket's Deployments UI gives consumers free release tracking without a third-party tool. | **M** | **v2.0** — small wrapper; high marketing leverage |
| D-4 | **`HELM_VALUES_FROM_AWS_SECRETSMANAGER` / `HELM_VALUES_FROM_SSM`** — declarative pull of values from AWS Secrets Manager / SSM Parameter Store as merged values | Flux has `valuesFrom: secret`; no Pipe ecosystem has the equivalent for AWS-native secret stores. Since we already authenticate to AWS, fetching values from Secrets Manager is a 30-line addition that solves the "I don't want to commit even encrypted secrets" use case **without** asking users to install SOPS. | **M** | **v2.1** — defer to after v2.0 launches; needs an ADR on schema (which path, which format) |
| D-5 | **`POST_RENDERER=kustomize`** — bundled `kustomize` binary + automatic `helm template \| kustomize build -` post-rendering | Flux supports this; no Bitbucket Pipe does. The "I love Helm but need to patch one label on one object" use case is universal and currently forces users off the Pipe. | **M** | **v2.1** — adds image size; needs careful UX design |
| D-6 | **Schema-validated input variables with rich error messages** — `pipe.yml` ships JSON Schema; pre-flight validates user inputs and prints "did you mean `CLUSTER_NAME` not `EKS_CLUSTER`?" before any AWS call | bitbucket-pipes-toolkit supports schema; few Pipes use it well. Combined with our `mypy --strict` + `ruff` story, this is a "this Pipe is built right" signal. | **S** | **v2.0** — leverages existing `pipe/schema.py` |
| D-7 | **Cold-start under 10 s** (current v1.3.0: full `awscli` + Python startup ≈ 25-40 s) — `boto3`-only + lazy imports + Alpine + `helm` precompiled | This is invisible until you ship 100 deploys/day. Competitors don't advertise it because most are 30 s+. "Fastest EKS-Helm Pipe on the Bitbucket Marketplace" is a defensible claim. | **M** | **v2.0** — already implied by "drop awscli" decision; just needs to be benchmarked and publicized |
| D-8 | **First-class IRSA support** (when the consumer mounts a service-account token; for pipes-on-self-hosted-runner cases) | Bitbucket self-hosted runners can run on EKS with IRSA. Supporting `AWS_WEB_IDENTITY_TOKEN_FILE` natively (the var `aws-actions/configure-aws-credentials` already uses) gives self-hosted runners a zero-config path. | **S** | **v2.0** — `boto3` already reads `AWS_WEB_IDENTITY_TOKEN_FILE`; just don't break it |
| D-9 | **`--show-only`-style filter for dry-run output** — let users render only specific templates in the diff for very large charts | Helm has `helm template --show-only`; CI tools rarely expose it. Reduces noise in PR comments to "show only the Deployment, not the 47 ConfigMaps." | **S** | **v2.1** |
| D-10 | **Status-summary output as machine-parsable JSON** to `BITBUCKET_PIPE_STORAGE_DIR/output.json` | No Bitbucket Pipe does this well. Enables consumers to write generic "post a deploy event to Datadog/Honeycomb" steps without parsing log output. | **S** | **v2.0** — pairs with TS-15 |

**Differentiator count not appearing in competitor Pipes (the gate requires ≥3):**
1. **D-1** — PR-comment helm-diff: no competing Pipe does this.
2. **D-2** — Cosign + SBOM signed Pipe image: no competing Pipe ships this.
3. **D-3** — Bitbucket Deployments dashboard integration: under-used by all competing Pipes.
4. **D-4** — Values-from-AWS-Secrets-Manager: not in any Pipe or major GHA.
5. **D-7** — Sub-10 s cold start with benchmark: no Pipe publishes this metric.

Five differentiators clear the gate. **D-1, D-2, D-3, D-7 are all in v2.0 scope.** D-4 and D-5 are deliberately deferred to v2.1.

---

### Anti-Features (Deliberately NOT Built)

Features that surface in user requests or competitor matrices but would break the Pipe's value proposition.

| # | Feature | Why Tempting | Why Problematic | Better Approach |
|---|---------|--------------|-----------------|-----------------|
| AF-1 | **Continuous reconciliation / drift detection** (à la Flux Helm Controller, ArgoCD auto-sync) | "Why not give the Pipe a `RECONCILE=true` mode?" | A Pipe is a **one-shot CI step**; reconciliation requires a long-running in-cluster controller. Re-running the Pipe on a cron doesn't fix drift between runs; it just *pretends* to. Building this would mean owning a controller — out of scope, and Flux/ArgoCD already win this space. | Document in README: "If you need drift detection, install Flux Helm Controller and use this Pipe only for bootstrapping." |
| AF-2 | **Multi-release / declarative manifest** (`releases:` list à la Helmfile) | Users with 10 releases want one Pipe call to deploy them all. | Helmfile already does this perfectly and is OSS. Re-implementing it inside a Pipe duplicates a battle-tested tool **and** breaks the "one Pipe call = one observable deployment" Bitbucket Deployments model. | Document: "For multi-release orchestration, call this Pipe once per release in a Bitbucket pipeline `parallel:` block, or use Helmfile." |
| AF-3 | **Templated/scaffolded chart generation** (deliverybot/helm's "app" built-in chart) | "Why not bundle a generic chart so users don't need their own?" | Users always need to customize. A bundled chart becomes a forever-maintenance burden (every new K8s API version breaks it) and is wrong for 95% of consumers. | Point users at `helm create` + Bitnami common charts. Provide one `examples/` chart that's clearly labelled "example only, not a product." |
| AF-4 | **Canary / blue-green strategy orchestration** (à la `azure/k8s-deploy` strategy=canary with baseline/-canary suffix workloads) | "If we have rollback, why not also canary?" | Canary requires either a service mesh (Istio/Linkerd SMI) or chart-level rolling-update semantics. Building generic canary logic into a Helm wrapper means *rewriting* Argo Rollouts / Flagger inside the Pipe. Wrong layer. | Document: "Use Argo Rollouts or Flagger as the chart's deployment kind; this Pipe handles the Helm release lifecycle around it." |
| AF-5 | **Managing Helm repos as long-lived state** (`helm repo add` persisted across runs, repo cache mounted as volume) | "Performance — why re-add the repo every run?" | Each Pipe invocation is ephemeral. Persisting repo state requires consumer-side cache volumes (which Bitbucket Pipes doesn't standardize) and creates a class of cache-corruption bugs. | Always `helm repo add --force-update` per run. Document trade-off. The cold-start budget (D-7) already accounts for this. |
| AF-6 | **Bitbucket-only secret manager wrapper** (a "fetch secret from Bitbucket repo variable and inject as Helm value" feature) | Looks convenient. | Bitbucket repo variables are *already* env vars when the Pipe runs. Wrapping that with a custom syntax invents a non-standard mechanism — violates the NIH rule. | Document the existing `helm --set $MY_SECRET` pattern. |
| AF-7 | **Bundled `kubectl`** (so the Pipe can also do `kubectl apply` post-deploy hooks) | "I want to label a node after deploy." | Scope creep. The Pipe is for Helm. `atlassian/aws-eks-kubectl-run` exists for kubectl. Bundling kubectl bloats the image and blurs the boundary. | Document: "Chain this Pipe with `atlassian/aws-eks-kubectl-run` for kubectl operations." |
| AF-8 | **Slack/Teams/email notifications** baked in | "Tell me when deploys fail." | Notification is a cross-cutting concern; every team uses a different tool. Building it in means maintaining 5+ integrations forever. | Emit structured output (D-10, TS-15) so the consumer chains their own notification Pipe (Atlassian ships `slack-notify`). |
| AF-9 | **Storing release state in S3/DynamoDB** (Terraform-style remote backend for Helm) | "What if the cluster is gone?" | Helm release state already lives in cluster Secrets (Helm 3). Adding a parallel external store creates split-brain. If the cluster is gone, the release is gone — that's the right semantics. | Use `helm get values <release> -o yaml` in a pre-Pipe step to back up state if needed. Document. |

**Anti-feature count (gate requires ≥3): 9 documented, each with reasoning.** ✓

---

## Feature Dependencies

```
TS-1 (--atomic) ──pairs──> TS-2 (--wait-for-jobs)
         └──recommends──> v2.0 rollback (already in scope)

TS-6 (typed exit codes) ──requires──> exception-hierarchy refactor (modernization baseline)

TS-7 (helm template validate) ──enhances──> TS-8 (helm lint)
                                └──enhances──> v2.0 DRY_RUN (already in scope)

TS-9 (log masking) ──blocks──> TS-15 (output emission)
         └──blocks──> D-1 (PR-comment helm-diff)
        [must redact rendered Secret manifests before any external posting]

TS-15 (set_output) ──requires──> D-10 (JSON output)

TS-16 (STS retry) ──requires──> v2.0 OIDC (already in scope)

D-1 (PR helm-diff) ──requires──> v2.0 helm-diff bundling (already in scope)
       └──requires──> Bitbucket API token surface (new) ──conflicts──> "no extra secrets" UX promise
                                                          └──mitigation──> use BITBUCKET_TOKEN
                                                                          (auto-provided in pipelines)

D-3 (Deployments dashboard) ──requires──> TS-15 (output emission)

D-4 (Secrets Manager values) ──requires──> v2.0 OIDC (already in scope)
                              └──conflicts──> AF-6 (custom secret wrapper) — D-4 is the
                                              standards-aligned alternative

D-7 (cold-start <10s) ──requires──> v2.0 "drop awscli" decision (already in scope)
                       └──requires──> benchmark harness (new — small, but must exist)

D-8 (IRSA) ──compatible-with──> v2.0 OIDC (different code path; both can coexist)

AF-2 (multi-release) ──conflicts──> Bitbucket Deployments single-deployment model
                                    (so we deliberately don't ship it)
```

### Dependency Notes

- **Critical:** TS-9 (log masking) is a **blocker** for D-1 and TS-15. Posting helm-diff output as a PR comment or writing it to an output file without redacting `kind: Secret` blocks is a credential-leak vector. **Must be in v2.0 before D-1 ships.**
- **Critical:** D-1 (PR comment) needs the Bitbucket API. The Bitbucket Pipes environment auto-provides `BITBUCKET_TOKEN` for repo write-access, so this does **not** require asking the consumer to configure a new secret.
- **Easy win cluster:** TS-1, TS-2, TS-3, TS-13, D-6 can all be done in a single PR — all are `pipe.yml` schema additions + thin Helm flag plumbing.
- **Defer cleanly:** D-4 (`HELM_VALUES_FROM_AWS_SECRETSMANAGER`) and D-5 (post-renderer/kustomize) are excellent v2.1 features. They don't unlock v2.0 and they each warrant their own ADR.

---

## MVP Definition

### v2.0 Launch — Table-stakes work

All TS items except TS-12 (deliberately excluded) and TS-14 (uninstall — can be cut if timeline pressures):

- [x] *Already locked in PROJECT.md:* OIDC, OCI/repo charts, dry-run, rollback, `HISTORY_MAX`, opt-in metadata
- [ ] **TS-1** `ATOMIC` variable
- [ ] **TS-2** `WAIT_FOR_JOBS` variable
- [ ] **TS-3** `DEBUG` variable (Atlassian convention)
- [ ] **TS-4** multiple `VALUES_FILE` (list, not scalar)
- [ ] **TS-5** `SET_STRING` / `SET_FILE` variables
- [ ] **TS-6** typed exit codes (depends on exception-hierarchy refactor, which is already in baseline)
- [ ] **TS-7** `VALIDATE_ONLY=true` (`helm template`-only path)
- [ ] **TS-8** `helm lint` integrated into validate/dry-run paths
- [ ] **TS-9** log masking (rendered Secrets + AWS tokens) — **security blocker for D-1**
- [ ] **TS-10** `KUBECONFIG_OUTPUT_PATH`
- [ ] **TS-11** Helm-version banner in pipe output
- [ ] **TS-13** release-name DNS-1123 validation
- [ ] **TS-14** `ACTION=uninstall` (can defer to v2.0.1 if needed)
- [ ] **TS-15** `set_output` for `release`, `revision`, `status`, `manifest_path`
- [ ] **TS-16** STS retry with backoff
- [ ] **TS-17** `KUBECONFIG_PATH` override

### v2.0 Launch — Differentiators

- [ ] **D-1** helm-diff posted as Bitbucket PR comment when running in a PR pipeline
- [ ] **D-2** Cosign-signed image + SBOM attestation (already in PROJECT scope; emphasize in README)
- [ ] **D-3** Bitbucket Deployments dashboard integration
- [ ] **D-6** Rich pipe.yml JSON Schema with friendly error messages
- [ ] **D-7** Cold-start benchmark + sub-10s guarantee
- [ ] **D-8** IRSA via `AWS_WEB_IDENTITY_TOKEN_FILE`
- [ ] **D-10** JSON output blob

### v2.1+ — After v2.0 stabilizes

- [ ] **D-4** `HELM_VALUES_FROM_AWS_SECRETSMANAGER` / `HELM_VALUES_FROM_SSM`
- [ ] **D-5** Kustomize post-renderer
- [ ] **D-9** `--show-only` filtering for dry-run

### Explicit non-goals — never ship

See Anti-Features table; AF-1 through AF-9.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|-----------|---------------------|----------|
| TS-1 ATOMIC | HIGH | LOW | **P1** |
| TS-2 WAIT_FOR_JOBS | HIGH | LOW | **P1** |
| TS-3 DEBUG | HIGH | LOW | **P1** |
| TS-4 multi-values | HIGH | LOW | **P1** |
| TS-5 SET_STRING/SET_FILE | MEDIUM | LOW | **P1** |
| TS-6 typed exit codes | MEDIUM | MEDIUM | **P1** (paired with baseline refactor) |
| TS-7 VALIDATE_ONLY | MEDIUM | LOW | **P1** |
| TS-8 helm lint | MEDIUM | LOW | **P2** (nice to have, not gating) |
| TS-9 log masking | HIGH (security) | MEDIUM | **P1** (blocker for D-1) |
| TS-10 KUBECONFIG_OUTPUT_PATH | MEDIUM | LOW | **P2** |
| TS-11 Helm version banner | LOW | LOW | **P1** (trivial, ships with banner work) |
| TS-13 release-name validation | MEDIUM | LOW | **P1** |
| TS-14 uninstall | MEDIUM | LOW | **P2** (defer to v2.0.1 if needed) |
| TS-15 set_output | HIGH | LOW | **P1** |
| TS-16 STS retry | HIGH | LOW | **P1** (security/reliability) |
| TS-17 KUBECONFIG_PATH | LOW | LOW | **P2** |
| D-1 PR helm-diff comment | HIGH | MEDIUM | **P1** (signature feature) |
| D-2 Cosign + SBOM | HIGH | MEDIUM | **P1** (already in scope) |
| D-3 Deployments dashboard | HIGH | MEDIUM | **P1** |
| D-6 schema-driven errors | MEDIUM | LOW | **P1** |
| D-7 cold-start <10s | MEDIUM | MEDIUM | **P1** (already implied by awscli drop) |
| D-8 IRSA | MEDIUM | LOW | **P1** (free with boto3 path) |
| D-10 JSON output | MEDIUM | LOW | **P1** (pairs with TS-15) |
| D-4 Secrets Manager values | HIGH | MEDIUM | **P2** (v2.1) |
| D-5 Kustomize post-renderer | MEDIUM | MEDIUM | **P3** (v2.1) |
| D-9 --show-only filter | LOW | LOW | **P3** (v2.1) |

**Priority key:**
- **P1**: v2.0 launch blocker
- **P2**: v2.0 if time permits, else v2.0.x
- **P3**: v2.1+

---

## Competitor Feature Analysis

| Feature | `atlassian/aws-eks-kubectl-run` | `azure/k8s-deploy` | `deliverybot/helm` | Helmfile / Flux | **Our Approach** |
|---|---|---|---|---|---|
| OIDC auth | No (static keys only) | Pairs with `azure/login` | No (kubeconfig file) | n/a (in-cluster) | **First-class, with static fallback (v2.0)** |
| Helm-diff / dry-run | No (kubectl-only) | No (kubectl-based) | No | Yes (Helmfile `diff`, Flux events) | **Yes + PR comment (D-1)** |
| Rollback | Manual via kubectl | Yes (canary reject) | No | Yes (`helm rollback`) | **Yes, dedicated `ACTION=rollback` (v2.0)** |
| OCI charts | n/a | Yes | Partial | Yes | **Yes (v2.0)** |
| Multi-values file | n/a | n/a | Yes | Yes | **Yes (TS-4)** |
| Canary strategy | No | Yes | Yes (`track`) | Yes (Flagger/Rollouts) | **No — AF-4** |
| Multi-release | No | No | No | Yes | **No — AF-2** |
| Image signing (Cosign) | No | No | No | n/a (the tool itself) | **Yes (D-2)** |
| Bundled `helm-diff` | n/a | n/a | No | Yes (Helmfile) | **Yes (v2.0)** |
| Bundled `kustomize` | No | Yes (manifest mode) | No | Yes (post-renderer) | **Deferred to v2.1 (D-5)** |
| Drift detection | No | No | No | Yes (Flux) | **No — AF-1** |
| Secret-store values | No | No | No | Yes (Flux `valuesFrom`) | **Yes for AWS-native, v2.1 (D-4)** |
| Bitbucket Deployments | No | n/a | n/a | n/a | **Yes (D-3)** |
| Output variables | Partial | Yes | Partial | n/a | **Yes, structured JSON (D-10)** |
| PR diff comment | No | No | No | Manual scripting | **Yes — signature feature (D-1)** |

---

## Most Surprising Findings (for the summary)

1. **No Bitbucket Pipe in the marketplace ships a Cosign-signed image with SBOM as of mid-2026.** D-2 is a credible "best-in-class supply-chain" claim with very little extra work beyond what's already in scope.
2. **Atlassian's own EKS Pipe (`aws-eks-kubectl-run`) has no OIDC support and no Helm support** — the gap our v2.0 fills is wider than the issue tracker suggested.
3. **Posting helm-diff as a Bitbucket PR comment (D-1) is genuinely novel** in the Pipe ecosystem and trivially achievable because Bitbucket Pipelines auto-provides `BITBUCKET_TOKEN`. No consumer setup, big "wow" demo.
4. **The "drop full `awscli`" decision in PROJECT.md is also the biggest marketing lever**: a documented sub-10s cold-start beats every competitor Pipe and most GHAs. Worth a benchmark in the README.
5. **TS-9 log masking is a non-obvious security blocker** — `helm get manifest` and `helm template --debug` both print rendered `Secret` manifests in plaintext. Any feature that exposes that output (D-1 PR comments, D-10 JSON output) is a credential-leak vector until we redact. **Must land first.**
6. **GitOps reconciliation (Flux/ArgoCD) and Helmfile's multi-release model are not gaps — they are wins.** They define what our Pipe deliberately does **not** do, freeing us to be the best-in-class **one-shot CI Pipe** rather than a worse imitation of either.

---

## Sources

- [atlassian/aws-eks-kubectl-run (Bitbucket)](https://bitbucket.org/atlassian/aws-eks-kubectl-run)
- [Deploy to AWS EKS — Bitbucket Cloud docs (Atlassian Support)](https://support.atlassian.com/bitbucket-cloud/docs/deploy-to-aws-eks-kubernetes/)
- [Deploy on AWS using Bitbucket Pipelines OpenID Connect (Atlassian Support)](https://support.atlassian.com/bitbucket-cloud/docs/deploy-on-aws-using-bitbucket-pipelines-openid-connect/)
- [Azure/k8s-deploy GitHub Action README](https://github.com/Azure/k8s-deploy/blob/main/README.md)
- [Azure/k8s-deploy Marketplace listing](https://github.com/marketplace/actions/deploy-to-kubernetes-cluster)
- [deliverybot/helm GitHub Action](https://github.com/deliverybot/helm)
- [Deliverybot Helm Action Marketplace](https://github.com/marketplace/actions/deliverybot-helm-action)
- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
- [databus23/helm-diff](https://github.com/databus23/helm-diff)
- [Flux helm-controller HelmRelease spec](https://github.com/fluxcd/helm-controller/blob/main/docs/spec/v2beta1/helmreleases.md)
- [Flux Manage Helm Releases](https://fluxcd.io/flux/guides/helmreleases/)
- [Flux CD vs ArgoCD: Helm Support Comparison (OneUptime, 2026-03)](https://oneuptime.com/blog/post/2026-03-06-flux-cd-vs-argocd-helm-support-comparison/view)
- [Helm upgrade docs (helm.sh)](https://helm.sh/docs/helm/helm_upgrade/)
- [Helm Performance Optimization (OneUptime, 2026-01)](https://oneuptime.com/blog/post/2026-01-17-helm-performance-optimization-large-scale/view)
- [How to Upgrade and Rollback Helm Releases Safely (OneUptime, 2026-01)](https://oneuptime.com/blog/post/2026-01-17-helm-upgrade-rollback-releases/view)
- [Helm Diff plugin: Preview Changes (OneUptime, 2026-02)](https://oneuptime.com/blog/post/2026-02-09-helm-diff-plugin-preview-changes/view)
- [helm-secrets (jkroepke) Usage wiki](https://github.com/jkroepke/helm-secrets/wiki/Usage)
- [Helm Secrets: Secure Kubernetes Secrets Management Guide (GitGuardian)](https://blog.gitguardian.com/how-to-handle-secrets-in-helm/)
- [HelmRelease ValuesFrom Secret in Flux (OneUptime, 2026-03)](https://oneuptime.com/blog/post/2026-03-05-helmrelease-valuesfrom-secret-flux/view)
- [Detect Helm Drift with Flux CD (OneUptime, 2026-03)](https://oneuptime.com/blog/post/2026-03-05-detect-helm-drift-flux-cd/view)
- [Argo CD anti-patterns (Codefresh)](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/)

---
*Feature research for: Bitbucket Pipelines Pipe — CI-driven Helm deployment to AWS EKS*
*Researched: 2026-06-16*
