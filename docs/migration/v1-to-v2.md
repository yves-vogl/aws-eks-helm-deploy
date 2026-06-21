# v1 → v2 Migration Guide (Draft)

> **Draft status:** This guide covers Phase 5 breaking changes and new workflows.
> Phase 7 will polish wording, add a table of contents, add mkdocs-material admonitions,
> integrate screenshots, and publish the guide at `/v2/migration/v1-to-v2/` on the docs site.

v2.0 is a clean rewrite of the v1.x shell pipe in Python. The core action — `helm upgrade
--install` targeting an AWS EKS cluster — is unchanged, but v2 ships OIDC authentication,
new chart sources (Helm repo, OCI registry), new actions (`diff`, `rollback`), and several
safety and observability features that were impossible in the v1 shell model. v1.3.0 is the
final v1.x release and is frozen on Docker Hub at `docker.io/yvogl/aws-eks-helm-deploy:1.3.0`.
v2 ships exclusively to `ghcr.io/yves-vogl/aws-eks-helm-deploy` (see Phase 6 for the release
pipeline).

---

## Breaking changes at a glance

| Change | v1.x | v2.0 | Reference |
|--------|-------|-------|-----------|
| `INJECT_BITBUCKET_METADATA` default | Unconditional injection of `bitbucket.*` values | Opt-in only; defaults to unset | META-02 / issue #16 |
| `SET` / `VALUES` env var syntax | Space-separated positional list | Comma-separated list (JSON-array fallback) | MIG-02 / `settings.py _CommaListEnvSource` |
| Image registry | `docker.io/yvogl/aws-eks-helm-deploy:1.x` | `ghcr.io/yves-vogl/aws-eks-helm-deploy:2` (rolling) or `:2.x.y` (pinned) | Phase 6 / MIG-01 |
| AWS auth | Static keys + `ROLE_ARN` | Static keys + `ROLE_ARN` + OIDC via `BITBUCKET_STEP_OIDC_TOKEN` | See [docs/guides/oidc-setup.md](../guides/oidc-setup.md) |
| `NAMESPACE` default | `kube-public` (v1 bug) | `default` | `settings.py` — fix shipped in Phase 1 |
| `awscli` dependency | Bundled in image | Removed; `boto3`-only EKS token generation | AUTH-07 / Phase 2 |
| Auth precedence when both static keys AND OIDC token are present | n/a (no OIDC in v1) | Static keys win (mirrors AWS CLI / boto3 default chain); see `auth.precedence.static_keys_won_over_oidc` WARN | AUTH-04 revised / Phase 4 |

---

## INJECT_BITBUCKET_METADATA — the headline breaking change (META-02)

In v1.x the pipe unconditionally injected five `--set bitbucket.*` values on every
`helm upgrade --install` call:

- `bitbucket.bitbucket_build_number`
- `bitbucket.bitbucket_repo_slug`
- `bitbucket.bitbucket_commit`
- `bitbucket.bitbucket_tag`
- `bitbucket.bitbucket_step_triggerer_uuid`

v2.0 flips the default: those values are NOT injected unless you set
`INJECT_BITBUCKET_METADATA=true`. This prevents v2 from silently coupling your chart to
Bitbucket-specific values that your chart may not even declare — a bug reported in issue #16.

The `INJECT_BITBUCKET_METADATA` setting is **tri-state** in v2:

| Value | Behaviour |
|-------|-----------|
| `true` | Injects all five `bitbucket.*` values (v1 parity). |
| `false` | No injection. No warning. |
| unset (default) | No injection. Detection WARN fires if `values.yaml` declares `bitbucket:`. |

### Detection WARN (META-03)

When `INJECT_BITBUCKET_METADATA` is unset (neither `true` nor `false`) and the resolved
chart's `values.yaml` contains a top-level `bitbucket:` key, the pipe emits a one-time
warning before the upgrade:

