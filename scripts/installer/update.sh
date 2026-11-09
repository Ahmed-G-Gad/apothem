#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Re-fetch the bundled Apothem source (self-contained — no package
#          installation) and re-materialize harness configuration.
# Contract: Idempotent. Exits 0 on success, non-zero on failure.
#           POSIX sh only (no bashisms): runs under dash/ash as well as bash.
#
# Trust model (tag-pinned, verified-by-default): mirrors install.sh. With no
# APOTHEM_REF set, the latest vMAJOR.MINOR.PATCH release tag is resolved. The
# clone is fetched, the tag is checked, and only then is it checked out, so a
# failed check leaves the clone where it was: `git verify-tag` must pass, the
# signature must be made by the maintainer key SECURITY.md publishes
# (fingerprint 5C8998F9F241720445D3F28B70396FED9C634163), and the signed tag
# object must name itself as that release. An unsigned / tampered tag, or one
# signed by another key, ABORTS before any config is written unless
# APOTHEM_ALLOW_UNVERIFIED=1 downgrades the abort to a loud warning; a tag the
# maintainer signed for another release and re-pointed here aborts either
# way. Because APOTHEM_ALLOW_UNVERIFIED=1 lets an unsigned tag, or one signed
# by another key, through, that re-pointed-tag check protects only tags that
# carry the maintainer key's signature. Changes to tracked files stop the
# update before the checkout, and the checkout runs without --force, so other
# local changes it would overwrite stop it too instead of being lost.
# Before anything is fetched, the update also stops when the clone hides
# changes from git (files marked assume-unchanged or skip-worktree), when its
# work tree is not APOTHEM_HOME, or when its own git config names a program
# for git to run or pulls in other config (gpg.program, gpg.openpgp.program,
# core.fsmonitor, core.hooksPath, include.*, includeIf.*). Every git command
# on the clone runs with its hooks turned off. Only a clone of an Apothem
# source tree is updated; any other folder is left alone. APOTHEM_REF=main
# checks out the branch on request (it needs APOTHEM_ALLOW_UNVERIFIED=1). The
# APOTHEM_SOURCE local-checkout path fetches nothing and skips verification.
# An install made from a release archive (install.sh's cosign or checksum
# path) has no git clone to update; re-run install.sh to update it.
#
# Usage:
#     sh scripts/installer/update.sh
#
# Environment overrides:
#     APOTHEM_HOME             Cloned source location (default: $HOME/.apothem)
#     APOTHEM_REPO             Git remote (default: https://github.com/ahmed-g-gad/apothem)
#     APOTHEM_REF              Git ref to update to. Unset = latest release tag;
#                             set to a tag to pin, or to "main" for the branch.
#     APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a failed tag-signature check to a
#                             warning and proceed, and allow a ref that is not
#                             a release tag. A re-pointed tag still aborts,
#                             but since an unsigned tag, or one signed by
#                             another key, gets through, that check protects
#                             only tags that carry the maintainer key's
#                             signature.
#     APOTHEM_SOURCE          Explicit local source tree to re-materialize from
#                             (skips tag resolution and verification)
#     APOTHEM_HARNESS         Harness to update (default: claude-code)
#     APOTHEM_PROFILE         Path to shared profile YAML
#     APOTHEM_AUTO_INSTALL_DEPS  If "1", install missing click / rich
#                             prerequisites automatically (pip), no prompt

set -eu

# git reads these from the environment and would then work on another
# repository, index or object store than the one each command names, swap
# objects through replace refs, take extra configuration, or run its helper
# programs and templates from elsewhere (mirrors install.sh).
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE \
    GIT_REPLACE_REF_BASE GIT_CEILING_DIRECTORIES GIT_CONFIG_PARAMETERS \
    GIT_CONFIG_COUNT GIT_EXEC_PATH GIT_TEMPLATE_DIR
GIT_NO_REPLACE_OBJECTS=1
export GIT_NO_REPLACE_OBJECTS

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

