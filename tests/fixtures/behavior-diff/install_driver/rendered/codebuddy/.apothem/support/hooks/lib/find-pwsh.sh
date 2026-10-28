#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Purpose: Locate a real PowerShell >= 7 on PATH for any bash-side surface
# that needs to spawn a pwsh subprocess, rejecting Microsoft Store launcher
# shims (zero-byte stubs at AppData/Local/Microsoft/WindowsApps under
# WSL/Git-Bash mounts that fail at exec time with "Executable not found").
# Contract: dot-source then call find_real_pwsh; prints the absolute path
# on success and returns 0; returns 1 when no candidate satisfies the
# version floor. Does not throw on probe failures — silently skips bad
# candidates so the caller's diagnostic envelope path runs.
# Dialect: bash only (arrays, `[[ … ]]`, `<( … )` — declared by the
# `#!/usr/bin/env bash` shebang above). This is a deliberate divergence from
# the strict-POSIX-sh sibling find-python.sh: that locator is dot-sourced by a
# `curl … | sh` installer and must parse under dash/ash, whereas this pwsh
# locator is only ever sourced from bash-side surfaces.
# Sibling files in hooks/lib/: find-pwsh.ps1 (PowerShell counterpart),
# find-python.sh (POSIX-sh counterpart for Python — paired-template peer),
# find-python.ps1 (PowerShell counterpart of the Python locator).
#
# Usage (sourced):  . lib/find-pwsh.sh && p="$(find_real_pwsh)" || exit 1
# Exit codes: prints absolute path on success; exits 1 if none found.

# Walk every PATH entry and print each executable file matching $1, in PATH
# order — the manual stand-in for `type -ap`. `type -ap` resolves an empty
# PATH segment (a doubled "::" or a leading/trailing delimiter) to the current
# directory; this locator's result is version-probed (executed), so a
# cwd-planted `pwsh` reached through an empty segment would be run. This walk
# SKIPS empty segments, closing the same footgun find-python.sh closes. A user
# who genuinely wants cwd searched adds an explicit "." entry — non-empty,
# still honored below.
_find_pwsh_path_candidates() {
    local name="$1"
    local saved_ifs="$IFS"
    local dir full
    IFS=:
    for dir in $PATH; do
        IFS="$saved_ifs"
        if [[ -z "$dir" ]]; then
            IFS=:
            continue
        fi
        full="${dir}/${name}"
        if [[ -f "$full" && -x "$full" ]]; then
            printf '%s\n' "$full"
        fi
        IFS=:
    done
    IFS="$saved_ifs"
}

# Probe a single candidate path: reject WindowsApps stubs and sub-1024-byte
# shims, then run the pwsh version probe and print the path if it meets
# min_major. Prints the path and returns 0 on a qualifying interpreter;
# returns 1 otherwise. Shared by both probe phases below.
_probe_pwsh_candidate() {
    local path="$1"
    local min_major="$2"
    local size probe_output major
    [[ -z "$path" ]] && return 1
    case "$path" in *WindowsApps*) return 1 ;; esac
    [[ -x "$path" ]] || return 1
    size=$(wc -c < "$path" 2>/dev/null || echo 0)
    [[ "$size" -lt 1024 ]] && return 1
    # SC2016: the single-quoted expression is intentionally NOT bash-expanded —
    # it's a PowerShell expression evaluated by pwsh.
    # shellcheck disable=SC2016
    probe_output=$("$path" -NoProfile -Command '$PSVersionTable.PSVersion.Major' 2>/dev/null) || return 1
    probe_output="${probe_output//$'\r'/}"
    probe_output="${probe_output//[[:space:]]/}"
    major="$probe_output"
    [[ -z "$major" ]] && return 1
    [[ ! "$major" =~ ^[0-9]+$ ]] && return 1
    if (( major >= min_major )); then
        printf '%s\n' "$path"
        return 0
    fi
    return 1
}

find_real_pwsh() {
    local min_major="${1:-7}"
    local candidates=(pwsh pwsh-preview)
    local fallback_paths=(
        /usr/local/bin/pwsh
        /usr/bin/pwsh
        /opt/microsoft/powershell/7/pwsh
        /opt/microsoft/powershell/7-preview/pwsh
    )
    local name path

    # Phase 1 — PATH probe via the empty-segment-skipping walk, rejecting
    # WindowsApps stubs.
    for name in "${candidates[@]}"; do
        while IFS= read -r path; do
            if _probe_pwsh_candidate "$path" "$min_major"; then
                return 0
            fi
        done < <(_find_pwsh_path_candidates "$name")
    done

    # Phase 2 — canonical install paths (Linux / macOS).
    for path in "${fallback_paths[@]}"; do
        if _probe_pwsh_candidate "$path" "$min_major"; then
            return 0
        fi
    done

    return 1
}
