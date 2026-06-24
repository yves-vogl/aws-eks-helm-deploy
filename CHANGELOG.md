# Changelog

## [2.1.0](https://github.com/yves-vogl/aws-eks-helm-deploy/compare/v2.0.0...v2.1.0) (2026-06-24)

Maintenance release on the v2.x line, ahead of the [Helm v3 EOL on 2026-11-11](https://helm.sh/docs/topics/version_skew/). Drop-in upgrade for `:2.x.y` and `:2` consumers — no env-var schema or exit-code changes, no behavioural changes beyond the underlying Helm patch.

### Features

* **helm:** bump bundled Helm from `3.18.6` → `3.21.1` (latest 3.x patch). Includes the 3.19/3.20/3.21 backport security fixes for the Go stdlib in the helm binary's bundled toolchain. ([#81](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/81))
* **deps:** bump bundled helm-diff plugin from `3.10.0` → `3.15.10`. Backward-compatible with Helm 3.x; the 3.15.x line also adds Helm v4 compat for forward portability. ([#81](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/81))
* **deps:** bump bundled `uv` from `0.11.21` → `0.11.24` (latest 0.11.x patch). ([#81](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/81))
* **deps:** advance Python `boto3` / `botocore` / `boto3-stubs` to the latest 1.43.x patch; `coverage` / `ruff` / `pymdown-extensions` likewise to the latest within their current major lines. No constraint-floor changes — the existing `~=` pins continue to govern. ([#81](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/81))

### Stays unchanged

* `cosign` stays at `2.6.3` — already the latest 2.x patch.
* Python base image, `bitbucket-pipes-toolkit`, `Jinja2`, `PyYAML`, `structlog`, `pydantic-settings`: no new release within their current major required a bump.
* Pipe public surface: env-var schema, exit-code map, structured-log shape, action verbs, chart-source URI schemes, SAFE_UPGRADE argv tail. All unchanged.

### Migration

Drop-in for v2.x consumers — no action required. Pull the new image:

```yaml
image: ghcr.io/yves-vogl/aws-eks-helm-deploy:2.1.0   # or :2 (rolling)
```

The `:2` floating tag now points to `:2.1.0`. The `:2` tag stays maintained on the v2.x line through Helm v3 EOL on 2026-11-11; thereafter consumers should bump to the `:3` line.

### Note

The v3.0.0 major release prep (Helm 4.2.2 + Cosign 3.1.1) is being staged on the `main` branch separately and launches in August 2026 — see [`docs/migration/v2-to-v3.md`](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/docs/migration/v2-to-v3.md) and [ADR-0010](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/docs/adr/0010-helm-v4-migration.md). The v2.x line and the v3.x line evolve in parallel until then.

## [2.0.0](https://github.com/yves-vogl/aws-eks-helm-deploy/releases/tag/v2.0.0) (2026-06-23)

Initial v2 GA release on GHCR. v1.x is frozen at v1.3.0 on Docker Hub.

See the [v2.0.0 GitHub Release](https://github.com/yves-vogl/aws-eks-helm-deploy/releases/tag/v2.0.0) for the full v2.0.0 changelog.

---

## v1.x history (Docker Hub, frozen)

Note: version releases in the 0.x.y range may introduce breaking changes.

## 1.3.0

- minor: Upgrading all dependencies to the latest stable version

## 1.2.1

- patch: Add helm timeout configurable #15

## 1.2.0

- minor: Support for create_namespace

## 1.1.0

- minor: Upgrade of dependencies. Do not require local Chart.yml

## 1.0.2

- patch: Add support for --wait

## 1.0.1

- patch: Changed to match contribution requirements

## 1.0.0

- major: Initial release
