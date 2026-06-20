#!/usr/bin/env bash
# Phase 6 / SEC-04 / D2 — .trivyignore grammar enforcement (CI gate).
# Wraps the Python parser to keep ci.yml invocation uniform with other shell helpers.
#
# Usage:
#   bash scripts/trivyignore-check.sh                       # validate .trivyignore
#   bash scripts/trivyignore-check.sh .trivyignore .trivyignore.bare
#                                                            # also emit a bare sidecar
#                                                            # for Trivy (inline comments
#                                                            # stripped; required because
#                                                            # Trivy does NOT honour them)
set -euo pipefail

TRIVYIGNORE="${1:-.trivyignore}"
BARE_OUT="${2:-}"

if [ -n "$BARE_OUT" ]; then
    exec uv run python scripts/_trivyignore_parser.py "$TRIVYIGNORE" --emit-bare "$BARE_OUT"
else
    exec uv run python scripts/_trivyignore_parser.py "$TRIVYIGNORE"
fi
