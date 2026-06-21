## Summary

<!-- 1-3 sentences: what changed and why. -->

## Linked issue

<!-- Closes #N, Related-to #N — or "N/A" for trivial changes. -->

## Type of change

<!-- Pick one and delete the others. -->

- [ ] `feat`: new capability
- [ ] `fix`: bug fix
- [ ] `docs`: documentation only
- [ ] `chore`: maintenance (no release-affecting change)
- [ ] `refactor`: internal restructuring, no behaviour change
- [ ] `test`: tests only
- [ ] `breaking-change`: contract change requiring `feat!:` or `BREAKING CHANGE:` footer

## Merge checklist

- [ ] Conventional Commit subject line in the merge commit
      (e.g. `feat(auth): add OIDC strategy`, `fix(deps): bump base image`).
- [ ] Tests added or updated where applicable (`tests/unit`, `tests/integration`,
      `tests/acceptance` as relevant).
- [ ] `uv run pytest tests/unit tests/structural --cov-fail-under=100` exits 0
      (the unit-coverage CI job is the gate).
- [ ] `uv run mypy --strict src/aws_eks_helm_deploy` exits 0.
- [ ] `uv run ruff check src/ tests/` exits 0.
- [ ] Docs updated (`docs/`, `CHANGELOG.md` via release-please, `README.md` if
      user-facing).
- [ ] ADR added under `docs/adr/` if this PR makes an architectural decision
      (consult `.planning/ROADMAP.md` for what counts).
- [ ] Release-Please Notes: merge commit uses a Conventional Commit subject so
      release-please can auto-generate the CHANGELOG entry; for a breaking change
      include `BREAKING CHANGE:` in the commit body.
- [ ] PR template fields above are filled in (not blank or placeholder).
- [ ] No `--no-verify` was used in any commit.
- [ ] No AI-attribution co-authorship in commit bodies (project policy).
- [ ] If touching `.github/workflows/*.yml`: every `uses:` line is pinned to a
      40-char SHA digest (Pitfall #5 — no `@v{N}` tags, no `@main`/`@latest`).
- [ ] If touching the release pipeline: structural tests in `tests/structural/`
      are green.

## ADR Reference

<!-- If an ADR was created or referenced: docs/adr/NNNN-*.md. Otherwise delete. -->

## Documentation Updates

<!-- What docs changed? README, CHANGELOG (auto via release-please), guides, etc. -->

## Notes for reviewers

<!-- Tricky logic, security boundary, performance risk, deferred follow-ups. -->

## Maintainer manual steps after merge (v2.0.0 tag-cut ceremony — D11)

*This section applies ONLY to the Phase 7 PR that lands the final v2.0 docs surface.*
*Subsequent PRs should remove this section from their body before opening.*

- [ ] `git tag v2.0.0 && git push --tags` — triggers `.github/workflows/release.yml`.
- [ ] Monitor release.yml run; verify Cosign signature + SBOM attestations attached.
- [ ] After the v2 docs site is live: enable GitHub Pages per [`docs/admin/repo-settings.md` §5](../blob/main/docs/admin/repo-settings.md#5-enable-github-pages-doc-02).
- [ ] After the first `mike deploy v2 latest` workflow run succeeds: run [`mike set-default v2 --push`](../blob/main/docs/admin/repo-settings.md#6-set-default-mike-alias-to-v2-doc-02-sc-3).
- [ ] Deploy the frozen v1 docs snapshot per [`docs/admin/repo-settings.md` §7](../blob/main/docs/admin/repo-settings.md#7-deploy-frozen-v1-docs-snapshot-d2--plan-07-01).
- [ ] Update the Bitbucket Pipe Marketplace listing per [`docs/admin/repo-settings.md` §8](../blob/main/docs/admin/repo-settings.md#8-update-bitbucket-pipe-marketplace-listing-d11).
- [ ] Post the Docker Hub README deprecation banner per [`docs/admin/repo-settings.md` §9](../blob/main/docs/admin/repo-settings.md#9-post-docker-hub-readme-deprecation-banner-mig-01).
- [ ] Compute the absolute end-of-support date for v1.x (= v2.0.0 release date + 6 months) and open a follow-up PR replacing the literal `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` placeholder in `SECURITY.md`, `docs/migration/v1-to-v2.md`, AND `docs/admin/repo-settings.md` sections 7 + 9 (SI-07-07 invariant gate enforces).
