---
phase: 05-log-masking-diff-rollback-metadata-flip
verified: 2026-06-20T12:00:00Z
status: passed
score: 13/13 must-haves verified
verdict: PASS
---

# Phase 5 — Goal-Backward Verification Report

**Phase Goal (ROADMAP):** Helm output emitted by the pipe never leaks `Secret` payloads; consumers can preview changes via `ACTION=diff` (or `DRY_RUN=true`) and optionally post the diff as a Bitbucket PR comment; `ACTION=rollback` is safe by default; `INJECT_BITBUCKET_METADATA` defaults to `false` (breaking change) with a loud deprecation warning when v1-style chart usage is detected. Closes #16 and addresses Pitfalls #2 and #3.

**Verdict:** **PASS** — all 4 Success Criteria are observably true in the shipped codebase, all 8 REQs are covered by source code + green tests, all 6 locked decisions D1–D6 are honoured (with research-driven corrections applied), all 3 risks R1–R3 are mitigated, and every mechanical gate is clean.

---

## Mechanical Gates

| Gate | Expected | Result |
|------|----------|--------|
| `uv run pytest tests/ -q --no-cov` | ≥ 469 passed | **469 passed, 18 deselected, 5 warnings** |
| `uv run pytest tests/unit --cov=src/aws_eks_helm_deploy --cov-branch --cov-fail-under=100` | 100.00% line + branch | **100.00% (1106 stmts, 216 branches, 0 missing) — 469 tests** |
| `uv run mypy --strict src/aws_eks_helm_deploy` | 0 issues | **Success: no issues found in 32 source files** |
| `uv run ruff check src/ tests/` | clean | **All checks passed!** |
| `uv run ruff format --check src/ tests/` | already formatted | **73 files already formatted** |
| `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` | EXACTLY 2 files | **2 files: `helm/client.py` + `chart/oci.py`** (D6 invariant) |
| `grep -F 'ARG HELM_DIFF_VERSION=3.10.0' Dockerfile` | 1 hit | **1 hit** (D2 pin) |
| `grep -F '/home/pipe/.local/share/helm/plugins/diff' Dockerfile` | 1 hit | **1 hit** (D2 path correction) |
| `grep -F 'a7875d4656b327b0b7f792f25a70f714801e402eb199ddd0f2df06a063e6bede' Dockerfile` | 1 hit | **1 hit** (SHA256 in comment; upstream `sha256sum -c` is the enforcement mechanism — see Dockerfile:110) |
| `grep -F 'COSIGN_VERSION=2.6.3' Dockerfile` | 1 hit | **1 hit** (`ARG COSIGN_VERSION=2.6.3`) — Phase 4 D8 carry-forward |
| `grep -F 'pipe:safe-upgrade' src/aws_eks_helm_deploy/helm/client.py` | 1 hit | **3 hits** (constant declaration at :61, docstring at :230, argv extend at :260) |
| `grep -rF 'SAFE_UPGRADE_DESCRIPTION' src/aws_eks_helm_deploy/actions/` | ≥ 2 hits | **4 hits** in `rollback.py` (module docstring :5, import :35, docstring :57, pre-flight check :167) |
| `grep -c 'self._redactor(' src/aws_eks_helm_deploy/helm/client.py` | ≥ 12 hits | **12 hits** — every stdout/stderr capture routes through redactor (T-05-01 mitigation) |
| `grep -rE '^import requests' src/aws_eks_helm_deploy/bitbucket/` | 0 hits | **0 hits** (exit=1, grep found nothing) |
| `grep -rF 'bitbucket_pipes_toolkit' src/aws_eks_helm_deploy/bitbucket/` | 0 hits | **0 hits** — stdlib urllib only (D3 / research correction) |
| `grep -F '<!-- aws-eks-helm-deploy:diff -->' src/aws_eks_helm_deploy/bitbucket/pr_comment.py` | 1 hit | **2 hits** (MARKER constant + docstring reference) |
| `grep -F 'meta.bitbucket_values_detected_without_opt_in' src/aws_eks_helm_deploy/actions/upgrade.py` | 1 hit | **2 hits** (docstring :_ + logger.warning emit) |
| `grep -F 'mig.v1_env_var_detected' src/aws_eks_helm_deploy/cli.py` | 1 hit | **2 hits** (docstring :_ + logger.warning emit) |

**Security invariant checks (VALIDATION.md §7):**

