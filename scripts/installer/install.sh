#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Place the bundled Apothem source tree (self-contained — no
#          package installation) and materialize harness configuration by
#          running `python -m apothem` directly from that tree.
# Contract: Idempotent on rerun (a re-run fetches an existing clone, checks
#           the tag, and only then checks it out, then re-materializes).
#           Exits 0 on success, non-zero on failure.
#           POSIX sh only (no bashisms): the documented `curl … | sh`
#           one-liner runs under dash/ash on Debian/Ubuntu/Alpine.
#
# Trust model (tag-pinned, verified-by-default):
#   With no APOTHEM_REF set, the installer resolves the latest released
#   vMAJOR.MINOR.PATCH tag and installs THAT release — the moving `main`
#   branch is no longer the default. How the release is checked depends on
#   APOTHEM_VERIFY, whose default `auto` picks one of two paths:
#     - cosign on PATH ("release"): two checks, both required. The release
#       tag must be signed by the maintainer key (below), and the signed tag
#       must be the one named for that release. cosign must then show that the
#       release workflow signed the release's SHA256SUMS and, through its
#       --certificate-github-workflow-sha check, that the certificate it
#       verified was issued to a run on the commit that tag points at. The
#       installer does not read the certificate itself. The platform
#       archive's SHA-256 must then match SHA256SUMS. Needs git, gpg and
#       cosign.
#     - no cosign ("signature"), or APOTHEM_HOME already a git clone: clone or
#       fetch the repository and check the tag with `git verify-tag`. Needs
#       git and gpg.
#   Either way the tag signature must be valid AND made by the maintainer key
#   published in SECURITY.md (fingerprint
#   5C8998F9F241720445D3F28B70396FED9C634163); a key the local keyring merely
#   trusts is not enough. A signed tag object that names another release
#   (a signed tag re-pointed at this name) is refused, and
#   APOTHEM_ALLOW_UNVERIFIED does not bypass that. A signed git tag names its
#   commit by SHA-1; the release path adds the SHA-256 digest that cosign
#   checks.
#   A failed check ABORTS the install before APOTHEM_HOME changes and before
#   any config is written. An existing clone is fetched and its tag is checked
#   BEFORE the clone is checked out, so a failed check leaves the clone as it
#   was; changes to tracked files, or local changes that the checkout would
#   overwrite, stop the update instead of being lost. The new source is
#   otherwise built and checked in a folder beside APOTHEM_HOME and swapped in
#   only when every check passed.
#   Explicit opt-outs:
#     - APOTHEM_REF=main           checks out the moving branch on request
#                                  (together with APOTHEM_ALLOW_UNVERIFIED=1).
#     - APOTHEM_ALLOW_UNVERIFIED=1 downgrades an unsigned or unverifiable tag,
#                                  or one signed by another key, on the clone
#                                  path to a loud warning and proceeds
#                                  (air-gapped or local use, or a release that
#                                  predates tag signing). Because it lets such
#                                  a tag through, the re-pointed-tag check
#                                  protects only tags that carry the
#                                  maintainer key's signature. The release
#                                  path never downgrades.
#     - APOTHEM_VERIFY=checksum    needs APOTHEM_ALLOW_UNVERIFIED=1. Checksum
#                                  mode does not verify the release.
#                                  SHA256SUMS comes from the same release as
#                                  the archive, so a match only shows the
#                                  download isn't damaged; anyone who can
#                                  change the release's files can change both.
#   The APOTHEM_SOURCE local-checkout path fetches nothing, so it skips tag
#   resolution and verification — it prints the source it is running and
#   proceeds.
#
# What happens to APOTHEM_HOME when the install replaces it:
#   - An earlier Apothem install keeps everything that is not part of its
#     source tree (backups, state, plans, memory and other engine data).
#   - A folder that holds no Apothem install is refused unless --yes is given;
#     with --yes it is moved, unchanged, to
#     <APOTHEM_HOME>.before-apothem-<time> and the install starts fresh.
#   - A folder that holds only the engine's data (backups, state, plans,
#     memory, contexts, learning, providers) is kept, like an earlier install.
#   - A git clone is replaced by a release archive only with --yes, and never
#     while it holds local work (changes, stashes, unpushed commits, or
#     untracked files in its source tree). Its own tree (history and source)
#     is then moved to <APOTHEM_HOME>.before-apothem-<time>, not deleted.
#   - A git clone of anything other than an Apothem source is treated like
#     any other folder that holds no Apothem install.
#   - Before an existing clone is fetched, the update stops when the clone
#     hides changes from git (assume-unchanged or skip-worktree files), when
#     its work tree is not APOTHEM_HOME, or when its own git config names a
#     program for git to run or pulls in other config (gpg.program,
#     gpg.openpgp.program, core.fsmonitor, core.hooksPath, include.*,
#     includeIf.*). Every git command on the clone runs with its hooks off.
#   - An entry to keep whose name has a space or another special character
#     stops the install; move it out of APOTHEM_HOME first.
#   - A symbolic link at APOTHEM_HOME is refused (point APOTHEM_HOME at the
#     folder the link leads to), except when it leads to an existing clone
#     that is updated in place.
#   - A failure or interrupt puts the earlier install back unchanged.
#
# Usage (recommended — tag-pinned, verified):
#     # default: resolves and verifies the latest signed release tag
#     curl -fsSL https://apothem.ahmedgad.com/install.sh | sh
#     # explicit pin to a known tag (also verified):
#     APOTHEM_REF=vMAJOR.MINOR.PATCH sh scripts/installer/install.sh
#
# Usage (inspect-first — the one-liner trusts this bootstrap script on
# first use; the fetched source is always signature-verified either way):
#     curl -fsSL -o install.sh https://apothem.ahmedgad.com/install.sh
#     less install.sh   # review, then run:
#     sh install.sh
#
# Usage (local install — from a cloned checkout):
#     sh scripts/installer/install.sh
#
# CLI flags (pass-through to the engine):
#     --clean, --fresh  Back up and remove the bounded config set, then
#                       materialize fresh.
#     --dry-run         Preview only; write nothing. The source is fetched
#                       and checked in a temporary directory, the same
#                       refusals apply as in a real run, and APOTHEM_HOME is
#                       left as it is.
#     --yes             Non-interactive; skip per-target confirmation prompts.
#                       Also authorizes replacing an existing git clone with
#                       a release archive, and moving a folder that holds no
#                       Apothem install aside to
#                       <APOTHEM_HOME>.before-apothem-<time>.
#
# Environment overrides:
#     APOTHEM_HOME              Install destination for the source tree
#                              (default: $HOME/.apothem)
#     APOTHEM_REPO             Git remote to clone
#                              (default: https://github.com/ahmed-g-gad/apothem)
#     APOTHEM_REF              Git ref to check out. Unset = resolve the latest
#                              vMAJOR.MINOR.PATCH tag. Set to a tag to pin, or
#                              to "main" for the moving branch.
#     APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a tag-verification failure
#                              (unsigned, unverifiable, or signed by another
#                              key) on the clone path from a fatal abort to a
#                              loud warning and proceed, and allow
#                              APOTHEM_VERIFY=checksum. It never relaxes the
#                              release path or the check that the signed tag
#                              names the release, but since it lets an
#                              unsigned tag, or one signed by another key,
#                              through, that check protects only tags that
#                              carry the maintainer key's signature.
#     APOTHEM_VERIFY           "auto" (default) uses "release" when cosign is
#                              on PATH and APOTHEM_HOME is not a git clone, and
#                              "signature" otherwise.
#                              "release" installs the platform archive once
#                              the tag carries the maintainer key's signature
#                              and names the release, cosign shows the release
#                              workflow signed SHA256SUMS in a run on the
#                              tag's commit, and the archive's SHA-256 matches
#                              it (needs cosign and gpg). "signature" clones
#                              (or fetches) and checks the tag's GPG signature
#                              against the pinned maintainer key (needs gpg).
#                              "checksum" installs the archive after the
#                              SHA-256 check alone and needs
#                              APOTHEM_ALLOW_UNVERIFIED=1: it does not verify
#                              the release, because SHA256SUMS comes from the
#                              same release as the archive.
#     APOTHEM_RELEASE_BASE     Release download base for the archive modes
#                              (default: <APOTHEM_REPO>/releases/download).
#     APOTHEM_SOURCE           Explicit local source tree to use instead of
#                              cloning (a checkout containing src/apothem).
#                              Skips tag resolution and verification.
#     APOTHEM_HARNESS          Harness to install (default: claude-code)
#     APOTHEM_PROFILE          Path to shared profile YAML
#     APOTHEM_SKIP_VERIFY      If "1", skip post-install verify
#     APOTHEM_AUTO_INSTALL_DEPS If "1", install the missing click / rich
#                              prerequisites automatically (pip) without prompting.

