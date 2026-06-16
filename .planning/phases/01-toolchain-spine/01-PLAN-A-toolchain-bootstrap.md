---
phase: 01-toolchain-spine
plan: A
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - uv.lock
  - .python-version
  - .pre-commit-config.yaml
  - .gitignore
  - src/aws_eks_helm_deploy/__init__.py
  - src/aws_eks_helm_deploy/settings.py
  - src/aws_eks_helm_deploy/errors.py
  - src/aws_eks_helm_deploy/pipe_io.py
  - src/aws_eks_helm_deploy/cli.py
  - src/aws_eks_helm_deploy/__main__.py
  - tests/__init__.py
  - tests/unit/__init__.py
  - tests/unit/test_settings.py
  - tests/unit/test_errors.py
  - tests/unit/test_pipe_io.py
  - tests/unit/test_cli.py
autonomous: true
requirements:
  - TOOL-01
  - TOOL-02
  - TOOL-03
  - TOOL-04
  - TOOL-05
tags:
  - python
  - uv
  - ruff
  - mypy
  - pre-commit
  - bootstrap

must_haves:
  truths:
    - "Maintainer can run `uv sync --all-extras` and get a green `.venv/` with all dev tools in under 10s warm cache."
    - "`uv run ruff check src tests` exits 0 with zero findings on the v2 skeleton."
    - "`uv run ruff format --check src tests` exits 0."
    - "`uv run mypy --strict src` exits 0 with zero errors."
    - "`uv run pre-commit run --all-files` runs ruff + ruff-format + mypy + a unit-test hook locally and exits 0."
    - "The package `aws_eks_helm_deploy` is importable (`python -c 'import aws_eks_helm_deploy'` succeeds)."
    - "`requirements.txt` is removed from the repo (v1 dep manifest retired)."
  artifacts:
    - path: "pyproject.toml"
      provides: "Package metadata, runtime deps, dev/integration/acceptance dependency-groups, ruff/mypy/pytest/coverage tool config."
      contains: "[project]"
      min_lines: 80
    - path: "uv.lock"
      provides: "Pinned dep graph; CI uses `uv sync --frozen`."
    - path: ".python-version"
      provides: "Pins local interpreter to 3.13 (uv-managed)."
    - path: ".pre-commit-config.yaml"
      provides: "ruff, ruff-format, mypy, pytest-unit hooks."
      contains: "ruff-pre-commit"
    - path: "src/aws_eks_helm_deploy/__init__.py"
      provides: "Package root; exposes __version__."
      contains: "__version__"
    - path: "src/aws_eks_helm_deploy/settings.py"
      provides: "pydantic-settings `Settings` BaseSettings with every v1 env-var name as Field(alias=...)."
      contains: "class Settings"
    - path: "src/aws_eks_helm_deploy/errors.py"
      provides: "PipeError hierarchy with typed exit codes."
      contains: "class PipeError"
    - path: "src/aws_eks_helm_deploy/pipe_io.py"
      provides: "Thin adapter around bitbucket-pipes-toolkit (success/fail channels)."
      contains: "class PipeIO"
    - path: "src/aws_eks_helm_deploy/cli.py"
      provides: "`main(argv) -> int` entrypoint; catches PipeError, dispatches placeholder action."
      contains: "def main"
    - path: "src/aws_eks_helm_deploy/__main__.py"
      provides: "`python -m aws_eks_helm_deploy` ENTRYPOINT shim."
      contains: "from aws_eks_helm_deploy.cli import main"
  key_links:
    - from: "src/aws_eks_helm_deploy/cli.py"
      to: "src/aws_eks_helm_deploy/settings.py"
      via: "import + Settings() instantiation"
      pattern: "from aws_eks_helm_deploy.settings import Settings"
    - from: "src/aws_eks_helm_deploy/cli.py"
      to: "src/aws_eks_helm_deploy/errors.py"
      via: "except PipeError as exc"
      pattern: "except PipeError"
    - from: "src/aws_eks_helm_deploy/__main__.py"
      to: "src/aws_eks_helm_deploy/cli.py"
      via: "from aws_eks_helm_deploy.cli import main; sys.exit(main())"
      pattern: "from aws_eks_helm_deploy.cli import main"
    - from: "pyproject.toml [project.scripts]"
      to: "src/aws_eks_helm_deploy/cli.py::main"
      via: "console_script entry point"
      pattern: "aws-eks-helm-deploy = \"aws_eks_helm_deploy.cli:main\""
