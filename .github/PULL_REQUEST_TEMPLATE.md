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
