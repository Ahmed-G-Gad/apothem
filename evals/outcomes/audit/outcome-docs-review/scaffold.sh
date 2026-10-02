#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.'
cat > 'README.md' <<'FIXTURE'
# tidy
Format YAML files in place.

    tidy --verbose config.yaml
FIXTURE

mkdir -p 'app'
cat > 'app/cli.py' <<'FIXTURE'
import argparse

def main():
    parser = argparse.ArgumentParser(prog="tidy")
    parser.add_argument("path")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()
FIXTURE