---

<objective>
Bootstrap the modern Python toolchain and the minimal `src/aws_eks_helm_deploy/` skeleton that downstream plans (B, C, D) depend on. After this plan: `uv sync --all-extras` produces a working `.venv/`, `ruff` + `mypy --strict` exit 0 on the source tree, pre-commit hooks run the same checks locally as CI, and a minimal unit-test layer for the four skeleton modules (`settings`, `errors`, `pipe_io`, `cli`) is in place (with full coverage configured but the strict 100% gate is wired in Plan B — Plan A passes pytest without the gate so we can iterate).

Purpose: Plan A delivers TOOL-01..05 (the toolchain side of Phase 1) and the skeleton modules without which Plans B (test infra), C (Dockerfile), and D (structured logging) cannot exist. `logging.py` is intentionally deferred to Plan D so OBS-01/02 lands in a focused commit.

Output:
- `pyproject.toml` + `uv.lock` + `.python-version` (TOOL-01, TOOL-02)
- `.pre-commit-config.yaml` (TOOL-05)
- `src/aws_eks_helm_deploy/` with `__init__.py`, `__main__.py`, `cli.py`, `settings.py`, `errors.py`, `pipe_io.py`
- `tests/unit/` covering all four skeleton modules (settings, errors, pipe_io, cli) — full-coverage gate wired in Plan B
- `requirements.txt` deleted (TOOL-02)
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-toolchain-spine/01-RESEARCH.md
@.planning/phases/01-toolchain-spine/01-PATTERNS.md
@pipe.yml
@pipe/schema.py
@pipe/pipe.py
@requirements.txt
@Dockerfile
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task A1: pyproject.toml + uv.lock + .python-version + .gitignore + requirements.txt removal</name>
  <files>pyproject.toml, uv.lock, .python-version, .gitignore, requirements.txt</files>
  <read_first>
    - .planning/phases/01-toolchain-spine/01-RESEARCH.md (Pattern 1: full `pyproject.toml` shape, Standard Stack table for version pins, Pitfall 1 on uv lock drift)
    - .planning/phases/01-toolchain-spine/01-PATTERNS.md (pyproject.toml section: env-var carry-over from `pipe/schema.py`, target shape)
    - requirements.txt (current v1 deps to retire: `awscli`, `docker`, `bitbucket-pipes-toolkit ~=4.4`, `Jinja2`, `MarkupSafe`)
    - pipe/schema.py (env-var names: AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, ROLE_ARN, SESSION_NAME, CLUSTER_NAME, CHART, RELEASE_NAME, NAMESPACE, CREATE_NAMESPACE, SET, VALUES, WAIT, DEBUG, TIMEOUT — preserved as Field(alias=...) in settings.py in Task A2)
  </read_first>
  <behavior>
    - After running `uv sync --all-extras`, `.venv/` contains: ruff 0.15.x, mypy 2.1.x, pytest 9.1.x, pytest-cov 7.1.x, pytest-mock 3.15.x, pytest-xdist 3.8.x, moto[eks,sts] 5.2.x, structlog 26.1.x, pydantic-settings 2.14.x, pre-commit 4.0.x, pip-audit 2.10.x, boto3 1.43.x, boto3-stubs[eks,sts], Jinja2 3.1.x, PyYAML 6.0.x, bitbucket-pipes-toolkit 6.2.x.
    - `uv sync --frozen` on a warm cache (lock present) completes in under 10 seconds (TOOL-01 target; do not gate the test on wall-clock — instead assert `uv sync --frozen --all-extras` exits 0 deterministically).
    - `uv.lock` is present and committed.
    - `requirements.txt` is removed (file deletion).
    - `.python-version` contains `3.13` on its only line.
    - `.gitignore` excludes `.venv/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `htmlcov/`, `.coverage`, `*.pyc`, `__pycache__/`, `dist/`, `*.egg-info/`.
  </behavior>
  <action>
    Create `pyproject.toml` using the exact shape from `01-PATTERNS.md` pyproject.toml section (which mirrors `01-RESEARCH.md` Pattern 1). Key points:
    - `[project]` block: `name = "aws-eks-helm-deploy"`, `version = "2.0.0-dev"`, `requires-python = ">=3.13"`, `dependencies` list per RESEARCH.md Standard Stack Core table (boto3 ~=1.43, bitbucket-pipes-toolkit ~=6.2, Jinja2 ~=3.1, PyYAML ~=6.0, structlog ~=26.0, pydantic-settings ~=2.14).
    - `[project.scripts]` exposes `aws-eks-helm-deploy = "aws_eks_helm_deploy.cli:main"`.
    - `[build-system]` uses hatchling; `[tool.hatch.build.targets.wheel] packages = ["src/aws_eks_helm_deploy"]`.
    - `[dependency-groups]` declares `dev`, `integration`, `acceptance` exactly as in PATTERNS.md (note: research corrected mypy to `~= 2.1`, pytest to `~= 9.1`, structlog `~= 26.0` — NOT the older STACK.md pins).
    - `[tool.uv] default-groups = ["dev"]`.
    - `[tool.ruff]` + `[tool.ruff.lint]` + `[tool.ruff.format]` blocks: `target-version = "py313"`, `line-length = 100`, `select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "N", "S", "C90", "ANN"]`, `ignore = ["ANN101", "ANN102", "S101"]`, per-file-ignores for `tests/**`.
    - `[tool.mypy]`: `python_version = "3.13"`, `strict = true`, `files = ["src"]` (NOT `tests` — keep strict scoped to src on day one per Phase 1 risk note in ROADMAP.md), `plugins = ["pydantic.mypy"]`.
    - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, markers `unit`/`integration`/`acceptance`, `addopts = "-m 'unit'"` ONLY in Plan A (the `--cov-fail-under=100` gate is added by Plan B together with the integration/acceptance test machinery; Plan A delivers the modules but does NOT gate coverage yet so it can ship without the kind/docker dependencies).
    - `[tool.coverage.run]`: `branch = true`, `source = ["aws_eks_helm_deploy"]`, `omit = ["*/tests/*", "*/__main__.py"]`.
    - `[tool.coverage.report]`: `show_missing = true`, `skip_covered = false`.

    Create `.python-version` containing only `3.13\n`.

    Create or extend `.gitignore` to include the lines listed in behavior. Do not overwrite unrelated entries.

    Delete `requirements.txt` (v1 dep manifest retired per TOOL-02; consumers and CI now resolve from `pyproject.toml` + `uv.lock`).

    Generate `uv.lock` by running `uv lock` once locally (executor runs `uv lock` then commits). This locks the resolver output; downstream `uv sync --frozen` is then deterministic. Document the warm-cache target in the README (deferred to Phase 7), but verify it manually here by running `time uv sync --all-extras --frozen` twice and noting the second run is sub-10s.

    [ASSUMED in RESEARCH A1]: `bitbucket-pipes-toolkit 6.2.0` is Python 3.13 compatible. If `uv sync` errors on toolkit install OR `python -c "import bitbucket_pipes_toolkit"` fails after sync, downgrade to the highest 5.x or 4.x line that imports cleanly on 3.13 and document the pin in CHANGELOG.md. Do NOT silently switch to a workaround — surface the version choice in the task summary.
  </action>
  <verify>
    <automated>uv sync --all-extras --frozen &amp;&amp; uv run python -c "import aws_eks_helm_deploy; import bitbucket_pipes_toolkit; import boto3; import pydantic_settings; import structlog; print('OK')" &amp;&amp; test ! -f requirements.txt &amp;&amp; grep -q '^3.13' .python-version</automated>
  </verify>
  <done>
    `uv sync --all-extras --frozen` exits 0; `.venv/` exists; all six runtime imports succeed; `requirements.txt` is gone; `.python-version` contains `3.13`; `uv.lock` and `pyproject.toml` are committed.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task A2: src/aws_eks_helm_deploy/ skeleton — Settings, errors, pipe_io, cli + tests</name>
  <files>src/aws_eks_helm_deploy/__init__.py, src/aws_eks_helm_deploy/__main__.py, src/aws_eks_helm_deploy/cli.py, src/aws_eks_helm_deploy/settings.py, src/aws_eks_helm_deploy/errors.py, src/aws_eks_helm_deploy/pipe_io.py, tests/__init__.py, tests/unit/__init__.py, tests/unit/test_settings.py, tests/unit/test_errors.py, tests/unit/test_pipe_io.py, tests/unit/test_cli.py</files>
  <read_first>
    - .planning/phases/01-toolchain-spine/01-RESEARCH.md (Patterns 2 + 4 + Architecture diagram + Code Examples for settings/errors tests; Pitfall 2 on mypy + boto3-stubs noise; Pitfall 3 on coverage with placeholder modules)
    - .planning/phases/01-toolchain-spine/01-PATTERNS.md (settings.py / errors.py / cli.py / __init__.py target shapes; Critical Anti-Patterns 1–5; NAMESPACE default bug fix from `kube-public` → `default`)
    - pipe/schema.py (v1 env-var names + defaults that Settings must mirror as Field(alias=...))
    - pipe/pipe.py lines 105–110, 131–136 (v1 entry pattern, exception handling — to supersede with typed PipeError catch)
  </read_first>
  <behavior>
    - `python -c "from aws_eks_helm_deploy import __version__"` works (importlib.metadata-driven; fallback to `0.0.0-dev` when not installed).
    - `python -m aws_eks_helm_deploy` runs `cli.main()` and exits with an integer exit code (Phase 1 skeleton: returns 0 with a "Phase 1 skeleton — no action executed" success message via pipe_io; real action dispatch lands in Phase 3+).
    - `Settings()` with no env vars produces: `namespace="default"` (NOT `kube-public` — v1 bug fixed per PATTERNS.md), `action="upgrade"`, `log_format="human"`, `debug=False`, `inject_bitbucket_metadata=False`.
    - `Settings()` reads `CLUSTER_NAME`, `DEBUG`, `LOG_FORMAT` from env when monkeypatched.
    - `PipeError("x").exit_code == 1`; `ConfigurationError("x").exit_code == 1`; `AuthenticationError("x").exit_code == 2`; `ClusterAccessError("x").exit_code == 3`; `ChartResolutionError("x").exit_code == 4`; `HelmError("x").exit_code == 5`; `HelmTimeoutError("x").exit_code == 6`.
    - `PipeIO` exposes `success(message: str) -> None` and `fail(message: str) -> None` that delegate to `bitbucket_pipes_toolkit`'s pipe instance; tests mock the toolkit and verify the calls happen with the right arguments.
    - `cli.main(argv=None) -> int` returns 0 on the placeholder success path; returns `exc.exit_code` when a PipeError is raised inside the try block; returns 99 on bare `Exception`.
    - `mypy --strict src` exits 0 against all six modules.
    - `ruff check src tests` and `ruff format --check src tests` both exit 0.
    - `pytest -m unit` exits 0; coverage is collected but the 100% gate is NOT yet enforced in Plan A (Plan B wires `--cov-fail-under=100`). However the four unit test files MUST exercise every importable symbol so that coverage is already at 100% by the time Plan B flips the gate.

    Test list (mandatory, all under tests/unit/):
    - `test_settings.py::test_settings_defaults` — instantiate `Settings()`, assert all defaults (especially `namespace == "default"` and `inject_bitbucket_metadata is False`).
    - `test_settings.py::test_settings_from_env` — monkeypatch env vars (CLUSTER_NAME, DEBUG=true, LOG_FORMAT=json), assert they are read.
    - `test_settings.py::test_settings_namespace_v1_bug_fixed` — explicit regression test asserting `Settings().namespace == "default"` and documenting the v1 `kube-public` bug in the test docstring.
    - `test_errors.py::test_pipe_error_exit_codes` — all seven exit codes.
    - `test_errors.py::test_pipe_error_user_message` — `user_message` property returns the message.
    - `test_errors.py::test_pipe_error_custom_exit_code` — `PipeError("x", exit_code=42).exit_code == 42`.
    - `test_pipe_io.py::test_success_delegates_to_toolkit` — mock `bitbucket_pipes_toolkit.Pipe`, assert success calls the toolkit success channel.
    - `test_pipe_io.py::test_fail_delegates_to_toolkit` — same for fail.
    - `test_cli.py::test_main_placeholder_success` — `main()` returns 0 on the Phase 1 placeholder path.
    - `test_cli.py::test_main_catches_pipe_error` — patch the placeholder to raise `ConfigurationError`, assert main returns 1 and `pipe.fail` was called.
    - `test_cli.py::test_main_catches_bare_exception` — patch to raise `RuntimeError`, assert main returns 99.
    - `test_cli.py::test_main_module_runs` — call the `__main__.py` path via `runpy.run_module("aws_eks_helm_deploy", run_name="__main__")`; assert `SystemExit.code` is an int.
  </behavior>
  <action>
    Implement the six source modules using the target shapes in `01-PATTERNS.md`:

    `src/aws_eks_helm_deploy/__init__.py` — `from __future__ import annotations`; `__version__` from `importlib.metadata.version("aws-eks-helm-deploy")` with `PackageNotFoundError` fallback to `"0.0.0-dev"`; `__all__ = ["__version__"]`.

    `src/aws_eks_helm_deploy/__main__.py` — `from aws_eks_helm_deploy.cli import main`; `import sys`; `if __name__ == "__main__": sys.exit(main())`. The `if` guard is `# pragma: no cover` per RESEARCH.md Pitfall 3.

    `src/aws_eks_helm_deploy/settings.py` — `pydantic_settings.BaseSettings` exactly per PATTERNS.md target shape. ALL fields use `Field(alias="ENV_NAME")` with explicit defaults. `model_config = SettingsConfigDict(env_file=None, case_sensitive=True, extra="ignore")`. NAMESPACE default is `"default"` (NOT `kube-public`). Field list per PATTERNS.md is canonical; do not add or omit fields.

    `src/aws_eks_helm_deploy/errors.py` — exact hierarchy from PATTERNS.md / RESEARCH.md Pattern 4 with seven classes and the documented exit codes (PipeError=1, ConfigurationError=1, AuthenticationError=2, ClusterAccessError=3, ChartResolutionError=4, HelmError=5, HelmTimeoutError=6). `user_message` property returns `str(self)`. Custom `exit_code` constructor argument overrides the class default.

    `src/aws_eks_helm_deploy/pipe_io.py` — STUB module that wraps `bitbucket_pipes_toolkit.Pipe`. Class `PipeIO`:
      - `__init__(self, *, pipe_metadata_path: str = "pipe.yml") -> None` — lazily constructs a `Pipe` instance on first use; type the `_pipe` attribute as `Pipe | None`.
      - `success(self, message: str) -> None` — calls `_pipe.success(message=message)`.
      - `fail(self, message: str) -> None` — calls `_pipe.fail(message=message)`.
      - If the import of `bitbucket_pipes_toolkit` is untyped, add `# type: ignore[import-untyped]` ONLY on that single line (per RESEARCH.md Pitfall 2). Explicitly mark this as a stub module in a module docstring — the full schema-driven Pipe initialization lands in Phase 2 once auth/CLUSTER_NAME validation exists.

    `src/aws_eks_helm_deploy/cli.py` — `main(argv: list[str] | None = None) -> int`. Do NOT call `configure_logging` here — that import lands in Plan D and `cli.py` will be extended at that point. For Plan A: instantiate `Settings()`, instantiate `PipeIO()`, try-except: on the success path call `pipe.success("Phase 1 skeleton — no action executed")` and return 0; on `PipeError` call `pipe.fail(exc.user_message)` and return `exc.exit_code`; on bare `Exception` call `pipe.fail("Unexpected error — see logs")` and return 99. The bare-Exception branch uses `# noqa: BLE001` per PATTERNS.md target shape. The `if __name__ == "__main__"` guard at the bottom of cli.py is `# pragma: no cover`.

    Write all four unit test files per the behavior list. Use `pytest-mock`'s `mocker` fixture to patch `bitbucket_pipes_toolkit.Pipe` in `test_pipe_io.py` and `test_cli.py`. Add `from __future__ import annotations` to every test file too (consistency with src; ANN ignored in `tests/**` per ruff config).

    Pre-commit install: run `uv run pre-commit install --install-hooks` once locally; commit the result (pre-commit installs into `.git/hooks/` which is not tracked, but `.pre-commit-config.yaml` lands here).

    Add `requirements` traceability comment as a docstring header in `settings.py` referencing TOOL-02 / OBS-02 (DEBUG field) so future readers can grep.

    Stub call-out: `pipe_io.py` is a deliberate stub (placeholder Pipe instantiation without full schema validation). Phase 2 replaces it with a schema-driven adapter. Document this in the module docstring.
  </action>
  <verify>
    <automated>uv run ruff check src tests &amp;&amp; uv run ruff format --check src tests &amp;&amp; uv run mypy --strict src &amp;&amp; uv run pytest -m unit -q --no-cov &amp;&amp; uv run python -c "from aws_eks_helm_deploy.settings import Settings; from aws_eks_helm_deploy.errors import PipeError, HelmTimeoutError; assert Settings().namespace == 'default'; assert HelmTimeoutError('x').exit_code == 6"</automated>
  </verify>
  <done>
    All four test files green under `pytest -m unit`; `ruff check`, `ruff format --check`, `mypy --strict src` all exit 0; the regression assertion (`Settings().namespace == 'default'`) holds; `python -m aws_eks_helm_deploy` exits 0 with the placeholder success message.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task A3: .pre-commit-config.yaml + pre-commit parity verification</name>
  <files>.pre-commit-config.yaml</files>
  <read_first>
    - .planning/phases/01-toolchain-spine/01-RESEARCH.md (Pattern 7: pre-commit config)
    - .planning/phases/01-toolchain-spine/01-PATTERNS.md (.pre-commit-config.yaml target shape)
  </read_first>
  <behavior>
    - `uv run pre-commit run --all-files` runs ruff (with --fix), ruff-format, mypy (strict, src), end-of-file-fixer, trailing-whitespace, check-yaml, check-toml, check-merge-conflict, and a local pytest-unit hook — all exit 0 on the Plan A skeleton.
    - The pre-commit hook set is parity-equivalent to the checks Plan B will wire into CI (`ruff check`, `ruff format --check`, `mypy --strict src`, `pytest -m unit`). No CI-only checks that pre-commit lacks; no pre-commit-only checks that CI lacks.
    - mypy hook's `additional_dependencies` contains `boto3-stubs[eks,sts]`, `pydantic-settings`, `structlog`, `types-PyYAML` (so the isolated pre-commit env can resolve the same types as the project venv).
  </behavior>
  <action>
    Write `.pre-commit-config.yaml` per the exact target shape in `01-PATTERNS.md` `.pre-commit-config.yaml` section (which mirrors RESEARCH.md Pattern 7):
    - `astral-sh/ruff-pre-commit` at `v0.15.17`: hooks `ruff` (`args: [--fix]`) and `ruff-format`.
    - `pre-commit/mirrors-mypy` at `v2.1.0`: hook `mypy` with `args: [--strict, src]` and `additional_dependencies: [boto3-stubs[eks,sts], pydantic-settings, structlog, types-PyYAML]`.
    - `pre-commit/pre-commit-hooks` at `v5.0.0`: hooks `end-of-file-fixer`, `trailing-whitespace`, `check-yaml`, `check-toml`, `check-merge-conflict`.
    - local `pytest-quick` hook running `uv run pytest -q -m unit --no-cov`, `language: system`, `pass_filenames: false`, `always_run: true`.

    Install hooks: `uv run pre-commit install --install-hooks` (one-shot; this is documented but does not modify a tracked file — `.git/hooks/` is not tracked).

    Run `uv run pre-commit run --all-files` to verify; if any hook reports a fixable change (ruff --fix, end-of-file-fixer), commit the resulting file changes as part of this task's commit so the working tree is clean afterwards.

    Version pin policy: pinned to the exact versions cited above (per RESEARCH.md "Version verification performed" block). Dependabot (Phase 6) will bump these in PRs.
  </action>
  <verify>
    <automated>uv run pre-commit run --all-files</automated>
  </verify>
  <done>
    `pre-commit run --all-files` exits 0 with no remaining diffs; all six hook groups (ruff, ruff-format, mypy, pre-commit-hooks, pytest-quick) are wired; mypy hook resolves boto3-stubs, pydantic-settings, structlog, types-PyYAML in its isolated env.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Developer machine → uv resolver → PyPI | Supply-chain ingress; resolver pulls wheels from PyPI; lockfile is the only thing that pins their hashes. |
