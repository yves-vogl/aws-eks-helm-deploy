"""Structural tests for Phase 7 / Plan 07-02 / DOC-04.

Asserts that:

(a) ``docs/adr/0000-template.md`` declares the MADR 4.0 provenance comment
    with the upstream blob SHA ``08dac30ed895cf728fc7da95f9702ca4dd5ab900``.
(b) The file contains the canonical MADR 4.0 section headings.
(c) All 9 numbered ADRs (0001..0009) exist with their authored filenames.
(d) Each authored ADR has the required MADR 4.0 sections.
(e) ``docs/adr/index.md`` lists all 9 ADRs and references the MADR SHA.

The structural test enforces presence + structure only; ADR prose content
is reviewed by humans in PR review (no NLP gate).
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"

#: The MADR 4.0 ``template/adr-template.md`` upstream blob SHA, captured at
#: tag ``4.0.0`` (released 2024-09-17). Recorded in 07-RESEARCH.md Q4 and
#: in the provenance comment of ``docs/adr/0000-template.md``.
MADR_4_0_TEMPLATE_BLOB_SHA: str = "08dac30ed895cf728fc7da95f9702ca4dd5ab900"

#: Filenames of every ADR shipped by Plan 07-02 (template + 9 authored ADRs) plus
#: ADR-0010 added for the helm v3 → v4 migration in v3.0.0 (issue #70).
EXPECTED_ADR_FILENAMES: frozenset[str] = frozenset(
    {
        "0000-template.md",
        "0001-github-primary-forge.md",
        "0002-v2-clean-break.md",
        "0003-cosign-keyless-over-gpg.md",
        "0004-boto3-only-over-awscli.md",
        "0005-release-please-over-semversioner.md",
        "0006-oidc-default-precedence.md",
        "0007-multi-arch-native-runners.md",
        "0008-mkdocs-material-now-zensical-later.md",
        "0009-src-layout-no-compat-shims.md",
        "0010-helm-v4-migration.md",
    }
)

#: MADR 4.0 canonical section headings asserted on every authored ADR.
MADR_REQUIRED_SECTIONS: tuple[str, ...] = (
    "## Context and Problem Statement",
    "## Considered Options",
    "## Decision Outcome",
)


def _authored_adrs() -> list[pathlib.Path]:
    """Return the 9 authored ADR files (excludes the 0000 template)."""
    return sorted(
        p for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md") if p.name != "0000-template.md"
    )


# ---------------------------------------------------------------------------
# docs/adr directory + 0000-template.md
# ---------------------------------------------------------------------------


def test_adr_dir_exists() -> None:
    """The ADR directory must exist under docs/adr/."""
    assert ADR_DIR.is_dir(), f"ADR directory missing: {ADR_DIR}"


def test_adr_template_exists() -> None:
    """The MADR 4.0 template must ship as docs/adr/0000-template.md."""
    template = ADR_DIR / "0000-template.md"
    assert template.is_file(), f"MADR template missing: {template}"


def test_adr_template_declares_madr_4_0_provenance() -> None:
    """The template MUST declare the MADR 4.0 upstream blob SHA verbatim.

    The provenance comment is the on-disk record of which upstream revision
    we vendored. The verifier reproduces this by downloading the upstream
    raw URL and confirming ``git hash-object`` matches the SHA recorded
    here. See 07-RESEARCH.md Q4 for the pinning rationale.
    """
    template = ADR_DIR / "0000-template.md"
    content = template.read_text(encoding="utf-8")
    assert MADR_4_0_TEMPLATE_BLOB_SHA in content, (
        "docs/adr/0000-template.md MUST declare the MADR 4.0 provenance "
        f"comment with upstream blob SHA {MADR_4_0_TEMPLATE_BLOB_SHA} "
        "(07-RESEARCH.md Q4). The verbatim copy was lost or the SHA was "
        "tampered with."
    )


def test_adr_template_has_madr_4_0_canonical_sections() -> None:
    """The template body must preserve the three canonical MADR 4.0 headings.

    These three are MADR-specific and confirm the body was not truncated
    nor replaced with a different ADR template (e.g. Michael Nygard's
    older format).
    """
    template = ADR_DIR / "0000-template.md"
    content = template.read_text(encoding="utf-8")
    for section in MADR_REQUIRED_SECTIONS:
        assert section in content, (
            f"docs/adr/0000-template.md missing canonical MADR 4.0 section heading: {section!r}"
        )


# ---------------------------------------------------------------------------
# Nine authored ADRs (0001..0009)
# ---------------------------------------------------------------------------


def test_all_nine_adrs_exist() -> None:
    """All 9 authored ADRs (0001..0009) must ship by Plan 07-02."""
    actual = {p.name for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md")}
    missing = EXPECTED_ADR_FILENAMES - actual
    assert not missing, (
        f"Missing ADR files (expected by Plan 07-02): "
        f"{sorted(missing)}; actual contents: {sorted(actual)}"
    )


def test_each_adr_has_madr_sections() -> None:
    """Every authored ADR must preserve MADR 4.0 section structure."""
    authored = _authored_adrs()
    assert len(authored) == 10, (
        f"Expected exactly 10 authored ADRs (0001..0010); "
        f"found {len(authored)}: {[p.name for p in authored]}"
    )
    for adr in authored:
        content = adr.read_text(encoding="utf-8")
        for section in MADR_REQUIRED_SECTIONS:
            assert section in content, f"{adr.name} missing required MADR section: {section!r}"


# ---------------------------------------------------------------------------
# docs/adr/index.md — curated archive
# ---------------------------------------------------------------------------


def test_adr_index_exists_and_lists_all_nine() -> None:
    """The index page must link to every authored ADR by filename stem."""
    index = ADR_DIR / "index.md"
    assert index.is_file(), f"ADR index missing: {index}"
    content = index.read_text(encoding="utf-8")
    for filename in EXPECTED_ADR_FILENAMES:
        if filename == "0000-template.md":
            continue
        stem = filename.removesuffix(".md")
        assert stem in content, (
            f"docs/adr/index.md does not link to ADR {stem!r} "
            "(the curated archive must list all 9 authored ADRs)"
        )
    assert MADR_4_0_TEMPLATE_BLOB_SHA in content, (
        "docs/adr/index.md should reference the MADR 4.0 provenance "
        f"SHA {MADR_4_0_TEMPLATE_BLOB_SHA} so consumers can verify "
        "the template upstream pin from the archive landing page."
    )
