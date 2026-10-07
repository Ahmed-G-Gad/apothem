#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Run this script after a CLI surface change to re-emit the completion scripts;
# byte-identical regeneration is the verification check.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/src/apothem/cli/completions"
mkdir -p "$OUT"

# Every golden is the SPDX header followed by `apothem completion <shell>`.
# That command pins the `apothem` program name and the _APOTHEM_COMPLETE
# variable, so the emitted script is the same whichever shim runs it. Click's
# `<shell>_source` env-var protocol is not used here: it derives the program
# name from the invocation, so under a `python -m apothem` shim it emitted
# `_python_mapothem_completion` functions bound to `python -m apothem`.
#
# Each script is generated into a temp file and promoted only on success: shell
# redirection opens its target with O_TRUNC before the command runs, so writing
# the group straight to the golden destroyed it the instant a generator failed.
# The quieter case is worse — a generator that exits 0 emitting nothing left a
# header-only file that the byte-identical verification check then treats as
# canonical, while the script still printed success.
for shell in bash zsh fish powershell; do
  case "$shell" in
    powershell) ext="ps1" ;;
    *) ext="$shell" ;;
  esac
  _body="$(mktemp "$OUT/.apothem.$ext.body.XXXXXX")"
  _out="$(mktemp "$OUT/.apothem.$ext.XXXXXX")"
  if ! { apothem completion "$shell" 2>/dev/null \
      || python -m apothem completion "$shell"; } > "$_body"; then
    rm -f "$_body" "$_out"
    echo "error: failed to regenerate apothem.$ext (apothem off PATH and the python fallback failed; run under PYTHONPATH=src)" >&2
    exit 1
  fi
  if [ ! -s "$_body" ]; then
    rm -f "$_body" "$_out"
    echo "error: apothem.$ext generated empty; refusing to overwrite the golden" >&2
    exit 1
  fi
  {
    printf '# SPDX-License-Identifier: MIT\n\n'
    cat "$_body"
  } > "$_out"
  rm -f "$_body"
  mv "$_out" "$OUT/apothem.$ext"
  printf '  ✓ %s\n' "apothem.$ext"
done

echo "Regeneration complete → $OUT"
