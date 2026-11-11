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
# local changes it would overwrite stop it too instead of being lost. The
# tag is checked out by the commit recorded when it was checked, so a tag
# moved after the check cannot change what is installed.
# Before anything is fetched, the update also stops when git will not work
# in the clone because another user owns it, when the clone's own git
# settings (in its config or config.worktree) hold any setting that is not
# on the short list install.sh keeps (CLONE_CONFIG_ALLOW: what git clone and
# git init write there, plus branch settings, user.name, user.email,
# maintenance.auto, maintenance.strategy, pull.rebase and pull.ff), when its
# info/attributes sets a filter, when the clone holds a submodule, when it
# hides changes from git (files marked assume-unchanged or skip-worktree),
# or when its work tree is not APOTHEM_HOME. Every git command on the clone
# runs with its hooks, its fsmonitor, its pager and git's automatic
# maintenance off, with no ext:: transport, and without looking inside
# nested repositories.
# Only one install, update or uninstall runs at a time: each holds the lock
# folder <APOTHEM_HOME>.lock while it runs. Only a clone of an Apothem
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
# objects through replace refs, take extra configuration or read its
# configuration from other files, or run its helper programs and templates
# from elsewhere (mirrors install.sh). git still reads the user's own global
# and system configuration from the places it always looks.
# GIT_CONFIG_NOSYSTEM stays as the caller set it: it only makes git skip
# the system configuration.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE \
    GIT_REPLACE_REF_BASE GIT_CEILING_DIRECTORIES GIT_CONFIG_PARAMETERS \
    GIT_CONFIG_COUNT GIT_EXEC_PATH GIT_TEMPLATE_DIR GIT_CONFIG \
    GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM
# No replace refs, no lazy fetch of a missing object (a fetch the clone's
# config shapes), only these transports whatever the caller set.
GIT_NO_REPLACE_OBJECTS=1
GIT_NO_LAZY_FETCH=1
GIT_ALLOW_PROTOCOL=file:git:http:https:ssh
export GIT_NO_REPLACE_OBJECTS GIT_NO_LAZY_FETCH GIT_ALLOW_PROTOCOL

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

# cgit ARGS — run git with ARGS on the clone, with its fsmonitor program
# and pager off, no automatic maintenance, only the file, git, http, https
# and ssh transports (so no ext:: or other remote helper program), no
# recursion into submodules, no git status run inside a nested repository,
# paths longer than Windows' usual limit allowed (Git for Windows), and,
# once HOOKS_OFF names an empty folder, with core.hooksPath pointing at it,
# so none of the clone's hook scripts run (mirrors install.sh).
HOOKS_OFF=""
cgit() {
    if [ -n "$HOOKS_OFF" ]; then
        git --no-pager -c core.fsmonitor= -c protocol.ext.allow=never \
            -c protocol.allow=never -c protocol.file.allow=always \
            -c protocol.git.allow=always -c protocol.http.allow=always \
            -c protocol.https.allow=always -c protocol.ssh.allow=always \
            -c submodule.recurse=false -c fetch.recurseSubmodules=false \
            -c diff.ignoreSubmodules=all -c gc.auto=0 -c maintenance.auto=false \
            -c core.longpaths=true -c core.hooksPath="$HOOKS_OFF" "$@"
    else
        git --no-pager -c core.fsmonitor= -c protocol.ext.allow=never \
            -c protocol.allow=never -c protocol.file.allow=always \
            -c protocol.git.allow=always -c protocol.http.allow=always \
            -c protocol.https.allow=always -c protocol.ssh.allow=always \
            -c submodule.recurse=false -c fetch.recurseSubmodules=false \
            -c diff.ignoreSubmodules=all -c gc.auto=0 -c maintenance.auto=false \
            -c core.longpaths=true "$@"
    fi
}

# exists PATH — return 0 when PATH is there, a dangling symbolic link included.
exists() {
    [ -e "$1" ] || [ -L "$1" ]
}

