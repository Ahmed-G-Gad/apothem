#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'app'
cat > 'app/ops.py' <<'FIXTURE'
import subprocess

API_TOKEN = "example-token-hardcoded-in-source"

def ping(host: str) -> str:
    return subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True, text=True).stdout
FIXTURE
