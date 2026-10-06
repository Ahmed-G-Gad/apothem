#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p 'app'
cat > 'app/upload.py' <<'FIXTURE'
from pathlib import Path

UPLOAD_DIR = Path("/srv/uploads")

def save_upload(filename: str, data: bytes) -> Path:
    target = UPLOAD_DIR / filename
    target.write_bytes(data)
    return target
FIXTURE
