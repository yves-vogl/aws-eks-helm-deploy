# Changelog

## [3.0.0](https://github.com/yves-vogl/aws-eks-helm-deploy/compare/v2.0.0...v3.0.0) (2026-08)

### ⚠ BREAKING CHANGES

* **helm:** The bundled Helm binary jumps from major **v3.18.6 → v4.2.2** ahead of the [Helm v3 EOL on 2026-11-11](https://helm.sh/docs/topics/version_skew/). The pipe's env-var schema and exit-code map are unchanged, but the kstatus-based `watcher` wait strategy in Helm v4 changes the operational characteristics of `SAFE_UPGRADE=true` deploys (different stderr output during readiness, possibly different timing). Consumers should bump to the `:3` floating tag explicitly. The `:2` floating tag stays frozen at the last helm-3 build through 2026-11-11, then sunsets. See [`docs/migration/v2-to-v3.md`](docs/migration/v2-to-v3.md) and [ADR-0010](docs/adr/0010-helm-v4-migration.md) for the full rationale and consumer migration playbook.

### Features

* **helm:** bump bundled Helm from 3.18.6 → 4.2.2 (latest stable, 5 months ahead of Helm v3 EOL). Migrate SAFE_UPGRADE argv tail from `--atomic` to `--rollback-on-failure` (helm v4 canonical; `--atomic` is now a deprecated alias emitting a stderr warning). `SAFE_UPGRADE_DESCRIPTION = "pipe:safe-upgrade"` marker preserved so `RollbackAction` recognises releases tagged by older helm-3 pipe builds. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **deps:** bump bundled Cosign from 2.6.3 → 3.1.1 (latest stable). Surface (`verify`, `sign --yes`, `attest --yes --predicate --type`, `--certificate-identity[-regexp]`, `--certificate-oidc-issuer`) is v3-stable. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **deps:** bump bundled helm-diff plugin from 3.10.0 → 3.15.10 (first plugin release with verified helm-v4 compat). ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))

### Bug Fixes

* **sec:** promote `trivy-image` CI gate from advisory (`continue-on-error: true`) to hard gate. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **sec:** curate `.trivyignore` for the helm 4.2.2 image (Go 1.26.3 toolchain) — 10 Go-stdlib CVE suppressions with full D2 grammar and uniform `expires=2026-12-20`. Includes CVE-2026-27145 (`x509.VerifyHostname` quadratic DoS) plus 9 carried-forward Go-stdlib CVEs that remain applicable against helm 4.2.2's pre-1.26.4 Go toolchain. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **ci:** wire release-please to the dot-prefixed config path `.release-please-config.json` + sync manifest to track the v2.0.0 GA cut. ([#73](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/73))

### Documentation

* **adr:** add **ADR-0010 — Helm v3 → v4 migration before EOL** documenting the migrate-vs-accept-risk decision, considered options, outcome, and CI confirmation gates. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **migration:** add `docs/migration/v2-to-v3.md` consumer-facing playbook — breaking changes at a glance, kstatus-wait deep-dive, `:3` / `:2` tag policy through 2026-11-11, quick migration checklist, August launch timeline. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **readme:** add v3.0.0-launch preview banner above the v2 status block. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **contributing:** document the August 2026 release lock for v3.0.0 — Release PR carries the `release-blocker:august-2026` label; maintainer-only merge after the launch window. ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))

### Continuous Integration

* **ci:** the integration test (`test_helm_version_in_cluster`) now asserts helm v4.x; the structural ADR-count test moves to 10 (covering ADR-0010). ([#71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71))
* **ci:** drop release-please `bootstrap-sha` + `release-as` one-shot fields after the v3.0.0 GA — release-please resumes standard commit-walking for v3.0.1+. ([#75](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/75))

## [2.0.0](https://github.com/yves-vogl/aws-eks-helm-deploy/releases/tag/v2.0.0) (2026-06-23)

Initial v2 GA release on GHCR. v1.x is frozen at v1.3.0 on Docker Hub. See the [v2.0.0 GitHub Release](https://github.com/yves-vogl/aws-eks-helm-deploy/releases/tag/v2.0.0) for the full v2.0.0 changelog — instated before this CHANGELOG.md came under release-please management.

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