# native_path PATH — print PATH in the form the chosen Python reads: the
# Windows form (cygpath -w) for a Windows Python, unchanged for a POSIX one.
# Returns 1, so the caller stops, when cygpath fails or prints anything but a
# drive or network path, or when a POSIX path does not start with "/".
native_path() {
    if [ "$PY_WINDOWS" = "1" ]; then
        _np_path="$(cygpath -w -- "$1" 2>/dev/null)" || return 1
        case "$_np_path" in
            [A-Za-z]:[\\/]* | [\\/][\\/]*) printf '%s\n' "$_np_path" ;;
            *) return 1 ;;
        esac
    else
        case "$1" in
            /*) printf '%s\n' "$1" ;;
            *) return 1 ;;
        esac
    fi
}

# engine_pythonpath — print the PYTHONPATH an engine run gets: the engine
# paths, then the full-path entries of the caller's PYTHONPATH that
# settle_python_form kept, joined with PY_PATHSEP.
engine_pythonpath() {
    printf '%s' "${ENGINE_PYPATH}${PYTHONPATH:+${PY_PATHSEP}${PYTHONPATH}}"
}

APOTHEM_HOME="${APOTHEM_HOME:-$HOME/.apothem}"
APOTHEM_REPO="${APOTHEM_REPO:-https://github.com/ahmed-g-gad/apothem}"
APOTHEM_REF="${APOTHEM_REF:-}"
APOTHEM_ALLOW_UNVERIFIED="${APOTHEM_ALLOW_UNVERIFIED:-0}"
HARNESS="${APOTHEM_HARNESS:-claude-code}"
PROFILE="${APOTHEM_PROFILE:-$HOME/.config/apothem/profile.yaml}"
# The primary-key fingerprint SECURITY.md publishes; mirrors install.sh.
MAINTAINER_FINGERPRINT="5C8998F9F241720445D3F28B70396FED9C634163"

# CLI prerequisites; `yaml` + `jsonschema` ship vendored inside the bundled
# tree (src/apothem/_vendor), so only click + rich come from the host.
RUNTIME_DEPS="click rich"
VENDORING_DOC="https://apothem.ahmedgad.com/docs/architecture/vendoring-strategy/"

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

# git clone and ls-remote would read a value that starts with "-" as an option.
case "$APOTHEM_REPO" in
    -*) die "APOTHEM_REPO must be a repository URL or path, not an option: ${APOTHEM_REPO}" ;;
esac
# A relative local path names a folder or a file (a git bundle) below the
# current one; git runs from another folder (see ngit), so make it absolute
# first.
case "$APOTHEM_REPO" in
    /*|*:*) ;;
    *)
        if [ -d "$APOTHEM_REPO" ]; then
            APOTHEM_REPO="$(cd -P -- "$APOTHEM_REPO" && pwd -P)"
        elif [ -e "$APOTHEM_REPO" ]; then
            _repo_dir="$(cd -P -- "$(dirname -- "$APOTHEM_REPO")" && pwd -P)"
            APOTHEM_REPO="${_repo_dir%/}/$(basename -- "$APOTHEM_REPO")"
        fi
        ;;
esac

# ngit ARGS — run a git command that works on no clone of its own from an
# empty folder made for it, with GIT_CEILING_DIRECTORIES at that folder's
# parent, so the config of a repository around the current folder (which can
# make git run programs) is never read (mirrors install.sh).
ngit() (
    _ng_dir="$(mktemp -d)" || exit 1
    # The subshell does not keep the caller's signal traps: remove the
    # folder on any exit, and turn a signal into an exit so that runs.
    trap 'cd / && rm -rf -- "$_ng_dir"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    cd -P -- "$_ng_dir" || exit 1
    _ng_dir="$(pwd -P)"
    if GIT_CEILING_DIRECTORIES="$(dirname -- "$_ng_dir")" git "$@"; then
        _ng_rc=0
    else
        _ng_rc=$?
    fi
    cd / && rm -rf -- "$_ng_dir"
    exit "$_ng_rc"
)

# abs_path PATH — print PATH made absolute against the current folder.
abs_path() {
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf '%s/%s\n' "$(pwd)" "$1" ;;
    esac
}

# resolve_latest_tag / verify_tag / is_release_tag mirror install.sh; see that
# script's helper comments for the per-function contract. Kept POSIX-clean.
resolve_latest_tag() {
    _rlt_tab="$(printf '\t')"
    ngit ls-remote --tags "$1" 2>/dev/null \
        | sed -n "s#^[0-9a-f][0-9a-f]*${_rlt_tab}refs/tags/\(v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)\(\^{}\)\{0,1\}\$#\1#p" \
        | sort -u \
        | sort -t. -k1.2,1n -k2,2n -k3,3n \
        | tail -n 1
}

# cgit ARGS — run git with ARGS and, once HOOKS_OFF names an empty folder,
# with core.hooksPath pointing at it, so none of the clone's hooks run
# (mirrors install.sh).
HOOKS_OFF=""
cgit() {
    if [ -n "$HOOKS_OFF" ]; then
        git -c core.hooksPath="$HOOKS_OFF" "$@"
    else
        git "$@"
    fi
}

VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(cgit -C "$1" verify-tag --raw "$2" 2>&1)"
}

# check_clone_setup DIR — the checks install.sh runs on an existing clone
# before the fetch; see that script's comment.
check_clone_setup() {
    _cs_flags="$(cgit -C "$1" ls-files -v 2>/dev/null)" \
        || die "$1 has changes to tracked files. Commit or stash them, then re-run."
    if printf '%s\n' "$_cs_flags" | awk '{ c = substr($0, 1, 1) } c ~ /[a-z]/ || c == "S" { found = 1; exit } END { exit found ? 0 : 1 }'; then
        die "$1 has changes to tracked files. Commit or stash them, then re-run."
    fi
    _cs_top="$(cgit -C "$1" rev-parse --show-toplevel 2>/dev/null || true)"
    _cs_here="$(cd "$1" && pwd -P)"
    if [ -z "$_cs_top" ] || [ "$_cs_top" != "$_cs_here" ]; then
        die "$1 is not the work tree of its git clone (core.worktree is set, or its .git points elsewhere). Remove that setting, then re-run."
    fi
    _cs_keys="$(cgit -C "$1" config --local --name-only --get-regexp . 2>/dev/null || true)"
    _cs_key="$(printf '%s\n' "$_cs_keys" | awk '
        {
            k = tolower($0)
            if (k == "gpg.program" || k == "gpg.openpgp.program" || k == "core.fsmonitor" || k == "core.hookspath" || index(k, "include.") == 1 || index(k, "includeif.") == 1) { print; exit }
        }')"
    if [ -n "$_cs_key" ]; then
        die "$1's own git config sets ${_cs_key}, which the update would trust. Remove it from $1/.git/config, then re-run."
    fi
}

# verify_tag_by_maintainer / verify_tag_valid_other_key mirror install.sh,
# which documents why a valid signature alone is not enough.
verify_tag_by_maintainer() {
    printf '%s\n' "$VERIFY_TAG_OUTPUT" | awk -v want="$MAINTAINER_FINGERPRINT" '
        $1 == "[GNUPG:]" && $2 == "VALIDSIG" {
            seen++
            fpr = (NF >= 12) ? $12 : $3
            if (toupper(fpr) != want) other++
        }
        END { exit (seen > 0 && other == 0) ? 0 : 1 }'
}

verify_tag_valid_other_key() {
    case "$VERIFY_TAG_OUTPUT" in
        "[GNUPG:] VALIDSIG "* | *"
[GNUPG:] VALIDSIG "*) ! verify_tag_by_maintainer ;;
        *) return 1 ;;
    esac
}

verify_tag_missing_key() {
    case "$VERIFY_TAG_OUTPUT" in
        *"[GNUPG:] NO_PUBKEY "*) return 0 ;;
        *) return 1 ;;
    esac
}

# is_release_tag REF — return 0 when REF is a strict vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), non-zero otherwise (a branch like main, a SHA, a
# pre-release tag like v1.2.3-rc1, or a malformed form like v1x.2.3 or
# v1.2.3.4). Drives whether tag verification applies to the fetched ref. This
# mirrors the anchored `^v[0-9]+\.[0-9]+\.[0-9]+\z` regex in update.ps1's
# Test-ReleaseTag: a POSIX `case` glob cannot express "one-or-more digits" or
# reject trailing junk on its own (a bare `v[0-9]*.[0-9]*.[0-9]*` matches
# v1.2.3-rc1, v1x.2.3 and v1.2.3.4, since `*` absorbs any characters). The
# reject gates run first. They drop any REF that carries a character outside
# the strict `v`/digit/dot set (a trailing newline included), a `v` after the
# first character, or a third dot. The shape gate then requires a leading `v`,
# two dots, and a digit at the start of each component, so it accepts exactly
# what the update.ps1 regex matches with case respected.
is_release_tag() {
    case "$1" in
        # Reject anything containing a character outside [v0-9.]; this drops
        # the `-rc1` suffix (hyphen/letters) and the stray `x` in v1x.2.3.
        *[!v0-9.]*) return 1 ;;
        # Reject a `v` after the first character (v1.2.3v) and a third dot
        # (v1.2.3.4, v1..2.3, v1.2.3.); the shape glob's `*` absorbs both.
        ?*v* | *.*.*.*) return 1 ;;
    esac
    case "$1" in
        v[0-9]*.[0-9]*.[0-9]*) return 0 ;;
        *) return 1 ;;
    esac
}

bold "Apothem updater"
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
    # The prefix-strip test is the one find-python.sh uses; update.ps1
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
[ -n "$PY" ] || die "No Python >= 3.10 found in PATH"
settle_python_form

# The current folder must never shadow the engine's modules: `-c` puts ''
# first on sys.path and `-m` puts the working directory there, so a
# `click.py`, `rich/` or `apothem/` in the folder this runs from would run
# instead of the real package. `-P` / PYTHONSAFEPATH does not exist on
# Python 3.10 and `-I` would drop PYTHONPATH and the user site, so every such
# start sets PYTHONSAFEPATH=1 and runs a `-c` program that first drops a
# leading ''. Only sys.path changes; the working directory does not.
DROP_CWD_FROM_PATH="import sys; sys.path[:1] = [] if sys.path[:1] == [''] else sys.path[:1]"
ENGINE_PROGRAM="${DROP_CWD_FROM_PATH}; import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"
PIP_PROGRAM="${DROP_CWD_FROM_PATH}; import runpy; runpy.run_module('pip', run_name='__main__', alter_sys=True)"

# CLI prerequisite check (robust probe; offers to install the missing deps).
probe_missing_deps() {
    _missing=""
    for _dep in $RUNTIME_DEPS; do
        PYTHONSAFEPATH=1 "$PY" -c "${DROP_CWD_FROM_PATH}; import ${_dep}" >/dev/null 2>&1 || _missing="${_missing:+$_missing }${_dep}"
    done
    printf '%s' "$_missing"
}

install_runtime_deps() {
    if ! PYTHONSAFEPATH=1 "$PY" -c "$PIP_PROGRAM" --version >/dev/null 2>&1; then
        warn "pip is unavailable under $PY - install $* manually."
        return 1
    fi
    info "Installing $* under $PY (pip)"
    if PYTHONSAFEPATH=1 "$PY" -c "$PIP_PROGRAM" install "$@"; then
        ok "Installed $*"
        return 0
    fi
    warn "pip install failed - install $* manually."
    return 1
}

MISSING_DEPS="$(probe_missing_deps)"
if [ -n "$MISSING_DEPS" ]; then
    warn "Missing Python prerequisites under $PY: ${MISSING_DEPS}"
    _do_install=0
    if [ "${APOTHEM_AUTO_INSTALL_DEPS:-0}" = "1" ]; then
        _do_install=1
    elif [ -t 0 ]; then
        printf '  Install %s under %s now? [y/N] ' "$MISSING_DEPS" "$PY"
        read -r _answer || _answer=""
        case "$_answer" in y | Y | yes | YES) _do_install=1 ;; esac
    fi
    if [ "$_do_install" = "1" ]; then
        # shellcheck disable=SC2086
        if install_runtime_deps $MISSING_DEPS; then
            MISSING_DEPS="$(probe_missing_deps)"
        fi
    fi
fi
if [ -n "$MISSING_DEPS" ]; then
    die "Missing prerequisites under $PY: ${MISSING_DEPS}. Install with: '$PY' -m pip install ${MISSING_DEPS} - or set APOTHEM_AUTO_INSTALL_DEPS=1 to install automatically. See ${VENDORING_DOC}."
fi

# Locate or fetch the source.
bold "Updating Apothem source"
SOURCE=""
if [ -n "${APOTHEM_SOURCE:-}" ]; then
    SOURCE="$(cd "$APOTHEM_SOURCE" 2>/dev/null && pwd || true)"
    [ -n "$SOURCE" ] && is_apothem_source "$SOURCE" \
        || die "APOTHEM_SOURCE is not an apothem source tree: ${APOTHEM_SOURCE}"
    ok "Using explicit source: $SOURCE"
    info "Local source — skipping tag resolution and signature verification"
elif { [ -e "$APOTHEM_HOME/.git" ] || [ -L "$APOTHEM_HOME/.git" ]; } && is_apothem_source "$APOTHEM_HOME"; then
    # A .git file (a worktree, or a clone made with --separate-git-dir) is a
    # clone too. A clone of anything but an Apothem source is not updated.
    command -v git >/dev/null 2>&1 || die "git not found in PATH"

    # Resolve the ref to update to. An unset APOTHEM_REF defaults to the latest
    # release tag (verified-by-default) rather than the moving `main` branch.
    if [ -z "$APOTHEM_REF" ]; then
        info "Resolving latest release tag from ${APOTHEM_REPO}"
        APOTHEM_REF="$(resolve_latest_tag "$APOTHEM_REPO")"
        if [ -z "$APOTHEM_REF" ]; then
            die "No vMAJOR.MINOR.PATCH release tag found at ${APOTHEM_REPO}. Pin a ref explicitly with APOTHEM_REF=<tag|main>."
        fi
        ok "Latest release tag: ${APOTHEM_REF}"
    fi
    if is_release_tag "$APOTHEM_REF" && [ "$APOTHEM_ALLOW_UNVERIFIED" != "1" ]; then
        # Release tags carry OpenPGP signatures whatever gpg.format says; git
        # runs gpg.openpgp.program for them, else gpg.program, else gpg.
        _gpg_prog="$(ngit config --get gpg.openpgp.program 2>/dev/null || true)"
        [ -n "$_gpg_prog" ] || _gpg_prog="$(ngit config --get gpg.program 2>/dev/null || true)"
        command -v "${_gpg_prog:-gpg}" >/dev/null 2>&1 \
            || die "gpg not found in PATH — needed to check the ${APOTHEM_REF} release tag's signature against the maintainer key. Install GnuPG (https://gnupg.org/download/), then re-run."
    fi

    # Fetch, check the tag, and only then check it out, so a failed check
    # leaves the clone where it was (mirrors install.sh).
    info "Updating clone at $APOTHEM_HOME (ref: ${APOTHEM_REF})"
    # Every git call on the clone from here runs with its hooks off; the
    # empty hooks folder goes on every way out.
    trap 'if [ -n "$HOOKS_OFF" ]; then rm -rf "$HOOKS_OFF"; fi' EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 131' QUIT
    trap 'exit 141' PIPE
    trap 'exit 143' TERM
    HOOKS_OFF="$(mktemp -d)" || die "Could not create a scratch directory for the update"
    check_clone_setup "$APOTHEM_HOME"
    cgit -C "$APOTHEM_HOME" fetch --quiet --tags origin \
        || die "Could not fetch from the origin of $APOTHEM_HOME. If a local tag differs from origin's, delete it with 'git -C $APOTHEM_HOME tag -d <tag>', then re-run."

    bold "Verifying source signature"
    if is_release_tag "$APOTHEM_REF"; then
        if verify_tag "$APOTHEM_HOME" "refs/tags/${APOTHEM_REF}" && verify_tag_by_maintainer; then
            # The signed tag object must name itself APOTHEM_REF: a signed tag
            # for another release, re-pointed here, would roll the update back.
            cgit -C "$APOTHEM_HOME" cat-file tag "refs/tags/${APOTHEM_REF}" 2>/dev/null | awk -v want="$APOTHEM_REF" '
                /^$/ { exit }
                $1 == "type" { type = $0 }
                $1 == "tag" { name = $0 }
                END { exit (type == "type commit" && name == "tag " want) ? 0 : 1 }' \
                || die "Tag ${APOTHEM_REF} carries the maintainer key's signature, but the signed tag object is not the ${APOTHEM_REF} release tag (it names another tag, or no commit), so it was re-pointed (possible tampering). Aborting before anything is checked out or re-materialized."
            ok "Tag ${APOTHEM_REF} carries a valid signature from the maintainer key ${MAINTAINER_FINGERPRINT}"
        elif [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Tag ${APOTHEM_REF} is unsigned, its signature did not verify, or the maintainer key did not make it — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        elif verify_tag_valid_other_key; then
            die "Tag ${APOTHEM_REF} carries a valid signature, but not from the maintainer key ${MAINTAINER_FINGERPRINT} that SECURITY.md publishes (possible tampering). Aborting before anything is checked out or re-materialized."
        elif verify_tag_missing_key; then
            die "Tag ${APOTHEM_REF} is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import', check that 'gpg --fingerprint 70396FED9C634163' shows the fingerprint published in SECURITY.md, then re-run this updater."
        else
            die "Tag ${APOTHEM_REF} is unsigned or its signature did not verify (possible tampering). Aborting before anything is checked out or re-materialized."
        fi
        # refs/tags/<tag>^{commit} can only mean the tag, never a branch that
        # shares its name or is literally named refs/tags/<tag>; HEAD must
        # then be the tag's commit. Changes to tracked files stop the update
        # first, and there is no --force, so other local changes the checkout
        # would overwrite stop it instead of being lost.
        { cgit -C "$APOTHEM_HOME" diff --quiet HEAD && cgit -C "$APOTHEM_HOME" diff --cached --quiet; } \
            || die "$APOTHEM_HOME has changes to tracked files. Commit or stash them, then re-run."
        cgit -C "$APOTHEM_HOME" checkout --quiet --detach "refs/tags/${APOTHEM_REF}^{commit}" \
            || die "Could not check out the ${APOTHEM_REF} tag in $APOTHEM_HOME. If it has local changes, commit or stash them, then re-run."
        _co_head="$(cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet HEAD || true)"
        _co_tag="$(cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet "refs/tags/${APOTHEM_REF}^{commit}" || true)"
        if [ -z "$_co_tag" ] || [ "$_co_head" != "$_co_tag" ]; then
            die "The checkout in $APOTHEM_HOME is at '${_co_head}', not at the ${APOTHEM_REF} tag's commit '${_co_tag}'. Aborting before re-materialization."
        fi
    else
        if [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Ref ${APOTHEM_REF} is not a signed release tag — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        else
            die "Ref ${APOTHEM_REF} is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
        fi
        { cgit -C "$APOTHEM_HOME" diff --quiet HEAD && cgit -C "$APOTHEM_HOME" diff --cached --quiet; } \
            || die "$APOTHEM_HOME has changes to tracked files. Commit or stash them, then re-run."
        # What origin has for the ref comes first, so a stale local branch
        # of the same name cannot stand in for it; otherwise the ref is taken
        # as given (a commit, or a branch only the clone has).
        if cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet "refs/remotes/origin/${APOTHEM_REF}" >/dev/null 2>&1; then
            cgit -C "$APOTHEM_HOME" checkout --quiet --detach "refs/remotes/origin/${APOTHEM_REF}" \
                || die "Could not check out ${APOTHEM_REF} in $APOTHEM_HOME. If it has local changes, commit or stash them, then re-run."
        else
            cgit -C "$APOTHEM_HOME" checkout --quiet --end-of-options "$APOTHEM_REF" \
                || die "Could not check out ${APOTHEM_REF} in $APOTHEM_HOME. If it has local changes, commit or stash them, then re-run."
        fi
    fi
    _co_status="$(cgit -C "$APOTHEM_HOME" status --porcelain --untracked-files=no 2>/dev/null)" || _co_status="unreadable"
    [ -z "$_co_status" ] \
        || die "The checkout in $APOTHEM_HOME does not match ${APOTHEM_REF} after the update. Aborting before re-materialization."
    SOURCE="$APOTHEM_HOME"
    is_apothem_source "$SOURCE" || die "Updated tree is not an apothem source: $SOURCE"
    ok "Source updated at $SOURCE (ref: ${APOTHEM_REF})"
    echo
elif is_apothem_source "$APOTHEM_HOME"; then
    die "$APOTHEM_HOME was installed from a release archive, which has no git clone to update. Re-run install.sh with cosign and gpg on PATH to update it to the latest verified release."
else
    die "No source found at $APOTHEM_HOME — run install.sh first or set APOTHEM_SOURCE"
fi
# Absolute, so no PYTHONPATH entry below can name the current folder.
SRC_PATH="$(abs_path "${SOURCE}/src")"
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
_ep_vendor="$(native_path "${SRC_PATH}/apothem/_vendor")" \
    || die "cygpath could not convert ${SRC_PATH}/apothem/_vendor to a Windows path"
_ep_src="$(native_path "${SRC_PATH}")" \
    || die "cygpath could not convert ${SRC_PATH} to a Windows path"
ENGINE_PYPATH="${_ep_vendor}${PY_PATHSEP}${_ep_src}"
echo

bold "Re-materializing harness: ${HARNESS}"
[ -f "$PROFILE" ] || die "Profile not found at $PROFILE — run install.sh first or set APOTHEM_PROFILE"
PYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" \
    "$PY" -c "$ENGINE_PROGRAM" update --harness "$HARNESS" --profile "$PROFILE"
ok "Harness ${HARNESS} updated"
echo

bold "Update complete."
