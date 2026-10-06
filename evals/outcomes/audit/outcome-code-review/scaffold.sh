#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'app'
cat > 'app/stats.py' <<'FIXTURE'
def average(values):
    """Return the mean of values."""
    return sum(values) / len(values)
FIXTURE
