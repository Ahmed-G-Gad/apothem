#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Place the bundled Apothem source tree (self-contained, no package
#          installation) and materialize harness configuration by running
#          `python -m apothem` from that tree.
# Contract: Idempotent (a re-run fetches an existing clone, checks the tag,
#           then checks it out and re-materializes). Exits 0 on success,
#           non-zero on failure. POSIX sh only: the `curl … | sh` one-liner
#           runs under dash/ash on Debian/Ubuntu/Alpine.
#
# Trust model (tag-pinned, verified by default):
#   With no APOTHEM_REF, the latest vMAJOR.MINOR.PATCH tag is installed, not
#   the moving `main`. APOTHEM_VERIFY (default `auto`) picks the path:
#     - cosign on PATH ("release"): the tag must be signed by the maintainer
#       key and be the tag named for that release; cosign must show the
#       release workflow signed SHA256SUMS in a run on the tag's commit
#       (--certificate-github-workflow-sha; the installer does not read the
#       certificate itself); the platform archive's SHA-256 must match
#       SHA256SUMS. Needs git, gpg and cosign.
#     - no cosign ("signature"), or APOTHEM_HOME already a git clone: clone
#       or fetch, then `git verify-tag`. Needs git and gpg.
#   Either way the signature must be valid AND made by the maintainer key in
#   SECURITY.md (5C8998F9F241720445D3F28B70396FED9C634163); a key the local
#   keyring trusts is not enough. A signed tag object naming another release
#   is refused, even with APOTHEM_ALLOW_UNVERIFIED. A signed git tag names
#   its commit by SHA-1; the release path adds the SHA-256 cosign checks.
#   A failed check aborts before APOTHEM_HOME or any config changes. An
#   existing clone is fetched and its tag checked BEFORE checkout, so a
#   failed check leaves it as it was; local changes stop the update instead
#   of being lost. Otherwise the new source is built and checked beside
#   APOTHEM_HOME and swapped in only when every check passed.
#   Opt-outs:
#     - APOTHEM_REF=main (with APOTHEM_ALLOW_UNVERIFIED=1): the moving branch.
#     - APOTHEM_ALLOW_UNVERIFIED=1: on the clone path, an unsigned or
#       unverifiable tag, or one signed by another key, gives a warning and
#       proceeds (air-gapped or local use, or a release older than tag
#       signing); the re-pointed-tag check then protects only tags with the
#       maintainer key's signature. The release path never downgrades.
#     - APOTHEM_VERIFY=checksum (needs APOTHEM_ALLOW_UNVERIFIED=1) does not
#       verify the release: SHA256SUMS comes from the same release as the
#       archive, so a match only shows the download is not damaged.
#   APOTHEM_SOURCE (a local checkout) fetches and verifies nothing.
#
# What happens to APOTHEM_HOME when the install replaces it:
#   - An earlier install keeps everything outside its source tree (backups,
#     state, plans, memory and other engine data). A folder holding only
#     that data is kept the same way.
#   - A folder with no Apothem install is refused without --yes; with --yes
#     it moves, unchanged, into a new <APOTHEM_HOME>.before-apothem-<time>.
#   - A git clone is replaced by a release archive only with --yes, never
#     while it holds local work (changes, stashes, unpushed commits, or
#     untracked files in its source tree); its tree moves into a new
#     <APOTHEM_HOME>.before-apothem-<time>. A clone of anything else is any
#     other folder.
#   - Before an existing clone is fetched or replaced, its owner, its own git
#     settings (CLONE_CONFIG_ALLOW), attributes, borrowed objects,
#     submodules, hidden changes and untracked source files are checked
#     (check_clone_setup), in a dry run too; git runs on it with its hooks,
#     fsmonitor, pager and maintenance off (cgit), and lazy fetch is off
#     for the whole run.
#   - An entry to keep whose name has a space or another special character
#     stops the install. A symbolic link at APOTHEM_HOME is refused unless it
#     leads to an existing clone that is updated in place.
#   - A failure or an interrupt puts the earlier install back; a forced kill
#     can leave folders the next install reports (check_leftovers). One run
#     at a time holds the lock (take_lock).
#
# Usage:
#     curl -fsSL https://apothem.ahmedgad.com/install.sh | sh   # latest release
#     APOTHEM_REF=vMAJOR.MINOR.PATCH sh scripts/installer/install.sh  # pinned
#     sh scripts/installer/install.sh   # from a cloned checkout
#   To read the script first (the one-liner trusts it on first use; the
#   source it fetches is verified either way): curl -fsSL -o install.sh
#   https://apothem.ahmedgad.com/install.sh, read it, then sh install.sh.
#
# Flags (--clean/--fresh, --dry-run, --yes): see the --help text below.
#
# Environment:
#     APOTHEM_HOME             Source tree destination (default $HOME/.apothem)
#     APOTHEM_REPO             Git remote
#                              (default https://github.com/ahmed-g-gad/apothem)
#     APOTHEM_REF              Ref to check out; unset = the latest release tag.
#     APOTHEM_ALLOW_UNVERIFIED "1": see Opt-outs above.
#     APOTHEM_VERIFY           auto (default: release when cosign is on PATH
#                              and APOTHEM_HOME is not a git clone, else
#                              signature), release, signature or checksum (see
#                              Trust model).
#     APOTHEM_RELEASE_BASE     Release download base for the archive modes
#                              (default <APOTHEM_REPO>/releases/download).
#     APOTHEM_SOURCE           Local source tree to use (a checkout holding
#                              src/apothem); skips tag resolution and checks.
#     APOTHEM_HARNESS          Harness to install (default: claude-code)
#     APOTHEM_PROFILE          Path to shared profile YAML
#     APOTHEM_SKIP_VERIFY      If "1", skip post-install verify
#     APOTHEM_AUTO_INSTALL_DEPS If "1", install the missing click / rich
#                              prerequisites automatically (pip) without prompting.

set -eu

# git reads these from the environment and would then work on another
# repository, index or object store than the one each command names, swap
# objects through replace refs, take extra configuration or read its
# configuration from other files, or run its helper programs and templates
# from elsewhere; none of them may reach the installer's git commands. git
# still reads the user's own global and system configuration from the
# places it always looks, and git, gpg and cosign are the ones PATH finds.
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

# The caller's PYTHONPATH is set aside until the Python is chosen: the safe
# separator and path form depend on it (settle_python_form). Until then
# every Python started here runs with no PYTHONPATH.
# APOTHEM_CALLER_PYTHONPATH is a plain shell variable, never exported.
unset APOTHEM_CALLER_PYTHONPATH
APOTHEM_CALLER_PYTHONPATH="${PYTHONPATH:-}"
unset PYTHONPATH
PY_WINDOWS=""
PY_PATHSEP=""

# keep_full_pythonpath VALUE — print the full-path entries of the
# PYTHONPATH value VALUE, joined as the chosen Python splits them. Python
# reads an empty or relative entry (":/x", ".") as the current folder, ahead
# of site-packages, where a planted click.py would run. A POSIX Python
# (Cygwin's and MSYS2's python3 too) splits on ":" and keeps entries that
# start with "/"; a Windows Python splits on ";" and keeps drive paths
# ("C:\x", "C:/x") and network paths ("\\server\x", "//server/x"), so
# "\lib", "C:rel" and "/c/x" are dropped. Reads PY_WINDOWS.
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
# reads (a Windows Python splits on ";", a POSIX one, Cygwin's and MSYS2's
# too, on ":"; uname cannot tell them apart, and Windows paths read to a
# POSIX Python as relative entries), then export the caller's full-path
# entries in that form as PYTHONPATH (unset when none). The probe runs
# isolated (-I). Sets PY_WINDOWS (1 or 0) and PY_PATHSEP.
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
# A trailing "/" or "/." would make the link test and the renames beside
# APOTHEM_HOME act on the folder a link leads to, not on the link.
while [ "$APOTHEM_HOME" != "/" ]; do
    case "$APOTHEM_HOME" in
        */.) APOTHEM_HOME="${APOTHEM_HOME%/.}" ;;
        */) APOTHEM_HOME="${APOTHEM_HOME%/}" ;;
        *) break ;;
    esac
    [ -n "$APOTHEM_HOME" ] || APOTHEM_HOME="/"
done
APOTHEM_REPO="${APOTHEM_REPO:-https://github.com/ahmed-g-gad/apothem}"
# Empty default sentinel: an unset APOTHEM_REF means "resolve the latest
# released tag" (see resolve_latest_tag); an explicit value pins a tag or the
# moving `main` branch. The resolution happens after the helper definitions so
# the value is logged once resolved.
APOTHEM_REF="${APOTHEM_REF:-}"
APOTHEM_ALLOW_UNVERIFIED="${APOTHEM_ALLOW_UNVERIFIED:-0}"
APOTHEM_VERIFY="${APOTHEM_VERIFY:-auto}"
APOTHEM_RELEASE_BASE="${APOTHEM_RELEASE_BASE:-${APOTHEM_REPO}/releases/download}"
HARNESS="${APOTHEM_HARNESS:-claude-code}"
PROFILE="${APOTHEM_PROFILE:-$HOME/.config/apothem/profile.yaml}"

# The trust roots, fixed here rather than read from the environment so that
# nothing outside this script can widen them. MAINTAINER_FINGERPRINT is the
# primary-key fingerprint SECURITY.md publishes; a release tag must be signed
# by it. The cosign identity is the release workflow at the tag being
# installed, in the owner casing GitHub writes into the certificate.
MAINTAINER_FINGERPRINT="5C8998F9F241720445D3F28B70396FED9C634163"
COSIGN_IDENTITY_REPO="Ahmed-G-Gad/apothem"
COSIGN_OIDC_ISSUER="https://token.actions.githubusercontent.com"
COSIGN_INSTALL_DOC="https://docs.sigstore.dev/cosign/system_config/installation/"

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

# CLI flags (opt-in, pass-through to the engine) ----------------------------------
CLEAN=0
DRY_RUN=0
ASSUME_YES=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --clean|--fresh) CLEAN=1 ;;
        --dry-run)       DRY_RUN=1 ;;
        --yes)           ASSUME_YES=1 ;;
        -h|--help)
            cat <<'USAGE'
Apothem installer

Usage: install.sh [--clean|--fresh] [--dry-run] [--yes] [-h|--help]

  --clean, --fresh  Back up and remove the bounded config set, then
                    materialize fresh.
  --dry-run         Preview only; write nothing (the source is checked in
                    a temporary directory with the same refusals as a real
                    run; APOTHEM_HOME is not changed).
  --yes             Non-interactive; skip per-target confirmation prompts.
                    Also authorizes replacing an existing git clone with a
                    release archive, and moving a folder that holds no
                    Apothem install aside into
                    <APOTHEM_HOME>.before-apothem-<time>.
  -h, --help        Show this help and exit.

Trust model (default): resolves the latest vMAJOR.MINOR.PATCH release and
verifies it before materializing anything. The release tag must carry a
valid signature from the maintainer key in SECURITY.md (needs gpg), and the
signed tag must be the one named for that release. With cosign on PATH it
also has cosign show that the release workflow signed SHA256SUMS, and that
the certificate it verified was issued to a run on that tag's commit, and
installs the release archive once its SHA-256 matches; without cosign it
clones the release tag. An existing clone is fetched and its tag is checked
before the clone is checked out; changes to its tracked files stop the
update. Any check failing aborts the install before APOTHEM_HOME changes.

  # default — latest signed tag, verified:
  curl -fsSL https://apothem.ahmedgad.com/install.sh | sh
  # pin a known tag (also verified):
  APOTHEM_REF=vMAJOR.MINOR.PATCH sh install.sh

APOTHEM_HOME: an earlier Apothem install keeps everything that is not part
of its source tree (backups, state, plans, memory and other engine data), and
so does a folder that holds only that data. A folder that holds no Apothem
install is refused unless --yes is given. A git clone is replaced by a release
archive only with --yes, and never while it holds local work (changes,
stashes, unpushed commits, or untracked files in its source tree); its own
tree is then moved into <APOTHEM_HOME>.before-apothem-<time>. A clone of
anything other than Apothem counts as a folder with no Apothem install. An
existing clone is not updated or replaced when another user owns it, when
its own git config holds a setting outside the short list that git clone
and git init write there (plus branch, user name and email, maintenance
and pull settings), or when its info/attributes sets a filter; an update in
place also stops when it holds a submodule, hides changes from git, or has
no work tree that git can find. Its hooks, fsmonitor and pager never run
during the update. An entry to keep whose name has a space or another
special character stops the install until it is moved out. A symbolic link
at APOTHEM_HOME is refused, except when it leads to an existing clone that
is updated in place. A failure or an interrupt puts the earlier install back
unchanged; folders that a forced kill leaves beside APOTHEM_HOME stop the
next fetched install, which names them. One install, update or uninstall
runs at a time (the lock is <APOTHEM_HOME>.lock).

