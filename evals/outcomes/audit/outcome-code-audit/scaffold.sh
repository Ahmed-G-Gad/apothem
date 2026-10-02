#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'app'
cat > 'app/calc.py' <<'FIXTURE'
def evaluate(expression: str) -> float:
    """Evaluate a user-supplied arithmetic expression."""
    return eval(expression)
FIXTURE
