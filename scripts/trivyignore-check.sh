#!/usr/bin/env bash
# Phase 6 / SEC-04 / D2 — .trivyignore grammar enforcement (CI gate).
# Wraps the Python parser to keep ci.yml invocation uniform with other shell helpers.
set -euo pipefail

TRIVYIGNORE="${1:-.trivyignore}"

exec uv run python scripts/_trivyignore_parser.py "$TRIVYIGNORE"
