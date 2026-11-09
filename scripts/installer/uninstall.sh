#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Remove materialized harness configuration (self-contained — no
#          package to uninstall) and optionally remove the bundled source
#          tree at $APOTHEM_HOME.
# Contract: Idempotent. Confirms before removal unless --yes is supplied.
#           POSIX sh only (no bashisms): runs under dash/ash as well as bash.
#           Holds the lock folder <APOTHEM_HOME>.lock while it runs, so it
#           never runs at the same time as an install or update.
#
# Usage:
#     bash scripts/installer/uninstall.sh [--yes] [--harness NAME] [--remove-source]
#
# Environment overrides:
#     APOTHEM_HOME     Bundled source location (default: $HOME/.apothem)
#     APOTHEM_SOURCE   Explicit local source tree to drive the CLI from
#     APOTHEM_HARNESS  Harness to uninstall (default: claude-code)

set -eu

# The caller's PYTHONPATH is set aside until the Python this script runs is
# chosen: which separator and which path form are safe depends on that
# Python, not on the shell (see settle_python_form). Until then every Python
# started here (the locator, the version probes) runs with no PYTHONPATH.
# APOTHEM_CALLER_PYTHONPATH is a plain shell variable, never exported
# (mirrors install.sh).
unset APOTHEM_CALLER_PYTHONPATH
APOTHEM_CALLER_PYTHONPATH="${PYTHONPATH:-}"
unset PYTHONPATH
PY_WINDOWS=""
PY_PATHSEP=""

# keep_full_pythonpath VALUE — print the entries of the PYTHONPATH value
# VALUE that are full paths, joined the way the chosen Python splits them.
# Python turns an empty or relative entry (":/x", "/x:", ".") into the
# current folder, ahead of site-packages, so a sitecustomize.py, click.py or
# apothem/ there would run in place of the real module. For a POSIX Python
# (including Cygwin's and MSYS2's own python3) the value is split on ":" and
# an entry is kept only when it starts with "/". For a Windows Python (the
# usual one under Git Bash) it is split on ";" and an entry is kept only when
# it is a drive path ("C:\x", "C:/x") or a network path ("\\server\x",
# "//server/x"), so a rooted "\lib", a drive-relative "C:rel" and a "/c/x"
# entry are dropped. Reads PY_WINDOWS, which settle_python_form sets.
keep_full_pythonpath() {
    if [ "$PY_WINDOWS" = "1" ]; then _kp_sep=";"; else _kp_sep=":"; fi
    _kp_rest="$1"
    _kp_keep=""
    while [ -n "$_kp_rest" ]; do
        _kp_entry="${_kp_rest%%"$_kp_sep"*}"
        case "$_kp_rest" in
            *"$_kp_sep"*) _kp_rest="${_kp_rest#*"$_kp_sep"}" ;;
            *) _kp_rest="" ;;
        esac
        if [ "$PY_WINDOWS" = "1" ]; then
            case "$_kp_entry" in
                [A-Za-z]:[\\/]* | [\\/][\\/]*) ;;
                *) continue ;;
            esac
        else
            case "$_kp_entry" in
                /*) ;;
                *) continue ;;
            esac
        fi
        _kp_keep="${_kp_keep:+${_kp_keep}${_kp_sep}}${_kp_entry}"
    done
    printf '%s' "$_kp_keep"
}

# settle_python_form — ask the chosen Python ($PY) which PYTHONPATH form it
# reads, then give it the caller's full-path entries in that form. A Windows
# Python (the usual one under Git Bash) splits on ";" and reads Windows
# paths. A POSIX Python, including Cygwin's and MSYS2's own python3, splits
# on ":" and reads POSIX paths. The shell cannot tell them apart: uname says
# MINGW, MSYS or CYGWIN for both, and a ";"-joined list of Windows paths
# reads to a POSIX Python as relative entries such as "C", folders in the
# current folder. The probe runs isolated (-I) and needs only os and sys.
# Sets PY_WINDOWS (1 or 0) and PY_PATHSEP, and exports the kept entries as
# PYTHONPATH (unset when none are kept).
settle_python_form() {
    _pf_form="$("$PY" -I -c 'import os, sys; sys.stdout.write(os.pathsep + sys.platform)' 2>/dev/null)" \
        || _pf_form=""
    case "$_pf_form" in
        ";win32") PY_WINDOWS=1; PY_PATHSEP=";" ;;
        :?*) PY_WINDOWS=0; PY_PATHSEP=":" ;;
        *) die "Could not tell which PYTHONPATH form ${PY} reads (it printed '${_pf_form}')." ;;
    esac
    _pp_keep="$(keep_full_pythonpath "$APOTHEM_CALLER_PYTHONPATH"; printf x)"
    _pp_keep="${_pp_keep%x}"
    if [ -n "$_pp_keep" ]; then
        PYTHONPATH="$_pp_keep"
        export PYTHONPATH
    else
        unset PYTHONPATH
    fi
}

# native_path PATH — print the full path PATH in the form the chosen Python
# reads: the Windows form (cygpath -w) for a Windows Python, unchanged for a
# POSIX one. Every caller passes a path that starts with "/". Returns 1, so
# the caller stops, when cygpath fails or prints anything but a drive or
# network path; that can only happen for a Windows Python.
native_path() {
    if [ "$PY_WINDOWS" = "1" ]; then
        _np_path="$(cygpath -w -- "$1" 2>/dev/null)" || return 1
        case "$_np_path" in
            [A-Za-z]:[\\/]* | [\\/][\\/]*) printf '%s\n' "$_np_path" ;;
            *) return 1 ;;
        esac
    else
        printf '%s\n' "$1"
    fi
}

# engine_pythonpath — print the PYTHONPATH an engine run gets: the engine
# paths, then the full-path entries of the caller's PYTHONPATH that
# settle_python_form kept, joined with PY_PATHSEP.
engine_pythonpath() {
    printf '%s' "${ENGINE_PYPATH}${PYTHONPATH:+${PY_PATHSEP}${PYTHONPATH}}"
}

APOTHEM_HOME="${APOTHEM_HOME:-$HOME/.apothem}"
# A trailing "/" or "/." would put the lock, <APOTHEM_HOME>.lock, inside
# APOTHEM_HOME instead of beside it (mirrors install.sh).
while [ "$APOTHEM_HOME" != "/" ]; do
    case "$APOTHEM_HOME" in
        */.) APOTHEM_HOME="${APOTHEM_HOME%/.}" ;;
        */) APOTHEM_HOME="${APOTHEM_HOME%/}" ;;
        *) break ;;
    esac
    [ -n "$APOTHEM_HOME" ] || APOTHEM_HOME="/"
