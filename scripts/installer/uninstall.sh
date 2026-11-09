#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Remove materialized harness configuration (self-contained — no
#          package to uninstall) and optionally remove the bundled source
#          tree at $APOTHEM_HOME.
# Contract: Idempotent. Confirms before removal unless --yes is supplied.
#           POSIX sh only (no bashisms): runs under dash/ash as well as bash.
#
# Usage:
#     bash scripts/installer/uninstall.sh [--yes] [--harness NAME] [--remove-source]
#
# Environment overrides:
#     APOTHEM_HOME     Bundled source location (default: $HOME/.apothem)
#     APOTHEM_SOURCE   Explicit local source tree to drive the CLI from
#     APOTHEM_HARNESS  Harness to uninstall (default: claude-code)

set -eu

# keep_full_pythonpath VALUE — print the entries of the PYTHONPATH value
# VALUE that are full paths, joined the way Python splits them. Python turns
# an empty or relative entry (":/x", "/x:", ".") into the current folder,
# ahead of site-packages, so a sitecustomize.py, click.py or apothem/ there
# would run in place of the real module. On POSIX an entry is kept only when
# it starts with "/". Under Git Bash, MSYS or Cygwin the Python is a Windows
# one that splits PYTHONPATH on ";": there an entry is kept only when it is a
# drive path ("C:\x", "C:/x") or a network path ("\\server\x", "//server/x"),
# so a rooted "\lib" and a drive-relative "C:rel" are dropped. Every Python
# this script starts gets only the kept entries (mirrors install.sh).
keep_full_pythonpath() {
    case "$(uname -s 2>/dev/null || true)" in
        MINGW* | MSYS* | CYGWIN*) _kp_sep=";" ;;
        *) _kp_sep=":" ;;
    esac
    _kp_rest="$1"
    _kp_keep=""
    while [ -n "$_kp_rest" ]; do
        _kp_entry="${_kp_rest%%"$_kp_sep"*}"
        case "$_kp_rest" in
            *"$_kp_sep"*) _kp_rest="${_kp_rest#*"$_kp_sep"}" ;;
            *) _kp_rest="" ;;
        esac
        if [ "$_kp_sep" = ";" ]; then
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
# PY_PATHSEP is the separator the Python this script starts reads in
# PYTHONPATH. Under Git Bash, MSYS or Cygwin that Python is a Windows one,
# which splits on ";" and wants Windows paths. MSYS rewrites a ":"-joined list
# of /c/... paths into ";"-joined Windows paths when it starts a Windows
# program, and in doing so splits a "C:\x" entry into "C" and "\x": the
# relative "C" then names a folder in the current folder, ahead of the
# standard library. So there every engine path is turned into its Windows form
# with cygpath -w and the list is joined with ";", which MSYS leaves alone.
case "$(uname -s 2>/dev/null || true)" in
    MINGW* | MSYS* | CYGWIN*) PY_PATHSEP=";" ;;
    *) PY_PATHSEP=":" ;;
esac

# native_path PATH — print PATH in the form the Python this script starts
# reads: unchanged on POSIX, the Windows form under Git Bash, MSYS or Cygwin.
native_path() {
    if [ "$PY_PATHSEP" = ";" ]; then
        cygpath -w -- "$1" 2>/dev/null
    else
        printf '%s\n' "$1"
    fi
}

# engine_pythonpath — print the PYTHONPATH an engine run gets: the engine
# paths, then the full-path entries of the caller's PYTHONPATH that
# keep_full_pythonpath kept, joined with PY_PATHSEP.
engine_pythonpath() {
    printf '%s' "${ENGINE_PYPATH}${PYTHONPATH:+${PY_PATHSEP}${PYTHONPATH}}"
}

_pp_keep="$(keep_full_pythonpath "${PYTHONPATH:-}"; printf x)"
_pp_keep="${_pp_keep%x}"
if [ -n "$_pp_keep" ]; then
    PYTHONPATH="$_pp_keep"
    export PYTHONPATH
else
    unset PYTHONPATH
fi

APOTHEM_HOME="${APOTHEM_HOME:-$HOME/.apothem}"
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

bold "Apothem uninstaller"
echo

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
    || die "cygpath could not convert ${SRC_PATH}/apothem/_vendor to a Windows path"
_ep_src="$(native_path "${SRC_PATH}")" \
    || die "cygpath could not convert ${SRC_PATH} to a Windows path"
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