```text
WARN  meta.bitbucket_values_detected_without_opt_in  chart=<chart>
      hint="Set INJECT_BITBUCKET_METADATA=true (v1 behaviour) or INJECT_BITBUCKET_METADATA=false
      (silence this warning and skip injection)"
```

The warning fires on every pipe run until you set the env var explicitly. It is not an error
— the upgrade continues with no `bitbucket.*` values injected.

Respond by:
- Setting `INJECT_BITBUCKET_METADATA: "true"` → restores v1 behaviour for charts that depend
  on those values.
- Setting `INJECT_BITBUCKET_METADATA: "false"` → silences the warning, accepts no injection.
  Useful when your chart declares `bitbucket:` defaults in `values.yaml` that you never
  override from Bitbucket Pipelines.

### Before / after example

**v1.x pipeline (bare invocation — implicit injection):**

```yaml
# bitbucket-pipelines.yml (v1.x)
script:
  - pipe: docker://yvogl/aws-eks-helm-deploy:1.3.0
    variables:
      CLUSTER_NAME: "my-cluster"
      RELEASE_NAME: "my-app"
      CHART: "charts/my-app"
      NAMESPACE: "production"
      # No INJECT_BITBUCKET_METADATA needed — v1 always injects
```

After `helm get values my-app -n production` in v1.x you would see:

```yaml
bitbucket:
  bitbucket_build_number: "42"
  bitbucket_commit: "abc123"
  bitbucket_repo_slug: "my-app"
  bitbucket_step_triggerer_uuid: "{uuid}"
  bitbucket_tag: ""
```

**v2.0 pipeline (explicit opt-in):**

```yaml
# bitbucket-pipelines.yml (v2.0)
script:
  - pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2
    variables:
      CLUSTER_NAME: "my-cluster"
      RELEASE_NAME: "my-app"
      CHART: "charts/my-app"
      NAMESPACE: "production"
      INJECT_BITBUCKET_METADATA: "true"   # explicit opt-in — same output as v1
```

Omitting `INJECT_BITBUCKET_METADATA` in v2 produces NO `bitbucket.*` keys in
`helm get values` output. The META-03 detection WARN fires if your chart declares
`bitbucket:` in `values.yaml` and the flag is unset.

---

## SET and VALUES env var syntax (MIG-02)

### v1.x: space-separated positional list

In v1.x, `SET` and `VALUES` were parsed by shell word-splitting. Multiple values were
space-separated within a single string:

```yaml
# v1.x — space-separated
variables:
  SET: "image.tag=v1.2.3 replicaCount=3"
  VALUES: "values-production.yaml values-secrets.yaml"
```

### v2.0: comma-separated list (JSON-array fallback)

v2 uses `_CommaListEnvSource` (a pydantic-settings extension in `settings.py`) that accepts:

1. **Comma-separated:** `SET="key1=val1,key2=val2"` → `["key1=val1", "key2=val2"]`
2. **JSON array:** `SET='["key1=val1","key2=val2"]'` → `["key1=val1", "key2=val2"]`
3. **Empty string:** `SET=""` → `[]`

```yaml
# v2.0 — comma-separated (recommended)
variables:
  SET: "image.tag=v1.2.3,replicaCount=3"
  VALUES: "values-production.yaml,values-secrets.yaml"
```

```yaml
# v2.0 — JSON-array form (interoperable with CI tooling that builds arrays)
variables:
  SET: '["image.tag=v1.2.3","replicaCount=3"]'
```

### Startup WARN when v1 syntax is detected

The v2.0 pipe scans `os.environ` at startup for `SET` and `VALUES` containing spaces in a
way that suggests v1 space-separated usage. If a v1-style value is detected, the pipe emits:

```text
WARN  mig.v1_env_var_detected  name="SET"
      hint="Rewrite SET to comma-separated format: SET=key1=val1,key2=val2"
```

The WARN is informational, not an error. The pipe continues with the v2 comma-separated
parser. Split values on spaces in v1 format will NOT be automatically split in v2 — you
must rewrite `SET` and `VALUES` to comma-separated form.