set -eu

# git reads these from the environment and would then work on another
# repository, index or object store than the one each command names, swap
# objects through replace refs, take extra configuration, or run its helper
# programs and templates from elsewhere; none of them may reach the
# installer's git commands.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE \
    GIT_REPLACE_REF_BASE GIT_CEILING_DIRECTORIES GIT_CONFIG_PARAMETERS \
    GIT_CONFIG_COUNT GIT_EXEC_PATH GIT_TEMPLATE_DIR
GIT_NO_REPLACE_OBJECTS=1
export GIT_NO_REPLACE_OBJECTS

# keep_full_pythonpath VALUE — print the entries of the PYTHONPATH value
# VALUE that are full paths, joined the way Python splits them. Python turns
# an empty or relative entry (":/x", "/x:", ".") into the current folder,
# ahead of site-packages, so a sitecustomize.py, click.py or apothem/ there
# would run in place of the real module. On POSIX an entry is kept only when
# it starts with "/". Under Git Bash, MSYS or Cygwin the Python is a Windows
# one that splits PYTHONPATH on ";": there an entry is kept only when it is a
# drive path ("C:\x", "C:/x") or a network path ("\\server\x", "//server/x"),
# so a rooted "\lib" and a drive-relative "C:rel" are dropped. Every Python
# this script starts gets only the kept entries.
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
                    Apothem install aside to
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
tree is then moved to <APOTHEM_HOME>.before-apothem-<time>. A clone of
anything other than Apothem counts as a folder with no Apothem install. An
existing clone is not updated when it hides changes from git, when its work
tree is elsewhere, or when its own git config names a program for git to
run; its hooks never run during the update. An entry
to keep whose name has a space or another special character stops the
install until it is moved out. A symbolic link at APOTHEM_HOME is refused,
except when it leads to an existing clone that is updated in place. A
failure or interrupt puts the earlier install back unchanged.

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

