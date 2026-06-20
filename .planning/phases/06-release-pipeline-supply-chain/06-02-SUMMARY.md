---
phase: 06-release-pipeline-supply-chain
plan: "02"
subsystem: release-versioning
tags: [release-please, ghcr, pipe-yml, workflow, structural-test, ci-02]
dependency_graph:
  requires: []
  provides:
    - .release-please-config.json
    - .release-please-manifest.json
    - .github/workflows/release-please.yml
    - tests/structural/test_release_please_config.py
  affects:
    - pipe.yml
tech_stack:
  added:
    - "googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7 (v5.0.0)"
  patterns:
    - "release-please extra-files with type=yaml + jsonpath for pipe.yml image field rewrite"
    - "SHA-pinned GitHub Actions workflow (40-char digest, no mutable tags)"
    - "Structural pytest assertions for JSON config schema (pytestmark=unit)"
key_files:
  created:
    - .release-please-config.json
    - .release-please-manifest.json
    - .github/workflows/release-please.yml
    - tests/structural/test_release_please_config.py
  modified:
    - pipe.yml
decisions:
  - "D1: release-please-action v5.0.0 (SHA 45996ed1...) — not v4 as CONTEXT originally stated (RESEARCH C2 correction)"
  - "D1: no auto-merge on Release PR — manual squash-merge by Yves is the single human review gate"
  - "D5: default changelog-types accepted — no customization in config"
  - "RESEARCH C2 applied: googleapis/release-please-action@v5.0.0, not v4"
  - "Open Question 2 CLOSED: pipe.yml image field updated to GHCR baseline in this plan (Task 3)"
  - "bump-minor-pre-major: false + bump-patch-for-minor-pre-major: false for pre-major release control"
  - "include-v-in-tag: true so tags are v2.0.0 not 2.0.0 (existing convention)"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 1
---

# Phase 6 Plan 02: release-please Config Bootstrap Summary

Bootstrap release-please as the release-versioning source-of-truth: JSON config, version manifest, driver workflow, pipe.yml GHCR migration, and structural schema gates.

## What Was Built

Three pieces of release-please configuration plus a pipe.yml migration and a structural test gate:

1. **`.release-please-config.json`** — declares the D1 contract: `release-type: python`, `package-name: aws-eks-helm-deploy`, `extra-files` block that wires `pipe.yml`'s `image:` field to release-please's YAML jsonpath rewriter. Full field rationale below.

2. **`.release-please-manifest.json`** — seeds version baseline at `2.0.0-rc.0`. release-please reads this on every workflow run to determine the next bump. The `"."` key denotes the root package (standard single-package shape).

3. **`.github/workflows/release-please.yml`** — driver workflow on `push: branches: [main]`. Opens-or-updates the Release PR as Conventional Commits accumulate. Does NOT auto-merge (D1). Permissions are minimal: `contents: write` + `pull-requests: write` only — no `id-token: write`, `packages: write`, or `attestations: write` (those belong to `release.yml`, Plans 06-03/04).

4. **`pipe.yml` (modified)** — one-time manual edit: `yvogl/aws-eks-helm-deploy:1.3.0` (Docker Hub, frozen v1.x) → `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0-rc.0` (GHCR, matches manifest baseline). After the first Release PR merges, release-please maintains this field via the `extra-files` config.

5. **`tests/structural/test_release_please_config.py`** — 8 structural tests (CI-02 schema gate): config exists, manifest exists, JSON is valid, required keys present, `release-type: python`, `package-name: aws-eks-helm-deploy`, `extra-files` includes `pipe.yml` with correct `type`/`jsonpath`, manifest seeds `2.0.0-rc.0`.

## Config Field Rationale

