"""Unit tests for scripts/scorecard-exception-check.py -- D3 grammar enforcement.

Phase 6 / SEC-10 / D3.

The module is loaded via importlib because the filename contains a hyphen.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import textwrap
import types
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module load -- importlib required because filename contains a hyphen
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "scripts" / "scorecard-exception-check.py"
)


def _load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("scorecard_exception_check", _SCRIPT_PATH)
    assert spec is not None, f"Could not build spec for {_SCRIPT_PATH}"
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scorecard_exception_check"] = mod
    spec.loader.exec_module(mod)
    return mod


sec_mod = _load_module()
check = sec_mod.check
main = sec_mod.main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    p = tmp_path / ".scorecard-exception.md"
    p.write_text(textwrap.dedent(content))
    return p


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _make_entry(
    check_name: str = "Token-Permissions",
    reason: str = "test reason",
    review_date: str | None = None,
    owner: str = "yves-vogl",
) -> str:
    if review_date is None:
        review_date = _future(90)
    return (
        f"  - check: {check_name}\n"
        f'    reason: "{reason}"\n'
        f"    review_date: {review_date}\n"
        f"    owner: {owner}\n"
    )


def _with_exceptions(tmp_path: pathlib.Path, entries: str) -> pathlib.Path:
    return _write(
        tmp_path,
        f"---\nexceptions:\n{entries}---\n\n# OpenSSF Scorecard Exceptions\n",
    )


# ---------------------------------------------------------------------------
# Tests -- empty / missing file
# ---------------------------------------------------------------------------


def test_empty_exceptions_passes(tmp_path: pathlib.Path) -> None:
    """exceptions: [] produces no errors."""
    p = _write(tmp_path, "---\nexceptions: []\n---\n\n# OpenSSF Scorecard Exceptions\n")
    assert check(p) == []


def test_missing_file_fails(tmp_path: pathlib.Path) -> None:
    """A missing file produces a 'not found' error."""
    p = tmp_path / ".scorecard-exception.md"
    errors: list[str] = check(p)
    assert len(errors) == 1
    assert "not found" in errors[0]


def test_no_frontmatter_fails(tmp_path: pathlib.Path) -> None:
    """A file with no --- block produces a frontmatter error."""
    p = _write(tmp_path, "# No frontmatter here\n")
    errors: list[str] = check(p)
    assert any("frontmatter" in e.lower() for e in errors), (
        f"Expected frontmatter error, got: {errors}"
    )


def test_frontmatter_with_non_dict_root_fails(tmp_path: pathlib.Path) -> None:
    """YAML frontmatter that is a list (not a dict) produces a mapping error."""
    p = _write(tmp_path, "---\n- item1\n- item2\n---\n")
    errors: list[str] = check(p)
    assert any("mapping" in e.lower() for e in errors), f"Expected mapping error, got: {errors}"


def test_exceptions_not_a_list_fails(tmp_path: pathlib.Path) -> None:
    """exceptions: 'string' (not a list) produces an error."""
    p = _write(tmp_path, '---\nexceptions: "not a list"\n---\n')
    errors: list[str] = check(p)
    assert any("list" in e.lower() for e in errors), f"Expected list error, got: {errors}"


# ---------------------------------------------------------------------------
# Tests -- valid entry
# ---------------------------------------------------------------------------


def test_valid_entry_passes(tmp_path: pathlib.Path) -> None:
    """A well-formed entry with review_date 90 days out passes."""
    p = _with_exceptions(tmp_path, _make_entry())
    assert check(p) == []


def test_review_date_exactly_at_boundary_passes(tmp_path: pathlib.Path) -> None:
    """review_date exactly 180 days from today is within the limit (inclusive)."""
    p = _with_exceptions(tmp_path, _make_entry(review_date=_future(180)))
    assert check(p) == []


# ---------------------------------------------------------------------------
# Tests -- missing required keys
# ---------------------------------------------------------------------------


def test_missing_check_key_fails(tmp_path: pathlib.Path) -> None:
    """Entry without 'check' key produces an error."""
    content = (
        "---\nexceptions:\n"
        f'  - reason: "no check key"\n'
        f"    review_date: {_future(90)}\n"
        "    owner: yves-vogl\n"
        "---\n"
    )
    p = _write(tmp_path, content)
    errors: list[str] = check(p)
    assert any("'check'" in e for e in errors), f"Expected 'check' error, got: {errors}"


def test_missing_reason_key_fails(tmp_path: pathlib.Path) -> None:
    """Entry without 'reason' key produces an error."""
    content = (
        "---\nexceptions:\n"
        "  - check: Token-Permissions\n"
        f"    review_date: {_future(90)}\n"
        "    owner: yves-vogl\n"
        "---\n"
    )
    p = _write(tmp_path, content)
    errors: list[str] = check(p)
    assert any("'reason'" in e for e in errors), f"Expected 'reason' error, got: {errors}"


def test_missing_review_date_key_fails(tmp_path: pathlib.Path) -> None:
    """Entry without 'review_date' key produces an error."""
    content = (
        "---\nexceptions:\n"
        "  - check: Token-Permissions\n"
        '    reason: "no review_date"\n'
        "    owner: yves-vogl\n"
        "---\n"
    )
    p = _write(tmp_path, content)
    errors: list[str] = check(p)
    assert any("'review_date'" in e for e in errors), f"Expected 'review_date' error, got: {errors}"


def test_missing_owner_key_fails(tmp_path: pathlib.Path) -> None:
    """Entry without 'owner' key produces an error."""
    content = (
        "---\nexceptions:\n"
        "  - check: Token-Permissions\n"
        '    reason: "no owner"\n'
        f"    review_date: {_future(90)}\n"
        "---\n"
    )
    p = _write(tmp_path, content)
    errors: list[str] = check(p)
    assert any("'owner'" in e for e in errors), f"Expected 'owner' error, got: {errors}"


# ---------------------------------------------------------------------------
# Tests -- stale / out-of-range review_date
# ---------------------------------------------------------------------------


def test_past_review_date_fails(tmp_path: pathlib.Path) -> None:
    """An entry with a past review_date is flagged as PAST."""
    p = _with_exceptions(tmp_path, _make_entry(review_date=_past(1)))
    errors: list[str] = check(p)
    assert any("is PAST" in e for e in errors), f"Expected PAST error, got: {errors}"


def test_review_date_exceeds_180_days_fails(tmp_path: pathlib.Path) -> None:
    """An entry with review_date > 180 days is flagged."""
    p = _with_exceptions(tmp_path, _make_entry(review_date=_future(200)))
    errors: list[str] = check(p)
    assert any("> 180 days" in e for e in errors), f"Expected >180d error, got: {errors}"


# ---------------------------------------------------------------------------
# Tests -- main() return codes
# ---------------------------------------------------------------------------


def test_main_returns_0_on_clean_file(tmp_path: pathlib.Path) -> None:
    """main() returns 0 for a valid file with empty exceptions list."""
    p = _write(tmp_path, "---\nexceptions: []\n---\n")
    result: int = main([str(p)])
    assert result == 0


def test_main_returns_1_on_stale_entry(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() returns 1 and prints ERROR: to stderr for a stale entry."""
    p = _with_exceptions(tmp_path, _make_entry(review_date=_past(1)))
    result: int = main([str(p)])
    assert result == 1
    captured = capsys.readouterr()
    assert "ERROR:" in captured.err
