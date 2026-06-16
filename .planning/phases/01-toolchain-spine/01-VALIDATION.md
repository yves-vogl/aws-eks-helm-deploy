---
phase: 1
slug: toolchain-spine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — created in Plan A Task A1, hardened by Plan B Task B1 (adds `--cov-fail-under=100`) |
| **Quick run command** | `uv run pytest -q --no-cov` (unit tier, no gate; < 3s) |
| **Full suite command** | `uv run pytest && uv run pytest -m integration --no-cov && uv run pytest -m acceptance --no-cov` |
| **Estimated runtime** | unit ~3s · integration ~30s (kind cluster lifecycle) · acceptance ~60s (docker build cold) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q --no-cov` (~3s; unit tier, no gate) — verifies the freshly committed module still imports and existing unit tests stay green.
- **After every plan wave merge:** Run the full suite: `uv run pytest` (with the 100% gate) + `pytest -m integration --no-cov` + `pytest -m acceptance --no-cov` if Plan C has merged.
- **Before `/gsd-verify-work`:** Full suite green AND `uv run mypy --strict src` AND `uv run ruff check src tests` AND `uv run ruff format --check src tests` AND `uv run pre-commit run --all-files` ALL exit 0.
- **Max feedback latency:** < 5s per task commit (unit-tier quick run with no-cov); < 90s per wave merge (full suite cold).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-A-01 | A | 1 | TOOL-01, TOOL-02 | T-01-A-01 (lockfile drift), T-01-A-SC | `uv sync --frozen` is the only resolver call; `requirements.txt` removed | smoke | `uv sync --all-extras --frozen && uv run python -c "import aws_eks_helm_deploy; import bitbucket_pipes_toolkit; import boto3; import pydantic_settings; import structlog"` | ❌ W0 | ⬜ pending |
| 01-A-02 | A | 1 | TOOL-02, TOOL-03, TOOL-04 | T-01-A-02 (env-var injection), T-01-A-03 (fail message disclosure) | pydantic validates env vars; `pipe.fail` accepts only message strings | unit + lint | `uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy --strict src && uv run pytest -m unit -q --no-cov` | ❌ W0 | ⬜ pending |
| 01-A-03 | A | 1 | TOOL-05 | T-01-A-04 (pre-commit pinned) | hooks pinned to exact maintainer versions | lint | `uv run pre-commit run --all-files` | ❌ W0 | ⬜ pending |
| 01-B-01 | B | 2 | TOOL-06 | — | 100% coverage gate prevents un-tested code paths shipping | unit | `uv run pytest -q` (default: unit + `--cov-fail-under=100`) | ❌ W0 | ⬜ pending |
| 01-B-02 | B | 2 | TOOL-07 | T-01-B-01 (fixture fail-open) | kind cluster torn down on teardown regardless of test outcome | integration | `uv run pytest -m integration -q --no-cov` | ❌ W0 | ⬜ pending |
| 01-B-03 | B | 2 | TOOL-08 | T-01-B-04 (non-root gate) | acceptance asserts uid != 0 AND uid >= 10000 inside the image | acceptance | `uv run pytest -m acceptance -q --no-cov` (after Plan C merges) | ❌ W0 | ⬜ pending |
| 01-C-01 | C | 2 | IMAGE-01, IMAGE-02, IMAGE-03 | T-01-C-04 (root container), T-01-C-05 (frozen resolver) | runtime uid=10001; `uv sync --frozen --no-dev` only | acceptance | `docker build -t aws-eks-helm-deploy:dev . && docker run --rm --entrypoint id aws-eks-helm-deploy:dev -u | grep 10001 && docker run --rm --entrypoint helm aws-eks-helm-deploy:dev diff version` | ❌ W0 | ⬜ pending |
| 01-C-02 | C | 2 | IMAGE-01..03 | T-01-C-03 (build context disclosure) | `.dockerignore` excludes `.git`, `.planning`, `tests` | acceptance | `docker build -t aws-eks-helm-deploy:ctx-test . && docker rmi aws-eks-helm-deploy:ctx-test` | ❌ W0 | ⬜ pending |
| 01-C-03 | C | 2 | IMAGE-05 | T-01-C-06 (commit metadata in annotations) | annotations are intentional supply-chain provenance | manual + automated | `grep -c 'manifest:org.opencontainers.image' docs/build.md \| awk '$1 >= 6 {exit 0} {exit 1}'`; manual verify via `docker buildx imagetools inspect` | ❌ W0 | ⬜ pending |
| 01-D-01 | D | 2 | OBS-01, OBS-02 | T-01-D-01 (credential binding) | `bind_safe_context` raises ValueError on blocklisted keys | unit | `uv run mypy --strict src/aws_eks_helm_deploy/logging.py && uv run python -c "from aws_eks_helm_deploy.logging import bind_safe_context; import pytest;\nimport sys;\ntry: bind_safe_context(aws_access_key_id='leak')\nexcept ValueError: sys.exit(0)\nelse: sys.exit(1)"` | ❌ W0 | ⬜ pending |
| 01-D-02 | D | 2 | OBS-01, OBS-02 | T-01-D-04 (timestamp missing) | `TimeStamper(fmt='iso')` always in shared_processors | unit | `uv run pytest tests/unit/test_logging.py -q --no-cov && uv run coverage report --include='src/aws_eks_helm_deploy/logging.py' --fail-under=100` | ❌ W0 | ⬜ pending |
| 01-D-03 | D | 2 | OBS-01 | T-01-D-02 (direct bind bypass) | `cli.main` calls `configure_logging(settings)` between Settings() and PipeIO() | unit | `uv run pytest tests/unit/test_cli.py -q --no-cov && uv run mypy --strict src && uv run ruff check src tests` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave dependency notes:**
- Plans A and C reference Wave 1 conceptually but C `COPY`s Plan A artifacts so C is scheduled in Wave 2 alongside B and D.
- Plan B Task B1 (flipping `--cov-fail-under=100`) MUST run after Plan D merges, because Plan D adds `logging.py` whose coverage must be at 100% before the gate trips.
- Within Wave 2: D → (B Task B1) is a hard order; C is independent of B and D and can interleave.

---

## Wave 0 Requirements

All Phase 1 test infrastructure is greenfield. Wave 0 = the union of files created by Plans A, B, D before any test can be exercised:

- [ ] `pyproject.toml` — pytest, coverage, ruff, mypy config (Plan A, Task A1)
- [ ] `.pre-commit-config.yaml` — local lint/type/test gate (Plan A, Task A3)
- [ ] `tests/__init__.py`, `tests/unit/__init__.py` — package markers (Plan A, Task A2)
- [ ] `tests/conftest.py` — top-level fixtures + default-marker hook (Plan B, Task B1)
- [ ] `tests/unit/test_settings.py`, `test_errors.py`, `test_pipe_io.py`, `test_cli.py` — Plan A unit tests (Plan A, Task A2)
- [ ] `tests/unit/test_logging.py` — Plan D unit tests (Plan D, Task D2)
- [ ] `tests/integration/__init__.py`, `conftest.py`, `test_helm_smoke.py` — Plan B integration tier (Plan B, Task B2)
- [ ] `tests/acceptance/__init__.py`, `conftest.py`, `test_image_smoke.py` — Plan B acceptance tier (Plan B, Task B3)
- [ ] `Makefile` — DX targets (Plan B, Task B3)
- [ ] `Dockerfile` + `.dockerignore` — required for the acceptance tier to build (Plan C, Task C1 + C2)

When all of the above exist and Plans A + D have merged before Plan B Task B1 flips the gate, the Phase 1 validation contract is fully active.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `uv sync --all-extras` < 10s warm cache | TOOL-01 | Wall-clock timing is host-dependent (CI runner vs M-series Mac vs Linux laptop); not stable as an automated gate | After Plan A Task A1: `time uv sync --all-extras --frozen` twice; second run should print real time < 10s on the developer's machine. Informational only — failure does not block; investigate if it regresses > 20s. |
| OCI annotations present on the built image | IMAGE-05 | `docker buildx imagetools inspect` output is buildx-version-dependent; brittle as a Phase 1 gate. Phase 6 release pipeline locks it in. | After Plan C Task C1: run the documented `docker buildx build --annotation ...` from `docs/build.md`; then `docker buildx imagetools inspect aws-eks-helm-deploy:dev | grep org.opencontainers.image` — all six annotations should be listed. |
| `LOG_FORMAT=json` actually emits one JSON object per line in production execution | OBS-01 | The unit test parses captured stderr lines; a smoke against the built Docker image gives end-to-end confidence. | After Plan C + D merge: `LOG_FORMAT=json docker run --rm aws-eks-helm-deploy:dev 2>&1 | head -5 | python -c "import sys, json; [json.loads(l) for l in sys.stdin]"` — exits 0. |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies declared
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (verified: A1/A2/A3 + B1/B2/B3 + C1/C2/C3 + D1/D2/D3 each have automated verify)
- [ ] Wave 0 covers all MISSING references (see Wave 0 Requirements above)
- [ ] No watch-mode flags (no `--watch`, no `pytest-watch`)
- [ ] Feedback latency < 5s per task quick-run
- [ ] `nyquist_compliant: true` to be set after Plan B Task B1 lands and the full suite gates pass

**Approval:** pending
