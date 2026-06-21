"""Structural tests for Phase 7 DOC-01 — README badge row + quickstart + docs-site link.

Hardened by Plan 07-06: sponsors/stars/open-issues badge assertions + docs-site URL
locked to ``yves-vogl.github.io/aws-eks-helm-deploy``. D6 style invariant: new badges
use ``?style=flat-square``; existing 7 badges keep their pre-edit form (no reorder).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths and invariants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
README_MD = REPO_ROOT / "README.md"

# The 10-badge row (7 existing from Phase 6 + 3 additive from Plan 07-06).
REQUIRED_BADGE_SOURCES: frozenset[str] = frozenset(
    {
        # Phase 6 baseline — byte-identical, no reorder.
        "img.shields.io/github/license",
        "img.shields.io/github/v/release",
        "GHCR Image",
        "actions/workflows/ci.yml/badge.svg",
        "coverage-100%25-brightgreen",
        "cosign-verified",
        "securityscorecards.dev",
        # Plan 07-06 additive — appended after the OpenSSF Scorecard badge.
        "img.shields.io/github/sponsors/yves-vogl",
        "img.shields.io/github/stars/yves-vogl/aws-eks-helm-deploy",
        "img.shields.io/github/issues/yves-vogl/aws-eks-helm-deploy",
    }
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_readme_exists() -> None:
    """README.md must exist at the repo root."""
    assert README_MD.is_file(), f"README.md missing at {README_MD}"


def test_readme_has_badge_row() -> None:
    """10-badge row (Phase 6 baseline + Plan 07-06 additions) lives in first 40 lines."""
    text = README_MD.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:40])
    missing = sorted({badge for badge in REQUIRED_BADGE_SOURCES if badge not in head})
    assert not missing, (
        "README.md badge row is missing required DOC-01 entries: "
        f"{missing}. The 10-badge row must remain in the first 40 lines."
    )


def test_readme_has_quickstart_section() -> None:
    """README.md must contain a ``## Quick start`` section (DOC-01 SC-1 anchor)."""
    text = README_MD.read_text(encoding="utf-8")
    assert re.search(r"^##\s+Quick start", text, re.IGNORECASE | re.MULTILINE), (
        "README.md must contain a `## Quick start` heading (DOC-01)."
    )


def test_readme_has_sponsors_badge() -> None:
    """Plan 07-06 additive badge: GitHub Sponsors."""
    text = README_MD.read_text(encoding="utf-8")
    assert "img.shields.io/github/sponsors/yves-vogl" in text, (
        "README.md must include the GitHub Sponsors badge (Plan 07-06 / DOC-01)."
    )


def test_readme_has_stars_badge() -> None:
    """Plan 07-06 additive badge: GitHub stargazers count."""
    text = README_MD.read_text(encoding="utf-8")
    assert "img.shields.io/github/stars/yves-vogl/aws-eks-helm-deploy" in text, (
        "README.md must include the GitHub Stars badge (Plan 07-06 / DOC-01)."
    )


def test_readme_has_open_issues_badge() -> None:
    """Plan 07-06 additive badge: open issues count."""
    text = README_MD.read_text(encoding="utf-8")
    assert "img.shields.io/github/issues/yves-vogl/aws-eks-helm-deploy" in text, (
        "README.md must include the GitHub Open Issues badge (Plan 07-06 / DOC-01)."
    )


def test_readme_has_docs_site_link_hardened() -> None:
    """README.md must link to the live docs site at ``yves-vogl.github.io/aws-eks-helm-deploy``."""
    text = README_MD.read_text(encoding="utf-8")
    assert "yves-vogl.github.io/aws-eks-helm-deploy" in text, (
        "README.md must surface the live docs-site URL "
        "(https://yves-vogl.github.io/aws-eks-helm-deploy/) — Plan 07-06."
    )


def test_readme_links_to_migration_guide() -> None:
    """README.md Status callout must link to the v1→v2 migration guide (DOC-01 + D6)."""
    text = README_MD.read_text(encoding="utf-8")
    assert "docs/migration/v1-to-v2.md" in text, (
        "README.md must link to docs/migration/v1-to-v2.md (Plan 07-06 / Status callout)."
    )


def test_readme_new_badges_use_flat_square_style() -> None:
    """D6 style invariant: sponsors / stars / open-issues badges use ``?style=flat-square``."""
    text = README_MD.read_text(encoding="utf-8")
    for new_badge_source in (
        "img.shields.io/github/sponsors/yves-vogl",
        "img.shields.io/github/stars/yves-vogl/aws-eks-helm-deploy",
        "img.shields.io/github/issues/yves-vogl/aws-eks-helm-deploy",
    ):
        # Find the line with the badge; assert the flat-square query lives on the same line.
        line = next(
            (ln for ln in text.splitlines() if new_badge_source in ln),
            None,
        )
        assert line is not None, f"Badge source {new_badge_source!r} not found in README.md"
        assert "style=flat-square" in line, (
            f"Plan 07-06 / D6 style invariant: badge {new_badge_source!r} must use "
            f"`?style=flat-square`. Offending line: {line!r}"
        )
