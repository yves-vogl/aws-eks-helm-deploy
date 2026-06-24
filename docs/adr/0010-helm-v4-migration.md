---
status: accepted
date: 2026-06-24
decision-makers: yves-vogl
consulted: claude-code (eks-deploy-expert), loop-security-engineer
informed: project contributors, downstream pipe consumers
---

# Helm v3 → v4 migration before the 2026-11-11 EOL

## Context and Problem Statement

The bundled Helm binary in the runtime image was pinned to Helm 3.18.6 through v2.0.0 and to 3.21.2 in the unreleased post-v2.0.0 main. Helm v3 enters end-of-life on **2026-11-11** ([Helm Version Support Policy](https://helm.sh/docs/topics/version_skew/)) — no further security backports after that date. Trivy scans against the helm 3.21.2 image surface 29 HIGH + 2 CRITICAL findings ([PR #68](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/68) trivy-image run, 2026-06-23), the bulk of which are transitive Go libraries that Helm v4 already bumped past. We need to decide: **migrate the pipe to Helm v4, or accept-risk and stay on an unsupported v3 line.**

## Decision Drivers

- Helm v3 EOL is a hard deadline (2026-11-11) — staying on v3 means accepting unsupported-binary risk indefinitely.
- The trivy-image gate became a hard gate in this same release line (see [Issue #67](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/67)); HIGH/CRITICAL CVE volume on v3.21.2 makes the gate unworkable without aggressive suppression.
- Helm v4 has been stable since v4.0.0 (released in 2026); chart authors and consumers have had several months to prepare.
- Only one CLI surface used by the pipe is affected by v4 breaking changes: `--atomic` is now a deprecated alias for `--rollback-on-failure` ([helm v4.2.2 `pkg/cmd/upgrade.go` L290-292](https://raw.githubusercontent.com/helm/helm/v4.2.2/pkg/cmd/upgrade.go)).
- The kstatus-based `watcher` wait strategy in helm v4 is a consumer-visible operational change for `SAFE_UPGRADE=true` deploys (different stderr lines, possibly different timing characteristics).
- The pipe's bundled-binary version is part of its public contract (consumers pin to a major tag and expect predictable behaviour) — a helm major bump should not happen silently on a `:2.x.y` patch release.

## Considered Options

* **Option A — Migrate to Helm v4 (`HELM_VERSION=4.2.2`) and bump the pipe to v3.0.0.**
* **Option B — Stay on Helm v3 until EOL, then accept unsupported runtime; release pipe v2.x patches only.**
* **Option C — Migrate to Helm v4 but keep the pipe on the v2.x line (treat the bundled-binary version as an implementation detail).**

## Decision Outcome

Chosen option: **"Option A — Migrate to Helm v4 and bump the pipe to v3.0.0"**, because it eliminates the EOL deadline as a recurring decision, clears the trivy-image gate to a workable state, and signals the kstatus-wait behavioural change to consumers via a SemVer-major bump so they can pin and opt-in deliberately. The migration is also cheap: one argv-tail rename (`--atomic` → `--rollback-on-failure`), one plugin bump (helm-diff 3.10.0 → 3.15.10), and supporting docstring + test updates — total 11 files, 107 insertions, 43 deletions.

### Consequences

* Good, because Helm v3 EOL stops being an open question — the pipe never carries an unsupported runtime.
* Good, because the trivy-image hard gate is feasible against helm 4.2.2's newer Go transitive dependencies (most v3.21.2 findings are fixed in v4's bundle).
* Good, because the SAFE_UPGRADE argv tail uses the canonical helm v4 form (`--rollback-on-failure`) and no longer emits a stderr deprecation warning on every safe upgrade.
* Good, because the `SAFE_UPGRADE_DESCRIPTION = "pipe:safe-upgrade"` marker is preserved across the migration, so historical releases tagged by helm-3 pipe builds remain rollback-safe via `RollbackAction`'s pre-flight check.
* Good, because the SemVer-major bump (pipe v3.0.0) gives consumers an explicit opt-in path; the `:2` floating tag stays frozen at the last helm-3 build through 2026-11-11 (see ADR-0002 freeze precedent).
* Bad, because consumers who tail-follow `:latest` get the kstatus-wait change automatically and may need to update brittle log-line assertions on `helm upgrade` stderr.
* Bad, because the bundled binary now requires the new argv (`--rollback-on-failure` does not exist in helm 3.x); downgrading the runtime to helm 3.x would silently break `SAFE_UPGRADE=true`. Documented inline in [`helm/client.py::_build_argv`](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/src/aws_eks_helm_deploy/helm/client.py) and locked in by the Dockerfile pin.
* Bad, because the migration accelerates the next decision point: consumers who never adopt v3 will be stranded on an EOL'd helm-3 build after 2026-11-11.

### Confirmation

- The [`integration (kind + helm)`](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.github/workflows/ci.yml) job pins the runner's Helm to `v4.2.2` matching the Dockerfile bundle, exercising the kstatus-wait code path against a real cluster.
- [`tests/unit/test_helm_client_argv.py`](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/tests/unit/test_helm_client_argv.py) asserts both that `--rollback-on-failure` is present in the SAFE_UPGRADE argv tail AND that the deprecated `--atomic` alias is NOT present (defensive; ensures the stderr deprecation warning never leaks back in).
- The [`acceptance (docker run image)`](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.github/workflows/ci.yml) job runs the built image and verifies `helm diff version` resolves the bundled helm-diff plugin against helm v4.2.2 — protects against the helm-diff/helm-major mismatch that motivated the plugin bump to 3.15.10.
- The [`trivy-image`](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.github/workflows/ci.yml) hard gate enforces "no HIGH/CRITICAL findings" — confirms the migration's CVE-curation goal is met.

## Pros and Cons of the Options

### Option A — Migrate to Helm v4, pipe v3.0.0

* Good, because covers every decision driver.
* Good, because the only required code change is `--atomic` → `--rollback-on-failure` (one line in `_build_argv`).
* Good, because helm-diff 3.15.10 is already verified compatible with helm v4 via the existing directory-copy install pattern.
* Good, because the `:2` tag freeze precedent already exists (ADR-0002 froze v1 at v1.3.0 on Docker Hub; we apply the same playbook to v2.x on GHCR through 2026-11-11).
* Neutral, because consumers must consciously bump to `:3` to adopt; this is the price of the SemVer signal.

### Option B — Stay on Helm v3 until EOL, then accept-risk

* Good, because zero migration cost in the short term.
* Good, because consumers on `:2` get no behavioural surprise.
* Bad, because after 2026-11-11 the pipe ships an unsupported binary with zero upstream security maintenance.
* Bad, because the trivy-image hard gate would need permanent suppression of any helm-3-side CVE published after EOL — operational sink, no end in sight.
* Bad, because we would still face this decision at some point — Helm v4 LTS will EOL too eventually; deferring the migration just resets the clock.

### Option C — Migrate to Helm v4, keep pipe on v2.x

* Good, because no consumer breakage signal — `:2.x.y+1` ships helm v4 transparently.
* Good, because matches the SemVer-strict reading: "the env-var schema and exit-code map didn't change."
* Bad, because the kstatus-wait behavioural change is invisible to consumers — log-line assertions and timing assumptions break silently mid-patch-release.
* Bad, because it conflates a runtime-bundle major change with a routine patch — the project's `image.bundled-component` contract becomes meaningless.
* Bad, because it sets a precedent that bundled-binary majors are "implementation details" — future runtime-major bumps (Python 3.13 → 3.14, helm v4 → v5) would face the same "should we signal this?" question with the wrong answer baked in.

## More Information

- Sources: [Issue #70](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/70) (migration tracking with full breaking-change audit table), [Issue #67](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/67) (trivy-image hard-gate motivation), [PR #71](https://github.com/yves-vogl/aws-eks-helm-deploy/pull/71) (the migration commit).
- Helm v4.0.0 release notes: https://github.com/helm/helm/releases/tag/v4.0.0
- Helm v4.2.2 source for `--atomic` deprecation: [pkg/cmd/upgrade.go L290-292](https://raw.githubusercontent.com/helm/helm/v4.2.2/pkg/cmd/upgrade.go)
- helm-diff v4-compatible release notes: https://github.com/databus23/helm-diff/releases (the v3.15.x line added helm v4 support)
- Cross-references: [ADR-0002](0002-v2-clean-break.md) (clean-break precedent for runtime-major bumps), [ADR-0009](0009-src-layout-no-compat-shims.md) (no compat shims — same philosophy applied to the helm-3 argv: we don't emit both `--atomic` and `--rollback-on-failure` for "v3+v4 compat", we pick the canonical v4 form and document the forward-incompatibility).
- Release timing: v3.0.0 is prepared on `main` after PR #71 merges; the release-please-generated Release PR is held until **August 2026** (six-week soak between content-freeze and tag-publish) — see [docs/migration/v2-to-v3.md](../migration/v2-to-v3.md) for the launch timeline.
- NIH check: we are bumping an upstream-maintained binary, not re-implementing helm. Not applicable.
