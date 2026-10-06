#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Generate the CycloneDX SBOM for the built apothem distributions.
#
# A thin wrapper around generate_sbom.py, the same generator the release
# workflow runs. It reads the wheel and sdist in DIST_DIR (default: dist/),
# lists every package vendored under apothem/_vendor (the vendor.txt pins,
# checked against the wheel) and the declared runtime requirements, and
# records each distribution's SHA-256. It describes what ships, not the
# checkout: build the distributions first (`python -m build`).
#
# Usage: generate-sbom.sh [OUTPUT] [DIST_DIR]
#   OUTPUT    default dist/release-assets/sbom.cdx.json
#   DIST_DIR  default dist/

set -euo pipefail
IFS=$'\n\t'

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly OUT_PATH="${1:-${REPO_ROOT}/dist/release-assets/sbom.cdx.json}"
readonly DIST_DIR="${2:-${REPO_ROOT}/dist}"

python_bin="$(command -v python3 || command -v python || true)"
if [[ -z "${python_bin}" ]]; then
    printf 'generate-sbom: no python3 or python on PATH\n' >&2
    exit 1
fi

"${python_bin}" "${REPO_ROOT}/scripts/release/generate_sbom.py" \
    --dist "${DIST_DIR}" \
    --output "${OUT_PATH}"
