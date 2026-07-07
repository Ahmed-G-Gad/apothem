#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Canonical fixture: Bash script with shebang + hash-form banner at line 2.
# The injector treats this fixture as canonical; --mode check exits 0
# and --mode fix-in-place is a no-op.

set -euo pipefail
echo "canonical sample"