Overrides:
  APOTHEM_REF=main             check out the moving branch (needs
                               APOTHEM_ALLOW_UNVERIFIED=1; aborts otherwise).
  APOTHEM_ALLOW_UNVERIFIED=1   downgrade an unsigned or unverifiable tag, or
                               one signed by another key, on the clone path
                               to a warning (air-gapped or local use, or a
                               release that predates tag signing). It never
                               relaxes the release path or the check that
                               the signed tag names the release, but since
                               it lets such a tag through, that check
                               protects only tags that carry the maintainer
                               key's signature.
  APOTHEM_SOURCE=<path>        run a local checkout (fetches nothing; no
                               verification).
  APOTHEM_VERIFY=release       require the tag signature, the cosign check on
                               the tag's commit and the SHA-256 archive check
                               (fails when cosign is missing).
  APOTHEM_VERIFY=signature     always clone (or fetch) and check the tag
                               signature against the maintainer key.
  APOTHEM_VERIFY=checksum      needs APOTHEM_ALLOW_UNVERIFIED=1. Installs the
                               release archive after checking its SHA-256
                               against the release's SHA256SUMS. Checksum mode
                               does not verify the release. SHA256SUMS comes
                               from the same release as the archive, so a match
                               only shows the download isn't damaged; anyone
                               who can change the release's files can change
                               both.
USAGE
            exit 0
            ;;
        *)
            printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "Unknown argument: $1" >&2
            printf '  %s\n' "Run with --help for usage." >&2
            exit 1
            ;;
    esac
    shift
done

# CLI prerequisites the engine imports from the host interpreter. The
# self-contained runtime ships `yaml` + `jsonschema` vendored inside the
# bundled tree (src/apothem/_vendor); only click + rich must be importable
# under the chosen interpreter, and the check fails loud if either is missing.
RUNTIME_DEPS="click rich"
VENDORING_DOC="https://apothem.ahmedgad.com/docs/architecture/vendoring-strategy/"

# dep_spec NAME — the pip requirement spec for an import name. Mirrors
# [project.dependencies] in pyproject.toml (click is pinned exactly there;
# keep the two surfaces in lockstep) so the prerequisite install pulls the
# same constrained versions the engine is tested against, never a bare
# unconstrained "latest".
dep_spec() {
    case "$1" in
        click) printf 'click==8.4.2' ;;
        rich)  printf 'rich>=15.0.0' ;;
        *)     printf '%s' "$1" ;;
    esac
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

# abs_path PATH — print PATH made absolute against the current folder.
abs_path() {
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf '%s/%s\n' "$(pwd)" "$1" ;;
    esac
}

# ngit ARGS — run a git command that works on no clone of its own (ls-remote,
# clone, init, a global config read) from an empty folder made for it, with
# GIT_CEILING_DIRECTORIES at that folder's parent. Run from the current
# folder, git would read the config of a repository there or above it, and
# that config can make git run programs (an ext:: url rewrite,
# core.sshCommand). Every path argument must be absolute.
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

# sq TEXT — print TEXT as one single-quoted shell word.
sq() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

# resolve_latest_tag REPO — print the highest vMAJOR.MINOR.PATCH tag advertised
# by the remote, or nothing when the remote carries no release tag. Uses only
# POSIX tools (git ls-remote, sed, sort -t. -k -n) so the moving-branch default
# is replaced by a pinned-tag default without bashisms. Pure-numeric semver
# only — pre-release / build-metadata tags (v1.2.3-rc1) are intentionally
# excluded so the default never resolves to a non-final release.
resolve_latest_tag() {
    # git ls-remote --tags prints "<sha>\trefs/tags/<tag>" (and "<tag>^{}" for
    # dereferenced annotated tags). Keep only lines that are exactly an
    # object name, a tab and refs/tags/vN.N.N, strip the "^{}" peel suffix and
    # the "refs/tags/" prefix, dedupe, then sort by the three numeric
    # components and take the highest.
    _rlt_tab="$(printf '\t')"
    ngit ls-remote --tags "$1" 2>/dev/null \
        | sed -n "s#^[0-9a-f][0-9a-f]*${_rlt_tab}refs/tags/\(v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)\(\^{}\)\{0,1\}\$#\1#p" \
        | sort -u \
        | sort -t. -k1.2,1n -k2,2n -k3,3n \
        | tail -n 1
}

# cgit ARGS — run git with ARGS on a clone: no fsmonitor program, pager or
# automatic maintenance, only the file, git, http, https and ssh transports
# (no ext:: or git-remote-<name>), no recursion into submodules, and
# core.longpaths=true (Git for Windows: checkout past the usual path limit).
# Once HOOKS_OFF names an empty folder (an update in place), core.hooksPath
# points at it, so no hook of the clone's runs. core.sshCommand is left
# alone: it would override the user's own GIT_SSH.
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

# verify_tag DIR REF — run `git verify-tag --raw` on REF in DIR: 0 for a
# signed tag whose key the keyring trusts, non-zero for an unsigned,
# tampered or unknown-key one. GnuPG's status lines ("[GNUPG:] KEYWORD ...",
# never translated) go to VERIFY_TAG_OUTPUT, so callers can tell a missing
# public key from a bad or absent signature, and decide whether to abort or
# warn (APOTHEM_ALLOW_UNVERIFIED=1). Callers pass release tags only.
VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(cgit -C "$1" verify-tag --raw "$2" 2>&1)"
}

# verify_tag_by_maintainer — return 0 when the captured status lines carry at
# least one VALIDSIG line and every one names MAINTAINER_FINGERPRINT as its
# primary key. `git verify-tag` alone accepts any key in the local keyring.
# Field 12 is the primary key's fingerprint (field 3, the signing key's,
# stands in for keys too old to have one). Only lines that start with the
# status prefix count; GnuPG escapes newlines in user IDs.
verify_tag_by_maintainer() {
    printf '%s\n' "$VERIFY_TAG_OUTPUT" | awk -v want="$MAINTAINER_FINGERPRINT" '
        $1 == "[GNUPG:]" && $2 == "VALIDSIG" {
            seen++
            fpr = (NF >= 12) ? $12 : $3
            if (toupper(fpr) != want) other++
        }
        END { exit (seen > 0 && other == 0) ? 0 : 1 }'
}

# verify_tag_valid_other_key — return 0 when GnuPG reported a valid signature
# (a VALIDSIG line) that verify_tag_by_maintainer rejects: the signature is
# sound, but another key made it.
verify_tag_valid_other_key() {
    case "$VERIFY_TAG_OUTPUT" in
        "[GNUPG:] VALIDSIG "* | *"
[GNUPG:] VALIDSIG "*) ! verify_tag_by_maintainer ;;
        *) return 1 ;;
    esac
}

# verify_tag_other_keys — print the primary-key fingerprints, other than
# MAINTAINER_FINGERPRINT, of the valid signatures in the captured status
# lines: each once, upper-case, comma-separated.
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

# other_key_message REF — the abort message for a tag with a valid signature
# from another key: it names the key (or keys) that signed it and the one a
# release tag must be signed by.
other_key_message() {
    _om_keys="$(verify_tag_other_keys)"
    case "$_om_keys" in
        *", "*) _om_keys="the keys ${_om_keys}" ;;
        *) _om_keys="the key ${_om_keys}" ;;
    esac
    printf '%s' "Tag $1 is signed by ${_om_keys}. A release tag must be signed by the maintainer key ${MAINTAINER_FINGERPRINT} that SECURITY.md publishes, and by no other key (possible tampering). Aborting before anything is checked out or materialized."
}

# verify_tag_missing_key — return 0 when the captured status lines show the
# signature could not be checked because the signing public key is absent
# from the local keyring (GnuPG's NO_PUBKEY status), non-zero for any other
# failure (unsigned tag, BAD signature).
verify_tag_missing_key() {
    case "$VERIFY_TAG_OUTPUT" in
        *"[GNUPG:] NO_PUBKEY "*) return 0 ;;
        *) return 1 ;;
    esac
}

# is_release_tag REF — return 0 when REF is a strict vMAJOR.MINOR.PATCH tag
# (not main, a SHA, v1.2.3-rc1, v1x.2.3 or v1.2.3.4), as install.ps1's
# `^v[0-9]+\.[0-9]+\.[0-9]+\z` matches it. A `case` glob's `*` absorbs any
# characters, so reject gates come first: a character outside v, digits and
# dots (a trailing newline too), a `v` after the first character, or a third
# dot. The shape gate then needs a leading `v`, two dots, and a digit at the
# start of each component.
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

# require_gpg — die unless the program `git verify-tag` runs for an OpenPGP
# signature (gpg.openpgp.program, else gpg.program, else gpg) is on PATH, so
# a missing GnuPG is named as such instead of surfacing as a failed signature
# check. Apothem release tags carry OpenPGP signatures whatever gpg.format
# says: that setting picks how git signs, not how it verifies.
require_gpg() {
    _rg_prog="$(ngit config --get gpg.openpgp.program 2>/dev/null || true)"
    [ -n "$_rg_prog" ] || _rg_prog="$(ngit config --get gpg.program 2>/dev/null || true)"
    command -v "${_rg_prog:-gpg}" >/dev/null 2>&1 \
        || die "gpg not found in PATH — needed to check the ${APOTHEM_REF} release tag's signature against the maintainer key. Install GnuPG (https://gnupg.org/download/), then re-run."
}

# check_release_tag DIR REF ALLOW — the key-pinned tag gate on refs/tags/REF
# in the repository at DIR, before any checkout. The ref is read once, and
# TAG_COMMIT records the commit checkout_ref checks out by ID, so a tag ref
# moved later changes nothing. The tag passes when the maintainer key signed
# it and it names itself REF and points at a commit (a signed tag for
# another release would roll the install back). Otherwise abort, unless
# ALLOW is 1: a missing or unverifiable signature then warns and returns 1,
# TAG_COMMIT the commit the tag pointed at.
TAG_COMMIT=""
check_release_tag() {
    TAG_COMMIT=""
    VERIFY_TAG_OUTPUT=""
    _ct_object="$(cgit -C "$1" rev-parse --verify --quiet "refs/tags/$2" 2>/dev/null || true)"
    if [ -n "$_ct_object" ] && verify_tag "$1" "$_ct_object" && verify_tag_by_maintainer; then
        cgit -C "$1" cat-file tag "$_ct_object" 2>/dev/null | awk -v want="$2" '
            /^$/ { exit }
            $1 == "type" { type = $0 }
            $1 == "tag" { name = $0 }
            END { exit (type == "type commit" && name == "tag " want) ? 0 : 1 }' \
            || die "Tag $2 carries the maintainer key's signature, but the signed tag object is not the $2 release tag (it names another tag, or no commit), so it was re-pointed (possible tampering). Aborting before anything is checked out or materialized."
        TAG_COMMIT="$(cgit -C "$1" rev-parse --verify --quiet "${_ct_object}^{commit}")" \
            || die "Could not read the commit the $2 tag points at"
        ok "Tag $2 carries a valid signature from the maintainer key ${MAINTAINER_FINGERPRINT}"
        return 0
    fi
    if [ "$3" = "1" ]; then
        if [ -n "$_ct_object" ]; then
            TAG_COMMIT="$(cgit -C "$1" rev-parse --verify --quiet "${_ct_object}^{commit}" 2>/dev/null || true)"
        fi
        warn "Tag $2 is unsigned, its signature did not verify, or the maintainer key did not make it — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        return 1
    fi
    if verify_tag_valid_other_key; then
        die "$(other_key_message "$2")"
    elif verify_tag_missing_key; then
        die "Tag $2 is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import', check that 'gpg --fingerprint 70396FED9C634163' shows the fingerprint published in SECURITY.md, then re-run this installer."
    fi
    die "Tag $2 is unsigned or its signature did not verify (possible tampering). Aborting before anything is checked out or materialized."
}

