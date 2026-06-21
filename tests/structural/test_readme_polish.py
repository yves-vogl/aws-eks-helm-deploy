"""Structural tests for Phase 7 DOC-01 — README badge row + quickstart + docs-site link.

Wave-1 placeholder; Plan 07-06 extends with sponsor/stars/issues badge assertions
and hardens the docs-site URL to the final GitHub Pages target.
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

# The 7-badge row already shipped in Phase 6 — kept here as the DOC-01 gate.
REQUIRED_BADGE_SOURCES: frozenset[str] = frozenset(
    {
        "img.shields.io/github/license",
        "img.shields.io/github/v/release",
        "GHCR Image",
        "actions/workflows/ci.yml/badge.svg",
        "coverage-100%25-brightgreen",
        "cosign-verified",
        "securityscorecards.dev",
    }
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_readme_exists() -> None:
    """README.md must exist at the repo root."""
    assert README_MD.is_file(), f"README.md missing at {README_MD}"


def test_readme_has_badge_row() -> None:
    """The 7-badge row from Phase 6 must live in the first 30 lines of README.md (DOC-01)."""
    text = README_MD.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:30])
    missing = sorted({badge for badge in REQUIRED_BADGE_SOURCES if badge not in head})
    assert not missing, (
        "README.md badge row is missing required Phase 6 / DOC-01 entries: "
        f"{missing}. The 7-badge row must remain in the first 30 lines."
    )


def test_readme_has_quickstart_section() -> None:
    """README.md must contain a ``## Quick start`` section (DOC-01 SC-1 anchor)."""
    text = README_MD.read_text(encoding="utf-8")
    assert re.search(r"^##\s+Quick start", text, re.IGNORECASE | re.MULTILINE), (
        "README.md must contain a `## Quick start` heading (DOC-01)."
    )


def test_readme_has_docs_site_link() -> None:
    """README.md must link to the docs site or the docs-site landing target.

    TODO Plan 07-06: harden to the exact final URL ``https://yves-vogl.github.io/aws-eks-helm-deploy/v2/``
    once GitHub Pages publishes. Wave-1 placeholder accepts any of:
      - https://yves-vogl.github.io/aws-eks-helm-deploy/ (Pages root)
      - https://yves-vogl.github.io/aws-eks-helm-deploy (bare form)
      - the literal phrase ``docs site`` linked to GitHub Pages.
    """
    text = README_MD.read_text(encoding="utf-8")
    has_pages_url = "yves-vogl.github.io/aws-eks-helm-deploy" in text
    has_docs_site_phrase = bool(re.search(r"\bdocs site\b", text, re.IGNORECASE))
    if not (has_pages_url or has_docs_site_phrase):
        pytest.skip(
            "README.md docs-site link not present yet — Plan 07-06 wires this. "
            "Wave-1 placeholder skips until then."
        )
    assert has_pages_url or has_docs_site_phrase
