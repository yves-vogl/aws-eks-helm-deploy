# Phase 7 Context — Documentation Site & Migration Guide

**Date:** 2026-06-21
**Phase:** 7 of 7 (FINAL phase for v2.0)
**Goal (from ROADMAP.md):** A maintainer landing on the README finds a 60-second quickstart and a link to a versioned `mkdocs-material` site with `/v1/` (frozen v1.3.0 reference) and `/v2/` (current); the migration guide is the headline page and is supported by a line-level before/after `bitbucket-pipelines.yml` diff under `examples/migration-v1-to-v2/`. ADRs cover every architectural decision. This is the final phase before the v2.0.0 tag-cut.

**Requirements covered (9):** DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07, DOC-08, MIG-03

## Domain Boundary

This phase **finalizes the v2.0 release**:
- Publishable docs site (mkdocs-material + mike, GitHub Pages).
- Migration guide as the headline page, polished from the Phase 5 draft.
- ADR archive covering every architectural decision shipped in Phases 1–6.
- README polish + landing-page navigation.
- examples/ folder with ≥4 ready-to-copy `bitbucket-pipelines.yml` snippets.
- v2.0.0 release ceremony (tag-cut, release.yml sign+SBOM+publish, Bitbucket Pipe Marketplace listing update).

**Out of scope (deferred):**
- Zensical migration → DOC-NEXT-01 (v2.1+).
- Lessons-learned pass (first 30 days post-v2.0.0) → tracked via `breaking-change` label on the GH Project board.

## Carrying Forward from Prior Phases

