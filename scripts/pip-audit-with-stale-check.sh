#!/usr/bin/env bash
# pip-audit-with-stale-check.sh — run pip-audit and detect stale --ignore-vuln suppressions.
#
# Usage: scripts/pip-audit-with-stale-check.sh
#
# Two-pass strategy:
#   Pass 1 — run pip-audit with active suppressions; fail on any NEW CVE.
#   Pass 2 — run pip-audit WITHOUT suppressions and check that each suppressed CVE
#             is still present; if a CVE has been fixed upstream, the suppression is
#             stale and this script exits non-zero so maintainers remove it.
#
# Add new suppressions by appending to SUPPRESSED_CVES below and passing
# the matching --ignore-vuln flags in AUDIT_ARGS.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

# CVEs intentionally suppressed; each entry must appear in AUDIT_ARGS too.
# Remove an entry here AND its --ignore-vuln counterpart once the upstream
# dependency ships a fix.
SUPPRESSED_CVES=(
    # No active suppressions. CVE-2026-25645 was removed after a [tool.uv]
    # override-dependencies entry in pyproject.toml forced requests >= 2.33.0,
    # which resolves uv.lock onto requests 2.34.2 (post-fix). See PR #83.
)

AUDIT_ARGS=(
    --skip-editable
)

# ── Pass 1: run pip-audit with suppressions ────────────────────────────────────

echo "pip-audit pass 1: running with active suppressions..."
uv run pip-audit "${AUDIT_ARGS[@]}"
echo "pip-audit pass 1: PASSED"

# ── Pass 2: stale-suppression check ───────────────────────────────────────────

echo "pip-audit pass 2: checking suppressed CVEs are still present (stale-ignore guard)..."

# Capture full audit output including suppressed findings (--skip-editable only).
audit_output="$(uv run pip-audit --skip-editable 2>&1 || true)"

stale=()
# Guard the loop: with set -u, expanding ${arr[@]} on an empty array throws
# "unbound variable". The ${arr[@]+...} pattern only expands when set.
for cve in "${SUPPRESSED_CVES[@]+"${SUPPRESSED_CVES[@]}"}"; do
    if ! echo "$audit_output" | grep -q "$cve"; then
        stale+=("$cve")
    fi
done

if [[ "${#stale[@]}" -gt 0 ]]; then
    echo ""
    echo "ERROR: the following CVE suppressions are STALE (no longer detected by pip-audit):"
    for cve in "${stale[@]}"; do
        echo "  - $cve"
    done
    echo ""
    echo "Action: remove the stale --ignore-vuln entry from .pre-commit-config.yaml"
    echo "        and remove the matching entry from SUPPRESSED_CVES in this script."
    exit 1
fi

echo "pip-audit pass 2: PASSED (all suppressed CVEs still present — suppressions are active)"