# check_fetched_ref DIR — the gate for APOTHEM_REF in the repository at DIR,
# run before it is checked out. A release tag goes through check_release_tag;
# any other ref (main, a SHA, a pre-release tag) cannot be verified, so it is
# refused unless APOTHEM_ALLOW_UNVERIFIED=1.
check_fetched_ref() {
    if is_release_tag "$APOTHEM_REF"; then
        check_release_tag "$1" "$APOTHEM_REF" "$APOTHEM_ALLOW_UNVERIFIED" || true
    elif [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
        warn "Ref ${APOTHEM_REF} is not a signed release tag — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
    else
        die "Ref ${APOTHEM_REF} is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
    fi
}

# require_clean_clone DIR — die when the clone at DIR has changes to tracked
# files, staged or not. Run after the tag check and before an in-place
# checkout: git checkout without --force carries such a change over to the
# new tree whenever the release does not touch that file, and the update
# would then run code the release does not hold.
require_clean_clone() {
    { cgit -C "$1" diff --quiet HEAD && cgit -C "$1" diff --cached --quiet; } \
        || die "$1 has changes to tracked files. Commit or stash them, then re-run."
}

# clone_git_ok DIR — die, saying what to do, when git will not work in the
# clone at DIR. For another user's clone ("dubious ownership", read in the C
# locale) git's own advice would trust that user's git config, so the
# message gives safer ways out.
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

# git_path DIR NAME — print, as a full path, where the clone at DIR keeps
# NAME: config and info/ sit in the git folder all its worktrees share,
# config.worktree in the worktree's own.
git_path() {
    _gp_path="$(cgit -C "$1" rev-parse --git-path "$2" 2>/dev/null)" || return 1
    [ -n "$_gp_path" ] || return 1
    case "$_gp_path" in
        /* | [A-Za-z]:[\\/]*) printf '%s\n' "$_gp_path" ;;
        *) printf '%s/%s\n' "$1" "$_gp_path" ;;
    esac
}

# The settings a clone's own git config (.git/config, and .git/config.worktree
# when there is one) may hold for an update in place: the ones git clone and
# git init write for a full clone (no partial-clone or promisor setting),
# branch settings, user.name and user.email, and the maintenance and pull
# settings git suggests. None names a program, a file or folder git reads
# from, a URL rewrite, or another work tree; only the file, git, http, https
# and ssh transports are allowed. Any other setting stops the update.
# Section and key compare without regard to case, the part between them
# exactly; `*` is any name that is not empty. The four install and update
# scripts hold the same list (test_installer_parity.py compares them).
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

# unallowed_config_key [REFUSE] — read setting names, one per line, as
# `git config --name-only --list` prints them, and print the first one
# CLONE_CONFIG_ALLOW does not hold or that is a line of REFUSE. Section: the
# text before the first dot; key: after the last; subsection: between. An
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

# checkout_ref DIR — check out APOTHEM_REF in the clone at DIR, after
# check_fetched_ref passed. A release tag is checked out, detached, by the
# commit check_release_tag recorded (TAG_COMMIT), never by its name again,
# and HEAD must then be that commit. Any other ref comes from origin when
# the fetch brought a remote-tracking branch of that name (not a stale local
# one), else as given. No --force: local changes the checkout would
# overwrite stop it. Afterwards the tracked files must match the ref.
checkout_ref() {
    if is_release_tag "$APOTHEM_REF"; then
        [ -n "$TAG_COMMIT" ] \
            || die "Could not check out the ${APOTHEM_REF} tag in $1. If it has local changes, commit or stash them, then re-run."
        cgit -C "$1" checkout --quiet --detach "$TAG_COMMIT" \
            || die "Could not check out the ${APOTHEM_REF} tag in $1. If it has local changes, commit or stash them, then re-run."
        _co_head="$(cgit -C "$1" rev-parse --verify --quiet HEAD || true)"
        if [ "$_co_head" != "$TAG_COMMIT" ]; then
            die "The checkout in $1 is at '${_co_head}', not at the ${APOTHEM_REF} tag's commit '${TAG_COMMIT}'. Aborting before anything is materialized."
        fi
    elif cgit -C "$1" rev-parse --verify --quiet "refs/remotes/origin/${APOTHEM_REF}" >/dev/null 2>&1; then
        cgit -C "$1" checkout --quiet --detach "refs/remotes/origin/${APOTHEM_REF}" \
            || die "Could not check out ${APOTHEM_REF} in $1. If it has local changes, commit or stash them, then re-run."
    else
        cgit -C "$1" checkout --quiet --end-of-options "$APOTHEM_REF" \
            || die "Could not check out ${APOTHEM_REF} in $1. If it has local changes, commit or stash them, then re-run."
    fi
    _co_status="$(cgit -C "$1" status --porcelain --untracked-files=no 2>/dev/null)" || _co_status="unreadable"
    [ -z "$_co_status" ] \
        || die "The checkout in $1 does not match ${APOTHEM_REF} after the update. Aborting before re-materialization."
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

# home_is_link — return 0 when APOTHEM_HOME is a symbolic link. The installers
# replace APOTHEM_HOME by renaming folders beside it, which would replace the
# link itself, so they refuse a link instead (install.ps1 does the same for a
# symbolic link or a junction).
home_is_link() {
    [ -L "$APOTHEM_HOME" ]
}

# is_clone DIR — return 0 when DIR is a git clone. Its .git may be a folder,
# or a file that points elsewhere (a worktree, or a clone made with
# --separate-git-dir).
is_clone() {
    [ -e "$1/.git" ] || [ -L "$1/.git" ]
}

# is_apothem_clone DIR — return 0 when DIR is a git clone of an Apothem source
# tree. A clone of anything else is an unrelated folder: it is moved aside
# (with --yes) or refused, never updated or replaced as an Apothem install.
is_apothem_clone() {
    is_clone "$1" && is_apothem_source "$1"
}

# exists PATH — return 0 when PATH is there, a dangling symbolic link included.
exists() {
    [ -e "$1" ] || [ -L "$1" ]
}

# list_entries DIR — print DIR's top-level names, hidden ones included, one
# per line; fail only when DIR cannot be entered. A glob that matches nothing
# stays unexpanded and is skipped, so the loop still ends with status 0.
list_entries() {
    (
        cd "$1" || exit 1
        for _le_e in * .[!.]* ..?*; do
            if exists "$_le_e"; then printf '%s\n' "$_le_e"; fi
        done
        true
    )
}

# The engine's own data folders in APOTHEM_HOME. They are never part of a
# source tree, so a swap always carries them over, and a folder that holds
# nothing else is updated like an empty one.
ENGINE_DATA_NAMES="backups state plans memory contexts learning providers"
is_engine_data() {
    case " $ENGINE_DATA_NAMES " in
        *" $1 "*) return 0 ;;
    esac
    return 1
}

# source_entries DIR — print, one per line, the top-level names that belong
# to the Apothem source tree at DIR rather than to the engine or the user:
# .git, the entries a git clone tracks, and those an archive install recorded
# in its .apothem-source-entries manifest. The engine's data names are left
# out whatever lists them.
SOURCE_MANIFEST=".apothem-source-entries"
source_entries() {
    {
        printf '%s\n' .git
        if is_clone "$1"; then
            cgit -C "$1" ls-tree --name-only HEAD 2>/dev/null || true
        fi
        if [ -f "$1/$SOURCE_MANIFEST" ]; then
            cat "$1/$SOURCE_MANIFEST"
        fi
    } | while IFS= read -r _se_name; do
        if ! is_engine_data "$_se_name"; then printf '%s\n' "$_se_name"; fi
    done
}

# carry_names SOURCE — print, space-separated, the entries of APOTHEM_HOME a
# keep-mode swap carries over: the engine's data, and every entry not named
# in SOURCE (newline-separated). Die, before anything moves, when such an
# entry's name has a space or another special character, since the swap
# moves entries by name.
carry_names() {
    _cn_keep=""
    for _cn_entry in "$APOTHEM_HOME"/* "$APOTHEM_HOME"/.[!.]* "$APOTHEM_HOME"/..?*; do
        exists "$_cn_entry" || continue
        _cn_base="${_cn_entry##*/}"
        if ! is_engine_data "$_cn_base"; then
            case "
$1
" in
                *"
${_cn_base}
"*) continue ;;
            esac
        fi
        case "$_cn_base" in
            *[!A-Za-z0-9._@+-]*)
                die "Cannot carry $APOTHEM_HOME/${_cn_base} over to the new install (its name has a space or another special character). Move it out of $APOTHEM_HOME, then re-run." ;;
        esac
        _cn_keep="${_cn_keep} ${_cn_base}"
    done
    printf '%s\n' "$_cn_keep"
}

# clone_has_local_work DIR — return 0 when replacing the clone at DIR would
# lose work: changes to tracked files, a stash, a commit no remote branch
# holds, or an untracked path inside a top-level entry the clone tracks (an
# untracked top-level entry of its own is carried over instead). A git
# command that fails counts as work, so an unreadable clone is not replaced.
# The caller has run the clone checks first; every git command goes through
# cgit, and git status takes --ignore-submodules=all (which, unlike a -c
# setting, .gitmodules cannot override), so none runs inside a nested
# repository.
clone_has_local_work() {
    _lw_out="$(GIT_OPTIONAL_LOCKS=0; export GIT_OPTIONAL_LOCKS; cgit -C "$1" status --porcelain --ignore-submodules=all --untracked-files=no 2>/dev/null)" || return 0
    [ -z "$_lw_out" ] || return 0
    _lw_out="$(cgit -C "$1" stash list 2>/dev/null)" || return 0
    [ -z "$_lw_out" ] || return 0
    _lw_out="$(cgit -C "$1" log --branches --not --remotes --oneline 2>/dev/null)" || return 0
    [ -z "$_lw_out" ] || return 0
    _lw_tracked="$(cgit -C "$1" ls-tree --name-only HEAD 2>/dev/null)" || return 0
    _lw_untracked="$(GIT_OPTIONAL_LOCKS=0; export GIT_OPTIONAL_LOCKS; cgit -C "$1" status --porcelain --ignore-submodules=all 2>/dev/null)" || return 0
    _lw_found="$(printf '%s\n' "$_lw_untracked" | LW_TRACKED="$_lw_tracked" LC_ALL=C awk '
        BEGIN { n = split(ENVIRON["LW_TRACKED"], names, "\n"); for (i = 1; i <= n; i++) top[names[i]] = 1 }
        substr($0, 1, 3) == "?? " {
            path = substr($0, 4)
            if (substr(path, 1, 1) == "\"") path = substr(path, 2)
            first = path
            slash = index(first, "/")
            if (slash > 0) first = substr(first, 1, slash - 1)
            if (slash > 0 && (first in top)) { print path; exit }
        }')"
    [ -n "$_lw_found" ]
}

# swap_in NEW MODE — put the checked tree at NEW (beside APOTHEM_HOME, so
# every move is a rename on one filesystem) in place of APOTHEM_HOME.
#   keep:  APOTHEM_HOME holds an earlier install (or only engine data).
#          Each top-level entry not in its source tree or in NEW (backups/,
#          state/ and other data) moves into NEW; the earlier tree moves
#          aside, NEW moves in, and the earlier source is removed.
#   aside: --yes allowed replacing what APOTHEM_HOME holds; it moves,
#          untouched, into a new sibling <APOTHEM_HOME>.before-apothem-<time>
#          (claim_aside), and NEW moves in.
# A failure or an interrupt puts everything back and says so, or names where
# the earlier tree was left. The rollback reads what is on disk, so it undoes
# exactly the steps that happened. Archive installs record their source
# entries so a later swap can tell them from data.
_SW_PHASE=""
_SW_MODE=""
_SW_NEW=""
_SW_OLD=""
_SW_ASIDE=""
_SW_ASIDE_ITEM=""
_SW_KEEP=""
_SW_KEEP_STAGING=0

# move_tree FROM TO — mv FROM to TO, and fail as mv would when FROM went
# inside a folder TO that appeared meanwhile (found by its inode), after
# moving it back. MOVED_BACK=1 says FROM is where it was: moved back, or
# never moved because mv failed (a file that appeared at TO, say).
file_id() { ls -di -- "$1" 2>/dev/null | LC_ALL=C awk 'NR == 1 { print $1 }'; }
MOVED_BACK=0
move_tree() {
    MOVED_BACK=0
    _mt_id="$(file_id "$1")"
    if ! mv "$1" "$2"; then
        [ -n "$_mt_id" ] && [ "$(file_id "$1")" = "$_mt_id" ] && MOVED_BACK=1
        return 1
    fi
    _mt_in="$2/${1##*/}"
    [ -n "$_mt_id" ] && exists "$_mt_in" && [ "$(file_id "$_mt_in")" = "$_mt_id" ] || return 0
    mv "$_mt_in" "$1" && MOVED_BACK=1 || warn "$1 could not be moved back from $_mt_in"
    return 1
}

swap_rollback() {
    _sw_ok=1
    if [ "$_SW_MODE" = "aside" ]; then
        # Undo the move-in, then move the set-aside folder back and remove
        # the folder it was moved into, which is then empty.
        if exists "$APOTHEM_HOME" && ! exists "$_SW_NEW" && exists "$_SW_ASIDE_ITEM"; then
            move_tree "$APOTHEM_HOME" "$_SW_NEW" || _sw_ok=0
        fi
        if [ "$_sw_ok" = "1" ] && ! exists "$APOTHEM_HOME" && exists "$_SW_ASIDE_ITEM"; then
            move_tree "$_SW_ASIDE_ITEM" "$APOTHEM_HOME" || _sw_ok=0
        fi
        if exists "$_SW_ASIDE_ITEM" || ! exists "$APOTHEM_HOME"; then _sw_ok=0; fi
        if [ "$_sw_ok" = "1" ] && [ -n "$_SW_ASIDE" ]; then
            rmdir "$_SW_ASIDE" 2>/dev/null || true
        fi
    else
        _sw_oldhome="${_SW_OLD:+${_SW_OLD}/home}"
        # Undo the move-in: the new tree is at APOTHEM_HOME while the
        # earlier one is aside.
        if exists "$APOTHEM_HOME" && ! exists "$_SW_NEW" && exists "$_sw_oldhome"; then
            move_tree "$APOTHEM_HOME" "$_SW_NEW" || _sw_ok=0
        fi
        # Undo the rename of the earlier tree.
        if [ "$_sw_ok" = "1" ] && ! exists "$APOTHEM_HOME" && exists "$_sw_oldhome"; then
            move_tree "$_sw_oldhome" "$APOTHEM_HOME" || _sw_ok=0
        fi
        if exists "$_sw_oldhome" || ! exists "$APOTHEM_HOME"; then _sw_ok=0; fi
        # Undo the carry: every planned entry now in NEW moves back. One that
        # is in both places cannot be put back without losing a copy.
        if [ "$_sw_ok" = "1" ]; then
            for _sw_name in $_SW_KEEP; do
                exists "${_SW_NEW}/${_sw_name}" || continue
                if exists "${APOTHEM_HOME}/${_sw_name}"; then
                    _sw_ok=0
                else
                    move_tree "${_SW_NEW}/${_sw_name}" "${APOTHEM_HOME}/${_sw_name}" || _sw_ok=0
                fi
            done
        fi
    fi
    _SW_PHASE=""
    if [ "$_sw_ok" = "1" ]; then
        if [ -n "$_SW_OLD" ]; then rmdir "$_SW_OLD" 2>/dev/null || true; fi
        return 0
    fi
    # Keep the staging folders: they may hold the only copy of the data.
    _SW_KEEP_STAGING=1
    return 1
}
# swap_report WHAT — roll back and print what happened, WHAT being what went
# wrong; return 0 when the earlier install is back in place.
swap_report() {
    if swap_rollback; then
        if [ "$_SW_MODE" = "aside" ]; then
            printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$1; the earlier folder is back in place and unchanged" >&2
        else
            printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$1; the earlier install at $APOTHEM_HOME is back in place and unchanged" >&2
        fi
        return 0
    fi
    if [ "$_SW_MODE" = "aside" ]; then
        printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$1, and moving the earlier folder back also failed: it is at $_SW_ASIDE_ITEM" >&2
    else
        # The earlier tree is aside only when the swap got that far.
        _sw_where="$APOTHEM_HOME"
        if [ -n "$_SW_OLD" ] && exists "${_SW_OLD}/home"; then _sw_where="${_SW_OLD}/home"; fi
        printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$1, and putting the earlier install back also failed: it is at ${_sw_where} (with any moved data under ${_SW_NEW}). Move it back to $APOTHEM_HOME by hand." >&2
    fi
    return 1
}
swap_abort() {
    swap_report "$1" || true
    exit 1
}

