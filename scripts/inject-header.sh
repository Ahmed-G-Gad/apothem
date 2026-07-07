#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

#
# Authorship-header injector — shell wrapper.
#
# Locates a Python 3 interpreter on PATH and delegates to the canonical
# injector at scripts/inject-header.py with the original argument vector
# preserved. The wrapper exists for environments where the user reaches
# for a .sh entrypoint by reflex (and for parity with the conventional
# src/apothem/hooks/lib/find-python.* pattern in this ecosystem); the substantive
# work lives in the Python script.
#
# Modes mirror the Python implementation: fix-in-place / emit-patch /
# check. Exit codes mirror the Python implementation:
#
#   0 — success or no divergence
#   1 — divergence found in `--mode check`
#   2 — irrecoverable error (missing fixture, missing interpreter)

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/inject-header.py"

if [ ! -f "${PYTHON_SCRIPT}" ]; then
    printf 'error: cannot locate %s\n' "${PYTHON_SCRIPT}" >&2
    exit 2
fi

# Locate a Python 3 interpreter. Prefer python3 per PEP 394; fall back
# to python (Windows installs and some minimal images map `python` to
# the 3.x interpreter).
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    printf 'error: no python3 interpreter found on PATH\n' >&2
    printf '       the wrapper requires python 3.10+ to run %s\n' "${PYTHON_SCRIPT}" >&2
    exit 2
fi

exec "${PYTHON}" "${PYTHON_SCRIPT}" "$@"