| From | Decision | How it shapes Phase 7 |
|---|---|---|
| Phase 4 | OIDC default precedence — static keys win when both present (commit 6e28005) | ADR-0006 documents the precedence; migration guide references it. |
| Phase 5 | `docs/guides/v1-to-v2.md` (435 lines) | Move to `docs/migration/v1-to-v2.md` and polish — do NOT rewrite. |
| Phase 5 | `docs/guides/oidc-setup.md` (73 lines) | Move to `docs/guides/oidc-setup.md` under mkdocs nav; polish IAM trust-policy. |
| Phase 6 | `docs/admin/repo-settings.md` (299 lines) | Move into mkdocs nav as `docs/admin/repo-settings.md`; surface maintainer-manual steps. |
| Phase 6 | GHCR-only publish (`ghcr.io/yves-vogl/aws-eks-helm-deploy`) | Migration guide "Distribution change" section already added; ADR-0001 (forge primacy) elaborates. |
| Phase 6 | Cosign keyless sign + Rekor + bundle for offline verify | ADR-0003 documents keyless choice; docs include `cosign verify` example. |
| Phase 6 | release-please orchestrates version bumps + CHANGELOG | ADR-0005 documents that decision. |
| Phase 6 | Multi-arch via native runners (`ubuntu-24.04` + `ubuntu-24.04-arm`) | ADR-0007 documents the no-QEMU choice. |
| Project | SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, .github/ISSUE_TEMPLATE/* | Already present (Phase 6). Phase 7 only refines wording for the 6-month v1.x window. |

## Locked Decisions

### D1 — Docs framework: `mkdocs-material 9.x` + `mike`
- **Locked by:** DOC-02, DOC-NEXT-01 (deferral noted).
- **Why:** Stable and well-known today. GitHub Pages compatible. Maintenance mode acceptable for the 12-18 month horizon.
- **Choice:** `mkdocs-material 9.5.x` (latest stable in the 9.x line at planning time — Researcher pins exact version).
- **Versioning plugin:** `mike` for the `/v1/` + `/v2/` split.
- **Deferral:** Zensical migration tracked as DOC-NEXT-01 (v2.1+).

### D2 — mike versioning layout
- **Locked by:** DOC-02.
- **Layout:**
  - `/v2/` (default + `latest` alias) — current docs (matches `main`).
  - `/v1/` (frozen) — single-page reference reflecting v1.3.0 README + variables table. **NOT** a full doc rewrite of v1; the v1 site is a deprecation pointer + variable cross-reference.
  - Root `/` redirects to `/v2/` (`mike set-default v2`).
- **Aliases:**
  - `mike deploy --push --update-aliases v2 latest` on every `main` commit.
  - `mike deploy --push v1` once at Phase 7 init; never touched again.
- **Banner on /v1/:** "v1 is frozen — security-only patches until 2027-MM-DD (= v2.0.0 release date + 6 months). Use v2: [link]."

### D3 — ADR template: MADR 4.0
- **Locked by:** DOC-04.
- **Path:** `docs/adr/NNNN-{title-slug}.md` (zero-padded 4-digit index).
- **Template:** Canonical MADR 4.0 (`docs/adr/template.md` shipped as `0000-template.md`).
- **Append-only:** Status transitions documented in-file; never delete or rewrite past ADRs.
- **Index:** `docs/adr/index.md` auto-listed by mkdocs nav (`docs/adr/`).

### D4 — ADR collection (9 ADRs)
- **Locked by:** DOC-04 (7 minimum) + 2 additions.
- **List:**
  1. `0001-github-primary-forge.md` — GitHub primary forge; Bitbucket Pipe Marketplace stays as a compat target (REQUIRED by DOC-04).
  2. `0002-v2-clean-break.md` — No compat shim layer; v1.x → v2.x is a clean break (REQUIRED by DOC-04).
  3. `0003-cosign-keyless-over-gpg.md` — Cosign keyless (OIDC → Fulcio → Rekor) over GPG (REQUIRED by DOC-04).
  4. `0004-boto3-only-over-awscli.md` — `boto3`-only over bundled awscli (REQUIRED by DOC-04).
  5. `0005-release-please-over-semversioner.md` — release-please-action over semversioner (REQUIRED by DOC-04).
  6. `0006-oidc-default-precedence.md` — Static keys win over OIDC when both present (mirrors botocore default chain) (REQUIRED by DOC-04).
  7. `0007-multi-arch-native-runners.md` — Native ubuntu-24.04-arm runners, no QEMU (REQUIRED by DOC-04).
  8. `0008-mkdocs-material-now-zensical-later.md` — mkdocs-material 9.x now; Zensical migration deferred to v2.1+ (NEW; documents the framework choice).
  9. `0009-src-layout-no-compat-shims.md` — `src/`-layout v2.x; no `v1.x` import-path shims (NEW; references Phase 1 risk note).

### D5 — Variable reference generator
- **Locked by:** DOC-02 SC-2.
- **Generator:** `scripts/generate-variables-doc.py` reads `src/aws_eks_helm_deploy/config/settings.py` (Pydantic model) and emits `docs/reference/variables.md`.
- **Banner in generated file:** `<!-- AUTOGENERATED FROM src/aws_eks_helm_deploy/config/settings.py — DO NOT EDIT BY HAND. Regenerate via `uv run scripts/generate-variables-doc.py`. -->`
- **CI gate:** `scripts/check-variables-drift.sh` runs generator + diff; CI step fails if generated output drifts from committed file.
- **Wired into:** new job in `.github/workflows/ci.yml` named `docs-drift` (matches Phase 6 job-fan-out shape).

### D6 — README badge row order
- **Locked by:** DOC-01.
- **Current order (already on main from Phase 6, kept):** license · release · GHCR image · CI build · coverage · Cosign verified · OpenSSF Scorecard.
- **Polish in Phase 7 (additions, no reorder):** sponsors (GitHub Sponsors) · stars · open issues.
- **Style:** consistent `?style=flat-square` via shields.io for net-new badges; existing badges keep their current style (no churn).
- **Quickstart section:** keep the existing "What this pipe does" structure; the 60-second snippet stays inline above the docs-site link.

### D7 — Migration guide location and polish strategy
- **Move:** `docs/guides/v1-to-v2.md` (435 lines, Phase 5+6 draft) → `docs/migration/v1-to-v2.md`.
- **Polish, do NOT rewrite:** keep all breaking-change coverage already drafted (INJECT_BITBUCKET_METADATA flip, NAMESPACE correction, image-tag pinning policy, distribution change).
- **Headline page in mkdocs nav:** `Migration v1 → v2` is the second top-level nav entry (after `Quickstart`), surfaced from index.md hero card.
- **examples/migration-v1-to-v2/ cross-reference:** every breaking change in the prose links to the matching line range in the before/after diff.

### D8 — `examples/` folder (5 directories minimum)
- **Locked by:** DOC-08 + MIG-03.
- **Structure:**
  - `examples/basic/bitbucket-pipelines.yml` — static keys + `local://` chart (DOC-08).
  - `examples/oidc-only/bitbucket-pipelines.yml` — OIDC + `repo://` chart (DOC-08).
  - `examples/oci-chart/bitbucket-pipelines.yml` — OIDC + `oci://` chart from GHCR (DOC-08).
  - `examples/multi-env/bitbucket-pipelines.yml` — multi-env deploy with `helm-diff` PR comment (DOC-08).
  - `examples/migration-v1-to-v2/{before.yml, after.yml, README.md}` — before/after diff with line-level explanations (MIG-03).
- **Validation:** each `bitbucket-pipelines.yml` is `bitbucket-pipelines-lint`-clean (validated in a new structural test).
- **Comments:** every example file has a header block: purpose, prerequisites, expected outcome — copy-paste-ready.

### D9 — GitHub Pages deploy workflow
- **File:** `.github/workflows/docs.yml`.
- **Triggers:**
  - `push` to `main` (deploy `v2` + `latest` aliases).
  - `push` of `v*` tag (deploy versioned alias for major like `v2.0`, but only at v2.0.0 → also re-runs `latest`).
  - `workflow_dispatch` (manual republish; useful if `gh-pages` branch drifts).
- **Permissions:**
  - `contents: write` (to push to `gh-pages` branch).
  - `id-token: read` (NOT write — no OIDC signing in this workflow; only the release.yml sign-and-attest job needs `id-token: write`).
- **Strict mode:** `mkdocs build --strict` (fail on warnings).
- **Action pinning:** `actions/checkout@<40-char-SHA>`, `actions/setup-python@<40-char-SHA>` (Researcher resolves digests via `gh api repos/owner/repo/git/refs/tags/...`).
- **Caching:** uv cache + mkdocs cache via `actions/cache@<SHA>` keyed on `uv.lock`.

### D10 — v1.x security-fix support window
- **Locked by:** DOC-06.
- **Wording in SECURITY.md:** "v1.x receives security fixes for 6 months from the v2.0.0 release date." The exact end-of-support date is calculated post-tag-cut and committed in a follow-up patch by the maintainer (recorded in `docs/migration/v1-to-v2.md` as well).
- **Phase 7 commits a placeholder:** `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` Verifier checks the placeholder exists.
- **No Phase 7 patch of SECURITY.md beyond the placeholder + 6-month wording sharpening:** existing 90-day coordinated disclosure window stays as-is.

### D11 — v2.0.0 release ceremony scope
- **In Phase 7 PR:**
  - All doc-site code + ADRs + examples + nav.
  - Migration guide move + polish.
  - README badge polish.
  - `docs.yml` workflow.
  - Variable generator + drift CI gate.
  - SECURITY.md 6-month placeholder update.
- **After Phase 7 PR merge to main (separate ceremony, NOT in PR):**
  - Manual `git tag v2.0.0 && git push --tags` (Yves runs this).
  - release.yml fires on tag → builds linux/amd64+linux/arm64 → signs → attests SBOMs (SPDX + CycloneDX) → publishes to GHCR.
  - Maintainer manually:
    - Computes 6-month placeholder → opens follow-up PR to commit absolute date.
    - Updates Bitbucket Pipe Marketplace listing (link in `docs/admin/repo-settings.md`).
    - Posts Docker Hub README deprecation banner.
- **Phase 7 PR body:** lists every maintainer manual step with exact commands (mirrors Phase 6 `docs/admin/repo-settings.md` shape).

## Deferred Ideas (carry to v2.1+ backlog)

- **DOC-NEXT-01** — Migrate from mkdocs-material to Zensical once stable (mkdocs-material entered maintenance mode early 2026). 12-18 month horizon.
- **Lessons-learned pass** — In the 30 days post-v2.0.0, fold any consumer-reported breaking change into the migration guide; tracked via the `breaking-change` label on the GH Project board.
- **Interactive examples** — Stretch goal for v2.1+: an interactive "Build your bitbucket-pipelines.yml" wizard hosted on the docs site (out of scope for v2.0).

## Canonical Refs

Every downstream agent (Researcher, Planner, Executor, Verifier) MUST read these before acting.

| Ref | Path | Why |
|---|---|---|
| ROADMAP | `.planning/ROADMAP.md` (lines 172–192) | Phase 7 SC + risks + DOC-NEXT-01 deferral. |
| REQUIREMENTS | `.planning/REQUIREMENTS.md` (DOC-01..08, MIG-03, DOC-NEXT-01) | Requirement text. |
| Phase 1 CONTEXT | `.planning/phases/01-toolchain-spine/01-CONTEXT.md` | `src/`-layout decision; ADR-0009 source. |
| Phase 2 CONTEXT | `.planning/phases/02-aws-layer-auth-foundation/02-CONTEXT.md` | boto3-only decision; ADR-0004 source. |
| Phase 3 CONTEXT | `.planning/phases/03-helm-core-upgrade-action/03-CONTEXT.md` | HelmClient subprocess invariant; ADR background. |
| Phase 4 CONTEXT | `.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md` | OIDC precedence; ADR-0006 source. |
| Phase 5 CONTEXT | `.planning/phases/05-log-masking-diff-rollback-metadata-flip/05-CONTEXT.md` | Log-masking + INJECT_BITBUCKET_METADATA flip; migration guide already drafted. |
| Phase 6 CONTEXT | `.planning/phases/06-release-pipeline-supply-chain/06-CONTEXT.md` | release-please, Cosign keyless, multi-arch native runners; ADR-0003/0005/0007 source. |
| Existing migration draft | `docs/guides/v1-to-v2.md` (435 lines) | Source for D7 polish — do NOT rewrite. |
| Existing OIDC guide | `docs/guides/oidc-setup.md` (73 lines) | Lives under mkdocs nav after Phase 7. |
| Maintainer runbook | `docs/admin/repo-settings.md` (299 lines) | Already lists exact `gh api` commands for branch protection, PVR, GPG. Phase 7 adds: Pages enablement, Bitbucket Pipe Marketplace listing update, Docker Hub banner. |
| SECURITY.md | `SECURITY.md` | D10 polish target. |
| CONTRIBUTING.md | `CONTRIBUTING.md` | DOC-05 — verify `uv sync` / `pre-commit` / `pytest` / `kind` loop is documented. |
| CODE_OF_CONDUCT.md | `CODE_OF_CONDUCT.md` | DOC-07 — verify Contributor Covenant 2.1 in place. |
| MADR template | https://adr.github.io/madr/ (Researcher pins exact version + SHA) | D3 ADR template source. |
| mkdocs-material docs | https://squidfunk.github.io/mkdocs-material/ (Researcher pins 9.x version) | D1 config source. |
| mike docs | https://github.com/jimporter/mike (Researcher pins exact version) | D2 versioning source. |

## Code Context (reusable assets)

- **README.md** — already polished with badge row in Phase 6; only additive badges in Phase 7 (sponsors/stars/issues).
- **docs/guides/v1-to-v2.md** — 435-line Phase 5 draft; Phase 7 moves + polishes, doesn't rewrite.
- **docs/guides/oidc-setup.md** — 73-line Phase 4 draft; folded into mkdocs nav.
- **docs/admin/repo-settings.md** — 299-line maintainer runbook; folded into mkdocs nav under `admin/`.
- **scripts/** — existing Python scripts; `generate-variables-doc.py` is a new sibling.
- **src/aws_eks_helm_deploy/config/settings.py** — Pydantic Settings model; source of truth for D5 generator.
- **SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md** — present from Phase 6; D10 polishes SECURITY only.
- **.github/workflows/ci.yml** — 7-job fan-out from Phase 6; Phase 7 adds 1 new job (`docs-drift`) following the same shape.

## Suggested Plan Slicing (Planner: refine)

7 plans across 4 waves (smaller than Phase 6's 11 plans — content-heavy not infra-heavy).

| Plan | Wave | Title | REQ coverage | Independent? |
|---|---|---|---|---|
| 07-01 | 1 | mkdocs-material scaffolding + nav + index.md + theme config | DOC-01, DOC-02 (partial) | yes |
| 07-02 | 1 | ADR collection (9 MADR ADRs + 0000-template) | DOC-04 | yes |
| 07-03 | 2 | Variable reference generator + CI drift gate (ci.yml `docs-drift` job) | DOC-02 (SC-2) | depends on 07-01 nav |
| 07-04 | 2 | Migration guide move + polish + examples/ + examples/migration-v1-to-v2/ | DOC-03, DOC-08, MIG-03 | depends on 07-01 nav |
| 07-05 | 2 | docs.yml deploy workflow + mike v1 + v2 publish + GitHub Pages enablement | DOC-02 (SC-1, SC-3) | depends on 07-01 |
| 07-06 | 3 | README badge polish (additive) + SECURITY.md 6-month wording + CONTRIBUTING.md verification | DOC-01, DOC-05, DOC-06, DOC-07 | yes |
| 07-07 | 4 | v2.0.0 release ceremony prep + maintainer manual-step doc + PR body template | (cross-REQ) | depends on 07-01..06 |

## Cap & Run-mode Notes

- **Estimated budget:** ~800k-1M subagent tokens (smaller than Phase 6's 1.4M).
- **Run mode:** autonomous; user has standing instruction "bei Fragen nehme ich Deine Empfehlungen."
- **Confirmation guardrails still active:** force-push, branch-delete, ROADMAP/REQUIREMENTS scope changes, new top-level dependencies (any new dep beyond mkdocs-material + mike + their plugin family needs explicit user confirmation), cluster/IAM/production touches.
- **No new top-level Python runtime deps allowed:** mkdocs + mkdocs-material + mike go into a `docs` extra in `pyproject.toml` (not runtime).

## Open Questions for Researcher

1. Exact pinned versions: mkdocs-material 9.5.x latest patch, mike latest, plus minimal plugin set (e.g., `mkdocs-material[imaging]`?).
2. MADR 4.0 canonical template URL + SHA pin (avoid live-fetching at build time).
3. GitHub Pages enablement: API call to PUT `pages` settings is in `docs/admin/repo-settings.md` already? If not, add to Plan 07-07.
4. `actions/checkout`, `actions/setup-python`, `actions/cache` 40-char SHA digests for the mkdocs branch in `docs.yml`.
5. Does mkdocs-material `[imaging]` extra need extra OS packages (cairo, pillow native deps)? — affects CI runner choice.

These are open for the Researcher pass — none block CONTEXT.md finalization.
