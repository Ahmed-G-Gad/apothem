#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'app'
cat > 'app/db.py' <<'FIXTURE'
from app.ui import render_row

def fetch_rows():
    rows = [("1", "alpha")]
    return [render_row(r) for r in rows]
FIXTURE

mkdir -p 'app'
cat > 'app/ui.py' <<'FIXTURE'
from app.db import fetch_rows

def render_row(row):
    return " | ".join(row)

def page():
    return "\n".join(fetch_rows())
FIXTURE