| Source modules → env vars (consumer-controlled) | `Settings()` parses every public env-var; pydantic-settings is the validation surface. |
| `pipe_io.py` → bitbucket-pipes-toolkit | Untyped third-party import; we wrap it; toolkit owns stdout. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-A-01 | Tampering | PyPI dependency resolution at `uv sync` time | mitigate | `uv.lock` is committed; CI uses `uv sync --frozen` (Plan B); Dockerfile uses `uv sync --frozen --no-dev` (Plan C); `pip-audit` runs locally via `uv run pip-audit` (full CI gate lands Phase 6). |
| T-01-A-02 | Tampering | Settings input parsing (env-var injection) | mitigate | `pydantic-settings` `extra="ignore"` rejects no-op extras; typed fields reject malformed input with `ValidationError`; `action`/`log_format` are still raw `str` in Phase 1 (Literal narrowing lands in Phase 5 when the action dispatch table exists) — documented assumption. |
| T-01-A-03 | Information Disclosure | `pipe_io.py` `fail()` messages | mitigate | `fail(message: str)` accepts only the message string the caller provides; we never pass exception args directly without first calling `exc.user_message`; the toolkit's own response body redaction is delegated until Phase 5 SEC-06 log-masking lands. |
| T-01-A-04 | Elevation of Privilege | Pre-commit hook executing arbitrary code | accept | Pre-commit hooks are pinned to exact versions of well-known maintainers (astral-sh, python/mypy, pre-commit/pre-commit-hooks) per RESEARCH.md Package Legitimacy Audit — all verdict OK. |
| T-01-A-SC | Tampering | Package legitimacy on `uv lock` / `uv sync` | mitigate | All Plan A packages appear in `01-RESEARCH.md ## Package Legitimacy Audit` with verdict "OK — Approved". Only `bitbucket-pipes-toolkit 6.2.0` carries an `[ASSUMED]` flag (Python 3.13 compat). Task A1 fails fast on import error — `python -c "import bitbucket_pipes_toolkit"` is in the verify command — and the executor surfaces the downgrade if required. No `[SLOP]` packages present. No blocking human checkpoint required since no `[SUS]` rows. |
</threat_model>