| Invariant | Check | Result |
|-----------|-------|--------|
| SI-1: No `"BITBUCKET_TOKEN"` literal in src (outside Pydantic alias) | `grep -rn '"BITBUCKET_TOKEN"' src/` | **1 hit in `settings.py:159`** — Pydantic `Field(alias="BITBUCKET_TOKEN")`, not a credential reference; `pr_comment.py:60` is inside a docstring. Both are acceptable per invariant intent. PASS |
| SI-2: `import subprocess` in exactly 2 files | verified above | **PASS** |
| SI-3: No `yaml.load(` in src | `grep -rn 'yaml\.load(' src/` returns exit=1 | **PASS — 0 hits** |
| SI-4: No `--password ` positional (space after password) | Python regex check: 0 matches | **PASS — `--password-stdin` appears 4 times; no positional `--password `** |
| SI-5: Both version pins present | `HELM_DIFF_VERSION=3.10.0` + `COSIGN_VERSION=2.6.3` in Dockerfile | **PASS** |
| SI-6: `sha256sum -c` in helm-diff-fetch stage | `Dockerfile:110` — `grep "  helm-diff-linux-amd64.tgz$" helm-diff_checksums.txt \| sha256sum -c` | **PASS** |
| SI-7: No `requests` import in `bitbucket/` | exit=1 (nothing found) | **PASS** |

---

## Success Criteria

| SC | Shipped? | Evidence (file:line + tests) |
|----|----------|------------------------------|
| **SC1 (SEC-06)** — Redactor replaces `data:`/`stringData:` of any `kind: Secret` manifest with `<redacted>` before bytes leave the pipe; lands before PIPE-03 wiring | **YES** | `helm/redact.py` (84 lines) — `redact_helm_output(text: str) -> str` uses `yaml.safe_load_all` + Secret-kind filter + `yaml.safe_dump_all(sort_keys=False)`; YAMLError → passthrough; no-Secret early-return avoids re-serialization artefacts. `helm/client.py:192` — constructor `redactor: Callable[[str], str] = redact_helm_output`; `self._redactor` wired at **12 capture sites** (upgrade_install stdout/stderr/timeout, history stdout/stderr, diff stdout/stderr/timeout, rollback stderr/timeout, `_run_helm_subcommand` error path, registry_login error path). Tests: `tests/unit/test_helm_redact.py` — 10 test functions (14 with parametrize), 100% line+branch coverage on `helm/redact.py`; `test_fuzz_no_secret_bytes_in_any_output` (5 parametrized cases asserting `"FUZZ_SECRET_VALUE_" not in result`); `tests/unit/test_helm_client_run.py` — 3 wiring assertions using tracking-redactor closure. Plan 05-02 landed before 05-04 (PR-comment). |
| **SC2 (PIPE-02 + PIPE-03)** — `ACTION=diff` runs `helm diff upgrade` via bundled helm-diff 3.10; prints colored diff to stdout without mutating cluster; when `$BITBUCKET_PR_ID` set + `POST_DIFF_AS_COMMENT=true`, posts masked diff via Bitbucket REST API | **YES** | `Dockerfile:92–112` — `helm-diff-fetch` stage, v3.10.0 pinned, SHA256-verified via upstream checksums file, COPY to `/home/pipe/.local/share/helm/plugins/diff`. `Dockerfile:151` — `RUN helm diff version` smoke-test at build time. `helm/client.py` — `_build_diff_argv()` + `diff()` methods; diff() routes stdout through `self._redactor` (line 500); exit code 1 is success (diff exists), ≥2 raises HelmExecutionError. `actions/diff.py` — `DiffAction`: chart resolve → `client.diff()` → emit already-redacted diff + `_maybe_post_pr_comment(diff_text)`. `cli.py:95` — `if settings.action == "diff" or (settings.action == "upgrade" and settings.dry_run): return DiffAction(...).run(pipe)`. `bitbucket/pr_comment.py` — stdlib `urllib.request`; GET/POST/PUT idempotency via `<!-- aws-eks-helm-deploy:diff -->` marker; `_sanitize_response_body` scrubs token on 4xx/5xx. Tests: `test_diff_action.py` (18 tests), `test_pr_comment.py` (14 tests), `test_helm_client_argv.py` (5 diff-argv tests), `test_helm_client_run.py` (7 diff run-mode tests), `test_cli.py` (4 dispatch tests). |
| **SC3 (PIPE-04 + PIPE-05)** — `ACTION=rollback` + `REVISION=<n>` invokes `helm rollback`; when `SAFE_UPGRADE=true`, `--wait --atomic --description "pipe:safe-upgrade"` added to upgrade; pre-flight history check refuses rollback to non-safe revisions | **YES** | `helm/client.py:61` — `SAFE_UPGRADE_DESCRIPTION: Final[str] = "pipe:safe-upgrade"`. `helm/client.py:260` — `argv.extend(["--wait", "--atomic", "--description", SAFE_UPGRADE_DESCRIPTION])` when `safe_upgrade=True`. `actions/upgrade.py:215, 230` — `safe_upgrade=s.safe_upgrade` forwarded at both `upgrade_install` call sites. `actions/rollback.py` — `_run_rollback()` calls `client.history()` (Phase 4 existing method), finds target revision, checks `SAFE_UPGRADE_DESCRIPTION in target.description`; raises `ChartResolutionError` with consumer-friendly message if absent or revision not found. `cli.py:99–100` — `if settings.action == "rollback": return RollbackAction(settings, strategy=strategy).run(pipe)`. Tests: `test_rollback_action.py` (10 tests), `test_helm_client_argv.py` (5 new — SAFE_UPGRADE argv + rollback argv), `test_helm_client_run.py` (7 new — rollback run-mode + redactor + timeout branches), `test_upgrade_action.py` (2 new — safe_upgrade forwarding), `test_cli.py` (2 new — rollback dispatch). |
| **SC4 (META-02 + META-03 + MIG-02)** — `INJECT_BITBUCKET_METADATA` unset → no `bitbucket.*` injected; chart's `values.yaml` with `bitbucket:` without opt-in → loud WARN; v1 env vars `SET`/`VALUES` trigger startup deprecation WARN. Closes #16 | **YES** | `settings.py:152` — `inject_bitbucket_metadata: bool \| None = Field(default=None, alias="INJECT_BITBUCKET_METADATA")` (tri-state; was `bool = False`). `actions/upgrade.py:195` — `build_bitbucket_set_args(logger) if s.inject_bitbucket_metadata else []` — `None` and `False` are both falsy (META-02 default-off). `actions/upgrade.py:94–130` — `BITBUCKET_VALUES_REGEX: Final[re.Pattern[str]]` + `_check_bitbucket_values_yaml()` emits `"meta.bitbucket_values_detected_without_opt_in"` WARN exactly when regex matches AND `inject_bitbucket_metadata is None`; called after `chart_source.resolve()` (D4 ordering). `cli.py:41–57` — `V1_DEPRECATED_ENV_VARS = ("SET", "VALUES")`; `_warn_on_v1_env_vars()` emits `"mig.v1_env_var_detected"` WARN unconditionally at startup. Tests: `test_upgrade_action.py` (+22 tests covering META-02 tri-state + META-03 detection paths + BITBUCKET_VALUES_REGEX correctness), `test_cli.py` (+6 MIG-02 tests including integration test asserting WARN precedes auth log). |