# trap_signals_to_exit — make each signal that would end the installer exit
# through the EXIT trap, so the staging folders are cleaned up. Untrapped,
# QUIT and PIPE end the shell without running it.
trap_signals_to_exit() {
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 131' QUIT
    trap 'exit 141' PIPE
    trap 'exit 143' TERM
}

# on_exit — the EXIT trap, set when the install lock is taken. A swap still
# under way (a command failing under set -e, or a signal after the swap's
# own trap was reset) is rolled back first; staging folders are removed
# unless a failed rollback left data in them; the lock goes last.
_ck_tmp=""
_ck_stage=""
_cl_stage=""
on_exit() {
    if [ -n "$_SW_PHASE" ]; then
        swap_report "Stopped while replacing $APOTHEM_HOME" || true
    fi
    if [ -n "$_ck_tmp" ]; then rm -rf "$_ck_tmp"; fi
    if [ -n "$HOOKS_OFF" ]; then rm -rf "$HOOKS_OFF"; fi
    if [ "$_SW_KEEP_STAGING" != "1" ]; then
        if [ -n "$_ck_stage" ]; then rm -rf "$_ck_stage"; fi
        if [ -n "$_cl_stage" ]; then rm -rf "$_cl_stage"; fi
        if [ -n "$_SW_OLD" ]; then rm -rf "$_SW_OLD"; fi
    fi
    release_lock
}

# The install lock: an install, update or uninstall holds the folder
# <APOTHEM_HOME>.lock (made by mkdir, holding its process ID) for its whole
# run, and on_exit removes it. One a forced kill leaves is reported with how
# to remove it, never taken over; one from another environment (lock_env)
# cannot have its process checked. For a linked APOTHEM_HOME it sits beside
# the folder the link leads to. The ps1 scripts hold a file there instead,
# open with no sharing, which Windows removes when the run ends.
LOCK_DIR=""
LOCK_HELD=0
take_lock() {
    _tl_home="$APOTHEM_HOME"
    if [ -L "$APOTHEM_HOME" ] && _tl_real="$(cd -P -- "$APOTHEM_HOME" 2>/dev/null && pwd -P)"; then
        _tl_home="$_tl_real"
    fi
    LOCK_DIR="${_tl_home}.lock"
    _tl_parent="$(dirname -- "$_tl_home")"
    if [ ! -d "$_tl_parent" ]; then
        # Nothing is at APOTHEM_HOME or beside it yet. A dry run writes
        # nothing, so it goes on without the lock; a real run makes the
        # parent folder it would make anyway.
        if [ "$DRY_RUN" = "1" ]; then return 0; fi
        mkdir -p "$_tl_parent" \
            || die "Could not create the parent directory of $APOTHEM_HOME"
    fi
    # Signals are ignored from the mkdir until LOCK_HELD says the lock is
    # this run's: a signal in between would otherwise leave a lock with no
    # process ID in it, and a run whose mkdir failed must never remove the
    # lock that another run holds.
    trap '' HUP INT QUIT PIPE TERM
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        LOCK_HELD=1
        trap_signals_to_exit
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
    # (an earlier installer's lock has no env)
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

# lock_env — print the system, host, process ID namespace and runtime root
# this run's process ID belongs to (WSL and Git Bash on one machine differ;
# so do two msys runtimes, such as Git Bash and MSYS2, each with its own
# process table). uname -o, not uname -s, so that MSYSTEM and the Windows
# build number play no part.
lock_env() {
    printf '%s %s %s %s\n' "$(uname -o 2>/dev/null || uname -s 2>/dev/null)" \
        "$(uname -n 2>/dev/null)" "$(readlink /proc/self/ns/pid 2>/dev/null)" \
        "$(cygpath -m / 2>/dev/null)"
}

# powershell_may_lock — return 0 where a PowerShell run can hold the lock
# file: Git Bash, MSYS2, Cygwin, and WSL (a lock on a Windows drive).
powershell_may_lock() {
    case "$(uname -s 2>/dev/null)" in
        MINGW* | MSYS* | CYGWIN*) return 0 ;;
    esac
    case "$(uname -r 2>/dev/null)" in
        *[Mm]icrosoft*) return 0 ;;
    esac
    return 1
}

# make_staging KIND — make a new, empty folder beside APOTHEM_HOME named
# .apothem-KIND.<leaf>.<six letters or digits>, <leaf> being APOTHEM_HOME's
# own folder name, and print its path. The leaf lets check_leftovers in a
# later run tell this home's staging folders from those of another
# APOTHEM_HOME in the same folder, which another run may be using.
make_staging() {
    mktemp -d "$(dirname -- "$APOTHEM_HOME")/.apothem-$1.$(basename -- "$APOTHEM_HOME").XXXXXX"
}

# CARRY_LIST — the file a keep-mode swap writes into the staging folder,
# beside the new tree and never inside it, before it moves anything: the
# names of the entries it carries from APOTHEM_HOME into the new tree, one
# per line, sorted. After a forced kill, check_leftovers reads it to name
# every entry that has to go back.
CARRY_LIST=".apothem-carried-entries"

# check_leftovers — stop, before anything is fetched or swapped, when a
# forced kill left staging folders beside APOTHEM_HOME:
# .apothem-{extract,clone,old}.<leaf>.*, <leaf> being APOTHEM_HOME's own
# folder name (another spelling of it where names ignore case; another
# home's are left out), and those with the earlier names (no leaf), with a
# note. Only real folders count. Nothing is moved or removed: the message
# names each folder, what it holds, and what to do; and, when APOTHEM_HOME
# is missing, its <APOTHEM_HOME>.before-apothem-<time> folders.
check_leftovers() {
    _lo_parent="$(dirname -- "$APOTHEM_HOME")"
    _lo_leaf="$(basename -- "$APOTHEM_HOME")"
    _lo_fold=0
    case "$(uname -s 2>/dev/null)" in
        MINGW* | MSYS* | CYGWIN* | Darwin*) _lo_fold=1 ;;
    esac
    _lo_mine=""
    _lo_older=""
    for _lo_dir in "$_lo_parent"/.apothem-old.* "$_lo_parent"/.apothem-extract.* "$_lo_parent"/.apothem-clone.*; do
        [ -d "$_lo_dir" ] && [ ! -L "$_lo_dir" ] || continue
        _lo_rest="${_lo_dir##*/}"
        _lo_rest="${_lo_rest#.apothem-*.}"
        case "$_lo_rest" in
            *.*)
                [ -n "${_lo_rest##*.}" ] && same_leaf "${_lo_rest%.*}" "$_lo_leaf" "$_lo_fold" || continue
                _lo_mine="${_lo_mine}${_lo_dir}
" ;;
            *)
                _lo_older="${_lo_older}${_lo_dir}
" ;;
        esac
    done
    [ -n "${_lo_mine}${_lo_older}" ] || return 0
    _lo_note=" (made by an earlier installer that did not record which home it was for, so it may belong to any Apothem home in ${_lo_parent}: check what it holds before you move or remove it)"
    _lo_base="${APOTHEM_HOME%"$_lo_leaf"}"
    _lo_list="$(
        printf '%s' "$_lo_mine" | LC_ALL=C sort | while IFS= read -r _lo_dir; do
            leftover_line "$_lo_dir" 0
        done
        printf '%s' "$_lo_older" | LC_ALL=C sort | while IFS= read -r _lo_dir; do
            printf '%s%s\n' "$(leftover_line "$_lo_dir" 1)" "$_lo_note"
        done
        if ! exists "$APOTHEM_HOME"; then
            for _lo_dir in "$_lo_base"*.before-apothem-* "$_lo_base".*.before-apothem-*; do
                [ -d "$_lo_dir" ] && [ ! -L "$_lo_dir" ] || continue
                _lo_name="${_lo_dir##*/}"
                same_leaf "${_lo_name%.before-apothem-*}" "$_lo_leaf" "$_lo_fold" || continue
                is_aside_name "${_lo_name##*.before-apothem-}" || continue
                printf '%s\n' "$_lo_dir"
            done | LC_ALL=C sort | while IFS= read -r _lo_dir; do
                if [ -d "$_lo_dir/$_lo_leaf" ] && [ ! -L "$_lo_dir/$_lo_leaf" ]; then
                    printf '%s\n' "${_lo_dir}: the earlier contents of $APOTHEM_HOME, moved aside, in ${_lo_dir}/${_lo_leaf}"
                else
                    printf '%s\n' "${_lo_dir}: the earlier contents of $APOTHEM_HOME, moved aside, in ${_lo_dir}"
                fi
            done
        fi
    )"
    printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "An earlier run was stopped part-way and left these folders beside $APOTHEM_HOME:" >&2
    printf '%s\n' "$_lo_list" | sed 's/^/    /' >&2
    printf '    %s\n' "Nothing was changed. If $APOTHEM_HOME is missing, move the earlier install back to it first. Then move every entry listed above as moved into a new source back into the home it came from, remove the folders listed above, and re-run." >&2
    exit 1
}

# same_leaf NAME LEAF FOLD — return 0 when NAME is LEAF, or, with FOLD 1,
# is LEAF but for ASCII case.
same_leaf() {
    [ "$1" = "$2" ] && return 0
    [ "$3" = "1" ] || return 1
    [ "$(printf '%sx' "$1" | LC_ALL=C tr 'A-Z' 'a-z')" = "$(printf '%sx' "$2" | LC_ALL=C tr 'A-Z' 'a-z')" ]
}

# is_aside_name TIME — return 0 when TIME is what claim_aside puts after
# .before-apothem-: 14 digits, or 14 digits, a dash and a process ID.
is_aside_name() {
    _an_time="${1%%-*}"
    case "$_an_time" in
        "" | *[!0-9]*) return 1 ;;
    esac
    [ "${#_an_time}" -eq 14 ] || return 1
    case "$1" in
        *-*)
            _an_pid="${1#*-}"
            case "$_an_pid" in
                "" | *[!0-9]*) return 1 ;;
            esac ;;
    esac
    return 0
}

# is_aside_temp DIR NAME — return 0 when DIR/NAME is an empty folder named
# aside. and 32 lower-case hex digits: install.ps1 makes one in its staging
# folder and renames it at once, so only a forced kill leaves it. It is left
# out when a staging folder is described.
is_aside_temp() {
    case "$2" in
        aside.*) ;;
        *) return 1 ;;
    esac
    _at_hex="${2#aside.}"
    [ "${#_at_hex}" -eq 32 ] || return 1
    case "$_at_hex" in
        *[!0-9a-f]*) return 1 ;;
    esac
    [ -d "$1/$2" ] && [ ! -L "$1/$2" ] || return 1
    _at_in="$(ls -A -- "$1/$2" 2>/dev/null)" || return 1
    [ -z "$_at_in" ]
}

# is_extract_staging DIR — return 0 when DIR is an archive's staging folder.
is_extract_staging() {
    case "${1##*/}" in
        .apothem-extract.*) return 0 ;;
    esac
    return 1
}

# join_names — read names, one per line, and print them joined with ", ".
join_names() {
    LC_ALL=C awk 'NR > 1 { printf ", " } { printf "%s", $0 } END { printf "\n" }'
}

