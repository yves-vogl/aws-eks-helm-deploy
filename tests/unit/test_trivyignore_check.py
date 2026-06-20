"""Unit tests for scripts/_trivyignore_parser.py — D2 grammar enforcement.

Phase 6 / SEC-04 / D2.
"""

from __future__ import annotations

import pathlib
import textwrap
from datetime import date, timedelta

import pytest

from scripts._trivyignore_parser import check, main

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    p = tmp_path / ".trivyignore"
    p.write_text(textwrap.dedent(content))
    return p


def _future(days: int) -> date:
    return date.today() + timedelta(days=days)


def _past(days: int) -> date:
    return date.today() - timedelta(days=days)


# ---------------------------------------------------------------------------
# Tests — file-level
# ---------------------------------------------------------------------------


def test_empty_file_passes(tmp_path: pathlib.Path) -> None:
    """An empty .trivyignore (just comments) produces no errors."""
    p = _write(
        tmp_path,
        """\
        # Phase 6 / SEC-04 / D2 — CVE suppression list.
        # Grammar: CVE-XXXX-NNNNN  # expires=YYYY-MM-DD rationale="…" reviewer=handle
        """,
    )
    assert check(p) == []


def test_missing_file_passes(tmp_path: pathlib.Path) -> None:
    """An absent .trivyignore is acceptable (no suppressions)."""
    p = tmp_path / ".trivyignore"
    assert not p.is_file()
    assert check(p) == []


def test_comment_lines_skipped(tmp_path: pathlib.Path) -> None:
    """A comment line starting with # that mentions CVE does NOT trip the parser."""
    p = _write(
        tmp_path,
        """\
        # CVE-XXXX-0001 is a sample that should never be triggered
        """,
    )
    assert check(p) == []


# ---------------------------------------------------------------------------
# Tests — valid entry
# ---------------------------------------------------------------------------


def test_valid_entry_passes(tmp_path: pathlib.Path) -> None:
    """A well-formed entry with expiry 90 days out passes with no errors."""
    exp = _future(90).isoformat()
    p = _write(
        tmp_path,
        f'CVE-2026-12345  # expires={exp} rationale="test suppression reason" reviewer=yves-vogl\n',
    )
    assert check(p) == []


def test_expiry_exactly_at_boundary_passes(tmp_path: pathlib.Path) -> None:
    """Expiry exactly 180 days from today is within the limit (inclusive)."""
    exp = _future(180).isoformat()
    p = _write(
        tmp_path,
        f'CVE-2026-11111  # expires={exp} rationale="boundary test" reviewer=yves-vogl\n',
    )
    assert check(p) == []


# ---------------------------------------------------------------------------
# Tests — grammar errors
# ---------------------------------------------------------------------------


def test_missing_expires_fails(tmp_path: pathlib.Path) -> None:
    """Line without expires= fails with a grammar error."""
    p = _write(
        tmp_path,
        'CVE-2026-12345  # rationale="missing expiry" reviewer=yves-vogl\n',
    )
    errors = check(p)
    assert len(errors) == 1
    assert "missing required grammar" in errors[0]


def test_missing_rationale_fails(tmp_path: pathlib.Path) -> None:
    """Line without rationale= fails with a grammar error."""
    exp = _future(90).isoformat()
    p = _write(
        tmp_path,
        f"CVE-2026-12345  # expires={exp} reviewer=yves-vogl\n",
    )
    errors = check(p)
    assert len(errors) == 1
    assert "missing required grammar" in errors[0]


def test_missing_reviewer_fails(tmp_path: pathlib.Path) -> None:
    """Line without reviewer= fails with a grammar error."""
    exp = _future(90).isoformat()
    p = _write(
        tmp_path,
        f'CVE-2026-12345  # expires={exp} rationale="no reviewer here"\n',
    )
    errors = check(p)
    assert len(errors) == 1
    assert "missing required grammar" in errors[0]


def test_past_expiry_fails(tmp_path: pathlib.Path) -> None:
    """An entry with a past expiry date is flagged as PAST."""
    exp = _past(1).isoformat()
    p = _write(
        tmp_path,
        f'CVE-2026-12345  # expires={exp} rationale="stale entry" reviewer=yves-vogl\n',
    )
    errors = check(p)
    assert any("is PAST" in e for e in errors), f"Expected PAST error, got: {errors}"


def test_expiry_exceeds_180_days_fails(tmp_path: pathlib.Path) -> None:
    """An entry with expiry > 180 days in the future is flagged."""
    exp = _future(200).isoformat()
    p = _write(
        tmp_path,
        f'CVE-2026-12345  # expires={exp} rationale="too far out" reviewer=yves-vogl\n',
    )
    errors = check(p)
    assert any("> 180 days" in e for e in errors), f"Expected >180d error, got: {errors}"


def test_malformed_iso_date_fails(tmp_path: pathlib.Path) -> None:
    """A digit-pattern expires= with an invalid calendar date is flagged as malformed.

    The LINE_RE matches digit patterns like YYYY-MM-DD, but date.fromisoformat()
    rejects invalid calendar dates (e.g. month 13 or day 40).
    """
    p = _write(
        tmp_path,
        'CVE-2026-12345  # expires=2099-13-40 rationale="bad date" reviewer=yves-vogl\n',
    )
    errors = check(p)
    assert any("malformed expires=" in e for e in errors), (
        f"Expected malformed error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Tests — main() return codes
# ---------------------------------------------------------------------------


def test_main_returns_0_on_empty_file(tmp_path: pathlib.Path) -> None:
    """main() returns 0 for a valid (comment-only) .trivyignore."""
    p = _write(tmp_path, "# nothing here\n")
    result = main([str(p)])
    assert result == 0


def test_main_returns_1_on_grammar_error(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() returns 1 and prints ERROR: to stderr for a malformed entry."""
    exp = _past(1).isoformat()
    p = _write(
        tmp_path,
        f'CVE-2026-99999  # expires={exp} rationale="stale" reviewer=yves-vogl\n',
    )
    result = main([str(p)])
    assert result == 1
    captured = capsys.readouterr()
    assert "ERROR:" in captured.err


def test_main_returns_2_on_no_argv(capsys: pytest.CaptureFixture[str]) -> None:
    """main() returns 2 and prints usage message when no arguments are given."""
    result = main([])
    assert result == 2
    captured = capsys.readouterr()
    assert "usage:" in captured.err
