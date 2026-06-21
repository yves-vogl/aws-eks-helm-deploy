# Phase 7 — Deferred Items (out-of-scope findings)

## From Plan 07-01 execution

- **Pre-existing ruff E501 in `scripts/_trivyignore_parser.py:99`** — line 103 chars (limit 100). Inherited from Phase 6 (commit cca2868). Out of scope for Plan 07-01 (whitelist: pyproject.toml + mkdocs.yml + docs/ + tests/structural/ only). Suggested fix: split the usage string. Track for a future cleanup PR — does NOT affect any Phase 7 plan.

## From Plan 07-03 execution

- **`site/` (mkdocs build output) not in `.gitignore`** — `uv run --extra docs mkdocs build --strict` produces `site/` at repo root. Plan 07-03 whitelist excludes `.gitignore`, so the entry was not added here. Suggested fix: add `site/` to `.gitignore` in a future docs cleanup PR (likely Plan 07-04 or a separate hygiene PR). Does NOT affect CI (workflows never commit `site/`); only matters for local mkdocs builds.
- **Pre-existing ruff format pending on `scripts/_trivyignore_parser.py`, `scripts/rescan-issue-creator.py`, `scripts/scorecard-exception-check.py`** — three Phase-6-era scripts that `ruff format --check` flags. Out of scope for Plan 07-03 (whitelist excludes these files). New Plan 07-03 files all pass both `ruff check` and `ruff format --check`.
