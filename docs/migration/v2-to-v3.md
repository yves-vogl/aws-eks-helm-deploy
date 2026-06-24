# v2 → v3 Migration Guide

> **Status:** Preview. v3.0.0 is content-frozen on `main` ahead of the **August 2026** launch window. This page is the consumer-facing migration playbook; pin the existing `:2` floating tag until the launch announcement.

[TOC]

!!! tip "TL;DR"
    The runtime image bumps **Helm 3.x → 4.2.2** and **Cosign 2.x → 3.1.1**. The pipe's env-var schema, exit-code map, and chart-source semantics are unchanged. The only consumer-visible behavioural change is in `SAFE_UPGRADE=true` deploys — Helm v4 uses the kstatus-based `watcher` wait strategy instead of the helm-3 resource-poll wait. For most pipelines, the migration is a one-line image-tag change: `:2` → `:3`.

v3.0.0 is a SemVer-major release driven by the **bundled-binary majors** rather than by any change in the pipe's own contract. The pipe's public surface (env vars, exit codes, structured-log shape, chart-source URI schemes, action verbs) is fully forward-compatible from v2.0. The bump exists so consumers can opt-in to the helm-v4 + cosign-v3 runtime deliberately — see [ADR-0010](../adr/0010-helm-v4-migration.md) for the rationale.

---

## Breaking changes at a glance

| Change | v2.x (helm 3.18.6 / cosign 2.6.3) | v3.0.0 (helm 4.2.2 / cosign 3.1.1) | Reference |
|--------|-------|-------|-----------|
| Bundled Helm | `3.18.6` | `4.2.2` | [ADR-0010](../adr/0010-helm-v4-migration.md) |
| Bundled Cosign | `2.6.3` | `3.1.1` | PR #71 |
| Bundled helm-diff plugin | `3.10.0` | `3.15.10` | PR #71 |
| `SAFE_UPGRADE=true` wait strategy | helm-3 resource-poll wait | **helm-4 kstatus-based `watcher` wait** | helm v4.2.2 `pkg/cmd/flags.go::AddWaitFlag` |
| Internal upgrade argv tail (advisory) | `--wait --atomic --description "pipe:safe-upgrade"` | `--wait --rollback-on-failure --description "pipe:safe-upgrade"` | helm v4.2.2 `pkg/cmd/upgrade.go::MarkDeprecated("atomic", …)` |
| Image-tag floating policy | `:2` rolling within v2.x | `:3` rolling within v3.x; `:2` frozen at last helm-3 build through **2026-11-11** | This guide §"Tag policy" |
| `trivy-image` CI gate | advisory until v3.0.0 prep work | **hard gate** in the v3 release | PR #71 |

The pipe's public API (env vars, exit codes, structured-log keys, action verbs, chart-source URI schemes) is **fully unchanged** from v2.0. If your pipeline does not pin to `:2` exclusively and you do not parse Helm CLI stderr from the pipe's logs, the migration is a one-line `image:` swap.

---

## Helm v3 → v4 — the headline runtime change

!!! warning "Breaking change"
    The bundled Helm binary jumps from major v3 to major v4. The pipe's `helm upgrade --install` surface is preserved (chart source, release name, namespace, set-string injection, `--history-max`, `--timeout`), but Helm v4 changes the **wait strategy** for `SAFE_UPGRADE=true` deploys and renames the `--atomic` flag to `--rollback-on-failure` (the pipe migrates to the canonical v4 name internally).

### Why now