# leftover_line DIR OLDNAME — print one line saying what the leftover folder
# DIR holds (see check_leftovers): that it cannot be read, that it is empty,
# the earlier install in DIR/home, the new source in DIR/<tree> with every
# entry moved into it from APOTHEM_HOME (from its own home, for OLDNAME 1:
# an earlier-name folder), or else every name in it. A clone's tree in
# DIR/home while APOTHEM_HOME is there is one a keep-clone swap was keeping.
# A DIR/home that holds no Apothem install while APOTHEM_HOME is there is a
# folder that appeared there, which the swap left alone (see swap_in).
leftover_line() {
    if ! ls -A -- "$1" >/dev/null 2>&1 || ! _ll_all="$(list_entries "$1")"; then
        printf '%s\n' "$1: could not be read (check its owner and permissions)"
        return 0
    fi
    _ll_names="$(printf '%s\n' "$_ll_all" | while IFS= read -r _ll_name; do
        [ -n "$_ll_name" ] || continue
        is_aside_temp "$1" "$_ll_name" || printf '%s\n' "$_ll_name"
    done | LC_ALL=C sort)"
    if [ -z "$_ll_names" ]; then
        printf '%s\n' "$1: empty"
        return 0
    fi
    case "$1" in
        */.apothem-old.*)
            if [ "$_ll_names" = "home" ] && [ -d "$1/home" ] && [ ! -L "$1/home" ]; then
                if exists "$1/home/.git" && exists "$APOTHEM_HOME"; then
                    printf '%s\n' "$1: the earlier clone's tree, which that run was keeping, in $1/home: move it to a folder of your own if you still need it"
                elif exists "$APOTHEM_HOME" && ! exists "$1/home/src/apothem" \
                    && ! exists "$1/home/$SOURCE_MANIFEST" && [ -n "$(ls -A -- "$1/home" 2>/dev/null)" ]; then
                    printf '%s\n' "$1: a folder that holds no Apothem install, in $1/home: check what it holds before you remove it"
                else
                    printf '%s\n' "$1: the earlier install that was being replaced, in $1/home"
                fi
                return 0
            fi ;;
        *)
            _ll_tree="$_ll_names"
            if [ -f "$1/$CARRY_LIST" ] && [ ! -L "$1/$CARRY_LIST" ]; then
                _ll_tree="$(printf '%s\n' "$_ll_names" | LC_ALL=C grep -vxF -- "$CARRY_LIST" || true)"
            fi
            case "$_ll_tree" in
                "" | *"
"*) ;;
                *)
                    if [ -d "$1/$_ll_tree" ] && [ ! -L "$1/$_ll_tree" ]; then
                        _ll_carried="$(leftover_carried "$1" "$_ll_tree" | join_names)"
                        _ll_from="$APOTHEM_HOME"
                        if [ "$2" = "1" ]; then _ll_from="the Apothem home it was made for"; fi
                        if [ -n "$_ll_carried" ]; then
                            printf '%s\n' "$1: the new source that was being installed, in $1/$_ll_tree, with these entries moved into it from ${_ll_from}: $_ll_carried"
                        else
                            printf '%s\n' "$1: the new source that was being installed, in $1/$_ll_tree"
                        fi
                        return 0
                    fi ;;
            esac ;;
    esac
    printf '%s\n' "$1: files from that run ($(printf '%s\n' "$_ll_names" | join_names))"
}

# leftover_carried DIR TREE — print, one per line, the entries a swap moved
# from APOTHEM_HOME into DIR/TREE: the names DIR's carry list holds that are
# in TREE; with no carry list (a folder from an earlier installer, or a kill
# before the swap began), for an archive's staging folder the entries of
# TREE that its source manifest does not name, and otherwise the engine's
# data folders TREE holds.
leftover_carried() {
    if [ -f "$1/$CARRY_LIST" ] && [ ! -L "$1/$CARRY_LIST" ]; then
        while IFS= read -r _lc_name; do
            [ -n "$_lc_name" ] || continue
            if exists "$1/$2/$_lc_name"; then printf '%s\n' "$_lc_name"; fi
        done < "$1/$CARRY_LIST"
    elif is_extract_staging "$1" && [ -f "$1/$2/$SOURCE_MANIFEST" ] \
        && [ ! -L "$1/$2/$SOURCE_MANIFEST" ]; then
        list_entries "$1/$2" 2>/dev/null | while IFS= read -r _lc_name; do
            LC_ALL=C grep -qxF -- "$_lc_name" "$1/$2/$SOURCE_MANIFEST" 2>/dev/null \
                || printf '%s\n' "$_lc_name"
        done | LC_ALL=C sort
    else
        for _lc_name in backups contexts learning memory plans providers state; do
            if exists "$1/$2/$_lc_name"; then printf '%s\n' "$_lc_name"; fi
        done
    fi
}

# aside_name — print the name claim_aside would try first,
# <APOTHEM_HOME>.before-apothem-<time>, with -<pid> added when that is
# taken. Die, before anything moves, when both are taken. This only checks
# early (in a dry run too); claim_aside makes the folder when the swap runs.
aside_name() {
    _an_name="${APOTHEM_HOME}.before-apothem-$(date +%Y%m%d%H%M%S)"
    if exists "$_an_name"; then _an_name="${_an_name}-$$"; fi
    if exists "$_an_name"; then
        die "Could not move the existing $APOTHEM_HOME aside; nothing was changed"
    fi
    printf '%s\n' "$_an_name"
}

# claim_aside — make the new folder an earlier tree is moved into, and print
# its path: <APOTHEM_HOME>.before-apothem-<time>, or <time>-<pid> when that
# name is taken. mkdir makes it in one step that fails when the name is
# already there, so the folder is always an empty one this run made; the
# earlier tree then moves inside it under its own name. It is never moved
# into a folder someone else made, or to a name checked first and used
# later. Fail, having made nothing, when both names are taken.
claim_aside() {
    _ca_name="${APOTHEM_HOME}.before-apothem-$(date +%Y%m%d%H%M%S)"
    if mkdir "$_ca_name" 2>/dev/null; then
        printf '%s\n' "$_ca_name"
        return 0
    fi
    if mkdir "${_ca_name}-$$" 2>/dev/null; then
        printf '%s\n' "${_ca_name}-$$"
        return 0
    fi
    return 1
}

swap_in() {
    _SW_NEW="$1"
    _SW_MODE="$2"
    _SW_OLD=""
    _SW_ASIDE=""
    _SW_ASIDE_ITEM=""
    _SW_KEEP=""
    if ! exists "$APOTHEM_HOME"; then
        move_tree "$_SW_NEW" "$APOTHEM_HOME" || die "Could not move the new source to $APOTHEM_HOME"
        return 0
    fi
    if [ "$_SW_MODE" = "aside" ]; then
        trap 'swap_abort "Interrupted while replacing $APOTHEM_HOME"' HUP INT TERM QUIT PIPE
        _SW_PHASE="claim"
        if ! _SW_ASIDE="$(claim_aside)"; then
            _SW_ASIDE=""
            trap_signals_to_exit
            _SW_PHASE=""
            die "Could not move the existing $APOTHEM_HOME aside; nothing was changed"
        fi
        _SW_ASIDE_ITEM="${_SW_ASIDE}/$(basename -- "$APOTHEM_HOME")"
        _SW_PHASE="aside"
        if ! move_tree "$APOTHEM_HOME" "$_SW_ASIDE_ITEM"; then
            if exists "$APOTHEM_HOME" && { [ "$MOVED_BACK" = "1" ] || ! exists "$_SW_ASIDE_ITEM"; }; then
                rmdir "$_SW_ASIDE" 2>/dev/null || true
                trap_signals_to_exit
                _SW_PHASE=""
                die "Could not move the existing $APOTHEM_HOME aside; nothing was changed"
            fi
            swap_abort "Could not move the existing $APOTHEM_HOME aside"
        fi
        _SW_PHASE="move-in"
        move_tree "$_SW_NEW" "$APOTHEM_HOME" \
            || swap_abort "Could not move the new source to $APOTHEM_HOME"
        trap_signals_to_exit
        _SW_PHASE=""
        warn "The earlier contents of $APOTHEM_HOME were moved, unchanged, to $_SW_ASIDE_ITEM"
        return 0
    fi
    # keep: list the entries to carry over before anything moves.
    _sw_new_names="$(list_entries "$_SW_NEW")" \
        || die "Could not list the new source at $_SW_NEW; nothing was changed"
    _sw_source="$(source_entries "$APOTHEM_HOME")
${_sw_new_names}"
    _SW_KEEP="$(carry_names "$_sw_source")" || exit 1
    for _sw_name in $_SW_KEEP; do
        if exists "${_SW_NEW}/${_sw_name}"; then
            die "Cannot carry $APOTHEM_HOME/${_sw_name} over to the new install, which has an entry of that name. Move it out of $APOTHEM_HOME, then re-run."
        fi
    done
    _SW_OLD="$(make_staging old)" \
        || die "Could not make room beside $APOTHEM_HOME; nothing was changed"
    # The carry list goes beside NEW, in its staging folder, before anything
    # moves, so that after a forced kill check_leftovers can name every entry
    # to move back. The names hold no space or special character
    # (carry_names checked), so they split safely.
    # shellcheck disable=SC2086
    printf '%s\n' $_SW_KEEP | LC_ALL=C sort > "$(dirname -- "$_SW_NEW")/${CARRY_LIST}" \
        || die "Could not write the list of entries to carry over beside $_SW_NEW; nothing was changed"
    trap 'swap_abort "Interrupted while replacing $APOTHEM_HOME"' HUP INT TERM QUIT PIPE
    for _sw_name in $_SW_KEEP; do
        _SW_PHASE="carry"
        if ! move_tree "${APOTHEM_HOME}/${_sw_name}" "${_SW_NEW}/${_sw_name}"; then
            # Moved back, it is not to be carried back from NEW.
            # shellcheck disable=SC2086
            [ "$MOVED_BACK" = "0" ] || _SW_KEEP="$(printf '%s\n' $_SW_KEEP | grep -vxF -- "$_sw_name" || true)"
            swap_abort "Could not move ${_sw_name} into the new install"
        fi
    done
    _SW_PHASE="aside"
    if ! move_tree "$APOTHEM_HOME" "${_SW_OLD}/home"; then
        # The earlier tree is still in place. Anything at _SW_OLD/home then
        # is not it, and not this run's either, so it is left there and
        # named, and _SW_OLD is no longer this run's to remove.
        if [ "$MOVED_BACK" = "1" ] && exists "${_SW_OLD}/home"; then
            warn "Something this run did not make appeared at ${_SW_OLD}/home and was left there. Check what it holds, then remove ${_SW_OLD}."
            _SW_OLD=""
        fi
        swap_abort "Could not move the existing $APOTHEM_HOME aside"
    fi
    _SW_PHASE="move-in"
    move_tree "$_SW_NEW" "$APOTHEM_HOME" \
        || swap_abort "Could not move the new source to $APOTHEM_HOME"
    trap_signals_to_exit
    _SW_PHASE=""
    if [ "$_SW_MODE" = "keep-clone" ]; then
        # keep-clone: an Apothem clone replaced with --yes. Its tree
        # (history and source, the carried entries aside) is kept in a new
        # <APOTHEM_HOME>.before-apothem-<time> folder, not deleted. From here
        # the folder that holds it is the clone's only copy, so on_exit must
        # not remove it; when no such folder can be made, it stays there.
        _sw_old="$_SW_OLD"
        _SW_OLD=""
        _sw_tree_aside="${_sw_old}/home"
        if _sw_claim="$(claim_aside)"; then
            if move_tree "${_sw_old}/home" "${_sw_claim}/$(basename -- "$APOTHEM_HOME")"; then
                _sw_tree_aside="${_sw_claim}/$(basename -- "$APOTHEM_HOME")"
                rmdir "$_sw_old" 2>/dev/null || true
            else
                rmdir "$_sw_claim" 2>/dev/null || true
            fi
        fi
        warn "The earlier clone's tree is kept at ${_sw_tree_aside}; delete it once you no longer need it."
        return 0
    fi
    rm -rf "$_SW_OLD" || warn "Could not remove the earlier source at ${_SW_OLD}; delete it by hand"
    _SW_OLD=""
}

# record_source_entries DIR — write DIR's top-level names to its manifest, so
# a later swap can tell this archive install's source from the engine's data.
record_source_entries() {
    { list_entries "$1" && printf '%s\n' "$SOURCE_MANIFEST"; } \
        | LC_ALL=C sort -u > "$1/$SOURCE_MANIFEST" \
        || die "Could not record the source entries in $1"
}

# Downloads from an https:// base never follow a redirect to plain http; a
# base set to another scheme (a local file:// mirror) is used as given.
CURL_PROTO=""
case "$APOTHEM_RELEASE_BASE" in
    https://*) CURL_PROTO="--proto =https --proto-redir =https" ;;
esac

bold "Apothem installer"
echo

# One install, update or uninstall at a time on APOTHEM_HOME (see
# take_lock). on_exit, the EXIT trap from here on, lets the lock go.
trap on_exit EXIT
trap_signals_to_exit
take_lock

# Prerequisite: Python >= 3.10 ----------------------------------------------------
#
# Locate a real CPython >= 3.10, rejecting Microsoft Store launcher shims.
# The locator at src/apothem/hooks/lib/find-python.sh is reused when a local
# tree is in use (see own_checkout below); otherwise an inline probe applies
# the same version floor and the same Store-shim rejection against PATH
# candidates.

bold "Checking prerequisites"

is_apothem_source() {
    [ -d "$1/src/apothem" ] && { [ -f "$1/pyproject.toml" ] || [ -d "$1/.claude-plugin" ]; }
}

