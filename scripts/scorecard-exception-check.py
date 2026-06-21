"""Phase 6 / SEC-10 / D3 -- .scorecard-exception.md review_date enforcement.

Parses the YAML frontmatter of .scorecard-exception.md and fails if any entry's
review_date is past OR more than 180 days in the future.
"""

from __future__ import annotations

import pathlib
import re
import sys
from datetime import date
from typing import Any

import yaml

MAX_DAYS = 180
FRONTMATTER_RE = re.compile(r"^---\s*$(.+?)^---\s*$", re.MULTILINE | re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.search(text)
    if not match:
        raise ValueError("No YAML frontmatter (--- ... ---) block found")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("Frontmatter is not a YAML mapping")
    return data


def _check_review_date(i: int, entry: dict[str, Any], today: date) -> list[str]:
    """Validate review_date for a single exception entry. Returns error list."""
    errors: list[str] = []
    raw_date = entry["review_date"]
    review = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date))
    if review < today:
        errors.append(
            f"Entry {i} ({entry.get('check', '?')}): review_date {review.isoformat()} is PAST"
        )
    elif (review - today).days > MAX_DAYS:
        errors.append(
            f"Entry {i} ({entry.get('check', '?')}): review_date"
            f" {review.isoformat()} > {MAX_DAYS} days"
        )
    return errors


def _check_entry(i: int, entry: dict[str, Any], today: date) -> list[str]:
    """Validate a single exceptions list entry. Returns error list."""
    errors: list[str] = []
    for key in ("check", "reason", "review_date", "owner"):
        if key not in entry:
            errors.append(f"Entry {i}: missing required key {key!r}")
    if "review_date" in entry:
        errors.extend(_check_review_date(i, entry, today))
    return errors


def check(path: pathlib.Path, today: date | None = None) -> list[str]:
    """Return a list of error messages; empty list means PASS."""
    errors: list[str] = []
    today = today or date.today()
    if not path.is_file():
        errors.append(f"{path} not found")
        return errors
    text = path.read_text()
    try:
        data = _parse_frontmatter(text)
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    exceptions = data.get("exceptions", []) or []
    if not isinstance(exceptions, list):
        errors.append("exceptions: must be a YAML list")
        return errors
    for i, entry in enumerate(exceptions, start=1):
        if not isinstance(entry, dict):
            errors.append(f"Entry {i}: not a mapping")
            continue
        errors.extend(_check_entry(i, entry, today))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = pathlib.Path(args[0]) if args else pathlib.Path(".scorecard-exception.md")
    errors = check(path)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"{path}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
