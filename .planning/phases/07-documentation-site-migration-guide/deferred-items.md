# Phase 7 — Deferred Items (out-of-scope findings)

## From Plan 07-01 execution

- **Pre-existing ruff E501 in `scripts/_trivyignore_parser.py:99`** — line 103 chars (limit 100). Inherited from Phase 6 (commit cca2868). Out of scope for Plan 07-01 (whitelist: pyproject.toml + mkdocs.yml + docs/ + tests/structural/ only). Suggested fix: split the usage string. Track for a future cleanup PR — does NOT affect any Phase 7 plan.