**Before / after migration:**

```yaml
# Before (v1.x):
SET: "image.tag=v1.2.3 replicaCount=3 ingress.enabled=true"

# After (v2.0):
SET: "image.tag=v1.2.3,replicaCount=3,ingress.enabled=true"
```

---

## ACTION=diff — preview changes (PIPE-02/03)

### Basic diff

Set `ACTION: "diff"` to preview what would change in the cluster without mutating anything.
The pipe runs `helm diff upgrade` using the bundled `helm-diff` 3.10 plugin. The diff is
printed to stdout with `kind: Secret` payloads automatically redacted (SEC-06) — secret
bytes never reach your pipeline logs or PR comments.

Required env vars: `CLUSTER_NAME`, `CHART`, `RELEASE_NAME`, `NAMESPACE`.

```yaml
# bitbucket-pipelines.yml — diff step
script:
  - pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2
    variables:
      ACTION: "diff"
      CLUSTER_NAME: "my-cluster"
      RELEASE_NAME: "my-app"
      CHART: "charts/my-app"
      NAMESPACE: "production"
      SET: "image.tag=$BITBUCKET_COMMIT"
```

Exit code `0` means diff ran successfully (even if there are no changes). Non-zero means
helm or diff encountered an error (chart resolution failure, cluster connectivity issue).

### Post diff as Bitbucket PR comment (PIPE-03)

When running in a Bitbucket Pull-Request build (`$BITBUCKET_PR_ID` is set automatically by
Bitbucket Pipelines), you can post the diff as a PR comment by setting
`POST_DIFF_AS_COMMENT: "true"` and providing a `BITBUCKET_TOKEN`.

The pipe posts a **single comment per PR** using the marker
`<!-- aws-eks-helm-deploy:diff -->`. Subsequent runs on the same PR **update** (PUT) the
existing comment rather than posting a new one, so the PR comment stays clean and reflects
the latest diff.

Required Bitbucket token permissions: `pullrequest:write` scope.

```yaml
# bitbucket-pipelines.yml — diff with PR comment
script:
  - pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2
    variables:
      ACTION: "diff"
      CLUSTER_NAME: "my-cluster"
      RELEASE_NAME: "my-app"
      CHART: "charts/my-app"
      NAMESPACE: "production"
      SET: "image.tag=$BITBUCKET_COMMIT"
      POST_DIFF_AS_COMMENT: "true"
      BITBUCKET_TOKEN: "<your-bitbucket-api-token>"   # store in Bitbucket repository variables
```

Store `BITBUCKET_TOKEN` as a **secured repository variable** in Bitbucket (Repository
settings → Repository variables → mark as Secured). The pipe never logs the literal token
value (`bitbucket_token` is a `SecretStr` in `settings.py`).

If the Bitbucket API returns a 4xx or 5xx response, the pipe emits a WARN log with the
token scrubbed from the response body and continues. PR-comment posting is observability,
not critical path — your diff still succeeds even if the comment cannot be posted.

---

## ACTION=rollback + SAFE_UPGRADE — safe rollback only (PIPE-04/05)

### Deploying with SAFE_UPGRADE=true

`SAFE_UPGRADE=true` causes `helm upgrade --install` to run with `--wait`, `--atomic`, AND
`--description "pipe:safe-upgrade"`. The description marker is persisted in helm's release
history and serves as the safety token for rollback pre-flight.

When `--atomic` is set, helm rolls back the release automatically on a failed upgrade. The
combination of `--wait` + `--atomic` ensures that only a deployment that passed Kubernetes
readiness checks leaves a `pipe:safe-upgrade` description in history.

```yaml
# bitbucket-pipelines.yml — upgrade with SAFE_UPGRADE=true
script:
  - pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2
    variables:
      ACTION: "upgrade"
      CLUSTER_NAME: "my-cluster"
      RELEASE_NAME: "my-app"
      CHART: "charts/my-app"
      NAMESPACE: "production"
      SET: "image.tag=$BITBUCKET_COMMIT"
      SAFE_UPGRADE: "true"
```

