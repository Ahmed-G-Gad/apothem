#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Purpose: bash bootstrap stub for apothem hook events. Resolves the
# installed tree it ships in, locates a real CPython >= 3.10 via find-python.sh, then
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
# Root discovery: the directory two levels above this script, i.e. the
# installed tree that ships this stub (`<root>/hooks/lib/bootstrap.sh`). That
# root holds `hooks/lib/find-python.sh` and `hooks/dispatch.py`. The stub
# never derives its root from the opened project ($CLAUDE_PROJECT_DIR,
# $LLM_PROJECT_DIR) or from $PWD: the locator is dot-sourced and the dispatcher
# is executed, so taking either from the project would run project-supplied
# code inside every hook. Handlers that need project data (plan suites, memory)
# read the project directory from the hook payload and the environment
# themselves, as data, never as code.
#
# Divergence from lib/resolve_root.py (deliberate): resolve_root.py locates a
# project root for scripts that read project files; this stub locates only its
# own installed tree. Keep both headers in step when either rule changes:
# bootstrap.sh, bootstrap.ps1, and resolve_root.py's docstring.

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

# --- Resolve the installed tree that ships this stub ------------------------
script_dir="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$script_dir/../.." && pwd)"
if [ ! -f "$root/hooks/dispatch.py" ]; then
    printf '{"systemMessage":"hook %s skipped: dispatch missing beside the bootstrap stub"}\n' "$event"
    exit 0
fi

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