# own_checkout — print the checkout this script file belongs to, if any,
# found by its own path only: $0, links followed, must be a regular file
# named install.sh in a scripts/installer folder whose ../.. is an Apothem
# source. A piped run has the shell's name in $0, and the current folder is
# never searched, so a tree planted there cannot run unverified. A bare
# `install.sh` with no "/" is refused, not looked up. Under `sh -c`, $0 is
# whatever the caller typed: bash, zsh and ksh put "c" in $-, which refuses
# it; dash does not, so pass no path-shaped name after `sh -c`.
OWN_CHECKOUT_MAX_LINKS=40
own_checkout() {
    case "$-" in
        *c*) return 1 ;;
    esac
    case "$0" in
        /*) _oc_self="$0" ;;
        */*) _oc_self="./$0" ;;
        *) return 1 ;;
    esac
    _oc_links=0
    while [ -L "$_oc_self" ]; do
        _oc_links=$((_oc_links + 1))
        [ "$_oc_links" -le "$OWN_CHECKOUT_MAX_LINKS" ] || return 1
        _oc_target="$(readlink "$_oc_self" 2>/dev/null)" || return 1
        case "$_oc_target" in
            /*) _oc_self="$_oc_target" ;;
            *) _oc_self="${_oc_self%/*}/${_oc_target}" ;;
        esac
    done
    case "$_oc_self" in
        */install.sh) ;;
        *) return 1 ;;
    esac
    [ -f "$_oc_self" ] || return 1
    _oc_dir="${_oc_self%/install.sh}"
    [ -n "$_oc_dir" ] || _oc_dir="/"
    _oc_dir="$(cd -P -- "$_oc_dir" 2>/dev/null && pwd -P)" || return 1
    case "$_oc_dir" in
        */scripts/installer) ;;
        *) return 1 ;;
    esac
    _oc_root="$(cd -P -- "$_oc_dir/../.." 2>/dev/null && pwd -P)" || return 1
    is_apothem_source "$_oc_root" || return 1
    printf '%s\n' "$_oc_root"
}

# The local tree, if any: APOTHEM_SOURCE when set, else this script's own
# checkout. An APOTHEM_SOURCE that is not an Apothem tree is refused under
# "Locating Apothem source"; until then it supplies no locator.
LOCAL_TREE=""
LOCAL_KIND=""
if [ -n "${APOTHEM_SOURCE:-}" ]; then
    LOCAL_TREE="$(cd "$APOTHEM_SOURCE" 2>/dev/null && pwd || true)"
    if [ -z "$LOCAL_TREE" ] || ! is_apothem_source "$LOCAL_TREE"; then
        LOCAL_TREE=""
    fi
    LOCAL_KIND=explicit
elif LOCAL_TREE="$(own_checkout)"; then
    LOCAL_KIND=checkout
else
    LOCAL_TREE=""
    # `sh install.sh` from inside scripts/installer looks like a checkout run
    # but cannot be told apart from `sh -c "$(curl …)" install.sh`; say why
    # the checkout is not used, and read nothing from the current folder.
    # Only existence tests here: the note shows when this folder looks like a
    # checkout's scripts/installer, never for a downloaded copy run in a
    # folder of its own, and never under a -c run.
    case "$-" in
        *c*) _oc_note=0 ;;
        *) _oc_note=1 ;;
    esac
    if [ "$_oc_note" = "1" ] && [ "$0" = "install.sh" ] \
        && [ -f ./install.sh ] && [ -d ../../src/apothem ]; then
        info "Not using a checkout: to install from one, run this script as ./install.sh or by its full path, or set APOTHEM_SOURCE."
    fi
fi

# A fetched install swaps folders beside APOTHEM_HOME, so it stops first on
# any that a run stopped part-way left there (see check_leftovers). A local
# tree is run where it is and leaves APOTHEM_HOME alone.
if [ -z "$LOCAL_KIND" ]; then
    check_leftovers
fi

PY=""
LOCATOR=""
if [ -n "$LOCAL_TREE" ] && [ -f "${LOCAL_TREE}/src/apothem/hooks/lib/find-python.sh" ]; then
    LOCATOR="${LOCAL_TREE}/src/apothem/hooks/lib/find-python.sh"
fi
if [ -n "$LOCATOR" ]; then
    # shellcheck source=/dev/null
    . "$LOCATOR"
    PY="$(find_real_python 3 10 2>/dev/null || true)"
fi

if [ -z "$PY" ]; then
    for _cand in python3 python python3.14 python3.13 python3.12 python3.11 python3.10; do
        # Probe the path PATH resolves the name to, so a shim can be recognised
        # before it is run. Running a Store alias opens the Store page instead
        # of Python, so a candidate under a WindowsApps directory is skipped.
        # The prefix-strip test is the one find-python.sh uses; install.ps1
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
fi

[ -n "$PY" ] || die "No Python >= 3.10 found in PATH"
settle_python_form
PY_VERSION="$("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
ok "$PY ($PY_VERSION)"

# Prerequisite: CLI prerequisites importable ---------------------------------------
#
# The engine vendors yaml and jsonschema but imports click and rich from the
# host Python. A missing one is reported and offered for install: yes with
# --yes or APOTHEM_AUTO_INSTALL_DEPS=1, asked at a terminal, declined (with
# guidance) in a piped run, so the host never changes silently.
#
# The current folder must never shadow the engine's modules: `-c` and `-m`
# put it first on sys.path. Python 3.10 has no PYTHONSAFEPATH, and `-I` would
# drop PYTHONPATH and the user site too, so every start sets PYTHONSAFEPATH=1
# and runs a `-c` program that first drops a leading ''.
DROP_CWD_FROM_PATH="import sys; sys.path[:1] = [] if sys.path[:1] == [''] else sys.path[:1]"
ENGINE_PROGRAM="${DROP_CWD_FROM_PATH}; import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"
PIP_PROGRAM="${DROP_CWD_FROM_PATH}; import runpy; runpy.run_module('pip', run_name='__main__', alter_sys=True)"

probe_missing_deps() {
    _missing=""
    for _dep in $RUNTIME_DEPS; do
        if ! PYTHONSAFEPATH=1 "$PY" -c "${DROP_CWD_FROM_PATH}; import ${_dep}" >/dev/null 2>&1; then
            _missing="${_missing:+$_missing }${_dep}"
        fi
    done
    printf '%s' "$_missing"
}

# install_runtime_deps DEPS — install the missing prerequisites under $PY with
# pip; returns 0 when the install command succeeds. Probes pip first and warns
# (non-fatally) on no-pip / no-network / PEP-668-externally-managed failures so
# the caller can fall through to manual guidance.
install_runtime_deps() {
    if ! PYTHONSAFEPATH=1 "$PY" -c "$PIP_PROGRAM" --version >/dev/null 2>&1; then
        warn "pip is unavailable under ${PY} — install $* manually."
        return 1
    fi
    info "Installing $* under ${PY} (pip)"
    if PYTHONSAFEPATH=1 "$PY" -c "$PIP_PROGRAM" install "$@"; then
        ok "Installed $*"
        return 0
    fi
    warn "pip install failed — install $* manually."
    return 1
}

MISSING_DEPS="$(probe_missing_deps)"
if [ -n "$MISSING_DEPS" ]; then
    warn "Missing Python prerequisites under ${PY}: ${MISSING_DEPS}"
    _do_install=0
    if [ "$ASSUME_YES" = "1" ] || [ "${APOTHEM_AUTO_INSTALL_DEPS:-0}" = "1" ]; then
        _do_install=1
    elif [ -t 0 ]; then
        printf '  Install %s under %s now? [y/N] ' "$MISSING_DEPS" "$PY"
        read -r _reply || _reply=""
        case "$_reply" in y|Y|yes|YES) _do_install=1 ;; esac
    fi
    if [ "$_do_install" = "1" ]; then
        _specs=""
        for _dep in $MISSING_DEPS; do
            _specs="${_specs:+$_specs }$(dep_spec "$_dep")"
        done
        # intentional word-split: each requirement spec is a separate pip arg.
        # shellcheck disable=SC2086
        install_runtime_deps $_specs || true
        MISSING_DEPS="$(probe_missing_deps)"
    fi
fi
if [ -n "$MISSING_DEPS" ]; then
    _specs=""
    for _dep in $MISSING_DEPS; do
        _specs="${_specs:+$_specs }$(dep_spec "$_dep")"
    done
    die "Missing prerequisites under ${PY}: ${MISSING_DEPS}. Install with: ${PY} -m pip install ${_specs} — or re-run with --yes (or APOTHEM_AUTO_INSTALL_DEPS=1) to install automatically. See ${VENDORING_DOC} for the vendoring strategy."
fi
ok "Prerequisites present: ${RUNTIME_DEPS}"
echo

# Locate or fetch the bundled source ----------------------------------------------
#
# Source precedence: 1. APOTHEM_SOURCE, a local tree (nothing fetched or
# verified); 2. this script's own checkout, when run by path from its
# scripts/installer/ (the current folder and its parents are never used);
# 3. APOTHEM_REPO fetched at the resolved ref (latest release tag, or
# APOTHEM_REF) and verified before materializing.

bold "Locating Apothem source"

SOURCE=""
if [ "$LOCAL_KIND" = "explicit" ]; then
    SOURCE="$LOCAL_TREE"
    [ -n "$SOURCE" ] \
        || die "APOTHEM_SOURCE is not an apothem source tree: ${APOTHEM_SOURCE}"
    ok "Using explicit source: $SOURCE"
    info "Local source — skipping tag resolution and signature verification"
elif [ "$LOCAL_KIND" = "checkout" ]; then
    SOURCE="$LOCAL_TREE"
    ok "Using local checkout: $SOURCE"
    info "Local checkout — skipping tag resolution and signature verification"
fi

# sha256_of FILE — print FILE's SHA-256 hex digest with whichever of
# sha256sum (GNU) or shasum (macOS) is present; fail when neither is.
sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        return 1
    fi
}

case "$APOTHEM_VERIFY" in
    auto|release|signature|checksum) ;;
    *) die "APOTHEM_VERIFY must be 'auto', 'release', 'signature' or 'checksum' (got '${APOTHEM_VERIFY}')." ;;
esac

# Pick the verification path for a fetched source: `auto` takes the release
# path when cosign is on PATH, else the key-pinned tag check. A ref that is
# not a release tag has no archive, so it takes the clone path (refused
# unless APOTHEM_ALLOW_UNVERIFIED=1). An existing clone stays a clone, so its
# history and local work are kept.
VERIFY_MODE="$APOTHEM_VERIFY"
if [ -z "$SOURCE" ] && [ "$VERIFY_MODE" = "auto" ]; then
    if [ -n "$APOTHEM_REF" ] && ! is_release_tag "$APOTHEM_REF"; then
        VERIFY_MODE=signature
    elif is_apothem_clone "$APOTHEM_HOME"; then
        VERIFY_MODE=signature
        info "$APOTHEM_HOME is a git clone — updating it and checking the release tag's signature. To use the cosign-checked release archive instead, move the clone aside first."
    elif command -v cosign >/dev/null 2>&1; then
        VERIFY_MODE=release
        info "cosign found — installing the release archive once both the release tag's signature and cosign's check of its SHA-256 digest pass"
    else
        VERIFY_MODE=signature
        info "cosign not found — checking the release tag's signature only. Install cosign (${COSIGN_INSTALL_DOC}) to also check the release archive's signed SHA-256 digest."
    fi
fi
if [ -z "$SOURCE" ] && [ "$VERIFY_MODE" = "release" ]; then
    command -v cosign >/dev/null 2>&1 \
        || die "APOTHEM_VERIFY=release needs cosign on PATH (${COSIGN_INSTALL_DOC}). Install it, or set APOTHEM_VERIFY=signature to check the release tag against the maintainer key alone."
fi

# Checksum mode verifies nothing about who published the release, so it runs
# only with APOTHEM_ALLOW_UNVERIFIED=1, and says so before downloading.
CHECKSUM_CAVEAT="Checksum mode does not verify the release. SHA256SUMS comes from the same release as the archive, so a match only shows the download isn't damaged; anyone who can change the release's files can change both."
if [ -z "$SOURCE" ] && [ "$VERIFY_MODE" = "checksum" ]; then
    if [ "$APOTHEM_ALLOW_UNVERIFIED" != "1" ]; then
        die "${CHECKSUM_CAVEAT} Set APOTHEM_ALLOW_UNVERIFIED=1 as well to install this way anyway, or install gpg (and cosign) and run without APOTHEM_VERIFY=checksum."
    fi
    warn "${CHECKSUM_CAVEAT} Proceeding because APOTHEM_ALLOW_UNVERIFIED=1."
fi

