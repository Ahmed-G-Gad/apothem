#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'app'
cat > 'app/cli.py' <<'FIXTURE'
import sys

def main(argv):
    if len(argv) < 2:
        print("Error 17")
        sys.exit(1)
    print("ok")
FIXTURE