done
HARNESS="${APOTHEM_HARNESS:-claude-code}"
ASSUME_YES=0
REMOVE_SOURCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --yes|-y)         ASSUME_YES=1 ;;
        --harness)        HARNESS="$2"; shift ;;
        --remove-source)  REMOVE_SOURCE=1 ;;
        *) printf "Unknown option: %s\n" "$1" >&2; exit 1 ;;
    esac
    shift
done

# Colour only an interactive terminal. NO_COLOR (https://no-color.org/) or a
# redirected stream (a pipe, a file, a CI log) gets plain text; stdout and
# stderr are checked separately because die() writes to stderr.
COLOR_OUT=0
COLOR_ERR=0
if [ -z "${NO_COLOR:-}" ]; then
    if [ -t 1 ]; then COLOR_OUT=1; fi
    if [ -t 2 ]; then COLOR_ERR=1; fi
fi

# paint ENABLED SGR TEXT — print TEXT, wrapped in the SGR colour code when
# ENABLED is 1.
paint() {
    if [ "$1" = "1" ]; then
        printf '\033[%sm%s\033[0m' "$2" "$3"
    else
        printf '%s' "$3"
    fi
}

bold()  { printf '%s\n' "$(paint "$COLOR_OUT" 1 "$*")"; }
info()  { printf '  %s %s\n' "$(paint "$COLOR_OUT" 36 '·')" "$*"; }
ok()    { printf '  %s %s\n' "$(paint "$COLOR_OUT" 32 '✓')" "$*"; }
warn()  { printf '  %s %s\n' "$(paint "$COLOR_OUT" 33 '!')" "$*"; }
die()   { printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$*" >&2; exit 1; }

# exists PATH — return 0 when PATH is there, a dangling symbolic link included.
exists() {
    [ -e "$1" ] || [ -L "$1" ]
}

# The install lock, <APOTHEM_HOME>.lock, held for the whole run; see
# install.sh's take_lock. The EXIT trap (release_lock) removes it on every
# way out of the run.
LOCK_DIR=""
LOCK_HELD=0
take_lock() {
    _tl_home="$APOTHEM_HOME"
    if [ -L "$APOTHEM_HOME" ] && _tl_real="$(cd -P -- "$APOTHEM_HOME" 2>/dev/null && pwd -P)"; then
        _tl_home="$_tl_real"
    fi
    LOCK_DIR="${_tl_home}.lock"
    _tl_parent="$(dirname -- "$_tl_home")"
    # With no folder to hold APOTHEM_HOME there is no install to remove, and the
    # run stops below without the lock.
    [ -d "$_tl_parent" ] || return 0
    # Signals are ignored from the mkdir until LOCK_HELD says the lock is
    # this run's: a signal in between would otherwise leave a lock with no
    # process ID in it, and a run whose mkdir failed must never remove the
    # lock that another run holds.
    trap '' HUP INT QUIT PIPE TERM
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        LOCK_HELD=1
        trap_signals_to_exit
        # The environment goes in before the process ID, so a lock that
        # names a process always says where that process runs.
        lock_env > "${LOCK_DIR}/env" || die "Could not write the lock ${LOCK_DIR}."
        printf '%s\n' "$$" > "${LOCK_DIR}/pid" || die "Could not write the lock ${LOCK_DIR}."
        return 0
    fi
    trap_signals_to_exit
    exists "$LOCK_DIR" \
        || die "Could not create the lock $LOCK_DIR. Check that you can write to ${_tl_parent}, then re-run."
    if [ ! -L "$LOCK_DIR" ] && [ ! -d "$LOCK_DIR" ]; then
        if powershell_may_lock; then
            die "$LOCK_DIR is the lock file of an Apothem PowerShell run (install.ps1, update.ps1 or uninstall.ps1) on $APOTHEM_HOME, and Windows removes it when that run ends; while the run is active, Windows will not let anyone remove it. Wait for that run to finish, then re-run. If no Apothem install, update or uninstall is running, remove $LOCK_DIR, then re-run."
        fi
        die "$LOCK_DIR is a file where the Apothem lock folder belongs. If no Apothem install, update or uninstall is running, remove $LOCK_DIR, then re-run."
    fi
    _tl_pid="$(cat "${LOCK_DIR}/pid" 2>/dev/null || true)"
    if [ -z "$_tl_pid" ]; then
        # A run that has just made the lock writes its process ID a moment
        # later; look again before calling the lock stale.
        sleep 1
        _tl_pid="$(cat "${LOCK_DIR}/pid" 2>/dev/null || true)"
    fi
    case "$_tl_pid" in
        "" | *[!0-9]*)
            die "$LOCK_DIR exists but names no running process; an Apothem run may have left it when it was stopped. Check that no Apothem install, update or uninstall is running, remove $LOCK_DIR, then re-run." ;;
    esac
    # A lock made before the environment was recorded has no env file; its
    # process is checked here as before.
    if [ -f "${LOCK_DIR}/env" ] && [ "$(cat "${LOCK_DIR}/env" 2>/dev/null)" != "$(lock_env)" ]; then
        die "$LOCK_DIR was made by an Apothem run in another environment (such as WSL, Git Bash or a container), so whether its process ${_tl_pid} still runs cannot be checked from here. Wait for that run to finish, then re-run. If no Apothem install, update or uninstall is running anywhere, remove $LOCK_DIR, then re-run."
    fi
    if process_running "$_tl_pid"; then
        die "Another Apothem install, update or uninstall is running on $APOTHEM_HOME. Wait for it to finish, then re-run. If none is running, remove $LOCK_DIR, then re-run."
    fi
    die "$LOCK_DIR was left by an Apothem run that did not finish (process ${_tl_pid} is no longer running). Check that no Apothem install, update or uninstall is running, remove $LOCK_DIR, then re-run."
}
release_lock() {
    if [ "$LOCK_HELD" = "1" ]; then
        rm -rf -- "$LOCK_DIR"
        LOCK_HELD=0
    fi
}