# home_mode WHAT — decide what a swap into APOTHEM_HOME may do with what is
# there now, refusing what --yes has not allowed, and print the swap_in mode
# (keep or aside). WHAT names the new source ("the vX archive", "a clone of
# vX") for the messages. A dry run applies the same refusals, so it fails
# where the real run would: the entries a keep-mode swap would carry over are
# checked here as well.
home_mode() {
    if home_is_link; then
        die "Destination $APOTHEM_HOME is a symbolic link. Point APOTHEM_HOME at the folder it links to, then re-run."
    fi
    if ! exists "$APOTHEM_HOME"; then
        printf '%s\n' keep
        return 0
    fi
    ls -A "$APOTHEM_HOME" >/dev/null || die "Cannot read $APOTHEM_HOME."
    # Empty, or holding nothing but the engine's data: kept like an earlier
    # install, without --yes. A file at APOTHEM_HOME is neither.
    _hm_only_data=0
    if [ -d "$APOTHEM_HOME" ]; then
        _hm_only_data=1
        for _hm_entry in "$APOTHEM_HOME"/* "$APOTHEM_HOME"/.[!.]* "$APOTHEM_HOME"/..?*; do
            exists "$_hm_entry" || continue
            is_engine_data "${_hm_entry##*/}" || _hm_only_data=0
        done
    fi
    if [ "$_hm_only_data" = "1" ]; then
        carry_names "$(source_entries "$APOTHEM_HOME")" >/dev/null || exit 1
        printf '%s\n' keep
        return 0
    fi
    if is_apothem_clone "$APOTHEM_HOME"; then
        [ "$ASSUME_YES" = "1" ] \
            || die "Destination $APOTHEM_HOME is a git clone; refusing to replace it with $1, which would remove its history. Set APOTHEM_VERIFY=signature to update the clone, move it aside, or re-run with --yes."
        # git status reads the clone's index, so the clone's own settings,
        # submodules and attributes are checked first, as for an update in
        # place.
        clone_git_ok "$APOTHEM_HOME"
        check_clone_config "$APOTHEM_HOME"
        check_clone_modules "$APOTHEM_HOME"
        check_clone_gitlinks "$APOTHEM_HOME"
        check_clone_attributes "$APOTHEM_HOME"
        if clone_has_local_work "$APOTHEM_HOME"; then
            die "$APOTHEM_HOME is a git clone with local work that replacing it would lose (changes, stashes, unpushed commits, or untracked files in its source tree). Commit and push that work, or move it elsewhere, then re-run."
        fi
        carry_names "$(source_entries "$APOTHEM_HOME")" >/dev/null || exit 1
        aside_name >/dev/null || exit 1
        if [ "$DRY_RUN" = "1" ]; then
            warn "Would replace the git clone at $APOTHEM_HOME with $1; the files the clone does not track (the engine's backups/ and state/ among them) would move into the new install, and the clone's own tree would be moved to a sibling folder named $(basename "$APOTHEM_HOME").before-apothem-<time> (--yes)" >&2
        else
            warn "Replacing the git clone at $APOTHEM_HOME with $1; the files the clone does not track (the engine's backups/ and state/ among them) move into the new install, and the clone's own tree will be moved to a sibling folder named $(basename "$APOTHEM_HOME").before-apothem-<time> (--yes)" >&2
        fi
        printf '%s\n' keep-clone
    elif is_apothem_source "$APOTHEM_HOME"; then
        case "$1" in
            "a clone of"*)
                [ "$ASSUME_YES" = "1" ] \
                    || die "Destination $APOTHEM_HOME is a release-archive install, not a git clone; refusing to replace it. Install cosign and gpg and re-run to update it in place, or re-run with --yes to switch it to a clone (its backups/ and state/ are kept)."
                carry_names "$(source_entries "$APOTHEM_HOME")" >/dev/null || exit 1
                if [ "$DRY_RUN" = "1" ]; then
                    warn "Would switch the release-archive install at $APOTHEM_HOME to $1; the engine's backups/, state/ and other data would be kept (--yes)" >&2
                else
                    warn "Switching the release-archive install at $APOTHEM_HOME to $1; the engine's backups/, state/ and other data are kept (--yes)" >&2
                fi ;;
            *)
                carry_names "$(source_entries "$APOTHEM_HOME")" >/dev/null || exit 1
                if [ "$DRY_RUN" = "1" ]; then
                    info "Would update the earlier install at $APOTHEM_HOME to $1" >&2
                else
                    info "Updating the earlier install at $APOTHEM_HOME to $1" >&2
                fi ;;
        esac
        printf '%s\n' keep
    else
        [ "$ASSUME_YES" = "1" ] \
            || die "Destination $APOTHEM_HOME is not empty and holds no Apothem install; refusing to replace it. Move it aside, point APOTHEM_HOME at another directory, or re-run with --yes to have it moved aside for you."
        aside_name >/dev/null || exit 1
        if [ "$DRY_RUN" = "1" ]; then
            warn "$APOTHEM_HOME holds no Apothem install; it would be moved, unchanged, to a sibling folder named $(basename "$APOTHEM_HOME").before-apothem-<time> (--yes)" >&2
        else
            warn "$APOTHEM_HOME holds no Apothem install; it will be moved, unchanged, to a sibling folder named $(basename "$APOTHEM_HOME").before-apothem-<time> (--yes)" >&2
        fi
        printf '%s\n' aside
    fi
}

# Archive modes: install the release's platform archive after checking its
# SHA-256 against the release's SHA256SUMS. They replace the git clone below.
# `release` checks two things before it trusts the digest, and both must
# pass: the release tag is signed by the maintainer key, and cosign shows
# that the release workflow signed SHA256SUMS in a run on the commit that tag
# points at. cosign itself checks that commit, against the GitHub workflow
# SHA its verified certificate carries, so no other code reads the bundle.
# Either check alone is not enough: anyone who can push a tag can make the
# workflow sign a release, and a signed tag says nothing about the archive.
if [ -z "$SOURCE" ] && { [ "$VERIFY_MODE" = "checksum" ] || [ "$VERIFY_MODE" = "release" ]; }; then
    command -v curl >/dev/null 2>&1 || die "curl not found in PATH — needed to download the release archive"
    if [ -z "$APOTHEM_REF" ]; then
        command -v git >/dev/null 2>&1 || die "git not found in PATH — needed to resolve the latest release tag"
        info "Resolving latest release tag from ${APOTHEM_REPO}"
        APOTHEM_REF="$(resolve_latest_tag "$APOTHEM_REPO")"
        [ -n "$APOTHEM_REF" ] \
            || die "No vMAJOR.MINOR.PATCH release tag found at ${APOTHEM_REPO}. Pin one with APOTHEM_REF, or set APOTHEM_SOURCE to a local checkout."
    fi
    is_release_tag "$APOTHEM_REF" \
        || die "APOTHEM_VERIFY=${VERIFY_MODE} needs a vMAJOR.MINOR.PATCH release tag; got '${APOTHEM_REF}'. Pin one with APOTHEM_REF."
    # What may happen to APOTHEM_HOME is settled before anything downloads.
    _ck_mode="$(home_mode "the ${APOTHEM_REF} archive")"
    case "$(uname -s 2>/dev/null)" in
        Darwin) _ck_platform=darwin ;;
        *)      _ck_platform=linux ;;
    esac
    _ck_name="apothem-${APOTHEM_REF}-${_ck_platform}.tar.gz"
    # Remove the downloads and the extraction on every way out of this block:
    # a die, a failing command under set -e, or an interrupt. A dry run keeps
    # the trap, since the engine previews from the extracted tree.
    trap on_exit EXIT
    trap_signals_to_exit
    _ck_tmp="$(mktemp -d)"
    _ck_tmp="$(abs_path "$_ck_tmp")"
    _ck_stage=""
    _ck_tag_commit=""
    if [ "$VERIFY_MODE" = "release" ]; then
        command -v git >/dev/null 2>&1 || die "git not found in PATH — needed to check the ${APOTHEM_REF} release tag"
        require_gpg
        bold "Verifying the ${APOTHEM_REF} release tag"
        # Only the tag and the commit it points at are fetched, into a
        # throwaway repository; the source itself comes from the archive.
        ngit init --quiet --bare "${_ck_tmp}/tag.git" \
            || die "Could not create a scratch repository to check the ${APOTHEM_REF} tag"
        git -c core.longpaths=true -C "${_ck_tmp}/tag.git" fetch --quiet --depth=1 --no-tags "$APOTHEM_REPO" \
            "+refs/tags/${APOTHEM_REF}:refs/tags/${APOTHEM_REF}" >"${_ck_tmp}/fetch.log" 2>&1 \
            || die "Could not fetch the ${APOTHEM_REF} tag from ${APOTHEM_REPO}: $(tail -n 2 "${_ck_tmp}/fetch.log" | LC_ALL=C tr '\n' ' ')"
        check_release_tag "${_ck_tmp}/tag.git" "$APOTHEM_REF" 0
        _ck_tag_commit="$TAG_COMMIT"
    fi
    info "Downloading ${_ck_name} and SHA256SUMS from the ${APOTHEM_REF} release"
    # shellcheck disable=SC2086
    curl -fsSL $CURL_PROTO "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/${_ck_name}" -o "${_ck_tmp}/${_ck_name}" \
        || die "Could not download ${_ck_name} from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}"
    # shellcheck disable=SC2086
    curl -fsSL $CURL_PROTO "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS" -o "${_ck_tmp}/SHA256SUMS" \
        || die "Could not download SHA256SUMS from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}"
    if [ "$VERIFY_MODE" = "release" ]; then
        # The certificate identity is exact, never a pattern: a regular
        # expression would also match a forged subject that merely contains
        # the repository path. It names the tag being installed, so a bundle
        # signed for another release does not verify here, and
        # --certificate-github-workflow-sha makes cosign require that the
        # certificate it verified was issued to a run on the signed tag's
        # commit.
        _ck_identity="https://github.com/${COSIGN_IDENTITY_REPO}/.github/workflows/release.yml@refs/tags/${APOTHEM_REF}"
        # Early releases published the same Sigstore bundle as SHA256SUMS.sig
        # (scripts/release/verify-provenance.sh accepts both names).
        # shellcheck disable=SC2086
        curl -fsSL $CURL_PROTO "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS.cosign.bundle" -o "${_ck_tmp}/SHA256SUMS.cosign.bundle" 2>/dev/null \
            || curl -fsSL $CURL_PROTO "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS.sig" -o "${_ck_tmp}/SHA256SUMS.cosign.bundle" \
            || die "Could not download SHA256SUMS.cosign.bundle, or SHA256SUMS.sig as early releases name it, from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}. Set APOTHEM_VERIFY=signature to check the release tag alone."
        if cosign verify-blob \
            --bundle "${_ck_tmp}/SHA256SUMS.cosign.bundle" \
            --certificate-identity "$_ck_identity" \
            --certificate-oidc-issuer "$COSIGN_OIDC_ISSUER" \
            --certificate-github-workflow-sha "$_ck_tag_commit" \
            "${_ck_tmp}/SHA256SUMS" >"${_ck_tmp}/cosign.log" 2>&1; then
            ok "cosign: SHA256SUMS is signed by the ${APOTHEM_REF} release workflow, in a run on the tag's commit ${_ck_tag_commit}"
        else
            _ck_said="$(tail -n 3 "${_ck_tmp}/cosign.log" | LC_ALL=C tr '\n' ' ')"
            die "cosign could not confirm that the ${APOTHEM_REF} release workflow (${_ck_identity}) signed SHA256SUMS in a run on the signed tag's commit ${_ck_tag_commit} (possible tampering). Aborting before anything is extracted. cosign said: ${_ck_said} If cosign could not reach Sigstore (offline or behind a proxy), set APOTHEM_VERIFY=signature to check the release tag alone."
        fi
    fi
    _ck_expected="$(awk -v n="$_ck_name" '$2 == n || $2 == "*" n { print $1; exit }' "${_ck_tmp}/SHA256SUMS")"
    [ -n "$_ck_expected" ] || die "SHA256SUMS for ${APOTHEM_REF} lists no ${_ck_name}"
    _ck_actual="$(sha256_of "${_ck_tmp}/${_ck_name}")" \
        || die "Neither sha256sum nor shasum is available to check ${_ck_name}"
    if [ "$_ck_actual" != "$_ck_expected" ]; then
        die "${_ck_name} does not match the release's SHA256SUMS (expected ${_ck_expected}, got ${_ck_actual}). Aborting before anything is extracted."
    fi
    ok "${_ck_name} matches the release's SHA256SUMS"
    # The release archive roots every file under apothem-<tag>/ (see
    # scripts/build_release_tarball.py). A real install extracts it into a
    # fresh staging directory beside APOTHEM_HOME, so swap_in's moves are
    # renames on one filesystem; a dry run extracts it into the scratch
    # directory and leaves APOTHEM_HOME alone.
    if [ "$DRY_RUN" = "1" ]; then
        _ck_stage="${_ck_tmp}/extract"
        mkdir "$_ck_stage" || die "Could not create a directory to extract ${_ck_name} into"
    else
        mkdir -p "$(dirname "$APOTHEM_HOME")" \
            || die "Could not create the parent directory of $APOTHEM_HOME"
        _ck_stage="$(make_staging extract)" \
            || die "Could not create a staging directory beside $APOTHEM_HOME"
    fi
    tar -xzf "${_ck_tmp}/${_ck_name}" -C "$_ck_stage" \
        || die "Could not extract ${_ck_name}"
    _ck_root="${_ck_stage}/apothem-${APOTHEM_REF}"
    is_apothem_source "$_ck_root" \
        || die "${_ck_name} does not hold an apothem source under apothem-${APOTHEM_REF}/"
    if [ "$DRY_RUN" = "1" ]; then
        SOURCE="$_ck_root"
        ok "Source ready at $SOURCE (release archive ${APOTHEM_REF}; dry run, so $APOTHEM_HOME is not changed)"
    else
        record_source_entries "$_ck_root"
        swap_in "$_ck_root" "$_ck_mode"
        rm -rf "$_ck_tmp" "$_ck_stage"
        _ck_tmp=""
        _ck_stage=""
        SOURCE="$APOTHEM_HOME"
        ok "Source ready at $SOURCE (release archive ${APOTHEM_REF})"
    fi
    echo
fi

