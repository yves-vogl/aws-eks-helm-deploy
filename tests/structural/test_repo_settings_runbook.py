"""Structural tests for Phase 7 / Plan 07-07.

Asserts docs/admin/repo-settings.md ships the 5 new sections (7-11) for the
v2.0.0 release ceremony per D11 (Phase 6 §§5-6 + §12 restored alongside):

- Section 7: Enable GitHub Pages (RESEARCH Q6).
- Section 8: Set default mike alias to v2 (RESEARCH Q10 pitfall #5).
- Section 9: Deploy frozen v1 docs snapshot (RESEARCH Q10 pitfall #6).
- Section 10: Update Bitbucket Pipe Marketplace listing (D11).
- Section 11: Post Docker Hub README deprecation banner (MIG-01 / D10).

Also asserts the SI-07-07 invariant: the D10 placeholder
'2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.' appears
at least twice in the runbook (sections 9 + 11).
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

RUNBOOK = pathlib.Path(__file__).resolve().parents[2] / "docs" / "admin" / "repo-settings.md"
D10_PLACEHOLDER = "2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut."


def test_runbook_exists() -> None:
    """docs/admin/repo-settings.md must exist."""
    assert RUNBOOK.is_file(), f"Missing: {RUNBOOK}"


def test_runbook_has_pages_enablement_section() -> None:
    """Section 7 — Enable GitHub Pages (DOC-02)."""
    assert "## 7. Enable GitHub Pages" in RUNBOOK.read_text(), (
        "Section 7 (Enable GitHub Pages) must be present in the runbook"
    )


def test_runbook_section_7_uses_gh_api_pages_endpoint() -> None:
    """Section 7 must use the RESEARCH Q6 verbatim gh api endpoint."""
    assert "gh api repos/yves-vogl/aws-eks-helm-deploy/pages" in RUNBOOK.read_text(), (
        "Section 7 must invoke the gh api pages endpoint per RESEARCH Q6"
    )


def test_runbook_has_mike_set_default_section() -> None:
    """Section 8 — Set default mike alias to v2 (DOC-02 SC-3)."""
    assert "## 8. Set default mike alias to v2" in RUNBOOK.read_text(), (
        "Section 8 (Set default mike alias to v2) must be present"
    )


def test_runbook_section_8_uses_mike_set_default_push() -> None:
    """Section 8 must use the `mike set-default v2 --push` one-shot."""
    assert "mike set-default v2 --push" in RUNBOOK.read_text(), (
        "Section 8 must invoke `mike set-default v2 --push` per RESEARCH Q10 pitfall #5"
    )


def test_runbook_has_mike_v1_deploy_section() -> None:
    """Section 9 — Deploy frozen v1 docs snapshot (D2 — Plan 07-01)."""
    assert "## 9. Deploy frozen v1 docs snapshot" in RUNBOOK.read_text(), (
        "Section 9 (Deploy frozen v1 docs snapshot) must be present"
    )


def test_runbook_section_9_uses_mike_deploy_push_v1() -> None:
    """Section 9 must invoke `mike deploy ... v1` and note CI-exclusion."""
    text = RUNBOOK.read_text()
    # Tolerate either form: `mike deploy --push v1` (direct) OR
    # `mike deploy --push --config-file ... v1` (current procedure when v1
    # source is staged under .v1-snapshot/). Substring check on both halves.
    assert "mike deploy --push" in text and " v1" in text, (
        "Section 9 must invoke `mike deploy --push ... v1` per RESEARCH Q10 pitfall #6"
    )
    assert "CI never touches it" in text or "NEVER from CI" in text, (
        "Section 9 must explicitly note this command MUST NOT run from CI (Q10 pitfall #6)"
    )


def test_runbook_has_marketplace_section() -> None:
    """Section 10 — Update Bitbucket Pipe Marketplace listing (D11)."""
    assert "## 10. Update Bitbucket Pipe Marketplace listing" in RUNBOOK.read_text(), (
        "Section 10 (Bitbucket Pipe Marketplace listing update) must be present"
    )


def test_runbook_has_docker_hub_banner_section() -> None:
    """Section 11 — Post Docker Hub README deprecation banner (MIG-01)."""
    assert "## 11. Post Docker Hub README deprecation banner" in RUNBOOK.read_text(), (
        "Section 11 (Docker Hub README deprecation banner) must be present"
    )


def test_runbook_propagates_d10_placeholder() -> None:
    """SI-07-07: the D10 6-month placeholder must appear ≥ 2 times (Sections 9 + 11)."""
    text = RUNBOOK.read_text()
    count = text.count(D10_PLACEHOLDER)
    assert count >= 2, (
        f"SI-07-07 invariant broken: D10 placeholder appears {count} time(s), "
        f"expected ≥ 2 (Section 9 v1 banner + Section 11 Docker Hub banner)"
    )


def test_runbook_sections_1_to_6_remain_present() -> None:
    """Append-only invariant — Phase 6 §§1-4 + restored §§5-6 must remain in the file."""
    text = RUNBOOK.read_text()
    for heading in [
        "## 1. Enable GitHub Private Vulnerability Reporting",
        "## 2. Configure Branch Protection on `main`",
        "## 3. Require GPG-Signed Commits",
        '## 4. Enable "Allow auto-merge" Repo Setting',
        "## 5. Create the v2.0 GitHub Project Board",
        "## 6. Create the Label Taxonomy",
    ]:
        assert heading in text, (
            f"Append-only invariant broken — section heading missing: {heading!r}"
        )


def test_runbook_has_sanity_check_section() -> None:
    """Section 12 — Sanity-Check Post-Actions (Phase 6 restored)."""
    assert "## 12. Sanity-Check Post-Actions" in RUNBOOK.read_text(), (
        "Section 12 (Sanity-Check Post-Actions, restored from Phase 6) must be present"
    )