---

## Locked Decisions (D1–D6)

| Decision | Honoured? | Evidence |
|----------|-----------|----------|
| **D1** — `helm/redact.py::redact_helm_output` uses `yaml.safe_load_all` + Secret-kind filter + `yaml.safe_dump_all(sort_keys=False)`; YAMLError → passthrough; HelmClient routes every capture through `self._redactor` | **YES** | `helm/redact.py:61–83` — exact algorithm. `helm/client.py:189, 192` — `redactor=` kwarg, `self._redactor` stored. 12 capture sites verified by grep count. No-Secret early-return (line 79) is the auto-corrected Rule 1 fix from 05-02-SUMMARY. |
| **D2** — `helm-diff-fetch` multi-stage; v3.10.0 pinned; SHA256 via upstream checksums file; COPY to `/home/pipe/.local/share/helm/plugins/diff` (NOT `/root/`, NOT `helm-diff`) | **YES** | `Dockerfile:92` (`FROM ... AS helm-diff-fetch`). `Dockerfile:98` (`ARG HELM_DIFF_VERSION`). `Dockerfile:107–110` (upstream `helm-diff_checksums.txt` + `sha256sum -c`). `Dockerfile:139` (`COPY --from=helm-diff-fetch /tmp/diff /home/pipe/.local/share/helm/plugins/diff`). Both path corrections from 05-RESEARCH applied. |
| **D3** — stdlib `urllib.request` only; marker-based single-comment-per-PR; 4xx-tolerant WARN only; `_sanitize_response_body` strips token | **YES** | `bitbucket/pr_comment.py:30–32` — `import urllib.error`, `import urllib.request` (no `requests`, no `bitbucket_pipes_toolkit`). `MARKER` constant at :41. `_sanitize_response_body(body, token)` at :56 — strips token literal + `Authorization: Bearer` header line. All 4xx/5xx paths call `logger.warning` with sanitized body and return (no raise). |
| **D4** — META detection: static grep `r"^\s*bitbucket\s*:"` on resolved chart's `values.yaml`; one-time WARN; tri-state `inject_bitbucket_metadata: bool \| None = None` | **YES** | `settings.py:152` (tri-state field). `actions/upgrade.py:94` — `BITBUCKET_VALUES_REGEX = re.compile(r"^\s*bitbucket\s*:", re.MULTILINE)`. `_check_bitbucket_values_yaml()` at :101–130 — reads `values.yaml` once, applies regex, WARNs only when result AND `inject_bitbucket_metadata is None`. Called after `resolve()` as D4 requires. |
| **D5** — `--description "pipe:safe-upgrade"` on upgrade when `safe_upgrade=True`; rollback pre-flight checks `HelmRevision.description` for substring; `HelmClient.history()` REUSED from Phase 4 | **YES** | `helm/client.py:260` — `argv.extend(["--wait", "--atomic", "--description", SAFE_UPGRADE_DESCRIPTION])`. `actions/rollback.py:157, 167` — `client.history()` reused (not re-implemented); `SAFE_UPGRADE_DESCRIPTION not in target.description` is the safety gate. Research correction from 05-CONTEXT.md applied verbatim. |
| **D6** — subprocess restricted to exactly 2 files (`helm/client.py` + `chart/oci.py`); Phase 4 D5 scope unchanged | **YES** | `grep -rE '^import subprocess' src/aws_eks_helm_deploy/` — EXACTLY 2 files. `helm/redact.py` is pure Python (yaml + re only). `bitbucket/pr_comment.py` uses `urllib.request`, no subprocess. All new action modules have no subprocess imports. |

