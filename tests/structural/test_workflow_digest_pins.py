"""Structural tests asserting every GitHub Action reference under `.github/workflows/*.yml` is
pinned to a 40-character commit SHA (Phase 6 / D7 / Pitfall #5 / RESEARCH §3 action digest table).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows"

DIGEST_PATTERN: re.Pattern[str] = re.compile(r"@([0-9a-f]{40})(?:\s|$)")

USES_LINE_PATTERN: re.Pattern[str] = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")

EXEMPT_LOCAL_REFS: set[str] = {"./", "../"}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _collect_uses_refs() -> list[tuple[pathlib.Path, int, str]]:
    """Collect all `uses:` action references from every workflow YAML file.

    Returns:
        A list of (file_path, line_number_1indexed, action_ref) tuples.
    """
    results: list[tuple[pathlib.Path, int, str]] = []
    for pattern in ("*.yml", "*.yaml"):
        for wf_file in sorted(WORKFLOWS_DIR.glob(pattern)):
            for line_no, line in enumerate(wf_file.read_text().splitlines(), start=1):
                m = USES_LINE_PATTERN.match(line)
                if m:
                    ref = m.group(1)
                    if not any(ref.startswith(prefix) for prefix in EXEMPT_LOCAL_REFS):
                        results.append((wf_file, line_no, ref))
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_workflows_directory_exists() -> None:
    """The .github/workflows directory must exist."""
    assert WORKFLOWS_DIR.is_dir(), f"Expected {WORKFLOWS_DIR} to exist"


def test_all_workflow_uses_pinned_to_digest() -> None:
    """Every `uses:` reference must contain a 40-character lowercase hex SHA digest.

    Pitfall #5 — mutable tags (@v4, @main) allow compromised actions to slip in overnight.
    """
    violations: list[str] = []
    for path, line_no, ref in _collect_uses_refs():
        if DIGEST_PATTERN.search(ref) is None:
            violations.append(
                f"{path.name}:{line_no} — `uses: {ref}` is NOT pinned to a 40-char SHA digest"
                " (Pitfall #5 / Phase 6 invariant)"
            )
    assert not violations, "\n".join(violations)


def test_no_unpinned_v_tag_references() -> None:
    """No `uses:` reference may end with a bare version tag like `@v4` (Pitfall #5)."""
    violations: list[str] = []
    for path, line_no, ref in _collect_uses_refs():
        if re.search(r"@v\d+", ref):
            violations.append(
                f"{path.name}:{line_no} — `uses: {ref}` contains a mutable version tag"
                " (Pitfall #5: use 40-char SHA digest instead)"
            )
    assert not violations, "\n".join(violations)


def test_no_main_or_master_branch_references() -> None:
    """No `uses:` reference may point to `@main`, `@master`, or `@HEAD`."""
    violations: list[str] = []
    for path, line_no, ref in _collect_uses_refs():
        if ref.endswith("@main") or ref.endswith("@master") or ref.endswith("@HEAD"):
            violations.append(
                f"{path.name}:{line_no} — `uses: {ref}` pins to a mutable branch reference"
                " (use 40-char SHA digest instead)"
            )
    assert not violations, "\n".join(violations)
