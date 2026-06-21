"""Structural tests for Phase 7 / Plan 07-07.

Asserts docs/admin/repo-settings.md ships the 5 new sections (5-9) for the
v2.0.0 release ceremony per D11:

- Section 5: Enable GitHub Pages (RESEARCH Q6).
- Section 6: Set default mike alias to v2 (RESEARCH Q10 pitfall #5).
- Section 7: Deploy frozen v1 docs snapshot (RESEARCH Q10 pitfall #6).
- Section 8: Update Bitbucket Pipe Marketplace listing (D11).
- Section 9: Post Docker Hub README deprecation banner (MIG-01 / D10).

Also asserts the SI-07-07 invariant: the D10 placeholder
'2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.' appears
at least twice in the runbook (sections 7 + 9).
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
    """Section 5 — Enable GitHub Pages (DOC-02)."""
    assert "## 5. Enable GitHub Pages" in RUNBOOK.read_text(), (
        "Section 5 (Enable GitHub Pages) must be present in the runbook"
    )


def test_runbook_section_5_uses_gh_api_pages_endpoint() -> None:
    """Section 5 must use the RESEARCH Q6 verbatim gh api endpoint."""
    assert "gh api repos/yves-vogl/aws-eks-helm-deploy/pages" in RUNBOOK.read_text(), (
        "Section 5 must invoke the gh api pages endpoint per RESEARCH Q6"
    )


def test_runbook_has_mike_set_default_section() -> None:
    """Section 6 — Set default mike alias to v2 (DOC-02 SC-3)."""
    assert "## 6. Set default mike alias to v2" in RUNBOOK.read_text(), (
        "Section 6 (Set default mike alias to v2) must be present"
    )


def test_runbook_section_6_uses_mike_set_default_push() -> None:
    """Section 6 must use the `mike set-default v2 --push` one-shot."""
    assert "mike set-default v2 --push" in RUNBOOK.read_text(), (
        "Section 6 must invoke `mike set-default v2 --push` per RESEARCH Q10 pitfall #5"
    )


def test_runbook_has_mike_v1_deploy_section() -> None:
    """Section 7 — Deploy frozen v1 docs snapshot (D2 — Plan 07-01)."""
    assert "## 7. Deploy frozen v1 docs snapshot" in RUNBOOK.read_text(), (
        "Section 7 (Deploy frozen v1 docs snapshot) must be present"
    )


def test_runbook_section_7_uses_mike_deploy_push_v1() -> None:
    """Section 7 must invoke `mike deploy --push v1` and note CI-exclusion."""
    text = RUNBOOK.read_text()
    assert "mike deploy --push v1" in text, (
        "Section 7 must invoke `mike deploy --push v1` per RESEARCH Q10 pitfall #6"
    )
    assert "CI never touches it" in text or "NEVER from CI" in text, (
        "Section 7 must explicitly note this command MUST NOT run from CI (Q10 pitfall #6)"
    )


def test_runbook_has_marketplace_section() -> None:
    """Section 8 — Update Bitbucket Pipe Marketplace listing (D11)."""
    assert "## 8. Update Bitbucket Pipe Marketplace listing" in RUNBOOK.read_text(), (
        "Section 8 (Bitbucket Pipe Marketplace listing update) must be present"
    )


def test_runbook_has_docker_hub_banner_section() -> None:
    """Section 9 — Post Docker Hub README deprecation banner (MIG-01)."""
    assert "## 9. Post Docker Hub README deprecation banner" in RUNBOOK.read_text(), (
        "Section 9 (Docker Hub README deprecation banner) must be present"
    )


def test_runbook_propagates_d10_placeholder() -> None:
    """SI-07-07: the D10 6-month placeholder must appear ≥ 2 times (Sections 7 + 9)."""
    text = RUNBOOK.read_text()
    count = text.count(D10_PLACEHOLDER)
    assert count >= 2, (
        f"SI-07-07 invariant broken: D10 placeholder appears {count} time(s), "
        f"expected ≥ 2 (Section 7 v1 banner + Section 9 Docker Hub banner)"
    )


def test_runbook_sections_1_to_4_remain_present() -> None:
    """Append-only invariant — sections 1-4 from Phase 6 must remain in the file."""
    text = RUNBOOK.read_text()
    for heading in [
        "## 1. Enable GitHub Private Vulnerability Reporting",
        "## 2. Configure Branch Protection on `main`",
        "## 3. Require GPG-Signed Commits",
        '## 4. Enable "Allow auto-merge" Repo Setting',
    ]:
        assert heading in text, (
            f"Append-only invariant broken — section heading missing: {heading!r}"
        )