---

## Risks (R1–R3)

| Risk | Mitigated? | Evidence |
|------|-----------|----------|
| **R1** — Log masking misses a Helm output channel (e.g. `helm get manifest` in a future feature) | **YES** | Centralized in `helm/redact.py`; every `HelmClient` method that captures stdout/stderr routes through `self._redactor` (12 call sites verified). New methods added in Phase 5 (`diff()`, `rollback()`) follow the same pattern. Fuzz test with 5 parametrized multi-doc Secret permutations asserts `"FUZZ_SECRET_VALUE_" not in result`. |
| **R2** — PR-comment poster leaks credentials in error paths | **YES** | `bitbucket/pr_comment.py::_sanitize_response_body(body, token)` — replaces all occurrences of token value with `[BITBUCKET_TOKEN: <redacted>]` AND replaces Authorization header lines with `[Authorization: <redacted>]`. Called on GET/POST/PUT error paths (:164, :176, :210). `test_401_get_token_is_scrubbed_from_warn_log` and `test_401_get_authorization_header_stripped_from_warn_log` are the regression gates (T-05-02). |
| **R3** — `--atomic` + HISTORY_MAX interaction (Pitfall #3): `--wait`-less prior revision breaks rollback target | **YES** — belt-and-suspenders | `SAFE_UPGRADE=true` couples all three flags (`--wait`, `--atomic`, `--description "pipe:safe-upgrade"`). `RollbackAction._run_rollback()` pre-flight rejects rollback to revisions whose description does not contain `"pipe:safe-upgrade"` — specifically prevents rolling back to `--wait`-less revisions. Consumer-facing error message names `SAFE_UPGRADE=true` as the remedy. Documented in `docs/guides/v1-to-v2.md`. |

---

## Requirements Coverage (8 REQs)

| REQ | Status | Plan | Evidence |
|-----|--------|------|----------|
| **SEC-06** | SATISFIED | 05-02 | `helm/redact.py::redact_helm_output` + 12 `self._redactor` call sites in `helm/client.py`; `test_helm_redact.py` (10 funcs) + `test_helm_client_run.py` (3 wiring tests); fuzz test proves no secret bytes in any output |
| **PIPE-02** | SATISFIED | 05-03 | `helm-diff-fetch` Dockerfile stage + `HelmClient.diff()` + `DiffAction` + `cli.py` dispatch for `ACTION=diff` and `DRY_RUN=true`; `test_diff_action.py` (18 tests) + 5 argv + 7 run-mode tests |
| **PIPE-03** | SATISFIED | 05-04 | `bitbucket/pr_comment.py` — stdlib urllib, GET/POST/PUT idempotency, `_sanitize_response_body`, marker-based; wired in `DiffAction._maybe_post_pr_comment` behind 5-gate conditional; `test_pr_comment.py` (14 tests) + 7 diff-action PR-comment integration tests |
| **PIPE-04** | SATISFIED | 05-05 | `HelmClient.rollback()` + `HelmClient._build_rollback_argv()` in `helm/client.py`; `RollbackAction` in `actions/rollback.py`; `cli.py:99–100` dispatch; `test_rollback_action.py` (10 tests) |
| **PIPE-05** | SATISFIED | 05-05 | `SAFE_UPGRADE_DESCRIPTION` constant; `_build_argv` safe_upgrade kwarg adds `--wait --atomic --description "pipe:safe-upgrade"`; `UpgradeAction` forwards at both call sites; `_run_rollback` pre-flight checks description substring; 5 argv + 2 upgrade + 10 rollback tests |
| **META-02** | SATISFIED | 05-01 + 05-06 | `Settings.inject_bitbucket_metadata: bool \| None = None` (tri-state, default None); `upgrade.py:195` — falsy gate means None and False both skip injection; 3 META-02 tri-state integration tests |
| **META-03** | SATISFIED | 05-06 | `BITBUCKET_VALUES_REGEX + _check_bitbucket_values_yaml()` in `actions/upgrade.py`; `re.MULTILINE` matches top-level + indented `bitbucket:` keys; WARN event `meta.bitbucket_values_detected_without_opt_in`; 9 detection unit tests + 4 regex correctness tests |
| **MIG-02** | SATISFIED | 05-06 + 05-07 | `_warn_on_v1_env_vars()` in `cli.py` — unconditional `os.environ` scan at startup for `"SET"` and `"VALUES"`, WARN event `mig.v1_env_var_detected`; `docs/guides/v1-to-v2.md` (363 lines, both event names documented verbatim, before-after examples); 6 MIG-02 tests |

---

## Notes for the Shipper

1. **SHA256 enforcement mechanism:** The SHA256 `a7875d4656...` appears as a comment in `Dockerfile:103` for documentation. The actual enforcement is the upstream checksums file approach at `Dockerfile:110` (`grep "  helm-diff-linux-amd64.tgz$" helm-diff_checksums.txt | sha256sum -c`) — matching the D2 contract ("preferred over committed checksum"). This is correct and matches D2 spec. The comment hash provides a cross-check reference.

2. **`"BITBUCKET_TOKEN"` in settings.py:** The `Field(alias="BITBUCKET_TOKEN")` at `settings.py:159` is the Pydantic environment-variable alias — the standard pattern used throughout this project for all env-var mappings. It is not a credential leak and satisfies security invariant SI-1's intent ("only `Settings.bitbucket_token` field references").

3. **`SAFE_UPGRADE_DESCRIPTION` in `actions/upgrade.py`:** The SAFE_UPGRADE_DESCRIPTION constant is imported in `rollback.py` but NOT directly in `upgrade.py` — `upgrade.py` uses `SAFE_UPGRADE_DESCRIPTION` transitively via the `helm/client.py` `_build_argv` method (the constant is defined there and used at line 260). The `safe_upgrade=s.safe_upgrade` kwarg threading is the wiring mechanism. This is correct per D5.

4. **Migration guide is a DRAFT (Phase 7 polishes):** `docs/guides/v1-to-v2.md` ships as plain Markdown (no mkdocs-material admonitions) per D context — Phase 7 wraps with mkdocs polish. 363 lines, 8 H2 headings, 14 fenced code blocks. MIG-02 is marked "partial" in the 05-07 summary because the Phase 7 polish pass is explicitly out of scope for Phase 5.

5. **helm diff exit-code semantics:** `HelmClient.diff()` treats exit code 0 (no diff) and 1 (diff exists) both as success; only ≥2 raises `HelmExecutionError`. This matches the upstream helm-diff plugin contract.

6. **Redactor in PR comment:** The PR comment poster (`post_diff_comment`) receives `diff_text` that is ALREADY redacted by `HelmClient.diff()` routing stdout through `self._redactor`. The `pr_comment.py` module does not call `redact_helm_output` directly — the redaction happens upstream at the HelmClient layer (D1 architecture). This is the correct design: single redaction point, then the already-clean string propagates to all callers.

7. **Phase 5 test count:** Phase 4 baseline was 340 tests. Phase 5 shipped 469 tests — an increase of 129 tests across 7 plans. All 469 pass in 2.16 s.

---

*Verified 2026-06-20 by `gsd-verifier` (Sonnet 4.6, goal-backward stance).*
