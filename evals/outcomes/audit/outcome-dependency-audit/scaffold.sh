#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.'
cat > 'requirements.txt' <<'FIXTURE'
requests
pyyaml==5.3
flask>=1.0
FIXTURE
