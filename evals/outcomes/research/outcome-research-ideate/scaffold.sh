#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.'
cat > 'notes.md' <<'FIXTURE'
Research notes: teams keep asking whether adding type hints to Python code pays off in fewer bugs.
We have access to public issue trackers and commit histories of open-source Python projects.
FIXTURE