# process_running PID — return 0 when the process PID is running. kill -0
# also fails for a running process that belongs to another user (a run under
# sudo on the same APOTHEM_HOME, say); only then does it say "not
# permitted".
process_running() {
    _pr_err="$(LC_ALL=C; export LC_ALL; kill -0 "$1" 2>&1)" && return 0
    case "$_pr_err" in
        *[Nn]"ot permitted"*) return 0 ;;
    esac
    return 1
}

# lock_env and powershell_may_lock: see install.sh.
lock_env() {
    printf '%s %s %s %s\n' "$(uname -o 2>/dev/null || uname -s 2>/dev/null)" \
        "$(uname -n 2>/dev/null)" "$(readlink /proc/self/ns/pid 2>/dev/null)" \
        "$(cygpath -m / 2>/dev/null)"
}
powershell_may_lock() {
    case "$(uname -s 2>/dev/null)" in
        MINGW* | MSYS* | CYGWIN*) return 0 ;;
    esac
    case "$(uname -r 2>/dev/null)" in
        *[Mm]icrosoft*) return 0 ;;
    esac
    return 1
}

# trap_signals_to_exit — make each signal that would end the run exit
# through the EXIT trap, so the lock is let go (mirrors install.sh).
trap_signals_to_exit() {
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 131' QUIT
    trap 'exit 141' PIPE
    trap 'exit 143' TERM
}

