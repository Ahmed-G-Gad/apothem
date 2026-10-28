#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Locate a real CPython >= 3.10 on PATH for the POSIX bootstrap
# stub, rejecting Microsoft Store launcher shims (zero-byte stubs at
# AppData/Local/Microsoft/WindowsApps under WSL/Git-Bash mounts).
# Contract: dot-source then call find_real_python; prints the absolute
# path on success and returns 0; returns 1 when no candidate satisfies
# the version floor. Does not throw on probe failures — silently skips
# bad candidates so the dispatcher's diagnostic envelope path runs.
# POSIX sh only (no bashisms): runs under dash/ash as well as bash, so a
# `curl … | sh` installer that dot-sources this locator stays portable.
# Sibling files in hooks/lib/: find-python.ps1 (PowerShell counterpart),
# bootstrap.sh (the script that dot-sources this locator), bootstrap.ps1
# (PowerShell counterpart of the bootstrap stub).
#
# Usage (sourced):  . lib/find-python.sh && py="$(find_real_python)" || exit 1
# Exit codes: prints absolute path on success; exits 1 if none found.

# Walk every PATH entry and print each executable file matching $1, in PATH
# order — the POSIX stand-in for bash's `type -ap`, which lists all matches
# rather than only the first (so a WindowsApps shim earlier on PATH does not
# mask a real interpreter found later).
_find_python_path_candidates() {
    _fpc_name="$1"
    _fpc_saved_ifs="$IFS"
    IFS=:
    for _fpc_dir in $PATH; do
        IFS="$_fpc_saved_ifs"
        # Skip an empty PATH segment (a doubled "::" or a leading/trailing
        # delimiter) rather than resolving it to the current directory. POSIX
        # maps an empty segment to cwd, but this locator's result is
        # version-probed (executed) and wired into the hook command that runs
        # on every tool use; discovering an attacker-planted cwd "python" there
        # is the footgun this guard closes. A user who genuinely wants cwd
        # searched adds an explicit "." entry — non-empty, still honored below.
        if [ -z "$_fpc_dir" ]; then
            IFS=:
            continue
        fi
        _fpc_full="${_fpc_dir}/${_fpc_name}"
        if [ -f "$_fpc_full" ] && [ -x "$_fpc_full" ]; then
            printf '%s\n' "$_fpc_full"
        fi
        IFS=:
    done
    IFS="$_fpc_saved_ifs"
}

find_real_python() {
    _frp_min_major="${1:-3}"
    _frp_min_minor="${2:-10}"
    _frp_candidates="python python3 python3.14 python3.13 python3.12 python3.11 python3.10"

    for _frp_name in $_frp_candidates; do
        # Probe every match for this name once. The inner loop runs in a
        # command-substitution subshell, so `break` (not `return`) emits the
        # first qualifying interpreter; the parent reads it back.
        _frp_winner=$(
            _find_python_path_candidates "$_frp_name" | while IFS= read -r _frp_path; do
                [ -z "$_frp_path" ] && continue
                # Skip Microsoft Store launcher shims. A POSIX prefix-strip
                # test, NOT `case`: this loop body runs inside `_frp_winner=$( … )`,
                # and macOS `/bin/sh` (bash 3.2) cannot parse a `case … ;; esac`
                # inside a command substitution. `dash -n` accepts it, which is
                # why the POSIX-parse gate missed it; `sh install.sh` on macOS
                # then fails at parse time. `${v#*WindowsApps}` differs from `$v`
                # exactly when `$v` contains "WindowsApps".
                if [ "${_frp_path#*WindowsApps}" != "$_frp_path" ]; then
                    continue
                fi
                [ -x "$_frp_path" ] || continue
                _frp_size=$(wc -c < "$_frp_path" 2>/dev/null || echo 0)
                [ "$_frp_size" -lt 1024 ] && continue
                _frp_probe=$("$_frp_path" -c 'import sys; sys.stdout.write(str(sys.version_info.major) + " " + str(sys.version_info.minor))' 2>/dev/null) || continue
                _frp_probe=$(printf '%s' "$_frp_probe" | tr -d '\r')
                _frp_major=$(printf '%s\n' "$_frp_probe" | cut -d' ' -f1)
                _frp_minor=$(printf '%s\n' "$_frp_probe" | cut -d' ' -f2)
                { [ -z "$_frp_major" ] || [ -z "$_frp_minor" ]; } && continue
                # Reject empty or non-numeric version components without `case`
                # (same bash-3.2 command-substitution limitation as above): strip
                # every ASCII digit and require a non-empty value with nothing left.
                { [ -z "$_frp_major" ] || [ -n "$(printf '%s' "$_frp_major" | tr -d '0123456789')" ]; } && continue
                { [ -z "$_frp_minor" ] || [ -n "$(printf '%s' "$_frp_minor" | tr -d '0123456789')" ]; } && continue
                if [ "$_frp_major" -gt "$_frp_min_major" ] || { [ "$_frp_major" -eq "$_frp_min_major" ] && [ "$_frp_minor" -ge "$_frp_min_minor" ]; }; then
                    printf '%s\n' "$_frp_path"
                    break
                fi
            done
        )
        if [ -n "$_frp_winner" ]; then
            printf '%s\n' "$_frp_winner"
            return 0
        fi
    done
    return 1
}
