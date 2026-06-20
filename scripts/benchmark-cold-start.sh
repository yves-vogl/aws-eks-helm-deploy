#!/usr/bin/env bash
# Phase 6 / IMAGE-06 — Cold-start benchmark.
#
# Measures image startup time (image pre-pulled) by running `docker run --rm <image> --help`
# N times and reporting the median. PASS threshold: 10s (target per IMAGE-06).
# CATASTROPHIC threshold: 30s (only this fails CI per RESEARCH A6 — runner jitter
# at the 10s boundary should not flap the release pipeline).
#
# Usage:
#   scripts/benchmark-cold-start.sh [<image>] [<runs>] [<output-json>]
#
# Defaults:
#   image = ghcr.io/yves-vogl/aws-eks-helm-deploy:latest
#   runs  = 5
#   output-json = /tmp/cold-start-results.json
#
# Output:
#   - Per-run timings to stdout
#   - JSON file with {image, runs, times_ms, median_ms, target_ms, catastrophic_ms, pass, catastrophic}
#   - Exits 0 if median < catastrophic_ms (30000 ms); 1 otherwise (rare CI fail)
#
# Note: IMAGE-06 cold-start is a DOCUMENTED benchmark, not a hard 10s gate (A6).

set -euo pipefail

IMAGE="${1:-ghcr.io/yves-vogl/aws-eks-helm-deploy:latest}"
N="${2:-5}"
OUTPUT_JSON="${3:-/tmp/cold-start-results.json}"

TARGET_MS=10000          # IMAGE-06 documented target
CATASTROPHIC_MS=30000    # hard CI failure threshold

echo "Benchmarking cold-start for ${IMAGE} (${N} runs)"
echo "Target: <${TARGET_MS}ms (notice); catastrophic: >${CATASTROPHIC_MS}ms (CI fail)"

# Pre-pull to exclude network time (the spec for IMAGE-06)
docker pull "${IMAGE}" > /dev/null 2>&1

times=()
for i in $(seq 1 "${N}"); do
  start_ns=$(date +%s%N)
  docker run --rm "${IMAGE}" --help > /dev/null 2>&1 || true   # --help may exit non-zero; ignore
  end_ns=$(date +%s%N)
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  times+=("${elapsed_ms}")
  echo "  Run ${i}: ${elapsed_ms}ms"
done

# Compute median (sort + pick middle)
mapfile -t sorted < <(printf '%s\n' "${times[@]}" | sort -n)
median_idx=$(( N / 2 ))
median_ms="${sorted[${median_idx}]}"

echo "Median cold-start: ${median_ms}ms"

# Emit JSON
times_json=$(printf '%s,' "${times[@]}")
times_json="[${times_json%,}]"

cat > "${OUTPUT_JSON}" <<EOF
{
  "image": "${IMAGE}",
  "runs": ${N},
  "times_ms": ${times_json},
  "median_ms": ${median_ms},
  "target_ms": ${TARGET_MS},
  "catastrophic_ms": ${CATASTROPHIC_MS},
  "pass": $([ "${median_ms}" -lt "${TARGET_MS}" ] && echo true || echo false),
  "catastrophic": $([ "${median_ms}" -gt "${CATASTROPHIC_MS}" ] && echo true || echo false)
}
EOF

cat "${OUTPUT_JSON}"

if [[ "${median_ms}" -gt "${CATASTROPHIC_MS}" ]]; then
  echo "CATASTROPHIC: median ${median_ms}ms > ${CATASTROPHIC_MS}ms — failing CI" >&2
  exit 1
fi

if [[ "${median_ms}" -gt "${TARGET_MS}" ]]; then
  echo "WARNING: median ${median_ms}ms exceeds IMAGE-06 target ${TARGET_MS}ms (not failing CI per A6)" >&2
fi

exit 0