# The install lock, <APOTHEM_HOME>.lock, held for the whole run; see
# install.sh's take_lock. on_exit removes it on every way out of the run.
LOCK_DIR=""
LOCK_HELD=0
take_lock() {
    _tl_home="$APOTHEM_HOME"
    if [ -L "$APOTHEM_HOME" ] && _tl_real="$(cd -P -- "$APOTHEM_HOME" 2>/dev/null && pwd -P)"; then
        _tl_home="$_tl_real"
    fi
    LOCK_DIR="${_tl_home}.lock"
    _tl_parent="$(dirname -- "$_tl_home")"
    # With no folder to hold APOTHEM_HOME there is nothing to update, and the
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

# on_exit — the EXIT trap from the moment the lock is taken: removes the
# empty hooks folder, then lets the lock go.
on_exit() {
    if [ -n "$HOOKS_OFF" ]; then rm -rf "$HOOKS_OFF"; fi
    release_lock
}

VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(cgit -C "$1" verify-tag --raw "$2" 2>&1)"
}

# clone_git_ok, git_path and the checks below them (the clone config
# allow-list, check_clone_config, check_clone_modules, check_clone_gitlinks
# and check_clone_setup) mirror install.sh, whose comments give the
# reasons: the checks run on an existing clone before the fetch, and the
# settings and attributes check runs before any git command that reads the
# clone's index or could run one of its programs.
clone_git_ok() {
    if _cg_err="$(LC_ALL=C; export LC_ALL; cgit -C "$1" rev-parse --git-dir 2>&1 >/dev/null)"; then
        return 0
    fi
    case "$_cg_err" in
        *"dubious ownership"*)
            die "$1 is owned by someone else, so git refuses to work in it (git reports \"dubious ownership\"). Run this as the user who owns $1, take ownership of it, or point APOTHEM_HOME at a folder you own, then re-run." ;;
    esac
    die "git could not read the clone at $1 ($(printf '%s\n' "$_cg_err" | sed -n '1p')). Repair it or move it aside, then re-run."
}