Helm v3 enters **end-of-life on 2026-11-11** ([Helm Version Support Policy](https://helm.sh/docs/topics/version_skew/)). After that date, no further security backports land on the v3 branch. v3.0.0 of this pipe is published five months ahead of the EOL so consumers have a controlled migration window instead of a rushed EOL-day bump.

### What changed under the hood

Helm v4 introduces a typed `WaitStrategy` enum for the `--wait` flag (`watcher` / `hookOnly` / `legacy`). Bare `--wait` still works (resolved to `watcher` via `NoOptDefVal`) — so the pipe's argv stays compatible — but the **default semantics** of the watcher are kstatus-based ([kstatus library](https://github.com/kubernetes-sigs/cli-utils/tree/master/pkg/kstatus)) rather than helm-3's resource-poll loop. In practice:

- **Custom-resource readiness**: kstatus watches CR status fields the helm-3 poller did not understand. If your charts include custom resources with `status.conditions`, the watcher correctly waits for `Ready=True` instead of declaring success on initial CR creation.
- **Stderr output during wait**: the lines emitted by `helm upgrade --wait` are different in v4. Pipelines that grep for specific helm-3 wait messages (e.g. `"beginning wait for"` or specific resource-name patterns) may need to update.
- **Timing characteristics**: kstatus polling cadence is event-driven rather than fixed-interval. For most charts the wall-clock difference is small, but pipelines with very tight `--timeout` windows may want to widen them by 10-20 % during the v3 ramp.

### What changed at the argv layer

When you set `SAFE_UPGRADE=true`, the pipe internally appends a fixed argv tail to `helm upgrade --install`:

| | argv tail |
|--|--|
| **v2.x (helm 3)** | `--wait --atomic --description "pipe:safe-upgrade"` |
| **v3.0.0 (helm 4)** | `--wait --rollback-on-failure --description "pipe:safe-upgrade"` |

Helm v4 keeps `--atomic` as a deprecated alias for `--rollback-on-failure` (`pkg/cmd/upgrade.go::MarkDeprecated`), but emits a stderr WARNING on every invocation. The pipe migrates to the canonical name to avoid the per-run warning noise.

**The `SAFE_UPGRADE_DESCRIPTION = "pipe:safe-upgrade"` marker is intentionally preserved.** The `RollbackAction` pre-flight check searches release-history descriptions for that substring before authorising a rollback — so releases tagged by older helm-3 pipe builds remain rollback-safe under v3.0.0. You do NOT need to redeploy historical releases to keep `ACTION=rollback` working.

### What did NOT change

- Chart-source URI schemes (`local://`, `repo://`, `oci://`) — unchanged.
- `ACTION=upgrade`, `ACTION=diff`, `ACTION=rollback` semantics — unchanged.
- `--set-string` / `--set-json` injection paths (META-01) — unchanged.
- `--history-max`, `--timeout`, `--namespace`, `--create-namespace` passthrough — unchanged.
- OCI registry auth via `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` — unchanged.
- The `helm-diff` plugin name (`name: "diff"`) and the `helm diff upgrade` subcommand the pipe invokes for `ACTION=diff` — unchanged.

---

## Cosign v2 → v3 — supply-chain bump

!!! warning "Breaking change"
    Image signing and verification use Cosign v3.1.1 (was 2.6.3). The pipe's cosign invocation surface (`verify`, `--certificate-identity`, `--certificate-oidc-issuer`) is identical between v2 and v3 — no consumer changes required for verifying v3.0.0+ images.

The v3 image is signed and the SBOM attestations are published with cosign 3.1.1 in the release pipeline. If you run `cosign verify` against v3.0.0 images, **use cosign 3.x on your end** for forward-compat — older cosign 2.x clients can still verify v3-signed images (the underlying Sigstore bundle format is compatible), but Sigstore's own recommendation is to track the major version.

```bash
# Same command shape, whether you run cosign 2.x or 3.x
cosign verify \
  --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/yves-vogl/aws-eks-helm-deploy:3
```

---

## Tag policy

!!! tip "Pin to `:3.0.0` for production. `:3` floats; `:2` freezes."
    The `:3` rolling tag auto-updates to the latest v3.x patch. `:2` stays frozen at the last helm-3 build through **2026-11-11** (Helm v3 EOL) and is sunset afterwards. `:latest` always points to the freshly-published release across any major and is reserved for ad-hoc inspection — never use it in CI.

### v3.x consumers (new active line)

```yaml
# bitbucket-pipelines.yml — production (patch-pinned, recommended)
image: ghcr.io/yves-vogl/aws-eks-helm-deploy:3.0.0

# bitbucket-pipelines.yml — rolling v3 major (auto-update within v3.x)
image: ghcr.io/yves-vogl/aws-eks-helm-deploy:3
```

### v2.x consumers (frozen at the last helm-3 build until 2026-11-11)

The `:2` tag continues to resolve to the most recent v2.x patch on GHCR through Helm v3 EOL (2026-11-11). After that date, no new images are published under `:2`. Pipelines that need to remain on Helm v3 until then can continue pinning to `:2` (or to a specific `:2.x.y` patch) with no action required.

```yaml
# bitbucket-pipelines.yml — staying on v2.x temporarily (until 2026-11-11)
image: ghcr.io/yves-vogl/aws-eks-helm-deploy:2
```

After 2026-11-11, `:2` consumers should plan to either bump to `:3` (recommended) or accept that they are running an unsupported helm-3 binary with no upstream security backports.

### v1.x consumers (frozen indefinitely on Docker Hub)

Unchanged from the v2 guide — see [§"Distribution change"](v1-to-v2.md#distribution-change-phase-6--mig-01) in the v1 → v2 migration. The Docker Hub freeze at `yvogl/aws-eks-helm-deploy:1.3.0` is permanent.

---

## Verification

### kstatus wait — observable change

After upgrading to v3, run a `SAFE_UPGRADE=true` deploy and compare the `helm upgrade` stderr against a v2 baseline. Differences you should expect:

- Wait-progress lines reference resources by their kstatus condition (e.g. `Reconciling`, `Ready`) instead of the helm-3 polling messages.
- Custom-resource readiness is correctly observed — if your charts include CRs with `status.conditions`, the watcher now waits for them.

If your CI parses Helm stderr (e.g. for deploy-monitoring metrics), capture a v2 + v3 sample of the same chart and update parsers as needed. The pipe's own structured logs (the JSON lines on stdout) are unchanged.

### Cosign verification

```bash
# Latest v3 image
cosign verify \
  --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/yves-vogl/aws-eks-helm-deploy:3

# Retrieve the SPDX SBOM
cosign verify-attestation --type spdxjson \
  --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/yves-vogl/aws-eks-helm-deploy:3

# Verify SLSA build provenance
gh attestation verify --owner yves-vogl ghcr.io/yves-vogl/aws-eks-helm-deploy:3
```

---

## Quick migration checklist

1. **Pin to v3 explicitly** — change the `image:` in your `bitbucket-pipelines.yml` from `ghcr.io/yves-vogl/aws-eks-helm-deploy:2` (or `:2.x.y`) to `ghcr.io/yves-vogl/aws-eks-helm-deploy:3.0.0`. The `:3` floating tag is also available after launch.
2. **Run a non-production deploy first** — confirm the kstatus-wait stderr output does not break any downstream log parsing or alerting you rely on.
3. **Widen `--timeout` if you depend on tight wait windows** — kstatus polling cadence differs from the helm-3 resource-poll loop; for tightly-timed deploys, give 10-20 % more wall-clock budget during the ramp.
4. **No env-var changes required.** Specifically: do NOT change `SAFE_UPGRADE`, `ACTION`, `CHART`, `CHART_VERSION`, `RELEASE_NAME`, `NAMESPACE`, `CREATE_NAMESPACE`, `HISTORY_MAX`, `REVISION`, `DRY_RUN`, `REPO_URL`, `REGISTRY_USERNAME`, `REGISTRY_PASSWORD`, OIDC settings, or any `SET_*` / `VALUES_*` settings. The v2 schema is preserved.
5. **Historical `SAFE_UPGRADE=true` releases remain rollback-safe.** The `pipe:safe-upgrade` marker is preserved across the migration, so `ACTION=rollback` works against releases tagged by older v2.x builds without redeployment.
6. **Bump your local `cosign` to 3.x (optional)** — v2.x cosign clients still verify v3-signed images, but Sigstore recommends tracking the major.
7. **`:2` continues to work through 2026-11-11.** If you cannot migrate immediately, the v2.x line stays available until Helm v3 EOL.

---

## Launch timeline

| Date | Event |
|------|-------|
| 2026-06-24 | Content freeze. PR #71 merged to `main`. release-please opens a Release PR for v3.0.0 — **held until August 2026**. |
| ~ August 2026 | v3.0.0 release PR merged → `v3.0.0` tag published → `:3.0.0`, `:3`, `:latest` floating tags updated on GHCR. |
| 2026-11-11 | Helm v3 EOL. `:2` floating tag freezes at the last published v2.x patch. New v2.x patches stop. |
| 2026-11-12 onwards | `:2` consumers should bump to `:3` or document an explicit accept-risk for running an unsupported helm-3 runtime. |

For the rationale behind the August soak window and the SemVer-major bump, see [ADR-0010](../adr/0010-helm-v4-migration.md).