# cgit ARGS — run git with ARGS. Once HOOKS_OFF names an empty folder (an
# existing clone is being updated in place), git runs with core.hooksPath
# pointing at it, so none of the clone's hooks run during the update.
HOOKS_OFF=""
cgit() {
    if [ -n "$HOOKS_OFF" ]; then
        git -c core.hooksPath="$HOOKS_OFF" "$@"
    else
        git "$@"
    fi
}

# verify_tag DIR REF — verify the checked-out tag's signature in DIR. Returns 0
# when `git verify-tag` succeeds (a GPG-signed tag whose key is trusted), and
# non-zero on an unsigned / tampered / unknown-key tag. The verifier's output
# is captured in VERIFY_TAG_OUTPUT so callers can tell a missing public key
# (no local trust root yet — remediation: import the maintainer key) from a
# bad or absent signature (hard abort). `--raw` captures GnuPG's status lines
# ("[GNUPG:] KEYWORD ...") instead of its human-readable messages, which GnuPG
# translates into the host's language. Callers decide whether a non-zero
# result aborts (default) or downgrades to a warning
# (APOTHEM_ALLOW_UNVERIFIED=1). A branch ref (e.g. main) is not a tag object and
# cannot be verify-tag'd; callers gate on the ref shape before calling this.
VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(cgit -C "$1" verify-tag --raw "$2" 2>&1)"
}

