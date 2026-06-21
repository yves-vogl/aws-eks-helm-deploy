---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: project contributors, CI maintainers
---

# release-please-action over semversioner for release automation

## Context and Problem Statement

v1 used `semversioner` with a hand-curated `.changes/` directory: every PR added a YAML fragment describing its change, and a manual `semversioner release` command consolidated them into a version bump + CHANGELOG entry. The ceremony was fragile (PRs forgot the fragment; merges produced duplicate entries; the release step was a manual command). For v2 we want strict Conventional Commits enforcement, automated release-PR generation, and a GitHub-native release flow that composes with cosign signing and SLSA attestation.

## Decision Drivers

* Conventional Commits as the single source of truth for version bumps and changelog entries.
* Release-PR model — a bot maintains an open PR that aggregates the next release; merging it cuts the version.
* Eliminate `.changes/` ceremony — fewer "I forgot the changelog" round-trips.
* GitHub-native release creation — the release tag, the GitHub Release object, and the changelog are all produced in one workflow.
* Composes cleanly with downstream cosign-signing and SLSA-attestation steps in the same release workflow.

## Considered Options

* Keep `semversioner` with `.changes/` directory and a manual release command.
* `release-please-action` v4 with `release-type: python`.
* Custom shell/Python script that reads Conventional Commits and bumps version.

## Decision Outcome

Chosen option: **"release-please-action v4 with `release-type: python`"**, because it covers every requirement (Conventional Commits parsing, release-PR maintenance, version bumping, CHANGELOG generation, GitHub Release creation, Python version-file syncing) with an off-the-shelf, widely-adopted GitHub Action. The release PR updates `pyproject.toml`, `CHANGELOG.md`, and `pipe.yml` (image tag pin for the Bitbucket Pipe Marketplace listing) in one commit; merging it triggers the downstream build → sign → attest → publish chain.

### Consequences

* Good, because Conventional Commits are now mechanically enforced rather than aspirational.
* Good, because the release-PR is always-on; contributors see at any time which version comes next and what is in it.
* Good, because GitHub Release objects are created automatically with the right tag, body, and asset list.
* Bad, because contributors must learn Conventional Commits (mitigated by CONTRIBUTING.md examples + commit-message templates).
* Bad, because release-please rewrites the release PR on each merge to main; that PR's review history is ephemeral.

## Pros and Cons of the Options

### Keep `semversioner`

* Good, because zero migration cost.
* Bad, because manual `.changes/` fragments are forgotten or duplicated.
* Bad, because the release step is a human-run command, not a workflow.
* Bad, because no native composition with GitHub Releases.

### `release-please-action` v4

* Good, because covers every requirement (parse, version, changelog, release object).
* Good, because GitHub-native and composes with cosign + SLSA in the same workflow.
* Good, because `release-type: python` knows about `pyproject.toml` version syncing.
* Neutral, because contributors must learn Conventional Commits.

### Custom script

* Good, because total control.
* Bad, because reinvents a maintained upstream tool (NIH).
* Bad, because we own every bug forever.
* Bad, because no community maintenance, no GitHub Action ecosystem integration.

## More Information

* Sources: [Phase 6 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/06-release-pipeline-supply-chain/06-CONTEXT.md), REQUIREMENTS.md CI-02 (release-please-action), 07-RESEARCH.md C2 (release-please version pin).
* Cross-references: ADR-0001 (forge primacy — release-please is GitHub-only), ADR-0003 (cosign — same workflow as release), ADR-0002 (clean break — v2 is the version line release-please owns).
* NIH check: `release-please-action` is the upstream maintained tool from Google's open-source release-automation team; reimplementing it would be NIH.
