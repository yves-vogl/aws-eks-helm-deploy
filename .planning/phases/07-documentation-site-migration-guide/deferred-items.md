# Phase 7 — Deferred Items (out-of-scope findings)

All items below were flagged during Phase 7 plan execution as out-of-scope.
Status as of 2026-06-23.

## From Plan 07-01 execution

- ~~**Pre-existing ruff E501 in `scripts/_trivyignore_parser.py:99`** — line 103 chars (limit 100).~~
  → **RESOLVED** in PR #47 (commit 084207c) — usage string split across 3 lines.

## From Plan 07-03 execution

- ~~**`site/` (mkdocs build output) not in `.gitignore`**.~~
  → **RESOLVED** in commit 926bf9b (`.gitignore` entry added during Phase 7 PR cleanup).
- ~~**Pre-existing ruff format pending on `scripts/_trivyignore_parser.py`, `scripts/rescan-issue-creator.py`, `scripts/scorecard-exception-check.py`**.~~
  → **RESOLVED** in PR #47 (commit 084207c) — all three files reformatted via `uv run ruff format`.

---

## Remaining (carry to v2.x post-tag-cut backlog)

These are Phase 6 follow-ups still marked `continue-on-error: true` in `.github/workflows/ci.yml`; SARIF still uploads so visibility is preserved.

- **META-01 curly-brace UUID round-trip** (integration job): `test_inject_bitbucket_metadata_sets_all_5_keys` fails because `{xxxxxxxx-…}` UUIDs round-trip differently through `helm-template` / `get-values`. Tried `-o json` — did not fix.
- **trivy-image `.trivyignore.bare` sidecar** (trivy-image job): `aquasecurity/trivy-action@v0.36.0` does not honor `trivyignores: .trivyignore.bare` for the 9 helm-stdlib Go CVEs. Fix: upgrade `trivy-action` OR migrate `.trivyignore` to YAML format (`.trivyignore.yaml`).
- **trivy-dockerfile `skip-dirs` syntax** (trivy-dockerfile job): KSV-0014 / KSV-0118 chart-fixture securityContext findings leak through `skip-dirs: tests/fixtures,.planning`. Need different syntax (e.g., one `--skip-dirs` per dir via `additional-args`, or a Trivy config file).