git_path() {
    _gp_path="$(cgit -C "$1" rev-parse --git-path "$2" 2>/dev/null)" || return 1
    [ -n "$_gp_path" ] || return 1
    case "$_gp_path" in
        /* | [A-Za-z]:[\\/]*) printf '%s\n' "$_gp_path" ;;
        *) printf '%s/%s\n' "$1" "$_gp_path" ;;
    esac
}

# The settings a clone's own git config (.git/config, and .git/config.worktree
# when there is one) may hold for an update in place to go ahead: the ones
# git clone and git init write there for a full clone (any git 2.x, any
# platform, sha1 or sha256, files or reftable refs, --no-tags,
# --single-branch, --depth; no partial-clone or promisor setting, since a
# lazy fetch of a missing object runs a fetch the clone's settings would
# shape), branch settings, which tools such as editors add, the user's
# name and email, the two maintenance settings `git maintenance register`
# writes, and the two pull settings git pull's own hint suggests. None of
# them names a program for git to run, a file or folder git reads settings,
# hooks, attributes or objects from, a URL rewrite, or another work tree or
# git folder. remote.origin.url names the address the update fetches from (a
# file in the git folder's remotes or branches folder can name an address
# too, which gives no more than that setting does). An address can name a
# transport whose helper git runs (<name>::...), so cgit allows only the
# file, git, http, https and ssh transports, and the release tag check
# decides what is checked out.
# Any other setting stops the update. Section and key compare without regard
# to case; the part between them (branch.<name>.merge) compares exactly, and
# `*` there stands for any name that is not empty, as `*` as the key stands
# for any key. install.sh, update.sh, install.ps1 and update.ps1 hold the
# same list (tests/scripts/test_installer_parity.py compares them).
# clone-config-allow-list begin
CLONE_CONFIG_ALLOW='core.repositoryformatversion
core.filemode
core.bare
core.logallrefupdates
core.symlinks
core.ignorecase
core.precomposeunicode
core.longpaths
extensions.objectformat
extensions.refstorage
extensions.worktreeconfig
remote.origin.url
remote.origin.fetch
remote.origin.tagopt
branch.*.*
user.name
user.email
maintenance.auto
maintenance.strategy
pull.rebase
pull.ff'
# clone-config-allow-list end

# unallowed_config_key [REFUSE] — read git setting names, one per line, as
# `git config --name-only --list` prints them, and print the first one that
# CLONE_CONFIG_ALLOW does not hold, or that is a line of REFUSE (byte for
# byte). The section is the text before the first dot, the key the text
# after the last dot, the subsection whatever lies between; a name with an
# empty section or key matches nothing. A two-part entry (user.name) matches
# only a name with no subsection, a three-part entry only a name with one.
unallowed_config_key() {
    # LC_ALL=C: bytes, as git compares (macOS awk collates in UTF-8).
    LC_ALL=C CLONE_CONFIG_ALLOW="$CLONE_CONFIG_ALLOW" CLONE_CONFIG_REFUSE="${1:-}" awk '
        function split_name(name, parts,    first, rest, i, last) {
            first = index(name, ".")
            if (first == 0) return 0
            parts["sec"] = tolower(substr(name, 1, first - 1))
            rest = substr(name, first + 1)
            last = 0
            for (i = length(rest); i > 0; i--) {
                if (substr(rest, i, 1) == ".") { last = i; break }
            }
            if (last == 0) {
                parts["has"] = 0
                parts["sub"] = ""
                parts["key"] = tolower(rest)
            } else {
                parts["has"] = 1
                parts["sub"] = substr(rest, 1, last - 1)
                parts["key"] = tolower(substr(rest, last + 1))
            }
            return 1
        }
        BEGIN {
            n = split(ENVIRON["CLONE_CONFIG_ALLOW"], allow, "\n")
            m = split(ENVIRON["CLONE_CONFIG_REFUSE"], names, "\n")
            for (j = 1; j <= m; j++) if (names[j] != "") refuse[names[j]] = 1
        }
        $0 == "" { next }
        {
            if (!split_name($0, got) || got["sec"] == "" || got["key"] == "") { print; exit }
            if ($0 in refuse) { print; exit }
            ok = 0
            for (j = 1; j <= n && !ok; j++) {
                if (allow[j] == "" || !split_name(allow[j], want)) continue
                if (want["sec"] != got["sec"] || want["has"] != got["has"]) continue
                if (want["key"] != "*" && want["key"] != got["key"]) continue
                if (want["has"]) {
                    if (want["sub"] == "*") { if (got["sub"] == "") continue }
                    else if (want["sub"] != got["sub"]) continue
                }
                ok = 1
            }
            if (!ok) { print; exit }
        }'
}

# config_file_problem DIR FILE — print the first setting, in file order, in
# config file FILE of the clone at DIR that an update does not accept: one
# unallowed_config_key reports, extensions.refstorage other than files or
# reftable (a later git reads refs from a folder it names), or
# branch.<name>.remote or .pushremote other than origin. Values are read
# NUL-ended, CR kept (a line break or CR in one fails). Die when FILE cannot be
# read, or a name holds a line break (a CR in a quoted subsection, which
# PowerShell would read as two names).
config_file_problem() {
    _cp_keys="$(cgit -C "$1" config --file "$2" --name-only --list 2>/dev/null)" \
        || die "Could not read the git config of $1 at ${2}."
    if printf '%s\n' "$_cp_keys" | LC_ALL=C awk 'index($0, "\r") { f = 1; exit } END { exit f ? 0 : 1 }'; then
        die "$1's own git config has a setting whose name holds a line break, which an update in place does not accept. Remove it from ${2}, then re-run."
    fi
    _cp_refuse="$(cgit -C "$1" config --file "$2" --null --list 2>/dev/null \
        | LC_ALL=C tr '\000\n\r' '\n\001\002' | LC_ALL=C awk '{
            sep = index($0, "\001")
            name = sep ? substr($0, 1, sep - 1) : $0
            value = sep ? substr($0, sep + 1) : ""
            low = tolower(name)
            if (low == "extensions.refstorage") {
                if (!sep || (value != "files" && value != "reftable")) print name
            } else if (low ~ /^branch\..+\.(push)?remote$/ && (!sep || value != "origin")) print name
        }')"
    printf '%s\n' "$_cp_keys" | unallowed_config_key "$_cp_refuse"
}

# need_plain_file DIR FILE — die when FILE, in DIR's git folder, exists or
# is a link but is not a plain file: from a pipe git could read other text
# than the check read.
need_plain_file() {
    if { [ -e "$2" ] || [ -L "$2" ]; } && [ ! -f "$2" ]; then
        die "$1's git folder holds ${2}, which is not a plain file, so git could read other text from it than this check reads. Make it a plain file or remove it, then re-run."
    fi
}

# sets_filter — succeed when the git attributes text on stdin sets a filter
# outside comments. NUL bytes are dropped (grep would call the text binary
# while git reads the lines around them), and a line is a comment only
# where # follows nothing but spaces, tabs and CR, as git reads it.
sets_filter() {
    _sf_blank="$(printf ' \t\r')"
    LC_ALL=C tr -d '\000' 2>/dev/null | LC_ALL=C grep -v "^[${_sf_blank}]*#" | LC_ALL=C grep -q 'filter='
}

# check_clone_config DIR — die when the clone at DIR has a setting of its
# own an update does not accept (config, then config.worktree; no
# include.path is followed), borrows objects from another repository
# (alternates), or its info/attributes sets a filter, or when one of those
# files is not a plain file. This runs before any git command that reads
# the clone's index or objects or could run one of its programs.
check_clone_config() {
    _cc_key=""
    for _cc_name in config config.worktree; do
        _cc_file="$(git_path "$1" "$_cc_name")" || die "Could not read the git config of $1."
        need_plain_file "$1" "$_cc_file"
        if [ -e "$_cc_file" ]; then
            _cc_key="$(config_file_problem "$1" "$_cc_file")" || exit 1
            [ -z "$_cc_key" ] || break
        fi
    done
    if [ -n "$_cc_key" ]; then
        die "$1's own git config sets ${_cc_key}, which an update in place does not accept in a clone's own config. Remove it from ${_cc_file}, then re-run."
    fi
    for _cc_name in objects/info/alternates objects/info/http-alternates; do
        _cc_file="$(git_path "$1" "$_cc_name")" || die "Could not read the git config of $1."
        if [ -e "$_cc_file" ]; then
            die "$1 borrows objects from another repository (${_cc_file} names it). A release clone does not, and the update would run git in that repository under settings nothing here checks. Run 'git -C $1 repack -a -d' to copy the objects in, remove ${_cc_file}, then re-run."
        fi
    done
    _cc_file="$(git_path "$1" info/attributes)" || die "Could not read the git config of $1."
    need_plain_file "$1" "$_cc_file"
    if [ -f "$_cc_file" ] && sets_filter < "$_cc_file"; then
        die "$1's own git attributes set a filter (filter=), which the update would trust. Remove it from ${_cc_file}, then re-run."
    fi
}

# check_clone_modules DIR — die when the clone at DIR keeps submodule
# repositories (its git folder's modules), where git would run under
# settings nothing here checks. Reads no index.
check_clone_modules() {
    _sm_dir="$(git_path "$1" modules)" || die "Could not read the git config of $1."
    if [ -d "$_sm_dir" ]; then
        die "$1 keeps submodule repositories in ${_sm_dir}. A release tree has no submodules, and the update would run git inside them. Remove the submodules and ${_sm_dir}, then re-run."
    fi
}

# check_clone_gitlinks DIR — die when the clone's index records a git
# repository in its tree (a gitlink, mode 160000), which git diff and git
# status would run git inside. A release tree has none.
check_clone_gitlinks() {
    _sm_list="$(cgit -C "$1" ls-files -s 2>/dev/null)" \
        || die "$1 has changes to tracked files. Commit or stash them, then re-run."
    _sm_path="$(printf '%s\n' "$_sm_list" | LC_ALL=C awk '$1 == "160000" { sub(/^[^\t]*\t/, ""); print; exit }')"
    if [ -n "$_sm_path" ]; then
        die "$1 holds a submodule at ${_sm_path} (its index records a git repository there). A release tree has none, and the update would run git inside it. Remove the submodule from the clone, then re-run."
    fi
}

# git_z DIR ARGS... — print git ARGS' NUL-ended records in the clone at
# DIR one per line (a line break in one turns into byte 001); die when git
# fails, which a "<001>!" line after its output marks.
git_z() {
    _gz_dir="$1"
    shift
    _gz_out="$( { cgit -C "$_gz_dir" "$@" 2>/dev/null || printf '\000\001!\000'; } | LC_ALL=C tr '\000\n' '\n\001')"
    case "
${_gz_out}
" in
        *"
$(printf '\001!')
"*) die "$_gz_dir has changes to tracked files. Commit or stash them, then re-run." ;;
    esac
    printf '%s\n' "$_gz_out"
}

# check_clone_attributes DIR — die when the clone's work tree has a
# .gitattributes (any case) git does not track, a tracked one that is not
# a plain file matching the index and HEAD, or one whose index copy sets a
# filter: git status, diff and checkout would apply it (it can name a
# filter of the user's own). Compares without filters. Leaves the
# untracked list in _ca_other.
check_clone_attributes() {
    _ca_index="$(git_z "$1" ls-files -s -z)" || exit 1
    _ca_head="$(git_z "$1" ls-tree -r -z HEAD)" || exit 1
    _ca_other="$(git_z "$1" ls-files -o -z)" || exit 1
    # HEAD's entries, "=", the index's: out come C<TAB>-<TAB>PATH (changed)
    # and H<TAB>OID<TAB>PATH (to compare).
    _ca_found="$(printf '%s\n=\n%s\n' "$_ca_head" "$_ca_index" | LC_ALL=C awk '
        $0 == "=" { in_index = 1; next }
        { tab = index($0, "\t") }
        tab == 0 { next }
        {
            path = substr($0, tab + 1)
            leaf = path
            sub(/.*\//, "", leaf)
            if (tolower(leaf) != ".gitattributes") next
            split(substr($0, 1, tab - 1), f, " ")
        }
        !in_index { head[path] = f[1] " " f[3]; order[++n] = path; next }
        !(path in seen) {
            seen[path] = 1
            if (f[3] != "0" || head[path] != f[1] " " f[2] || index(path, "\001")) print "C\t-\t" path
            else print "H\t" f[2] "\t" path
        }
        END { for (i = 1; i <= n; i++) if (!(order[i] in seen)) print "C\t-\t" order[i] }')"
    _ca_tab="$(printf '\t')"
    printf '%s\n' "$_ca_found" | while IFS= read -r _ca_line; do
        [ -n "$_ca_line" ] || continue
        _ca_kind="${_ca_line%%"$_ca_tab"*}"
        _ca_line="${_ca_line#*"$_ca_tab"}"
        _ca_oid="${_ca_line%%"$_ca_tab"*}"
        _ca_path="${_ca_line#*"$_ca_tab"}"
        if [ "$_ca_kind" = "C" ]; then
            :
        elif cgit -C "$1" cat-file blob "$_ca_oid" 2>/dev/null | sets_filter; then
            die "$1 has a .gitattributes file at $1/${_ca_path} that sets a filter (filter=). git would apply it while it reads the clone. Remove the filter and commit that change, then re-run."
        elif [ ! -e "$1/$_ca_path" ] && [ ! -L "$1/$_ca_path" ]; then
            continue
        elif [ ! -L "$1/$_ca_path" ] && [ -f "$1/$_ca_path" ] \
            && [ "$(cgit -C "$1" hash-object --no-filters -- "$_ca_path" 2>/dev/null)" = "$_ca_oid" ]; then
            continue
        fi
        die "$1 has a changed .gitattributes file at $1/${_ca_path}. git would apply it while it reads the clone. Undo the change, then re-run."
    done || exit 1
    _ca_path="$(printf '%s\n' "$_ca_other" | LC_ALL=C awk '{ leaf = $0; sub(/.*\//, "", leaf) } tolower(leaf) == ".gitattributes" { print; exit }')"
    if [ -n "$_ca_path" ]; then
        die "$1 has a .gitattributes file that git does not track, at $1/${_ca_path}. git would apply it while it reads the clone. Remove it, then re-run."
    fi
}

# check_clone_src DIR LIST — die, listing them, when the untracked LIST has
# paths under src/ (in any case: a file system that ignores case finds Src
# as src) other than files in __pycache__ folders (which
# remove_source_caches removes): the engine could load them.
check_clone_src() {
    _sr_found="$(printf '%s\n' "$2" | SR_HOME="$1" LC_ALL=C awk '
        tolower(substr($0, 1, 4)) != "src/" { next }
        {
            path = $0
            sub(/\/$/, "", path)
            n = split(path, part, "/")
            for (i = 1; i < n; i++) if (part[i] == "__pycache__") next
            if (++count <= 20) print "    " ENVIRON["SR_HOME"] "/" $0
        }
        END { if (count > 20) print "    and " (count - 20) " more" }')"
    [ -n "$_sr_found" ] || return 0
    printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$1 has files under src that git does not track, and the engine could load them:" >&2
    printf '%s\n' "$_sr_found" >&2
    printf '    %s\n' "Nothing was changed. Move these files out of $1/src, then re-run." >&2
    exit 1
}

# remove_source_caches DIR — remove every __pycache__ folder or link under
# DIR/src, so no bytecode the release did not make loads.
remove_source_caches() {
    [ ! -d "$1/src" ] || find "$1/src" -name __pycache__ \( -type d -o -type l \) -prune -exec rm -rf -- {} + \
        || die "Could not remove the Python cache folders (__pycache__) under $1/src. Remove them, then re-run."
}

# check_clone_setup DIR — die, before anything is fetched, when updating
# the clone at DIR in place would trust something the release does not
# hold: a clone git will not work in, settings, attributes or borrowed
# objects of its own (check_clone_config, before any git command that reads
# the index), submodules, a work tree other than DIR (core.worktree, or a
# .git pointing at another clone's), files git ignores changes to
# (assume-unchanged, skip-worktree), work-tree .gitattributes files, or
# untracked files under src. Every check only reads, so a dry run makes
# them too.
check_clone_setup() {
    clone_git_ok "$1"
    check_clone_config "$1"
    check_clone_modules "$1"
    # Ask git, not folder names: under Git Bash, git and pwd can spell one
    # folder differently (other capitals, or /tmp for the Windows temp).
    _cs_inside="$(cgit -C "$1" rev-parse --is-inside-work-tree 2>/dev/null || true)"
    _cs_prefix="$(cgit -C "$1" rev-parse --show-prefix 2>/dev/null)" || _cs_prefix="?"
    if [ "$_cs_inside" != "true" ] || [ -n "$_cs_prefix" ]; then
        die "$1 is not the work tree of its git clone (git finds no work tree there, as when its git config sets core.bare to true). Set core.bare to false, then re-run."
    fi
    check_clone_gitlinks "$1"
    _cs_flags="$(cgit -C "$1" ls-files -v 2>/dev/null)" \
        || die "$1 has changes to tracked files. Commit or stash them, then re-run."
    if printf '%s\n' "$_cs_flags" | LC_ALL=C awk '{ c = substr($0, 1, 1) } c ~ /[a-z]/ || c == "S" { found = 1; exit } END { exit found ? 0 : 1 }'; then
        die "$1 has changes to tracked files. Commit or stash them, then re-run."
    fi
    check_clone_attributes "$1"
    check_clone_src "$1" "$_ca_other"
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

# verify_tag_other_keys / other_key_message mirror install.sh: the message
# names the key (or keys) that signed the tag and the one that must.
verify_tag_other_keys() {
    printf '%s\n' "$VERIFY_TAG_OUTPUT" | awk -v want="$MAINTAINER_FINGERPRINT" '
        $1 == "[GNUPG:]" && $2 == "VALIDSIG" {
            fpr = toupper((NF >= 12) ? $12 : $3)
            if (fpr != want && !(fpr in seen)) {
                seen[fpr] = 1
                out = (out == "") ? fpr : out ", " fpr
            }
        }
        END { print out }'
}

other_key_message() {
    _om_keys="$(verify_tag_other_keys)"
    case "$_om_keys" in
        *", "*) _om_keys="the keys ${_om_keys}" ;;
        *) _om_keys="the key ${_om_keys}" ;;
    esac
    printf '%s' "Tag $1 is signed by ${_om_keys}. A release tag must be signed by the maintainer key ${MAINTAINER_FINGERPRINT} that SECURITY.md publishes, and by no other key (possible tampering). Aborting before anything is checked out or re-materialized."
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

# warn_home_access — warn, never stop, when other users can write to
# APOTHEM_HOME (a new one: by the umask) or the folder holding it. Git Bash,
# MSYS2 and Cygwin make mode bits up from Windows permissions, which the ps1
# scripts read instead.
warn_home_access() {
    _ha_os="$(uname -s 2>/dev/null)" || _ha_os=
    case "$_ha_os" in MINGW* | MSYS* | CYGWIN*) return 0 ;; esac
    _ha_d="$APOTHEM_HOME"
    if [ -L "$_ha_d" ]; then
        warn_writable "$(dirname -- "$_ha_d")" 1 "$_ha_d"
        [ -d "$_ha_d" ] || return 0
    fi
    if [ -d "$_ha_d" ]; then
        _ha_d="$(cd -P -- "$_ha_d" && pwd -P)" || return 0
    fi
    warn_writable "$_ha_d" 0 "$_ha_d"
    warn_writable "$(dirname -- "$_ha_d")" 1 "$_ha_d"
}

# warn_writable DIR KIND CHILD — KIND 0: warn when others can write to DIR.
# KIND 1: when they can replace CHILD in DIR (the sticky bit stops that; a
# missing DIR is skipped). A group named after you is your own group. stat
# gives the group's whole name; a new DIR takes the group of a setgid
# folder above it, and always on macOS and the BSDs.
warn_writable() {
    _ww_l=new _ww_f="$1"
    if [ -d "$1" ]; then
        _ww_l="$(ls -ldL -- "$1" 2>/dev/null)" || return 0
    elif [ "$2" = 1 ] || [ -e "$1" ]; then
        return 0
    else
        _ww_f="$(dirname -- "$1")"
        _ww_l="new $(ls -ldL -- "$_ww_f" 2>/dev/null)" || _ww_l=new
    fi
    _ww_g="$(stat -Lc %G -- "$_ww_f" 2>/dev/null || stat -Lf %Sg -- "$_ww_f" 2>/dev/null)" || _ww_g=
    _ww_w="$(printf '%s\n' "$_ww_l" | awk -v me="$(id -un 2>/dev/null)" -v g="$(id -gn 2>/dev/null)" -v p="$2" -v u="$(umask)" -v sg="$_ww_g" -v os="${_ha_os:-}" 'NR == 1 {
        m = $1
        if (m == "new") { m = "d----" (u ~ /[0145].$/ ? "w" : "-") "--" (u ~ /[0145]$/ ? "w" : "-") "-"; $4 = substr($2, 7, 1) ~ /[sS]/ || os ~ /Darwin|BSD/ ? (sg != "" ? sg : $5) : g }
        else if (sg != "") $4 = sg
        if (p && substr(m, 10, 1) ~ /[tT]/) exit
        if (substr(m, 9, 1) == "w") print "all users"
        else if (substr(m, 6, 1) == "w" && $4 != me) print "the group " $4
    }')" || return 0
    [ -n "$_ww_w" ] || return 0
    if [ "$2" = 1 ]; then
        warn "Other users can replace ${3}: $_ww_w can write to $1, the folder that holds it. To fix it, run chmod go-w \"$1\", or move APOTHEM_HOME."
    elif [ -d "$1" ]; then
        warn "Other users can change the code Apothem runs as you: $_ww_w can write to $1. To fix it, run chmod go-w \"$1\", or move APOTHEM_HOME."
    else
        warn "A new $1 would let $_ww_w change the code Apothem runs as you (umask $(umask)). To fix it, run umask 022, then run the installer again."
    fi
}

bold "Apothem updater"
echo

# One install, update or uninstall at a time on APOTHEM_HOME (see
# take_lock). on_exit, the EXIT trap from here on, lets the lock go, and
# each signal that ends the run exits through it.
trap on_exit EXIT
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
    # Every git call on the clone from here runs with its hooks off; on_exit
    # removes the empty hooks folder on every way out.
    HOOKS_OFF="$(mktemp -d)" || die "Could not create a scratch directory for the update"
    check_clone_setup "$APOTHEM_HOME"
    cgit -C "$APOTHEM_HOME" fetch --quiet --tags origin \
        || die "Could not fetch from the origin of $APOTHEM_HOME. If a local tag differs from origin's, delete it with 'git -C $APOTHEM_HOME tag -d <tag>', then re-run."

    bold "Verifying source signature"
    TAG_COMMIT=""
    if is_release_tag "$APOTHEM_REF"; then
        # The tag ref is read once: the signature, the signed tag object's
        # own name and the commit all come from that one tag object, and the
        # commit is then checked out by its ID, so a tag ref moved after the
        # check cannot change what is installed (mirrors install.sh).
        _tag_object="$(cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet "refs/tags/${APOTHEM_REF}" 2>/dev/null || true)"
        if [ -n "$_tag_object" ] && verify_tag "$APOTHEM_HOME" "$_tag_object" && verify_tag_by_maintainer; then
            # The signed tag object must name itself APOTHEM_REF: a signed tag
            # for another release, re-pointed here, would roll the update back.
            cgit -C "$APOTHEM_HOME" cat-file tag "$_tag_object" 2>/dev/null | awk -v want="$APOTHEM_REF" '
                /^$/ { exit }
                $1 == "type" { type = $0 }
                $1 == "tag" { name = $0 }
                END { exit (type == "type commit" && name == "tag " want) ? 0 : 1 }' \
                || die "Tag ${APOTHEM_REF} carries the maintainer key's signature, but the signed tag object is not the ${APOTHEM_REF} release tag (it names another tag, or no commit), so it was re-pointed (possible tampering). Aborting before anything is checked out or re-materialized."
            TAG_COMMIT="$(cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet "${_tag_object}^{commit}")" \
                || die "Could not read the commit the ${APOTHEM_REF} tag points at"
            ok "Tag ${APOTHEM_REF} carries a valid signature from the maintainer key ${MAINTAINER_FINGERPRINT}"
        elif [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            if [ -n "$_tag_object" ]; then
                TAG_COMMIT="$(cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet "${_tag_object}^{commit}" 2>/dev/null || true)"
            fi
            warn "Tag ${APOTHEM_REF} is unsigned, its signature did not verify, or the maintainer key did not make it — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        elif verify_tag_valid_other_key; then
            die "$(other_key_message "$APOTHEM_REF")"
        elif verify_tag_missing_key; then
            die "Tag ${APOTHEM_REF} is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import', check that 'gpg --fingerprint 70396FED9C634163' shows the fingerprint published in SECURITY.md, then re-run this updater."
        else
            die "Tag ${APOTHEM_REF} is unsigned or its signature did not verify (possible tampering). Aborting before anything is checked out or re-materialized."
        fi
        # The commit recorded above is checked out by its ID, so neither a
        # tag ref moved since nor a branch named like the tag can stand in
        # for it, and HEAD must then be that commit. Changes to tracked files
        # stop the update first, and there is no --force, so other local
        # changes the checkout would overwrite stop it instead of being lost.
        { cgit -C "$APOTHEM_HOME" diff --quiet HEAD && cgit -C "$APOTHEM_HOME" diff --cached --quiet; } \
            || die "$APOTHEM_HOME has changes to tracked files. Commit or stash them, then re-run."
        [ -n "$TAG_COMMIT" ] \
            || die "Could not check out the ${APOTHEM_REF} tag in $APOTHEM_HOME. If it has local changes, commit or stash them, then re-run."
        cgit -C "$APOTHEM_HOME" checkout --quiet --detach "$TAG_COMMIT" \
            || die "Could not check out the ${APOTHEM_REF} tag in $APOTHEM_HOME. If it has local changes, commit or stash them, then re-run."
        _co_head="$(cgit -C "$APOTHEM_HOME" rev-parse --verify --quiet HEAD || true)"
        if [ "$_co_head" != "$TAG_COMMIT" ]; then
            die "The checkout in $APOTHEM_HOME is at '${_co_head}', not at the ${APOTHEM_REF} tag's commit '${TAG_COMMIT}'. Aborting before re-materialization."
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
    remove_source_caches "$APOTHEM_HOME"
    SOURCE="$APOTHEM_HOME"
    is_apothem_source "$SOURCE" || die "Updated tree is not an apothem source: $SOURCE"
    ok "Source updated at $SOURCE (ref: ${APOTHEM_REF})"
    echo
elif is_apothem_source "$APOTHEM_HOME"; then
    die "$APOTHEM_HOME was installed from a release archive, which has no git clone to update. Re-run install.sh with cosign and gpg on PATH to update it to the latest verified release."
else
    die "No source found at $APOTHEM_HOME — run install.sh first or set APOTHEM_SOURCE"
fi
[ -n "${APOTHEM_SOURCE:-}" ] || warn_home_access
# Absolute, so no PYTHONPATH entry below can name the current folder.
SRC_PATH="$(abs_path "${SOURCE}/src")"
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
_ep_vendor="$(native_path "${SRC_PATH}/apothem/_vendor")" \
    || die "cygpath could not give the Windows path (a drive or network path) of ${SRC_PATH}/apothem/_vendor, which ${PY} needs. Check that cygpath works in this shell, or run update.ps1 from PowerShell instead."
_ep_src="$(native_path "${SRC_PATH}")" \
    || die "cygpath could not give the Windows path (a drive or network path) of ${SRC_PATH}, which ${PY} needs. Check that cygpath works in this shell, or run update.ps1 from PowerShell instead."
ENGINE_PYPATH="${_ep_vendor}${PY_PATHSEP}${_ep_src}"
echo

bold "Re-materializing harness: ${HARNESS}"
[ -f "$PROFILE" ] || die "Profile not found at $PROFILE — run install.sh first or set APOTHEM_PROFILE"
PYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" \
    "$PY" -c "$ENGINE_PROGRAM" update --harness "$HARNESS" --profile "$PROFILE"
ok "Harness ${HARNESS} updated"
echo

bold "Update complete."
