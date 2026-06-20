---
phase: 5
slug: log-masking-diff-rollback-metadata-flip
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from 05-RESEARCH.md "Validation Architecture" + "Security Domain" sections.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 (unit tier runs by default via `addopts = "-m 'unit'"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit -q --no-cov` |
| **Full suite command** | `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` |
| **Integration tier command** | `uv run pytest tests/integration -m integration` (deselected by default) |
| **Acceptance tier command** | `uv run pytest tests/acceptance -m acceptance` (Docker-gated, skips cleanly without daemon) |
| **Estimated runtime** | ~10 s quick, ~60 s full + coverage |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit -q --no-cov`
- **After every plan wave merge:** Run `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100`
- **Before `/gsd-verify-work`:** Full suite must be green AND `uv run mypy --strict src/aws_eks_helm_deploy` clean AND `uv run ruff check src/ tests/` clean
- **Max feedback latency:** ~60 seconds (matches Phase 4 budget)

---

## Per-Task Verification Map

*Populated after planner produces per-plan task IDs. Phase 5 will produce ~6–8 plans with ~30–50 tasks total. Each row maps task → REQ → automated command.*

Skeleton — planner fills task IDs:

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-02-* | 02 (redactor) | 1 | SEC-06 | T-05-01 | Secret data/stringData → `<redacted>` before any output stream | unit | `uv run pytest tests/unit/test_helm_redact.py -x` | ❌ W0 | ⬜ pending |
| 05-02-* | 02 (redactor) | 1 | SEC-06 | T-05-01 | Non-YAML helm output passes through unchanged | unit | same | ❌ W0 | ⬜ pending |
| 05-02-* | 02 (redactor) | 1 | SEC-06 | T-05-01 | Multi-doc YAML: only `kind: Secret` docs redacted | unit | same | ❌ W0 | ⬜ pending |
| 05-02-* | 02 (HelmClient wiring) | 2 | SEC-06 | T-05-01 | `upgrade_install` stdout/stderr through redactor | unit (mock) | `uv run pytest tests/unit/test_helm_client_run.py -x` | ✅ (extend) | ⬜ pending |
| 05-03-* | 03 (DiffAction + Dockerfile) | 2 | PIPE-02 | — | `HelmClient.diff()` builds correct argv | unit | `uv run pytest tests/unit/test_helm_client_argv.py -x` | ✅ (extend) | ⬜ pending |
| 05-03-* | 03 (DiffAction) | 2 | PIPE-02 | — | `DiffAction.run()` happy path | unit (mock) | `uv run pytest tests/unit/test_diff_action.py -x` | ❌ W0 | ⬜ pending |
| 05-04-* | 04 (PR-comment) | 3 | PIPE-03 | T-05-02 | POST when no existing comment | unit (mock urllib) | `uv run pytest tests/unit/test_pr_comment.py -x` | ❌ W0 | ⬜ pending |
| 05-04-* | 04 (PR-comment) | 3 | PIPE-03 | T-05-02 | PUT when marker comment found | unit (mock urllib) | same | ❌ W0 | ⬜ pending |
| 05-04-* | 04 (PR-comment) | 3 | PIPE-03 | T-05-02 | 401 response: NO token bytes in WARN log | unit (mock urllib) | same | ❌ W0 | ⬜ pending |
| 05-05-* | 05 (rollback) | 2 | PIPE-04 | — | `HelmClient.rollback()` argv correct | unit | `uv run pytest tests/unit/test_helm_client_argv.py -x` | ✅ (extend) | ⬜ pending |
| 05-05-* | 05 (rollback) | 2 | PIPE-05 | — | Pre-flight: revision with `pipe:safe-upgrade` description passes | unit (mock) | `uv run pytest tests/unit/test_rollback_action.py -x` | ❌ W0 | ⬜ pending |
| 05-05-* | 05 (rollback) | 2 | PIPE-05 | — | Pre-flight: revision without `pipe:safe-upgrade` raises ChartResolutionError | unit (mock) | same | ❌ W0 | ⬜ pending |
| 05-05-* | 05 (upgrade wiring) | 2 | PIPE-05 | — | SAFE_UPGRADE=true adds `--wait --atomic --description "pipe:safe-upgrade"` to argv | unit | `uv run pytest tests/unit/test_helm_client_argv.py -x` | ✅ (extend) | ⬜ pending |
| 05-06-* | 06 (META detection) | 2 | META-02 | — | `Settings.inject_bitbucket_metadata` default is `None` | unit | `uv run pytest tests/unit/test_settings.py -x` | ✅ (extend) | ⬜ pending |
| 05-06-* | 06 (META detection) | 2 | META-03 | — | WARN emitted when values.yaml has `bitbucket:` AND setting is `None` | unit | `uv run pytest tests/unit/test_upgrade_action.py -x` | ✅ (extend) | ⬜ pending |
| 05-06-* | 06 (MIG-02) | 2 | MIG-02 | — | WARN on `SET`/`VALUES` env var at startup | unit | `uv run pytest tests/unit/test_cli.py -x` | ✅ (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_helm_redact.py` — new file for SEC-06 redactor tests
- [ ] `tests/unit/test_diff_action.py` — new file for PIPE-02/03 DiffAction tests
- [ ] `tests/unit/test_pr_comment.py` — new file for PIPE-03 PR-comment poster tests
- [ ] `tests/unit/test_rollback_action.py` — new file for PIPE-04/05 RollbackAction tests
- [ ] `tests/fixtures/charts/secret-emitting/` — minimal chart fixture emitting `kind: Secret` (currently NO Secret-emitting fixture in the test suite — see 05-RESEARCH.md "Existing Secret-emitting fixture")
- [ ] Wave 0 ALSO adds the 5 new Settings fields (`POST_DIFF_AS_COMMENT`, `BITBUCKET_TOKEN`, `SAFE_UPGRADE`, `INJECT_BITBUCKET_METADATA`, `REVISION`) — extends existing `test_settings.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `helm-diff` plugin is discoverable in the runtime container | PIPE-02 | Requires Docker daemon + actual image build | `docker run --rm <pipe-image> helm plugin list` — expect `diff` row with version 3.10.0 |
| PR comment is visible in a real Bitbucket PR | PIPE-03 | Requires a live Bitbucket workspace and PR | Trigger ACTION=diff against a real PR with `POST_DIFF_AS_COMMENT=true` — observe the comment renders the redacted diff |
| Rollback refusal message is helpful to consumers | PIPE-05 | UX judgment, not assertable | Re-deploy a release without SAFE_UPGRADE, attempt rollback to that revision; confirm error mentions SAFE_UPGRADE=true as the remedy |
| v1-to-v2 migration guide reads correctly | MIG-02 | Doc UX judgment | Review `docs/guides/v1-to-v2.md` once drafted (Plan 05-07) |

---

## Security Domain (from 05-RESEARCH.md)

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V5 Input Validation | yes | `yaml.safe_load_all` (NOT `yaml.load`); `int()` coercion for revision |
| V7 Error Handling & Logging | yes | `_sanitize_response_body` strips BITBUCKET_TOKEN literal from all error paths; `redact_helm_output` strips Secret payloads from logs/PR-comments/stdout |
| V14 Configuration | yes | Cosign-equivalent SHA256 verification of helm-diff plugin at build time |

### Known Threat Patterns

| Threat ID | Pattern | STRIDE | Standard Mitigation |
|-----------|---------|--------|---------------------|
| T-05-01 | Secret YAML in any output stream | Info Disclosure | `redact_helm_output()` applied at every HelmClient stdout/stderr capture AND before PR-comment POST/PUT |
| T-05-02 | BITBUCKET_TOKEN leak in 4xx/5xx log paths | Info Disclosure | `_sanitize_response_body` strips token literal + `Authorization:` header lines from logged response bodies |
| T-05-03 | YAML bomb / billion-laughs via crafted helm output | DoS | `yaml.safe_load_all` uses SafeLoader; alias expansion disabled |
| T-05-04 | Token in argv / env vars of subprocess call | Info Disclosure | D6 invariant: NO subprocess in `bitbucket/pr_comment.py`; HTTP via stdlib `urllib.request`; token passed as `Authorization` header only |
| T-05-05 | Tampered helm-diff binary | Tampering | D2: SHA256 verify against upstream `helm-diff_3.10.0_checksums.txt` before extract |

### Security Invariants (plan-checker MUST enforce)

1. `grep -rn '"BITBUCKET_TOKEN"' src/` returns ZERO literal string occurrences — only `Settings.bitbucket_token` field references.
2. `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` returns EXACTLY 2 files (`helm/client.py`, `chart/oci.py`) — Phase 4 D5 / Phase 5 D6 invariant.
3. `grep -rn 'yaml.load(' src/` returns ZERO (only `yaml.safe_load_all` / `yaml.safe_dump_all` allowed).
4. `grep -F '--password ' src/aws_eks_helm_deploy/helm/client.py` returns ZERO matches with a space — `--password-stdin` only (Phase 4 D7 carry-forward).
5. `grep -F 'COSIGN_VERSION=2.6.3' Dockerfile` returns ≥1 (Phase 4 D8 carry-forward) AND `grep -F 'HELM_DIFF_VERSION=3.10.0' Dockerfile` returns ≥1 (Phase 5 D2).
6. SHA256 check command in `helm-diff-fetch` stage matches upstream checksum file format `sha256sum -c`.
7. No `requests` direct import in `bitbucket/` (forced stdlib usage per Phase 5 D3 correction).

---

## Verifier Bar (mirrors Phase 4 VERIFICATION shape)

Phase 5 verifier MUST assert:

- 4 Success Criteria observable in shipped code (1 redactor, 1 diff+PR-comment, 1 rollback+SAFE_UPGRADE, 1 metadata-flip+MIG-detect)
- 8 REQs covered by source + green tests (SEC-06, PIPE-02..05, META-02..03, MIG-02)
- 6 locked decisions D1–D6 honoured (with the 3 research-driven corrections applied)
- 3 ROADMAP risks R1–R3 mitigated (centralized redactor + fuzz test, token-scrub in 4xx paths, SAFE_UPGRADE pre-flight)
- All mechanical gates: 100% line+branch unit coverage, mypy --strict clean, ruff clean, the 7 security invariants above
- Cold-start budget regression check: image build time + first-action latency must not exceed Phase 4 budget by more than 15% (helm-diff bundle adds ~5 MB compressed; expected <2 s build delta)

---

*This file will be updated post-planning when task IDs are assigned. The skeleton above lets the planner author rows that match the task-ID format `{phase}-{plan}-{seq}` (e.g., `05-02-03`).*
