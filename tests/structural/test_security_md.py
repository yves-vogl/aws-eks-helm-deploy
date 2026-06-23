"""Structural tests for Phase 7 / Plan 07-06 / DOC-06 + D10.

Asserts SECURITY.md contains the 6-month placeholder verbatim (SI-07-07 gate),
the Private Vulnerability Reporting link, and the unchanged 90-day disclosure window.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths and invariants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SECURITY_MD = REPO_ROOT / "SECURITY.md"

# Post tag-cut: the v1.x EOS date is now absolute (SI-07-07 invariant).
# v2.0.0 was released 2026-06-23 → EOS = 2026-12-23.
V1_EOS_DATE = "2026-12-23"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_security_md_exists() -> None:
    """SECURITY.md must exist at the repo root."""
    assert SECURITY_MD.is_file(), f"SECURITY.md missing at {SECURITY_MD}"


def test_security_md_has_v1_eos_date() -> None:
    """SI-07-07 gate: the v1.x EOS date 2026-12-23 must be present verbatim."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert V1_EOS_DATE in text, (
        f"SECURITY.md must contain the v1.x EOS date `{V1_EOS_DATE}` "
        "(v2.0.0 released 2026-06-23 + 6 months). SI-07-07 gate failure."
    )


def test_security_md_mentions_v1_x_six_month_window() -> None:
    """DOC-06: the v1.x supported-versions row mentions the 6-month security-fix window."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "6 months" in text, (
        "SECURITY.md must mention the 6-month security-fix window for v1.x (DOC-06 / D10)."
    )


def test_security_md_has_pvr_link() -> None:
    """SECURITY.md must surface a Private Vulnerability Reporting channel."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "Private Vulnerability Reporting" in text or "security/advisories/new" in text, (
        "SECURITY.md must reference GitHub Private Vulnerability Reporting "
        "(either by name or via the security/advisories/new link)."
    )


def test_security_md_disclosure_timeline_unchanged() -> None:
    """D10 constraint: the 90-day coordinated disclosure window stays unchanged."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "Day 90 (max)" in text, (
        "SECURITY.md disclosure timeline must keep the 'Day 90 (max)' marker "
        "(D10: 90-day window unchanged)."
    )


def test_security_md_has_scope_section() -> None:
    """DOC-06 + Phase 6 governance: SECURITY.md must have a Scope section."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "## Scope" in text, (
        "SECURITY.md must contain a `## Scope` section (DOC-06 / Phase 6 governance)."
    )