bold "Apothem uninstaller"
echo

# One install, update or uninstall at a time on APOTHEM_HOME (see
# take_lock). The EXIT trap lets the lock go on every way out, and each
# signal that ends the run exits through it.
trap release_lock EXIT
trap_signals_to_exit
take_lock

is_apothem_source() {
    [ -d "$1/src/apothem" ] && { [ -f "$1/pyproject.toml" ] || [ -d "$1/.claude-plugin" ]; }
}

# Resolve a Python interpreter >= 3.10, rejecting Microsoft Store launcher shims.
PY=""
for _cand in python3 python python3.14 python3.13 python3.12 python3.11 python3.10; do
    # Probe the path PATH resolves the name to, so a shim can be recognised
    # before it is run. Running a Store alias opens the Store page instead
    # of Python, so a candidate under a WindowsApps directory is skipped.
    # The prefix-strip test is the one find-python.sh uses; uninstall.ps1
    # skips the same directory.
    _cand_path="$(command -v "$_cand" 2>/dev/null)" || continue
    [ -n "$_cand_path" ] || continue
    if [ "${_cand_path#*WindowsApps}" != "$_cand_path" ]; then
        continue
    fi
    if "$_cand_path" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1; then
        PY="$_cand_path"
        break
    fi
done
[ -n "$PY" ] || die "No Python >= 3.10 found in PATH — nothing to uninstall"
settle_python_form

# Locate the bundled source so the CLI can drive the harness uninstall.
SOURCE=""
if [ -n "${APOTHEM_SOURCE:-}" ]; then
    SOURCE="$(cd "$APOTHEM_SOURCE" 2>/dev/null && pwd || true)"
    [ -n "$SOURCE" ] && is_apothem_source "$SOURCE" \
        || die "APOTHEM_SOURCE is not an apothem source tree: ${APOTHEM_SOURCE}"
elif is_apothem_source "$APOTHEM_HOME"; then
    SOURCE="$APOTHEM_HOME"
