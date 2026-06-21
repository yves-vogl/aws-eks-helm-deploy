"""Structural tests for Phase 7 / Plan 07-04 / DOC-03.

Asserts the migration guide covers every breaking change AND that the D10
6-month placeholder is committed verbatim (SI-07-07 gate; Plan 07-06 also
embeds this string in SECURITY.md).
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_MD = REPO_ROOT / "docs" / "migration" / "v1-to-v2.md"
OLD_MIGRATION_MD = REPO_ROOT / "docs" / "guides" / "v1-to-v2.md"

# Literal section tokens / breaking-change names that MUST appear in the guide
# (DOC-03). The intent is structural: each token represents a breaking change
# Yves wants surfaced. A failure here means the move + polish silently dropped
# a section.
REQUIRED_BREAKING_CHANGE_TOKENS: frozenset[str] = frozenset(
    {
        "INJECT_BITBUCKET_METADATA",
        "NAMESPACE",
        "SET",
        "VALUES",
        "Distribution change",
        "ghcr.io/yves-vogl/aws-eks-helm-deploy",
    },
)

# SI-07-07 gate: the D10 placeholder appears verbatim in this file AND in
# SECURITY.md (Plan 07-06). Tag-cut replaces the literal string.
D10_PLACEHOLDER = "2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut."


# ---------------------------------------------------------------------------
# File location
# ---------------------------------------------------------------------------


def test_migration_guide_at_new_path() -> None:
    """The polished guide lives at docs/migration/v1-to-v2.md."""
    assert MIGRATION_MD.is_file(), f"missing: {MIGRATION_MD}"


def test_old_migration_guide_removed() -> None:
    """The Phase 5/6 draft location is empty after the git mv."""
    assert not OLD_MIGRATION_MD.exists(), (
        f"{OLD_MIGRATION_MD} should be removed by `git mv` to docs/migration/"
    )


# ---------------------------------------------------------------------------
# Content gates (DOC-03)
# ---------------------------------------------------------------------------


def test_migration_guide_covers_every_breaking_change() -> None:
    """DOC-03 gate: every breaking-change token appears in the guide."""
    text = MIGRATION_MD.read_text(encoding="utf-8")
    missing = {token for token in REQUIRED_BREAKING_CHANGE_TOKENS if token not in text}
    assert not missing, f"migration guide is missing breaking-change tokens: {sorted(missing)}"


def test_migration_guide_covers_inject_bitbucket_metadata() -> None:
    """DOC-03 spotlight: INJECT_BITBUCKET_METADATA section is non-trivially documented."""
    text = MIGRATION_MD.read_text(encoding="utf-8")
    # The token should appear at least 3 times (section heading + admonition +
    # before/after example) — a single mention would mean only the glance
    # table covers it, which is not enough.
    occurrences = text.count("INJECT_BITBUCKET_METADATA")
    assert occurrences >= 3, (
        f"INJECT_BITBUCKET_METADATA documented only {occurrences} times; "
        f"expected at least 3 (section header + admonition + example)."
    )


def test_migration_guide_has_d10_six_month_placeholder() -> None:
    """SI-07-07 gate: the D10 6-month placeholder is committed verbatim."""
    text = MIGRATION_MD.read_text(encoding="utf-8")
    assert D10_PLACEHOLDER in text, (
        f"D10 placeholder string missing from {MIGRATION_MD}; expected literal: {D10_PLACEHOLDER!r}"
    )


def test_migration_guide_cross_references_examples_diff() -> None:
    """MIG-03 gate: the guide cross-links to the examples/migration-v1-to-v2 diff."""
    text = MIGRATION_MD.read_text(encoding="utf-8")
    assert "examples/migration-v1-to-v2" in text, (
        "migration guide must cross-reference examples/migration-v1-to-v2/"
    )


def test_migration_guide_uses_mkdocs_admonitions() -> None:
    """Polish gate: the guide uses mkdocs-material admonitions (>=3 blocks)."""
    text = MIGRATION_MD.read_text(encoding="utf-8")
    count = text.count("!!! ")
    assert count >= 3, (
        f"migration guide has only {count} admonition blocks; "
        f"expected at least 3 (warning/tip/info/note)."
    )