if [ -z "$SOURCE" ]; then
    command -v git >/dev/null 2>&1 || die "git not found in PATH — needed to fetch ${APOTHEM_REPO}"

    # Resolve the ref to fetch. An unset APOTHEM_REF defaults to the latest
    # released tag (verified-by-default trust model) rather than the moving
    # `main` branch. An explicit APOTHEM_REF is honored verbatim (a pinned tag,
    # a SHA, or "main" for the moving branch).
    if [ -z "$APOTHEM_REF" ]; then
        info "Resolving latest release tag from ${APOTHEM_REPO}"
        APOTHEM_REF="$(resolve_latest_tag "$APOTHEM_REPO")"
        if [ -z "$APOTHEM_REF" ]; then
            die "No vMAJOR.MINOR.PATCH release tag found at ${APOTHEM_REPO}. Pin a ref explicitly with APOTHEM_REF=<tag|main>, or set APOTHEM_SOURCE to a local checkout."
        fi
        ok "Latest release tag: ${APOTHEM_REF}"
    fi
    if is_release_tag "$APOTHEM_REF" && [ "$APOTHEM_ALLOW_UNVERIFIED" != "1" ]; then
        require_gpg
    fi

    # An existing clone is fetched, its tag is checked, and only then is it
    # checked out, so a failed check leaves the clone as it was. Otherwise
    # the clone is made in a fresh staging directory, checked and checked out
    # there, and swapped in by swap_in, which keeps the engine's backups/ and
    # state/ from an earlier archive install. A dry run clones into a scratch
    # directory and leaves APOTHEM_HOME alone; on an existing clone it first
    # makes the same read-only checks of the clone as a real run, so it
    # stops where the real run would.
    _cl_stage=""
    if is_apothem_clone "$APOTHEM_HOME" && [ "$DRY_RUN" != "1" ]; then
        info "Updating existing clone at $APOTHEM_HOME (ref: ${APOTHEM_REF})"
        # Every git call on the clone from here runs with its hooks off.
        trap on_exit EXIT
        trap_signals_to_exit
        HOOKS_OFF="$(mktemp -d)" || die "Could not create a scratch directory for the update"
        check_clone_setup "$APOTHEM_HOME"
        cgit -C "$APOTHEM_HOME" fetch --quiet --tags origin \
            || die "Could not fetch from the origin of $APOTHEM_HOME. If a local tag differs from origin's, delete it with 'git -C $APOTHEM_HOME tag -d <tag>', then re-run."
        bold "Verifying source signature"
        check_fetched_ref "$APOTHEM_HOME"
        require_clean_clone "$APOTHEM_HOME"
        checkout_ref "$APOTHEM_HOME"
        remove_source_caches "$APOTHEM_HOME"
        _cl_tree="$APOTHEM_HOME"
    else
        if is_apothem_clone "$APOTHEM_HOME"; then
            # Only a dry run gets here with a clone at APOTHEM_HOME.
            check_clone_setup "$APOTHEM_HOME"
            _cl_mode="keep"
        else
            _cl_mode="$(home_mode "a clone of ${APOTHEM_REF}")"
        fi
        trap on_exit EXIT
        trap_signals_to_exit
        if [ "$DRY_RUN" = "1" ]; then
            _cl_stage="$(mktemp -d)" || die "Could not create a scratch directory for the dry run"
        else
            mkdir -p "$(dirname "$APOTHEM_HOME")" \
                || die "Could not create the parent directory of $APOTHEM_HOME"
            _cl_stage="$(make_staging clone)" \
                || die "Could not create a staging directory beside $APOTHEM_HOME"
        fi
        _cl_tree="$(abs_path "${_cl_stage}/apothem")"
        info "Cloning ${APOTHEM_REPO}"
        # Full clone (no --single-branch) so both tags and branches are
        # checkout-able from the placed tree, then pin to the resolved ref.
        # core.longpaths (Git for Windows; other gits ignore it) lets the
        # clone write its pack files under a long staging folder.
        ngit -c core.longpaths=true clone --quiet --no-checkout "$APOTHEM_REPO" "$_cl_tree" \
            || die "git clone failed for $APOTHEM_REPO"
        bold "Verifying source signature"
        check_fetched_ref "$_cl_tree"
        checkout_ref "$_cl_tree"
    fi
    is_apothem_source "$_cl_tree" || die "Fetched tree is not an apothem source: $_cl_tree"
    if [ -z "$_cl_stage" ]; then
        SOURCE="$APOTHEM_HOME"
        ok "Source ready at $SOURCE (ref: ${APOTHEM_REF})"
    elif [ "$DRY_RUN" = "1" ]; then
        SOURCE="$_cl_tree"
        ok "Source ready at $SOURCE (ref: ${APOTHEM_REF}; dry run, so $APOTHEM_HOME is not changed)"
    else
        swap_in "$_cl_tree" "$_cl_mode"
        rm -rf "$_cl_stage"
        _cl_stage=""
        SOURCE="$APOTHEM_HOME"
        ok "Source ready at $SOURCE (ref: ${APOTHEM_REF})"
    fi
    echo
fi
[ -n "$LOCAL_KIND" ] || warn_home_access
# Absolute, so no PYTHONPATH entry below can name the current folder.
SRC_PATH="$(abs_path "${SOURCE}/src")"
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
#
# The entries are joined with PY_PATHSEP and written in the form the chosen
# Python reads (see settle_python_form and native_path): ":" and POSIX paths
# for a POSIX Python, ";" and Windows paths for a Windows one.
_ep_vendor="$(native_path "${SRC_PATH}/apothem/_vendor")" \
    || die "cygpath could not give the Windows path (a drive or network path) of ${SRC_PATH}/apothem/_vendor, which ${PY} needs. Check that cygpath works in this shell, or run install.ps1 from PowerShell instead."
_ep_src="$(native_path "${SRC_PATH}")" \
    || die "cygpath could not give the Windows path (a drive or network path) of ${SRC_PATH}, which ${PY} needs. Check that cygpath works in this shell, or run install.ps1 from PowerShell instead."
ENGINE_PYPATH="${_ep_vendor}${PY_PATHSEP}${_ep_src}"
echo

# Profile setup ------------------------------------------------------------------

# A first run with no profile creates one from the example and carries on to
# materialize and verify in the same run (the engine only warns about the
# placeholder identity). A dry run writes nothing, so it previews with the
# example profile in place instead of copying it.
bold "Profile setup"
ENGINE_PROFILE="$PROFILE"
if [ -f "$PROFILE" ]; then
    ok "Found profile at $PROFILE"
else
    EXAMPLE_PATH="${SOURCE}/src/apothem/schemas/profile.example.yaml"
    [ -f "$EXAMPLE_PATH" ] \
        || die "Could not locate profile.example.yaml — create $PROFILE manually before continuing"
    if [ "$DRY_RUN" = "1" ]; then
        info "No profile at $PROFILE — the dry run previews with the example profile and writes nothing"
        ENGINE_PROFILE="$EXAMPLE_PATH"
    else
        info "No profile found at $PROFILE — creating it from the example"
        mkdir -p "$(dirname "$PROFILE")"
        cp "$EXAMPLE_PATH" "$PROFILE"
        ok "Created $PROFILE from the example profile"
        warn "Its identity fields are placeholders. Edit $PROFILE, then run 'apothem update --harness ${HARNESS}' to apply your identity."
    fi
fi
echo

# Materialize harness ------------------------------------------------------------
#
# Run the bundled engine directly from the source tree — self-contained, no
# package installation: the engine and its vendored dependencies resolve
# because the tree's vendor and src/ directories are prepended to PYTHONPATH.

bold "Installing harness: ${HARNESS}"
# Accumulate opt-in engine flags as positional parameters; POSIX sh has no
# arrays, so `set --` builds the argv that is then expanded with "$@".
set --
[ "$CLEAN" = "1" ]      && set -- "$@" --clean
[ "$DRY_RUN" = "1" ]    && set -- "$@" --dry-run
[ "$ASSUME_YES" = "1" ] && set -- "$@" --yes
PYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" \
    "$PY" -c "$ENGINE_PROGRAM" install --harness "$HARNESS" --profile "$ENGINE_PROFILE" "$@"
if [ "$DRY_RUN" = "1" ]; then
    ok "Harness ${HARNESS} preview generated (dry-run)"
else
    ok "Harness ${HARNESS} installed"
fi
echo

if [ "$DRY_RUN" = "1" ]; then
    echo
    bold "Dry-run complete — no changes were made."
    exit 0
fi

# Verify -------------------------------------------------------------------------

if [ "${APOTHEM_SKIP_VERIFY:-0}" = "1" ]; then
    warn "APOTHEM_SKIP_VERIFY=1 — skipping verification"
else
    bold "Verifying installation"
    if PYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" \
        "$PY" -c "$ENGINE_PROGRAM" verify --harness "$HARNESS"; then
        ok "verify passed"
    else
        warn "verify reported issues — run the verify command below for details"
    fi
fi
echo

# Entry-point shim ---------------------------------------------------------------
#
# Place an `apothem` command on PATH so the operator runs `apothem <command>`
# instead of the verbose self-contained form. The shim forwards to the bundled
# engine with the vendored PYTHONPATH (mirroring the self-contained banner). The
# POSIX user-bin convention is $HOME/.local/bin (override with APOTHEM_BIN_DIR).
# When the bin directory is not already on PATH, the banner prints the exact
# line to add it and the shim's full path (or, with no shim, the self-contained
# form), so it never advertises a bare `apothem` command the operator cannot
# yet resolve.

BIN_DIR="${APOTHEM_BIN_DIR:-$HOME/.local/bin}"
SHIM="${BIN_DIR}/apothem"
PY_ABS="$(command -v "$PY" 2>/dev/null || printf '%s' "$PY")"
SHIM_OK=0
if mkdir -p "$BIN_DIR" 2>/dev/null; then
    if {
        printf '%s\n' '#!/bin/sh'
        printf '%s\n' '# Apothem entry-point shim (generated by install.sh).'
        printf '%s\n' '# The current folder is kept off sys.path, so its modules never shadow the engine:'
        printf '%s\n' '# only the absolute entries of PYTHONPATH are passed on, after the engine paths.'
        printf 'apothem_pp=%s\n' "$(sq "$ENGINE_PYPATH")"
        printf 'apothem_sep=%s\n' "$(sq "$PY_PATHSEP")"
        cat <<'SHIM_BODY'
# apothem_sep is the separator the engine's Python reads: ":" for a POSIX
# Python, ";" for a Windows one, where only drive and network paths are kept.
apothem_rest="${PYTHONPATH:-}"
while [ -n "$apothem_rest" ]; do
    apothem_entry="${apothem_rest%%"$apothem_sep"*}"
    case "$apothem_rest" in
        *"$apothem_sep"*) apothem_rest="${apothem_rest#*"$apothem_sep"}" ;;
        *) apothem_rest="" ;;
    esac
    if [ "$apothem_sep" = ";" ]; then
        case "$apothem_entry" in
            [A-Za-z]:[\\/]* | [\\/][\\/]*) apothem_pp="${apothem_pp};${apothem_entry}" ;;
        esac
    else
        case "$apothem_entry" in
            /*) apothem_pp="${apothem_pp}:${apothem_entry}" ;;
        esac
    fi
done
SHIM_BODY
        printf 'PYTHONSAFEPATH=1 PYTHONPATH="$apothem_pp" exec %s -c %s "$@"\n' \
            "$(sq "$PY_ABS")" "$(sq "$ENGINE_PROGRAM")"
    } >"$SHIM" 2>/dev/null; then
        if chmod +x "$SHIM" 2>/dev/null; then SHIM_OK=1; fi
    fi
fi
if [ "$SHIM_OK" = "1" ]; then
    ok "Installed apothem command: $SHIM"
else
    warn "Could not place an apothem shim in $BIN_DIR — use the self-contained form below."
fi

SHIM_ON_PATH=0
if [ "$SHIM_OK" = "1" ]; then
    case ":${PATH}:" in
        *":${BIN_DIR}:"*) SHIM_ON_PATH=1 ;;
        *) SHIM_ON_PATH=0 ;;
    esac
fi
echo

# Next-step banner ---------------------------------------------------------------

bold "Installation complete."
if [ "$SHIM_ON_PATH" = "1" ]; then
    cat <<EOF

The 'apothem' command is on your PATH.

Recommended first step — the guided setup (profile -> preview -> install):
  apothem quickstart

Or run individual commands:
  apothem harnesses list        # list all harnesses
  apothem doctor                # check system health
  apothem profile edit          # edit your profile

Optional — enable <TAB> shell completion (opt-in; appends to your shell rc):
  apothem completion bash >> ~/.bashrc     # bash
  apothem completion zsh  >> ~/.zshrc      # zsh
  apothem completion fish > ~/.config/fish/completions/apothem.fish  # fish

EOF
else
    if [ "$SHIM_OK" = "1" ]; then
        info "Add ${BIN_DIR} to your PATH, then run the guided setup: apothem quickstart"
        printf '    export PATH=%s:"$PATH"\n' "$(sq "$BIN_DIR")"
        echo
        RUN_HEADER="Until then, run the apothem command by its full path:"
        RUN_CMD="$(sq "$SHIM")"
    else
        RUN_HEADER="Run the engine from the bundled source (self-contained — no package installation; the current folder is kept off sys.path):"
        RUN_CMD="PYTHONSAFEPATH=1 PYTHONPATH=$(sq "$ENGINE_PYPATH") $(sq "$PY") -c $(sq "$ENGINE_PROGRAM")"
    fi
    cat <<EOF
${RUN_HEADER}
  ${RUN_CMD} <command>

Recommended first step — the guided setup (profile -> preview -> install):
  ${RUN_CMD} quickstart

Or run individual commands:
  ${RUN_CMD} harnesses list   # list harnesses
  ${RUN_CMD} doctor           # system health
  ${RUN_CMD} profile edit     # edit profile

Optional — once the 'apothem' command is on your PATH, enable <TAB> shell
completion (opt-in; appends to your shell rc):
  apothem completion bash >> ~/.bashrc   # or zsh / fish

EOF
fi
