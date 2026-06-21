"""Structural tests for Phase 7 / Plan 07-04 / DOC-08 + MIG-03.

Lints every ``examples/**/*.yml`` and ``examples/**/*.yaml`` against the
SchemaStore ``vendor.bitbucket-pipelines`` schema via
``check-jsonschema 0.37.3`` (RESEARCH Q8). Also asserts the MIG-03 trio
(``before.yml``, ``after.yml``, ``README.md``) is complete and every example
YAML opens with the D8 header block.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
MIGRATION_DIR = EXAMPLES_DIR / "migration-v1-to-v2"

REQUIRED_EXAMPLE_DIRS: frozenset[str] = frozenset(
    {"basic", "oidc-only", "oci-chart", "multi-env", "migration-v1-to-v2"},
)

# Required header tokens per D8 — every example yml opens with these in the
# first few comment lines. `# Example` matches both `# Example:` and
# `# Example (MIG-03):` so the migration before/after files can carry a
# scope tag in their title.
HEADER_TOKENS: frozenset[str] = frozenset(
    {"# Example", "# Prerequisites:", "# Expected outcome:"},
)


def _collect_example_yamls() -> list[pathlib.Path]:
    """Return every yml/yaml file under examples/, sorted for stable output."""
    return sorted(
        list(EXAMPLES_DIR.rglob("*.yml")) + list(EXAMPLES_DIR.rglob("*.yaml")),
    )


# ---------------------------------------------------------------------------
# Directory + file presence
# ---------------------------------------------------------------------------


def test_examples_dir_exists() -> None:
    """examples/ must exist (D8 corpus root)."""
    assert EXAMPLES_DIR.is_dir(), f"missing: {EXAMPLES_DIR}"


def test_all_required_example_subdirs_exist() -> None:
    """All five D8 sub-directories must be present."""
    actual = {p.name for p in EXAMPLES_DIR.iterdir() if p.is_dir()}
    missing = REQUIRED_EXAMPLE_DIRS - actual
    assert not missing, f"missing example sub-directories: {sorted(missing)}"


def test_each_required_example_has_bitbucket_pipelines_yml() -> None:
    """Each non-migration sub-directory ships a bitbucket-pipelines.yml."""
    for dirname in REQUIRED_EXAMPLE_DIRS - {"migration-v1-to-v2"}:
        path = EXAMPLES_DIR / dirname / "bitbucket-pipelines.yml"
        assert path.is_file(), f"missing: {path}"


def test_migration_dir_has_before_after_readme() -> None:
    """MIG-03: the migration sub-directory ships before.yml + after.yml + README.md."""
    assert (MIGRATION_DIR / "before.yml").is_file(), "missing migration before.yml"
    assert (MIGRATION_DIR / "after.yml").is_file(), "missing migration after.yml"
    assert (MIGRATION_DIR / "README.md").is_file(), "missing migration README.md"


# ---------------------------------------------------------------------------
# Header convention (D8)
# ---------------------------------------------------------------------------


def test_each_example_yml_has_header_block() -> None:
    """Each yml opens with the D8 header block (Purpose / Prereq / Outcome)."""
    yamls = _collect_example_yamls()
    assert yamls, "no example yamls found"
    for path in yamls:
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:10])
        for token in HEADER_TOKENS:
            assert token in head, (
                f"{path} is missing required header token {token!r}; first 10 lines:\n{head}"
            )


# ---------------------------------------------------------------------------
# Lint gate — check-jsonschema against vendor.bitbucket-pipelines
# ---------------------------------------------------------------------------


def test_examples_yamls_lint_clean_via_check_jsonschema() -> None:
    """DOC-08 + MIG-03 gate: every example yml is vendor.bitbucket-pipelines clean."""
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    if importlib.util.find_spec("check_jsonschema") is None:
        pytest.skip("check_jsonschema not importable")

    yamls = _collect_example_yamls()
    assert yamls, "no example yamls found"

    cmd: list[str] = [
        "uv",
        "run",
        "check-jsonschema",
        "--builtin-schema",
        "vendor.bitbucket-pipelines",
    ]
    cmd.extend(str(p) for p in yamls)

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, (
        f"check-jsonschema failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