Note: when `SAFE_UPGRADE=true`, the pipe owns the helm release `--description` field. You
cannot combine `SAFE_UPGRADE=true` with a custom `--description` in v2.0. Append-semantics
for custom descriptions are deferred to v2.1+.

### Rolling back to a safe revision

`ACTION=rollback` + `REVISION=<n>` rolls back a release to a specific revision. Before
invoking `helm rollback`, the pipe runs a pre-flight check: it reads the helm release history
for the target revision and checks whether the description contains the substring
`pipe:safe-upgrade`.

If the substring is absent, the pipe **refuses the rollback** with exit code 4 and a clear
error message:

```text
ERROR  ChartResolutionError: Refusing rollback to revision 3 of release 'my-release' —
       that revision was NOT deployed with SAFE_UPGRADE=true (no --wait/--atomic guarantee).
       Re-deploy with SAFE_UPGRADE=true first, then retry rollback.
```

If you see this error, re-deploy the target configuration with `SAFE_UPGRADE=true` on the
upgrade step, then run the rollback step again pointing at the new revision number.

```yaml
# bitbucket-pipelines.yml — rollback step
script:
  - pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2
    variables:
      ACTION: "rollback"
      CLUSTER_NAME: "my-cluster"
      RELEASE_NAME: "my-app"
      NAMESPACE: "production"
      REVISION: "5"   # must have been deployed with SAFE_UPGRADE=true
```

The rollback step itself does NOT need `SAFE_UPGRADE=true` — the safety check is on the
**target revision's history**, not on the current pipeline step. A rollback to a
safe-upgraded revision is permitted from any pipeline step.

---

## New v2 environment variables

| Env var | Type | Default | Closes | Notes |
|---------|------|---------|--------|-------|
| `POST_DIFF_AS_COMMENT` | `bool` | `false` | PIPE-03 | Requires `BITBUCKET_TOKEN` and a PR build (`BITBUCKET_PR_ID` set by Bitbucket Pipelines). |
| `BITBUCKET_TOKEN` | `secret` | (none) | PIPE-03 | Pipe never logs the literal value (`SecretStr` in source). Store as a secured repo variable. |
| `SAFE_UPGRADE` | `bool` | `false` | PIPE-05 | Adds `--wait --atomic --description "pipe:safe-upgrade"` to upgrade argv. |
| `REVISION` | `int (≥ 0)` | (none) | PIPE-04 | Required when `ACTION=rollback`. |
| `INJECT_BITBUCKET_METADATA` | `bool \| unset` | unset | META-02/03 | Tri-state. Unset triggers detection WARN if chart `values.yaml` declares `bitbucket:`. |
| `ACTION` | `enum` | `upgrade` | PIPE-02/04 | v2 accepts `upgrade`, `diff`, `rollback`. |

---

## Quick migration checklist

- [ ] Update the image reference from `docker.io/yvogl/aws-eks-helm-deploy:1.x` to
      `ghcr.io/yves-vogl/aws-eks-helm-deploy:2` (or a pinned `:2.x.y` tag).
- [ ] Add `INJECT_BITBUCKET_METADATA: "true"` to any pipeline step whose chart uses
      `.Values.bitbucket.*` (check your `values.yaml` for a `bitbucket:` key).
- [ ] Rewrite `SET` from space-separated to comma-separated format (`SET: "k1=v1,k2=v2"`).
- [ ] Rewrite `VALUES` from space-separated to comma-separated format
      (`VALUES: "base.yaml,overrides.yaml"`).
- [ ] Change the `NAMESPACE` reference if your v1 pipeline relied on the (buggy) default
      `kube-public`; v2 defaults to `default`.
- [ ] If using OIDC authentication: see [docs/guides/oidc-setup.md](../guides/oidc-setup.md) —
      static keys win when both `AWS_ACCESS_KEY_ID` and `BITBUCKET_STEP_OIDC_TOKEN` are set
      (`static keys win` per AUTH-04 revised). Remove static keys from the step to use OIDC.