# verify_tag_by_maintainer — return 0 when the captured status lines carry at
# least one VALIDSIG line and every VALIDSIG line names MAINTAINER_FINGERPRINT
# as its primary key, non-zero otherwise. `git verify-tag` alone accepts a
# valid signature from any key the local keyring holds, so a key an attacker
# got into that keyring would pass it; this check pins the one key that signs
# Apothem releases. VALIDSIG's tenth argument (field 12 here) is the primary
# key's fingerprint; GnuPG leaves it out only for keys too old to have one, so
# the signing key's fingerprint (field 3) stands in then. Only lines that start
# with the status prefix count; GnuPG escapes newlines inside user IDs, so a
# key's name cannot forge one.
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

# is_release_tag REF — return 0 when REF is a strict vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), non-zero otherwise (a branch like main, a SHA, a
# pre-release tag like v1.2.3-rc1, or a malformed form like v1x.2.3 or
# v1.2.3.4). Drives whether tag verification applies to the fetched ref. This
# mirrors the anchored `^v[0-9]+\.[0-9]+\.[0-9]+\z` regex in install.ps1's
# Test-ReleaseTag: a POSIX `case` glob cannot express "one-or-more digits" or
# reject trailing junk on its own (a bare `v[0-9]*.[0-9]*.[0-9]*` matches
# v1.2.3-rc1, v1x.2.3 and v1.2.3.4, since `*` absorbs any characters). The
# reject gates run first. They drop any REF that carries a character outside
# the strict `v`/digit/dot set (a trailing newline included), a `v` after the
# first character, or a third dot. The shape gate then requires a leading `v`,
# two dots, and a digit at the start of each component, so it accepts exactly
# what the install.ps1 regex matches with case respected.
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