fi
[ -n "$SOURCE" ] || die "No apothem source found at $APOTHEM_HOME — nothing to uninstall"
# Absolute, so no PYTHONPATH entry below can name the current folder.
SRC_PATH="${SOURCE}/src"
case "$SRC_PATH" in /*) ;; *) SRC_PATH="$(pwd)/${SRC_PATH}" ;; esac

if [ "$ASSUME_YES" -eq 0 ]; then
    printf "  Remove %s harness configuration? [y/N] " "$HARNESS"
    read -r ANSWER
    case "$ANSWER" in
        [Yy]*) ;;
        *) warn "Aborted."; exit 0 ;;
    esac
fi

bold "Uninstalling harness: ${HARNESS}"
# Vendor-first PYTHONPATH mirrors the install/update invocations.
_ep_vendor="$(native_path "${SRC_PATH}/apothem/_vendor")" \
    || die "cygpath could not give the Windows path (a drive or network path) of ${SRC_PATH}/apothem/_vendor, which ${PY} needs. Check that cygpath works in this shell, or run uninstall.ps1 from PowerShell instead."
_ep_src="$(native_path "${SRC_PATH}")" \
    || die "cygpath could not give the Windows path (a drive or network path) of ${SRC_PATH}, which ${PY} needs. Check that cygpath works in this shell, or run uninstall.ps1 from PowerShell instead."
ENGINE_PYPATH="${_ep_vendor}${PY_PATHSEP}${_ep_src}"
# The current folder must never shadow the engine's modules: `-m` puts it
# first on sys.path and `-c` puts '' there. `-P` / PYTHONSAFEPATH does not
# exist on Python 3.10 and `-I` would drop PYTHONPATH and the user site, so
# the engine starts with PYTHONSAFEPATH=1 and a `-c` program that first drops
# a leading '' (mirrors install.sh). Only sys.path changes.
DROP_CWD_FROM_PATH="import sys; sys.path[:1] = [] if sys.path[:1] == [''] else sys.path[:1]"
ENGINE_PROGRAM="${DROP_CWD_FROM_PATH}; import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"
PYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" \
    "$PY" -c "$ENGINE_PROGRAM" uninstall --harness "$HARNESS" --yes
ok "Harness ${HARNESS} uninstalled"
echo

# Entry-point shim ---------------------------------------------------------------
#
# Remove the `apothem` PATH shim install.sh placed at
# ${APOTHEM_BIN_DIR:-$HOME/.local/bin}/apothem (same dir/filename derivation).
# Only the file carrying the install.sh-generated marker is removed, so an
# operator's own `apothem` on PATH is never touched. Every install.sh since
# 1.0.1 writes that marker line, both the earlier `-m apothem` shim and the
# current one, so both are removed. Idempotent: absent shim is
# a no-op. Never removes the directory — only the specific shim file.
SHIM_BIN_DIR="${APOTHEM_BIN_DIR:-$HOME/.local/bin}"
SHIM="${SHIM_BIN_DIR}/apothem"
SHIM_MARKER='# Apothem entry-point shim (generated by install.sh).'
if [ -f "$SHIM" ] && grep -qF "$SHIM_MARKER" "$SHIM" 2>/dev/null; then
    if rm -f "$SHIM" 2>/dev/null; then
        ok "Removed apothem command: $SHIM"
    else
        warn "Could not remove the apothem shim at $SHIM — remove it manually."
    fi
fi
echo

if [ "$REMOVE_SOURCE" -eq 1 ]; then
    # Only the managed clone at APOTHEM_HOME is removable; an explicit
    # APOTHEM_SOURCE (operator's own checkout) is never deleted.
    if [ "$SOURCE" = "$APOTHEM_HOME" ] && [ -d "$APOTHEM_HOME/.git" ]; then
        if [ "$ASSUME_YES" -eq 0 ]; then
            printf "  Remove the bundled source at %s? [y/N] " "$APOTHEM_HOME"
            read -r ANSWER
            case "$ANSWER" in
                [Yy]*) ;;
                *) warn "Kept the bundled source."; SOURCE=""; ;;
            esac
        fi
        if [ -n "$SOURCE" ]; then
            bold "Removing bundled source"
            rm -rf "$APOTHEM_HOME"
            ok "Removed $APOTHEM_HOME"
        fi
    else
        warn "Source at $SOURCE is operator-owned (not the managed clone) — not removed."
    fi
fi
echo

bold "Uninstall complete."
cat <<EOF

Next steps:
  1. Remove another harness:        bash scripts/installer/uninstall.sh --harness <name>
  2. Remove the bundled source too: bash scripts/installer/uninstall.sh --remove-source --yes
  3. Re-install a harness later:    bash scripts/installer/install.sh

EOF
