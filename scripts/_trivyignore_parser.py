"""Phase 6 / SEC-04 / D2 — .trivyignore grammar parser.

Enforces the D2 grammar:
  CVE-XXXX-NNNNN  # expires=YYYY-MM-DD rationale="…" reviewer=<github-handle>

Rules:
  - expires=YYYY-MM-DD must be in the future AND within 180 days of today.
  - rationale="…" must be non-empty.
  - reviewer=<github-handle> must be present.

This module is CI infrastructure (NOT product code); exempt from 100% coverage rule
per Plan 06-07's pyproject.toml omit list.
"""

from __future__ import annotations

import pathlib
import re
import sys
from datetime import date

LINE_RE = re.compile(
    r"^(?P<cve>CVE-\d{4}-\d+)\s+"
    r"#\s*expires=(?P<expires>\d{4}-\d{2}-\d{2})\s+"
    r"rationale=\"(?P<rationale>[^\"]+)\"\s+"
    r"reviewer=(?P<reviewer>\S+)"
)
MAX_DAYS = 180


def _check_expiry(i: int, cve: str, expires_str: str, today: date) -> list[str]:
    """Validate the expires= field for a single entry. Returns error list."""
    errors: list[str] = []
    try:
        expires = date.fromisoformat(expires_str)
    except ValueError:
        errors.append(f"Line {i}: malformed expires= field: {expires_str!r}")
        return errors
    if expires < today:
        errors.append(
            f"Line {i}: {cve} expiry {expires.isoformat()} is PAST — remove or extend"
        )
    elif (expires - today).days > MAX_DAYS:
        errors.append(
            f"Line {i}: {cve} expiry {expires.isoformat()} is > {MAX_DAYS} days — shorten"
        )
    return errors


def check(path: pathlib.Path, today: date | None = None) -> list[str]:
    """Return a list of error messages; empty list means PASS."""
    errors: list[str] = []
    today = today or date.today()
    if not path.is_file():
        # An absent .trivyignore is acceptable (no suppressions); not an error.
        return errors
    for i, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cve = line.split()[0]
        if not cve.startswith("CVE-"):
            continue
        match = LINE_RE.match(line)
        if not match:
            errors.append(f"Line {i}: missing required grammar: {line!r}")
            continue
        errors.extend(_check_expiry(i, cve, match["expires"], today))
        if not match["rationale"].strip():
            errors.append(f"Line {i}: {cve} rationale is empty")
        if not match["reviewer"]:
            errors.append(f"Line {i}: {cve} missing reviewer")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: trivyignore-check.sh <path-to-trivyignore>", file=sys.stderr)
        return 2
    path = pathlib.Path(args[0])
    errors = check(path)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"{path}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