<verification>
- Run `uv sync --all-extras --frozen` — exits 0, `.venv/` populated.
- Run `uv run ruff check src tests` — zero findings.
- Run `uv run ruff format --check src tests` — clean.
- Run `uv run mypy --strict src` — zero errors.
- Run `uv run pytest -m unit -q --no-cov` — all unit tests green.
- Run `uv run pre-commit run --all-files` — all hooks pass.
- Run `python -c "import aws_eks_helm_deploy; from aws_eks_helm_deploy.settings import Settings; assert Settings().namespace == 'default'"` — exit 0.
- Confirm `requirements.txt` is removed: `test ! -f requirements.txt`.
</verification>

<success_criteria>
- TOOL-01: `uv sync --all-extras` warm-cache produces a working `.venv/` (sub-10s target verified manually, not gated).
- TOOL-02: `src/aws_eks_helm_deploy/` exists with six modules; `requirements.txt` removed; `pyproject.toml` is the single dep manifest.
- TOOL-03: `ruff check` + `ruff format --check` exit 0 on src + tests.
- TOOL-04: `mypy --strict src` exits 0.
- TOOL-05: `pre-commit run --all-files` exits 0 locally, with hooks that mirror what Plan B will wire into CI.
- Stubs explicitly named: `pipe_io.py` is documented as a stub (full schema-driven init lands in Phase 2); `cli.py` placeholder action returns success (real ACTION dispatch lands in Phase 3+).
- All Plan A unit tests cover their target module's importable symbols at 100% line+branch (verified by Plan B's gate when wired).
</success_criteria>

