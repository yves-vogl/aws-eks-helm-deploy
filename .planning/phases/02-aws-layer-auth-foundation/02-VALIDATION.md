---
phase: 2
slug: aws-layer-auth-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-17
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (inherited from Phase 1) |
| **Mocking** | moto 5.2.x `@mock_aws` for STS / EKS; `pytest-mock` for boto3 client patching |
| **Config file** | `pyproject.toml` (no Phase 2 modifications — Phase 1 already wired `--cov-fail-under=100`) |
| **Quick run command** | `uv run pytest -q --no-cov` (unit tier, no gate; < 5s including moto warmup) |
| **Full suite command** | `uv run pytest && uv run pytest -m integration --no-cov && uv run pytest -m acceptance --no-cov` |
| **Estimated runtime** | unit ~5s (moto adds ~1s warm-up) · integration ~30s (kind reuse from Phase 1 fixture) · acceptance ~60s (unchanged) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q --no-cov` (~5s; unit tier, no gate) — verifies the freshly committed module + existing 33+ Phase 1 tests stay green.
- **After every plan wave merge:** Run the full suite: `uv run pytest` (with the 100% gate) + `pytest -m integration --no-cov` (when kind is installed).
- **Before `/gsd-verify-work`:** Full suite green AND `uv run mypy --strict src` AND `uv run ruff check src tests` AND `uv run ruff format --check src tests` AND `uv run pre-commit run --all-files` ALL exit 0.
- **Max feedback latency:** < 5s per task commit (unit-tier quick run); < 90s per wave merge.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | SC | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|----|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-1-01 | 02-01 | 1 | AUTH-07 | SC1 | T-02-01-02 | EksTokenError surfaces public STS error codes only — no credential leak | unit | `uv run pytest -m unit -q tests/unit/test_errors.py --no-cov` | ❌ W0 | ⬜ pending |
| 02-1-02 | 02-01 | 1 | AUTH-07 | SC2 (structural; see deviation), SC3 | T-02-01-01, T-02-01-03, T-02-01-04 | Regional STS endpoint enforced; SigV4 signature covers `x-k8s-aws-id`; awscli import absent (audit grep gate) | unit | `uv run pytest -m unit -q tests/unit/test_eks_token.py --cov=aws_eks_helm_deploy.aws.eks_token --cov-branch --cov-fail-under=100 --no-header && grep -RIn '^\\s*from awscli' src/ \| awk 'NR>0{exit 1}'` | ❌ W0 | ⬜ pending |
| 02-2-01 | 02-02 | 1 | AUTH-01 | SC1, SC4 | T-02-02-01, T-02-02-02, T-02-02-03 | AwsCredentials.\_\_repr\_\_ masks secret; to_boto3_kwargs collides with CREDENTIAL_BLOCKLIST (raises ValueError when fed into bind_safe_context); frozen dataclass | unit | `uv run pytest -m unit -q tests/unit/test_auth_base.py --cov=aws_eks_helm_deploy.auth.base --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 02-3-01 | 02-03 | 2 | AUTH-01 | SC1, SC4 | (delegated to T-02-02-*) | StaticKeysStrategy is pure value-object wrapper — no AWS imports; satisfies AuthStrategy Protocol structurally | unit | `uv run pytest -m unit -q tests/unit/test_static_keys.py --cov=aws_eks_helm_deploy.auth.static_keys --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 02-3-02 | 02-03 | 2 | AUTH-02 | SC1, SC4 | T-02-03-01, T-02-03-02, T-02-03-04 | Regional STS endpoint enforced; ClientError → AuthenticationError; base strategy delegated to via .get_credentials() | unit | `uv run pytest -m unit -q tests/unit/test_assume_role.py --cov=aws_eks_helm_deploy.auth.assume_role --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 02-4-01 | 02-04 | 3 | AUTH-01, AUTH-02 | SC1 | T-02-04-02, T-02-04-03 | select_strategy decision tree covers all four branches; _derive_session_name enforces 64-char limit and IAM regex | unit | `uv run pytest -m unit -q tests/unit/test_auth_select.py --cov=aws_eks_helm_deploy.auth --cov-branch --cov-fail-under=100 --no-header` | ❌ W0 | ⬜ pending |
| 02-4-02 | 02-04 | 3 | AUTH-01, AUTH-02 | SC1; closes Phase 1 OBS-01 PARTIAL | T-02-04-01, T-02-04-04, T-02-04-05 | bind_safe_context called with auth_strategy class name only (never credential values); ConfigurationError surfaces via pipe.fail; structlog emits ≥1 JSON line on stderr | unit | `uv run pytest -m unit -q tests/unit/test_cli.py --cov=aws_eks_helm_deploy.cli --cov-branch --cov-fail-under=100 --no-header && uv run pytest -q` | ❌ W0 | ⬜ pending |
| 02-4-03 | 02-04 | 3 | AUTH-07 (end-to-end shape) | SC4 | (delegated to T-02-01-*) | End-to-end token shape on kind cluster name — no real EKS webhook validation (out of scope per RESEARCH G) | integration | `uv run pytest -m integration -q --no-cov tests/integration/test_auth_smoke.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave dependency notes:**
- **Wave 1 (parallel):** 02-01 + 02-02 — no inter-dependency; can ship in either order.
- **Wave 2 (depends on Wave 1):** 02-03 depends on 02-02 (`auth/base.py` exports). 02-03 does NOT depend on 02-01 (independent file paths).
- **Wave 3 (depends on Wave 1 + Wave 2):** 02-04 depends on 02-01 (`generate_eks_token`), 02-02 (Protocol + dataclass), AND 02-03 (concrete strategies). Composition root.
- **File-overlap check:** No same-wave plans share any `files_modified` entry. `errors.py` is modified only by 02-01 (Wave 1). `settings.py` may be modified only by 02-04 (Wave 3) — to add `aws_session_token` field if not already present.

**Strict ordering enforcement:**
- 02-04 Task 02-4-02 (cli wire-in) modifies `cli.py` — this is the same file Phase 1's PLAN-01 created. The Phase 1 placeholder action message text changes; no behavioral break.
- 02-04 Task 02-4-02 also modifies `tests/unit/test_cli.py` — existing 4 Phase 1 tests get a fixture-based short-circuit; their assertions remain valid.

---

## Wave 0 Requirements

All Phase 2 test infrastructure builds on Phase 1's foundation (test tiers, conftest, kind fixture). New files created BEFORE tests can be exercised:

- [ ] `src/aws_eks_helm_deploy/aws/__init__.py` (Plan 02-01, Task 02-1-01) — required before `test_eks_token.py` can import.
- [ ] `src/aws_eks_helm_deploy/aws/eks_token.py` (Plan 02-01, Task 02-1-02) — required before any unit OR integration test of token generation.
- [ ] `src/aws_eks_helm_deploy/errors.py` (Plan 02-01, Task 02-1-01) — EksTokenError needed before token-gen error tests.
- [ ] `src/aws_eks_helm_deploy/auth/__init__.py` (Plan 02-02 empty placeholder; Plan 02-04 fills it) — package marker required.
- [ ] `src/aws_eks_helm_deploy/auth/base.py` (Plan 02-02, Task 02-2-01) — Protocol + dataclass required by 02-03 and 02-04 modules.
- [ ] `src/aws_eks_helm_deploy/auth/static_keys.py` (Plan 02-03, Task 02-3-01) — required by 02-04 select_strategy.
- [ ] `src/aws_eks_helm_deploy/auth/assume_role.py` (Plan 02-03, Task 02-3-02) — required by 02-04 select_strategy.
- [ ] `tests/unit/test_eks_token.py` (Plan 02-01, Task 02-1-02) — first to land; covers AUTH-07 unit surface.
- [ ] `tests/unit/test_auth_base.py` (Plan 02-02, Task 02-2-01) — covers AUTH-01 Protocol/dataclass surface.
- [ ] `tests/unit/test_static_keys.py` (Plan 02-03, Task 02-3-01) — covers AUTH-01 strategy surface.
- [ ] `tests/unit/test_assume_role.py` (Plan 02-03, Task 02-3-02) — covers AUTH-02 strategy surface.
- [ ] `tests/unit/test_auth_select.py` (Plan 02-04, Task 02-4-01) — covers AUTH-01 + AUTH-02 decision-tree surface.
- [ ] `tests/integration/test_auth_smoke.py` (Plan 02-04, Task 02-4-03) — covers AUTH-07 end-to-end shape.

Existing Phase 1 infrastructure REUSED (no new files):
- `tests/conftest.py` (auto-mark hook).
- `tests/integration/conftest.py::kind_cluster` (session fixture, reused by 02-4-03's Test 2).
- `tests/acceptance/conftest.py::built_image` (NOT reused in Phase 2 — acceptance tier is unchanged; Phase 1's three acceptance tests still pass).
- `pyproject.toml` `[tool.pytest.ini_options].addopts` already has `--cov-fail-under=100` — Phase 2 inherits the gate.

When all source files in 02-01..04 have merged AND their corresponding test files exist AND `pytest -q` exits 0 at 100% coverage, the Phase 2 validation contract is fully active.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AUTH-07 absence of `awscli` import in source (audit grep) | AUTH-07 | A unit test for "the codebase contains no `awscli` import" is structurally a code-grep; it does not add unit-test value. Surfaced here as the canonical gate. | `grep -RIn '\\bawscli\\b' src/ \|\| echo "OK: no awscli reference in src/"`. Expected: NO matching lines. If any line matches, AUTH-07 is violated. |
| AUTH-07 absence of `awscli` from the built Docker image | AUTH-07 (image side) | Phase 1 verified no `awscli` in Dockerfile via the IMAGE-* gates; Phase 2 inherits. A live-image check is host-dependent. | `docker run --rm aws-eks-helm-deploy:dev python -c "import awscli" 2>&1 \| grep "No module named"` — expects ModuleNotFoundError. |
| Phase 1 OBS-01 PARTIAL closure | OBS-01 (Phase 1 carry-over) | Manual smoke against Docker confirms the JSON-line emission added by Task 02-4-02. | `LOG_FORMAT=json AWS_ACCESS_KEY_ID=AKIA-FAKE AWS_SECRET_ACCESS_KEY=fake docker run --rm -e LOG_FORMAT=json -e AWS_ACCESS_KEY_ID=AKIA-FAKE -e AWS_SECRET_ACCESS_KEY=fake-secret -e CLUSTER_NAME=test aws-eks-helm-deploy:dev 2>&1 \| python3 -c "import sys, json; [json.loads(l) for l in sys.stdin if l.strip()]"` — exits 0 once at least one JSON line is emitted. |
| Integration test on kind | AUTH-07 end-to-end | Requires kind + docker locally; CI gating lands in Phase 6. | `uv run pytest -m integration -q --no-cov tests/integration/test_auth_smoke.py` — both tests pass; cluster is created+torn down by Phase 1 fixture. |
| `RoleSessionName` truncation visible in STS CloudTrail | AUTH-02 (operational) | Requires a real AWS account and CloudTrail access; not gateable in CI. | Manual smoke once Phase 2 ships in a dev/staging Bitbucket pipeline against a real EKS cluster. The session name should appear in CloudTrail under the assumed-role event and should be ≤ 64 chars matching `[\\w+=,.@-]+`. |

*All other phase behaviors have automated verification.*

---

## ROADMAP / RESEARCH Deviation Surface

This phase ships THREE documented deviations from the ROADMAP wording. They are intentional and surfaced here so the phase-checker / plan-checker can verify them up-front:

1. **ROADMAP Phase 2 SC2 "byte-equal" wording** is structurally impossible (timestamp + HMAC vary per call). Replaced with **structural equivalence** per RESEARCH Section A. (See `02-01-PLAN.md <deviations>` section.)
2. **`EksTokenError.exit_code = 3`** is intentionally shared with `ClusterAccessError` (both are EKS-reach failures from the consumer's perspective). Distinct exit codes would not add consumer value. (See `02-01-PLAN.md <deviations>` section.)
3. **Phase 1 OBS-01 PARTIAL gap** is closed in Phase 2 by adding `logger.info("auth strategy selected", auth_strategy=...)` to `cli.py`. The Phase 1 verifier's "human_needed" verdict can be retroactively resolved when Phase 2 ships. (See `02-04-PLAN.md <deviations>` Deviation 2.)

The phase-checker / phase-verifier MUST acknowledge these deviations before flagging them as gaps in `02-VERIFICATION.md`.

---

## Coverage Roll-Up

Phase 2 adds the following modules; all MUST hit 100% line + 100% branch by the end of the phase (per the active `--cov-fail-under=100` gate from Phase 1):

| Module | Owner Plan | Coverage Target | Branch Coverage Note |
|--------|------------|------------------|----------------------|
| `src/aws_eks_helm_deploy/aws/__init__.py` | 02-01 | 100% (trivial) | No branches. |
| `src/aws_eks_helm_deploy/aws/eks_token.py` | 02-01 | 100% line + 100% branch | Both `ClientError` and `NoCredentialsError` branches must be exercised. |
| `src/aws_eks_helm_deploy/auth/__init__.py` | 02-02 (empty) → 02-04 (filled) | 100% line + 100% branch | All four `select_strategy` decision branches + all four `_derive_session_name` fallback paths. |
| `src/aws_eks_helm_deploy/auth/base.py` | 02-02 | 100% line + 100% branch | The `len(access_key_id) < 4` branch in `__repr__` must be exercised. |
| `src/aws_eks_helm_deploy/auth/static_keys.py` | 02-03 | 100% line + 100% branch | Trivial — pure value-object wrapper. |
| `src/aws_eks_helm_deploy/auth/assume_role.py` | 02-03 | 100% line + 100% branch | Both `ClientError` and `NoCredentialsError` branches must be exercised. |
| `src/aws_eks_helm_deploy/cli.py` | extended by 02-04 | 100% line + 100% branch | New `except PipeError` on `select_strategy` must be exercised. |
| `src/aws_eks_helm_deploy/errors.py` | extended by 02-01 | 100% (existing 100% + new EksTokenError class) | New class tested in `test_errors.py`. |
| `src/aws_eks_helm_deploy/settings.py` | conditionally extended by 02-04 | 100% (already at 100% from Phase 1; new `aws_session_token` field is field-declaration only, no branch) | If the field is already present from Phase 1 (planner expects so), no coverage change. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify OR documented Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (8 tasks across 4 plans, every task has an automated verify)
- [ ] Wave 0 covers all MISSING references (see Wave 0 Requirements above)
- [ ] No watch-mode flags (no `--watch`, no `pytest-watch`)
- [ ] Feedback latency < 5s per task quick-run (verified locally: moto warmup ~1s + test execution < 4s)
- [ ] All three documented deviations are surfaced to the phase-checker (this file's "ROADMAP / RESEARCH Deviation Surface" section)
- [ ] `nyquist_compliant: true` to be set after Wave 3 lands and the full unit + integration suites pass

**Approval:** pending