- [ ] (Optional) Add `SAFE_UPGRADE: "true"` to upgrade steps you want to be safely
      rollbackable via `ACTION=rollback`.

---

## Phase 7 will expand this guide

This guide is a Phase 5 draft. Phase 7 will polish wording, add screenshots, generate a
table of contents, add `mkdocs-material` admonitions, and integrate the guide at
`/v2/migration/v1-to-v2/` on the docs site (using `mike` for version-stamped publishing).

Phase 7 will also ship `examples/migration-v1-to-v2/` (MIG-03) — a before/after
`bitbucket-pipelines.yml` diff with line-level explanations of every required change.

Related guides:
- [OIDC setup guide (Phase 4 draft)](../guides/oidc-setup.md) — IAM trust-policy template + OIDC
  configuration walkthrough.
- [Phase 5 breaking changes source on GitHub](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/ROADMAP.md) — ROADMAP Phase 5 entry
  lists the 8 requirements addressed in this phase.

<!-- Draft authored in Phase 5; polished in Phase 7 alongside the mkdocs-material site. -->

---

## Distribution change (Phase 6 / MIG-01)

**The v2.x image is published exclusively to GitHub Container Registry.** Docker Hub is frozen at v1.3.0.

### v1.x consumers (frozen)

The Docker Hub repository `yvogl/aws-eks-helm-deploy` continues to host v1.3.0 forever. No new tags will ever be pushed there. Existing pipeline files that reference `yvogl/aws-eks-helm-deploy:1.3.0` (or `:latest`, which is permanently pinned to 1.3.0) continue to work indefinitely.

### v2.x consumers (active)

The v2.x image is at:

- `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0` — specific patch version
- `ghcr.io/yves-vogl/aws-eks-helm-deploy:2` — rolling major tag (auto-updates to the latest v2.x patch release)
- `ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` — rolling tag pointing to the latest release

For a `bitbucket-pipelines.yml` consumer, the migration is a single-line change:

```yaml
# v1.x
image: yvogl/aws-eks-helm-deploy:1.3.0

# v2.x — patch-pinned (recommended for production)
image: ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0

# v2.x — rolling major (auto-update to latest v2.x patch)
image: ghcr.io/yves-vogl/aws-eks-helm-deploy:2
```

### Why GHCR-only

- Native OIDC push from GitHub Actions eliminates long-lived Docker Hub credentials as a CI secret.
- Cosign keyless signing + SLSA build provenance + SBOM attestation are end-to-end in a single trust domain (GitHub OIDC → Fulcio → Rekor → GHCR).
- Multi-arch native runners (`ubuntu-24.04` + `ubuntu-24.04-arm`) produce reproducible `linux/amd64` + `linux/arm64` manifests.

### Verifying the v2.x image

Every v2.x release image is signed with Cosign keyless and carries SBOM attestations:

```bash
# Verify the image signature
cosign verify \
  --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/yves-vogl/aws-eks-helm-deploy:2

# Retrieve the SPDX SBOM
cosign verify-attestation --type spdxjson \
  --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/yves-vogl/aws-eks-helm-deploy:2

# Verify SLSA build provenance
gh attestation verify --owner yves-vogl ghcr.io/yves-vogl/aws-eks-helm-deploy:2
```

### Docker Hub README update (maintainer one-shot)

The following text is to be pasted verbatim into the Docker Hub repo description
at https://hub.docker.com/repository/docker/yvogl/aws-eks-helm-deploy (per
`docs/admin/repo-settings.md` §7 maintainer runbook):

```
⚠ This repository is FROZEN at v1.3.0.
v2.0+ is published to GitHub Container Registry:
  ghcr.io/yves-vogl/aws-eks-helm-deploy:2

See https://github.com/yves-vogl/aws-eks-helm-deploy for migration.
```
