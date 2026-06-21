#!/usr/bin/env bash
set -euo pipefail
# Regenerate the variables doc and fail if it drifts from the committed file.
uv run --extra docs python scripts/generate-variables-doc.py
git diff --exit-code -- docs/reference/variables.md