# check_release_tag DIR REF ALLOW — the key-pinned tag gate. Checks the tag
# refs/tags/REF in the repository at DIR, before anything is checked out, and
# prints the result. The tag passes when the maintainer key signed it and the
# signed tag object names itself REF and points at a commit: a signed tag for
# another release, re-pointed at refs/tags/REF, would otherwise roll an
# install back to that release. Any other outcome aborts with the reason,
# unless ALLOW is 1, which downgrades a missing or unverifiable signature to a
# warning and returns 1. On a pass, TAG_COMMIT holds the tag's commit.
TAG_COMMIT=""
check_release_tag() {
    TAG_COMMIT=""
    if verify_tag "$1" "refs/tags/$2" && verify_tag_by_maintainer; then
        cgit -C "$1" cat-file tag "refs/tags/$2" 2>/dev/null | awk -v want="$2" '
            /^$/ { exit }
            $1 == "type" { type = $0 }
            $1 == "tag" { name = $0 }
            END { exit (type == "type commit" && name == "tag " want) ? 0 : 1 }' \
            || die "Tag $2 carries the maintainer key's signature, but the signed tag object is not the $2 release tag (it names another tag, or no commit), so it was re-pointed (possible tampering). Aborting before anything is checked out or materialized."
        TAG_COMMIT="$(cgit -C "$1" rev-parse --verify --quiet "refs/tags/$2^{commit}")" \
            || die "Could not read the commit the $2 tag points at"
        ok "Tag $2 carries a valid signature from the maintainer key ${MAINTAINER_FINGERPRINT}"
        return 0
    fi
    if [ "$3" = "1" ]; then
        warn "Tag $2 is unsigned, its signature did not verify, or the maintainer key did not make it — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        return 1
    fi
    if verify_tag_valid_other_key; then
        die "Tag $2 carries a valid signature, but not from the maintainer key ${MAINTAINER_FINGERPRINT} that SECURITY.md publishes (possible tampering). Aborting before anything is checked out or materialized."
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

# check_clone_setup DIR — die, before anything is fetched, when the clone at
# DIR is set up so that updating it in place would trust something the
# release does not hold: files git has been told to ignore changes to
# (assume-unchanged or skip-worktree, which require_clean_clone cannot see),
# a work tree other than DIR (core.worktree, or a .git that points at
# another clone's), or local git configuration that names a program for
# git to run or pulls in other configuration.
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

# checkout_ref DIR — check out APOTHEM_REF in the clone at DIR, after
# check_fetched_ref has passed. A release tag is checked out, detached, as
# refs/tags/<REF>^{commit}: that name can only mean the tag, never a branch
# that shares the tag's name or is literally named refs/tags/<REF>, and HEAD
# must then be the tag's commit. Any other ref is taken from origin when the
# fetch brought a remote-tracking branch of that name, so a stale local
# branch cannot stand in for it, and otherwise as given (a commit, or a
# branch only the clone has). No --force: a clone with local changes that the
# checkout would overwrite stops instead of losing them. Afterwards the
# tracked files must match the ref.
checkout_ref() {
    if is_release_tag "$APOTHEM_REF"; then
        cgit -C "$1" checkout --quiet --detach "refs/tags/${APOTHEM_REF}^{commit}" \
            || die "Could not check out the ${APOTHEM_REF} tag in $1. If it has local changes, commit or stash them, then re-run."
        _co_head="$(cgit -C "$1" rev-parse --verify --quiet HEAD || true)"
        _co_tag="$(cgit -C "$1" rev-parse --verify --quiet "refs/tags/${APOTHEM_REF}^{commit}" || true)"
        if [ -z "$_co_tag" ] || [ "$_co_head" != "$_co_tag" ]; then
            die "The checkout in $1 is at '${_co_head}', not at the ${APOTHEM_REF} tag's commit '${_co_tag}'. Aborting before anything is materialized."
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
            git -C "$1" ls-tree --name-only HEAD 2>/dev/null || true
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
clone_has_local_work() {
    _lw_out="$(GIT_OPTIONAL_LOCKS=0 git -C "$1" status --porcelain --untracked-files=no 2>/dev/null)" || return 0
    [ -z "$_lw_out" ] || return 0
    _lw_out="$(git -C "$1" stash list 2>/dev/null)" || return 0
    [ -z "$_lw_out" ] || return 0
    _lw_out="$(git -C "$1" log --branches --not --remotes --oneline 2>/dev/null)" || return 0
    [ -z "$_lw_out" ] || return 0
    _lw_tracked="$(git -C "$1" ls-tree --name-only HEAD 2>/dev/null)" || return 0
    _lw_untracked="$(GIT_OPTIONAL_LOCKS=0 git -C "$1" status --porcelain 2>/dev/null)" || return 0
    _lw_found="$(printf '%s\n' "$_lw_untracked" | LW_TRACKED="$_lw_tracked" awk '
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

# swap_in NEW MODE — put the checked tree at NEW in place of APOTHEM_HOME.
# NEW sits beside APOTHEM_HOME, so every move is a rename on one filesystem.
#   MODE keep:  APOTHEM_HOME holds an earlier Apothem install (or only the
#               engine's data). Every top-level entry that is not part of its
#               source tree or of NEW (the engine's backups/, state/ and data
#               folders among them) moves into NEW first; then the earlier
#               tree moves aside, NEW moves in, and the earlier source is
#               removed.
#   MODE aside: APOTHEM_HOME holds something else, and --yes allowed
#               replacing it. It moves, untouched, to a sibling
#               <APOTHEM_HOME>.before-apothem-<time> folder, and NEW moves in.
# A failure or an interrupt at any step puts everything back where it was and
# says so, or names where the earlier tree was left when that also fails.
# The rollback works from what is on disk, not from how far the swap got, so
# an interrupt between two steps undoes exactly the steps that happened.
# Archive installs record their source entries (the manifest) so a later
# swap can tell them from the engine's data.
_SW_PHASE=""
_SW_MODE=""
_SW_NEW=""
_SW_OLD=""
_SW_ASIDE=""
_SW_KEEP=""
_SW_KEEP_STAGING=0
swap_rollback() {
    _sw_ok=1
    if [ "$_SW_MODE" = "aside" ]; then
        # Undo the move-in, then move the set-aside folder back.
        if exists "$APOTHEM_HOME" && ! exists "$_SW_NEW" && exists "$_SW_ASIDE"; then
            mv "$APOTHEM_HOME" "$_SW_NEW" || _sw_ok=0
        fi
        if [ "$_sw_ok" = "1" ] && ! exists "$APOTHEM_HOME" && exists "$_SW_ASIDE"; then
            mv "$_SW_ASIDE" "$APOTHEM_HOME" || _sw_ok=0
        fi
        if exists "$_SW_ASIDE" || ! exists "$APOTHEM_HOME"; then _sw_ok=0; fi
    else
        _sw_oldhome="${_SW_OLD:+${_SW_OLD}/home}"
        # Undo the move-in: the new tree is at APOTHEM_HOME while the
        # earlier one is aside.
        if exists "$APOTHEM_HOME" && ! exists "$_SW_NEW" && exists "$_sw_oldhome"; then
            mv "$APOTHEM_HOME" "$_SW_NEW" || _sw_ok=0
        fi
        # Undo the rename of the earlier tree.
        if [ "$_sw_ok" = "1" ] && ! exists "$APOTHEM_HOME" && exists "$_sw_oldhome"; then
            mv "$_sw_oldhome" "$APOTHEM_HOME" || _sw_ok=0
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
                    mv "${_SW_NEW}/${_sw_name}" "${APOTHEM_HOME}/${_sw_name}" || _sw_ok=0
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
        printf '  %s %s\n' "$(paint "$COLOR_ERR" 31 '✗')" "$1, and moving the earlier folder back also failed: it is at $_SW_ASIDE" >&2
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

# on_exit — the EXIT trap while a staging folder exists. A swap still under
# way (a command failing under set -e, or a signal after the swap's own
# trap was reset) is rolled back first; staging folders are removed unless a
# failed rollback left data in them.
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
}

# aside_name — print the sibling name an earlier folder is moved to,
# <APOTHEM_HOME>.before-apothem-<time>, with -<pid> added when that is
# taken. Die, before anything moves, when both are taken: mv would move the
# folder into the one that is there.
aside_name() {
    _an_name="${APOTHEM_HOME}.before-apothem-$(date +%Y%m%d%H%M%S)"
    if exists "$_an_name"; then _an_name="${_an_name}-$$"; fi
    if exists "$_an_name"; then
        die "Could not move the existing $APOTHEM_HOME aside; nothing was changed"
    fi
    printf '%s\n' "$_an_name"
}

swap_in() {
    _SW_NEW="$1"
    _SW_MODE="$2"
    _SW_OLD=""
    _SW_ASIDE=""
    _SW_KEEP=""
    if ! exists "$APOTHEM_HOME"; then
        mv "$_SW_NEW" "$APOTHEM_HOME" || die "Could not move the new source to $APOTHEM_HOME"
        return 0
    fi
    if [ "$_SW_MODE" = "aside" ]; then
        _SW_ASIDE="$(aside_name)" || exit 1
        trap 'swap_abort "Interrupted while replacing $APOTHEM_HOME"' HUP INT TERM QUIT PIPE
        _SW_PHASE="aside"
        if ! mv "$APOTHEM_HOME" "$_SW_ASIDE"; then
            if exists "$APOTHEM_HOME" && ! exists "$_SW_ASIDE"; then
                trap_signals_to_exit
                _SW_PHASE=""
                die "Could not move the existing $APOTHEM_HOME aside; nothing was changed"
            fi
            swap_abort "Could not move the existing $APOTHEM_HOME aside"
        fi
        _SW_PHASE="move-in"
        mv "$_SW_NEW" "$APOTHEM_HOME" \
            || swap_abort "Could not move the new source to $APOTHEM_HOME"
        trap_signals_to_exit
        _SW_PHASE=""
        warn "The earlier contents of $APOTHEM_HOME were moved, unchanged, to $_SW_ASIDE"
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
    # keep-clone: an Apothem clone replaced with --yes. Its tree (history and
    # source, the carried entries aside) is kept beside APOTHEM_HOME, not
    # deleted.
    _sw_tree_aside=""
    if [ "$_SW_MODE" = "keep-clone" ]; then
        _sw_tree_aside="$(aside_name)" || exit 1
    fi
    _SW_OLD="$(mktemp -d "$(dirname "$APOTHEM_HOME")/.apothem-old.XXXXXX")" \
        || die "Could not make room beside $APOTHEM_HOME; nothing was changed"
    trap 'swap_abort "Interrupted while replacing $APOTHEM_HOME"' HUP INT TERM QUIT PIPE
    for _sw_name in $_SW_KEEP; do
        _SW_PHASE="carry"
        mv "${APOTHEM_HOME}/${_sw_name}" "${_SW_NEW}/${_sw_name}" \
            || swap_abort "Could not move ${_sw_name} into the new install"
    done
    _SW_PHASE="aside"
    mv "$APOTHEM_HOME" "${_SW_OLD}/home" \
        || swap_abort "Could not move the existing $APOTHEM_HOME aside"
    _SW_PHASE="move-in"
    mv "$_SW_NEW" "$APOTHEM_HOME" \
        || swap_abort "Could not move the new source to $APOTHEM_HOME"
    trap_signals_to_exit
    _SW_PHASE=""
    if [ -n "$_sw_tree_aside" ]; then
        # From here the folder holds the clone's only copy, so on_exit must
        # not remove it.
        _sw_old="$_SW_OLD"
        _SW_OLD=""
        if ! exists "$_sw_tree_aside" && mv "${_sw_old}/home" "$_sw_tree_aside"; then
            rmdir "$_sw_old" 2>/dev/null || true
        else
            _sw_tree_aside="${_sw_old}/home"
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
        | sort -u > "$1/$SOURCE_MANIFEST" \
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

# own_checkout — print the checkout this script file belongs to, if any.
# It is found by the script's own path and nothing else: $0, with any
# symbolic links followed, must be an existing regular file named install.sh
# in a scripts/installer folder whose ../.. is an Apothem source. A piped run (`curl … | sh`, `sh < install.sh`)
# has $0 set to the shell's name, so it never matches, and the current folder
# and its parents are never searched: a folder shaped like an Apothem tree
# there could otherwise put its own code in front of an unverified install.
#
# A bare `install.sh` with no "/" (as `sh -c "$(curl …)" install.sh` sets
# it) names nothing on disk, so it is refused rather than looked up in the
# current folder. A symbolic link, whatever its name, is followed to the
# real file first, and the name and folder checks apply to that file.
#
# Under `sh -c "<text>" <name>`, $0 is whatever the caller typed, not the
# file the text came from, so a path-shaped $0 there proves nothing. bash,
# zsh and ksh put "c" in $- for a -c run, and that refuses it here. dash
# leaves $- empty under -c, so with dash the check cannot tell; do not pass
# a path-shaped name after `sh -c`.
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
PY_VERSION="$("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
ok "$PY ($PY_VERSION)"

# Prerequisite: CLI prerequisites importable ---------------------------------------
#
# The bundled engine ships yaml + jsonschema vendored, but imports click + rich
# from the host interpreter. Probe each (a missing module is a quiet boolean,
# never a crash), report any gap, and offer to install the prerequisites under
# the chosen interpreter — auto-confirmed with --yes or APOTHEM_AUTO_INSTALL_DEPS=1,
# prompted interactively, and declined (with manual guidance) in a piped
# non-interactive session so the install never silently mutates the host.
#
# The current folder must never shadow the engine's modules. Python puts ''
# (the working directory) first on sys.path for `-c`, and `-m` puts the
# working directory there, so a `click.py`, `rich/` or `apothem/` in the
# folder the installer (or the shim) runs from would run instead of the real
# package. `-P` / PYTHONSAFEPATH does not exist on Python 3.10, and `-I` would
# also drop PYTHONPATH and the user site (where click and rich may be
# installed). So every such start sets PYTHONSAFEPATH=1 (3.11+ then adds
# nothing) and runs a `-c` program whose first statement drops a leading ''.
# Only sys.path changes; the working directory and the arguments do not.
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
# Source precedence:
#   1. APOTHEM_SOURCE — an explicit local source tree (no fetch; verification
#      is skipped because nothing is fetched).
#   2. This script's own checkout (it was run by path from
#      scripts/installer/ of an apothem source tree; no fetch; verification
#      skipped). The current folder and its parents are never used.
#   3. A git clone of APOTHEM_REPO into APOTHEM_HOME, pinned to the resolved
#      ref (the latest release tag by default, or an explicit APOTHEM_REF),
#      then signature-verified before materializing (idempotent: an existing
#      clone is fetched and checked out to the ref).

bold "Locating Apothem source"

SOURCE=""
if [ "$LOCAL_KIND" = "explicit" ]; then
    SOURCE="$LOCAL_TREE"
    [ -n "$SOURCE" ] \
        || die "APOTHEM_SOURCE is not an apothem source tree: ${APOTHEM_SOURCE}"
    ok "Using explicit source: $SOURCE"
    # The local-source path fetches nothing, so there is no tag to resolve and
    # no signature to verify. State plainly what is being run and skip the
    # tag-resolution + verification gate (which applies only to fetched refs).
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

# Pick the verification path for a fetched source. `auto` takes the release
# path when cosign is on PATH and the key-pinned tag check otherwise. A ref
# that is not a release tag (main, a SHA) has no release archive, so it goes
# to the clone path, whose gate refuses it unless APOTHEM_ALLOW_UNVERIFIED=1.
# An existing git clone at APOTHEM_HOME stays a clone: replacing it with an
# archive would drop its history and any local work, so it is updated through
# the clone path's key-pinned tag check.
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
        git -C "${_ck_tmp}/tag.git" fetch --quiet --depth=1 --no-tags "$APOTHEM_REPO" \
            "+refs/tags/${APOTHEM_REF}:refs/tags/${APOTHEM_REF}" >"${_ck_tmp}/fetch.log" 2>&1 \
            || die "Could not fetch the ${APOTHEM_REF} tag from ${APOTHEM_REPO}: $(tail -n 2 "${_ck_tmp}/fetch.log" | tr '\n' ' ')"
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
            _ck_said="$(tail -n 3 "${_ck_tmp}/cosign.log" | tr '\n' ' ')"
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
        _ck_stage="$(mktemp -d "$(dirname "$APOTHEM_HOME")/.apothem-extract.XXXXXX")" \
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
    # directory and leaves APOTHEM_HOME alone.
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
        _cl_tree="$APOTHEM_HOME"
    else
        if is_apothem_clone "$APOTHEM_HOME"; then
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
            _cl_stage="$(mktemp -d "$(dirname "$APOTHEM_HOME")/.apothem-clone.XXXXXX")" \
                || die "Could not create a staging directory beside $APOTHEM_HOME"
        fi
        _cl_tree="$(abs_path "${_cl_stage}/apothem")"
        info "Cloning ${APOTHEM_REPO}"
        # Full clone (no --single-branch) so both tags and branches are
        # checkout-able from the placed tree, then pin to the resolved ref.
        ngit clone --quiet --no-checkout "$APOTHEM_REPO" "$_cl_tree" \
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
# Absolute, so no PYTHONPATH entry below can name the current folder.
SRC_PATH="$(abs_path "${SOURCE}/src")"
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
#
# The entries are joined with PY_PATHSEP and written in the form that Python
# reads (see native_path): ":" and POSIX paths on POSIX, ";" and Windows paths
# under Git Bash, MSYS or Cygwin.
_ep_vendor="$(native_path "${SRC_PATH}/apothem/_vendor")" \
    || die "cygpath could not convert ${SRC_PATH}/apothem/_vendor to a Windows path"
_ep_src="$(native_path "${SRC_PATH}")" \
    || die "cygpath could not convert ${SRC_PATH} to a Windows path"
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
# apothem_sep is the separator the engine's Python reads: ":" on POSIX, ";"
# under Git Bash, MSYS or Cygwin, where only drive and network paths are kept.
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