<artifacts>
## Artifacts this phase produces (Plan A scope)

**Files (new):**
- `pyproject.toml` — project metadata, runtime deps, dev/integration/acceptance groups, ruff/mypy/pytest/coverage config.
- `uv.lock` — pinned resolver output.
- `.python-version` — `3.13`.
- `.pre-commit-config.yaml` — ruff + ruff-format + mypy + pre-commit-hooks + local pytest-unit hook.
- `.gitignore` (extended) — `.venv/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `htmlcov/`, `.coverage`, `*.pyc`, `__pycache__/`, `dist/`, `*.egg-info/`.
- `src/aws_eks_helm_deploy/__init__.py` — `__version__`.
- `src/aws_eks_helm_deploy/__main__.py` — `sys.exit(main())`.
- `src/aws_eks_helm_deploy/settings.py` — `Settings(BaseSettings)`.
- `src/aws_eks_helm_deploy/errors.py` — `PipeError`, `ConfigurationError`, `AuthenticationError`, `ClusterAccessError`, `ChartResolutionError`, `HelmError`, `HelmTimeoutError`.
- `src/aws_eks_helm_deploy/pipe_io.py` — `PipeIO` (STUB; lazy toolkit wrap).
- `src/aws_eks_helm_deploy/cli.py` — `main(argv: list[str] | None = None) -> int`.
- `tests/__init__.py`, `tests/unit/__init__.py` — package markers.
- `tests/unit/test_settings.py`, `tests/unit/test_errors.py`, `tests/unit/test_pipe_io.py`, `tests/unit/test_cli.py` — unit tests.

**Files (removed):**
- `requirements.txt` — retired (TOOL-02).

**New Python symbols (importable):**
- `aws_eks_helm_deploy.__version__: str`
- `aws_eks_helm_deploy.settings.Settings` — fields: `aws_region`, `aws_access_key_id`, `aws_secret_access_key`, `role_arn`, `session_name`, `cluster_name`, `chart`, `release_name`, `namespace`, `create_namespace`, `set_values`, `values_files`, `wait`, `timeout`, `action`, `dry_run`, `log_format`, `debug`, `inject_bitbucket_metadata`.
- `aws_eks_helm_deploy.errors.PipeError` (+ `user_message` property), `ConfigurationError`, `AuthenticationError`, `ClusterAccessError`, `ChartResolutionError`, `HelmError`, `HelmTimeoutError`.
- `aws_eks_helm_deploy.pipe_io.PipeIO` (STUB) — methods `success(message)`, `fail(message)`.
- `aws_eks_helm_deploy.cli.main(argv: list[str] | None = None) -> int`.

**New CLI surface:**
- `python -m aws_eks_helm_deploy` (via `__main__.py`).
- `aws-eks-helm-deploy` console script (via `[project.scripts]`).

**New env vars consumed by Settings (alias preservation from v1 + new in v2):**
- v1 carry-over: `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ROLE_ARN`, `SESSION_NAME`, `CLUSTER_NAME`, `CHART`, `RELEASE_NAME`, `NAMESPACE`, `CREATE_NAMESPACE`, `SET`, `VALUES`, `WAIT`, `DEBUG`, `TIMEOUT`.
- New in v2: `ACTION`, `DRY_RUN`, `LOG_FORMAT`, `INJECT_BITBUCKET_METADATA`.

**Stubs (called out explicitly):**
- `PipeIO`: stub. Lazy toolkit init; no schema validation. Replaced in Phase 2 with full `Pipe(pipe_metadata=..., schema=...)` initialization once CLUSTER_NAME-required schema exists.
- `cli.main()`: placeholder success path. Real ACTION dispatch (upgrade/diff/rollback) lands in Phase 3+.
</artifacts>

<output>
On completion, create `.planning/phases/01-toolchain-spine/01-01-SUMMARY.md` recording:
- Exact `bitbucket-pipes-toolkit` version pinned (resolved at Task A1 import-check time).
- Whether `uv sync --frozen --all-extras` warm-cache time hit the sub-10s target (informational; not gated).
- Any pre-commit hook auto-fixes applied to the working tree.
- The two stubs explicitly named: `PipeIO` and `cli.main()` placeholder.
</output>
