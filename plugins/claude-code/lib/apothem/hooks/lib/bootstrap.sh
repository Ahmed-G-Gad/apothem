#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Purpose: bash bootstrap stub for apothem hook events. Resolves the
# project root, locates a real CPython >= 3.10 via find-python.sh, then
# execs hooks/dispatch.py with the event name (and optional context-file
# relative to project root).
# Dialect: bash (the ERR trap below is a bashism, not POSIX sh; the shebang
# is `#!/usr/bin/env bash`). The interpreter locator it sources, find-python.sh,
# is strict-POSIX sh so a `curl … | sh` installer can dot-source it; this
# bootstrap is invoked as a bash script by the harness, not piped to sh.
# Contract: stdin/stdout passthrough; every bootstrap-owned failure branch
# (missing event, missing locator/dispatch, no interpreter, unexpected error)
# emits a JSON diagnostic envelope on stdout and exits 0 (fail-open) so hook
# failures never stall the host harness. Once control reaches the exec at the
# end, dispatch.py owns the process and its exit code — dispatch.py is itself
# fail-open, so the effective disposition remains exit 0.
# Sibling files in hooks/lib/: bootstrap.ps1 (PowerShell counterpart),
# find-python.sh (interpreter locator this stub sources), find-python.ps1
# (PowerShell counterpart of the locator).
#
# Root discovery order:
#   1. $CLAUDE_PROJECT_DIR if it points at a directory containing hooks/.
#   2. $LLM_PROJECT_DIR (vendor-neutral alias) if it points at a directory
#      containing hooks/.
#   3. Upward walk from $PWD looking for hooks/dispatch.py.
#   4. The directory two levels above this script (i.e. $HOME/.claude when
#      this lives at $HOME/.claude/hooks/lib/bootstrap.sh).
#   5. $HOME/.claude as final fallback (Claude Code harness root).
#
# Divergence from lib/resolve_root.py (deliberate, not accidental): this stub
# and bootstrap.ps1 use env → $PWD-walk → script-relative → $HOME order and a
# runtime marker of `hooks/dispatch.py` (an installed, dispatch-ready root),
# whereas resolve_root.py uses env → script-relative → cwd-walk → $HOME order
# and a directory-marker set (`hooks/`+`rules/` in HOOKS mode, or `CLAUDE.md`
# in MARKER mode). The bootstrap needs the concrete dispatcher present before
# it execs, so it keys on the dispatch file directly and prefers the running
# $PWD over the script location; resolve_root.py serves scripts that may run
# before dispatch.py exists (scaffolding), so it keys on directory markers and
# prefers the script's own location. Keep the three in step when the marker or
# order changes: bootstrap.sh, bootstrap.ps1, and resolve_root.py's docstring.

# Why `-u` only (not `-euo pipefail`): the dispatch contract is fail-open —
# any blocking error must surface as a JSON envelope on stdout with exit 0
# so the host harness never stalls. `-e` would short-circuit the explicit
# diagnostic-envelope branches below; `pipefail` is unused since no
# pipelines run in this script. `-u` catches typos in variable names,
# which is the one failure mode worth aborting on.
set -u

# Trap unexpected errors: emit a JSON envelope and exit 0 so the hook
# runtime sees a valid envelope rather than an unhandled non-zero exit.
trap 'printf "{\"systemMessage\":\"hook bootstrap: unexpected error at line %s\"}\n" "${LINENO}"; exit 0' ERR

event="${1:-}"
context_file="${2:-}"

if [ -z "$event" ]; then
    printf '{"systemMessage":"hook bootstrap: missing event name"}\n'
    exit 0
fi

# --- Resolve project root ----------------------------------------------------
root="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$root" ] || [ ! -d "$root/hooks" ]; then
    root="${LLM_PROJECT_DIR:-}"
fi
if [ -z "$root" ] || [ ! -d "$root/hooks" ]; then
    cursor="$PWD"
    root=""
    while [ -n "$cursor" ]; do
        if [ -f "$cursor/hooks/dispatch.py" ]; then
            root="$cursor"
            break
        fi
        parent="$(dirname "$cursor")"
        [ "$parent" = "$cursor" ] && break
        cursor="$parent"
    done
fi
if [ -z "$root" ]; then
    script_dir="$(cd "$(dirname "$0")" && pwd)"
    candidate="$(cd "$script_dir/../.." && pwd)"
    if [ -f "$candidate/hooks/dispatch.py" ]; then
        root="$candidate"
    fi
fi
[ -z "$root" ] && root="$HOME/.claude"

# --- Locate Python via the locator stub --------------------------------------
locator="$root/hooks/lib/find-python.sh"
if [ ! -f "$locator" ]; then
    printf '{"systemMessage":"hook %s skipped: locator stub missing at %s"}\n' \
        "$event" "$locator"
    exit 0
fi
# shellcheck source=find-python.sh disable=SC1091
. "$locator"

# Guard the command substitution so the ERR trap does NOT fire on the
# expected no-interpreter path. `if ! winner=$(...)` consumes the locator's
# non-zero exit as a tested condition rather than an uncaught error, so a
# host with no real CPython sees the intended "no Python interpreter found"
# envelope, not the trap's "unexpected error at line N" line.
if ! py="$(find_real_python 2>/dev/null)" || [ -z "$py" ]; then
    printf '{"systemMessage":"hook %s skipped: no Python interpreter found"}\n' "$event"
    exit 0
fi

dispatch="$root/hooks/dispatch.py"
if [ ! -f "$dispatch" ]; then
    printf '{"systemMessage":"hook %s skipped: dispatch missing at %s"}\n' \
        "$event" "$dispatch"
    exit 0
fi

# --- Hand off to dispatch.py -------------------------------------------------
if [ -n "$context_file" ]; then
    exec "$py" "$dispatch" --event-name "$event" --context-file "$context_file"
else
    exec "$py" "$dispatch" --event-name "$event"
fi
