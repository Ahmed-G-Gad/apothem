#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Minimal hook example — emits a single line to stderr to confirm the hook fired.
# Wire this into settings.json under "hooks" -> "PreToolUse" with an empty matcher
# so it fires on every PreToolUse event during smoke-testing, then remove once
# the pipeline is verified.

set -euo pipefail

EVENT_NAME="${1:-unknown}"

printf '[hello-hook] PreToolUse event received: %s\n' "${EVENT_NAME}" >&2

exit 0