| Field | Value | Why |
|-------|-------|-----|
| `release-type` | `python` | Tells release-please to bump `[project].version` in `pyproject.toml` |
| `package-name` | `aws-eks-helm-deploy` | Used in Release PR titles and tag prefix |
| `bump-minor-pre-major` | `false` | Pre-major behavior: `feat:` does NOT auto-bump minor (we're at 2.0.0-rc.0; want explicit control) |
| `bump-patch-for-minor-pre-major` | `false` | Symmetric with above — pre-major patch bumps are also explicit |
| `include-component-in-tag` | `false` | Single-package repo; no component prefix in tag |
| `include-v-in-tag` | `true` | Tags are `v2.0.0` not `2.0.0` (matches existing project convention) |
| `draft` | `false` | Release is published immediately when merged (not as a draft) |
| `prerelease` | `false` | First full release is not marked pre-release by release-please |
| `changelog-types` | (not set) | Default D5: `feat` → minor, `fix` → patch, `feat!`/`BREAKING CHANGE` → major |
| `extra-files[0]` | `{type: yaml, path: pipe.yml, jsonpath: $.image}` | release-please rewrites `image:` field to the new version on every release PR |

`changelog-types` is intentionally absent (D5 decision — accept release-please defaults, no bikeshedding).

## Open Question 2 from 06-RESEARCH.md — CLOSED

The research file noted uncertainty about which plan would perform the one-time `pipe.yml` image field update from Docker Hub to GHCR. This plan (06-02, Task 3) resolves it: the field is updated to `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0-rc.0` as the pre-release-please bootstrap. After the first Release PR merges, release-please takes over via the `extra-files` config.

## pipe.yml Migration Note

This is a breaking change in the v2.0 distribution wire format:
- **v1.x consumers** continue to pull `yvogl/aws-eks-helm-deploy:1.3.0` from Docker Hub (frozen forever at that tag).
- **v2.0+ consumers** pull `ghcr.io/yves-vogl/aws-eks-helm-deploy:2` (rolling major tag, added in Plans 06-03/04) or specific tags.

The Docker Hub `yvogl` namespace repo is frozen. The Bitbucket Pipe Marketplace listing reads `pipe.yml`'s `image:` field to resolve the container to run — so the migration makes the Marketplace automatically pick up the v2 GHCR image when consumers reference this pipe.

## Note for Plan 06-10

After the accumulated Phase 6 commits land on `main` and release-please runs for the first time, the Release PR will target `v2.0.0` (graduating from `2.0.0-rc.0`). Document in `docs/admin/repo-settings.md` as part of the release-cut runbook:

> The first release-please Release PR will propose `v2.0.0`. Review the auto-generated `CHANGELOG.md` for accuracy (all Phase 4/5/6 Conventional Commit history since the last manual release). Squash-merge to trigger `release.yml` (Plan 06-03 + 06-04).

## Deviations from Plan

None — plan executed exactly as written.

One clarification on the verify step: the plan included `! grep -E 'id-token:\s*write' .github/workflows/release-please.yml` as a check. This check matched a comment in the workflow header (`# id-token:write is therefore NOT requested here`). The actual `permissions:` block contains no `id-token: write` entry — the security invariant is correctly satisfied. The comment text triggered the grep pattern. Documented here for transparency; no code change needed.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: JSON config + manifest + structural test | `23c537f` | `.release-please-config.json`, `.release-please-manifest.json`, `tests/structural/test_release_please_config.py` |
| Task 2: release-please.yml driver workflow | `c476064` | `.github/workflows/release-please.yml` |
| Task 3: pipe.yml GHCR migration | `65b102a` | `pipe.yml` |

## Quality Gates Passed

- `uv run pytest tests/structural/test_release_please_config.py -x --no-cov` — 8/8 pass
- `uv run pytest tests/structural/test_workflow_digest_pins.py -x --no-cov` — 4/4 pass (new workflow covered)
- `uv run pytest tests/structural -q --no-cov` — 19/19 pass
- `uv run pytest tests/unit -q --no-cov` — 469/469 pass (no regression)
- `uv run mypy --strict src/aws_eks_helm_deploy` — 0 errors
- `uv run ruff check src/ tests/ scripts/` — clean
- `grep -F '45996ed1f6d02564a971a2fa1b5860e934307cf7' .github/workflows/release-please.yml` — 1 hit
- `python -c "import json; data=json.load(open('.release-please-config.json')); assert data['release-type']=='python'"` — passes
- `python -c "import yaml; data=yaml.safe_load(open('pipe.yml')); assert data['image'].startswith('ghcr.io/yves-vogl/aws-eks-helm-deploy:')"` — passes
- `grep -E 'uses:.*@(v[0-9]+|main|master|latest)$' .github/workflows/release-please.yml` — 0 hits (all SHA-pinned)
- Pre-commit hooks — passed on all 3 commits

## Self-Check: PASSED

- `.release-please-config.json` exists and is valid JSON with required keys
- `.release-please-manifest.json` exists and seeds `2.0.0-rc.0`
- `.github/workflows/release-please.yml` exists, YAML-valid, both `uses:` SHA-pinned
- `tests/structural/test_release_please_config.py` exists, 8 tests pass
- `pipe.yml` `image:` field starts with `ghcr.io/yves-vogl/aws-eks-helm-deploy:`
- Commits `23c537f`, `c476064`, `65b102a` all exist in git log
