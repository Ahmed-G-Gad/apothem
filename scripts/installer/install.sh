#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Place the bundled Apothem source tree (self-contained — no
#          package installation) and materialize harness configuration by
#          running `python -m apothem` directly from that tree.
# Contract: Idempotent on rerun (a re-run fast-forwards the clone and
#           re-materializes). Exits 0 on success, non-zero on failure.
#           POSIX sh only (no bashisms): the documented `curl … | sh`
#           one-liner runs under dash/ash on Debian/Ubuntu/Alpine.
#
# Trust model (tag-pinned, verified-by-default):
#   With no APOTHEM_REF set, the installer resolves the latest released
#   vMAJOR.MINOR.PATCH tag and checks THAT out — the moving `main` branch is
#   no longer the default. Before materializing, the fetched tag is verified
#   with `git verify-tag` (a GPG-signed tag); an unsigned, tampered, or
#   missing-signature tag ABORTS the install before any config is written.
#   Two explicit opt-outs exist:
#     - APOTHEM_REF=main           checks out the moving branch on request.
#     - APOTHEM_ALLOW_UNVERIFIED=1 downgrades a verification abort to a loud
#                                  warning and proceeds (air-gapped, local, or
#                                  pre-signed-release interim use).
#   The APOTHEM_SOURCE local-checkout path fetches nothing, so it skips tag
#   resolution and verification — it prints the source it is running and
#   proceeds.
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
#     --dry-run         Preview only; write nothing.
#     --yes             Non-interactive; skip per-target confirmation prompts.
#                       Also authorizes replacing an existing non-clone
#                       directory at APOTHEM_HOME.
#
# Environment overrides:
#     APOTHEM_HOME              Install destination for the cloned source
#                              (default: $HOME/.apothem)
#     APOTHEM_REPO             Git remote to clone
#                              (default: https://github.com/ahmed-g-gad/apothem)
#     APOTHEM_REF              Git ref to check out. Unset = resolve the latest
#                              vMAJOR.MINOR.PATCH tag. Set to a tag to pin, or
#                              to "main" for the moving branch.
#     APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a tag-verification failure
#                              from a fatal abort to a loud warning and proceed.
#     APOTHEM_VERIFY           "signature" (default) verifies the release tag's
#                              GPG signature. "checksum" instead downloads the
#                              release's platform archive and installs it only
#                              if its SHA-256 matches the release's SHA256SUMS:
#                              integrity without proof of the publisher, for
#                              hosts without the maintainer's public key.
#     APOTHEM_RELEASE_BASE     Release download base for checksum mode
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

APOTHEM_HOME="${APOTHEM_HOME:-$HOME/.apothem}"
APOTHEM_REPO="${APOTHEM_REPO:-https://github.com/ahmed-g-gad/apothem}"
# Empty default sentinel: an unset APOTHEM_REF means "resolve the latest
# released tag" (see resolve_latest_tag); an explicit value pins a tag or the
# moving `main` branch. The resolution happens after the helper definitions so
# the value is logged once resolved.
APOTHEM_REF="${APOTHEM_REF:-}"
APOTHEM_ALLOW_UNVERIFIED="${APOTHEM_ALLOW_UNVERIFIED:-0}"
APOTHEM_VERIFY="${APOTHEM_VERIFY:-signature}"
APOTHEM_RELEASE_BASE="${APOTHEM_RELEASE_BASE:-${APOTHEM_REPO}/releases/download}"
HARNESS="${APOTHEM_HARNESS:-claude-code}"
PROFILE="${APOTHEM_PROFILE:-$HOME/.config/apothem/profile.yaml}"

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
  --dry-run         Preview only; write nothing.
  --yes             Non-interactive; skip per-target confirmation prompts.
                    Also authorizes replacing an existing non-clone
                    directory at APOTHEM_HOME.
  -h, --help        Show this help and exit.

Trust model (default): resolves and checks out the latest signed
vMAJOR.MINOR.PATCH release tag, verifies its signature with `git verify-tag`,
and aborts before materializing if the tag is unsigned or tampered. The
recommended path is the tag-pinned VERIFIED install.

  # default — latest signed tag, verified:
  curl -fsSL https://apothem.ahmedgad.com/install.sh | sh
  # pin a known tag (also verified):
  APOTHEM_REF=vMAJOR.MINOR.PATCH sh install.sh

Overrides:
  APOTHEM_REF=main             check out the moving branch (unverified).
  APOTHEM_ALLOW_UNVERIFIED=1   downgrade a verification abort to a warning
                               (air-gapped / local / pre-signed-release use).
  APOTHEM_SOURCE=<path>        run a local checkout (fetches nothing; no
                               verification).
  APOTHEM_VERIFY=checksum      without the maintainer's public key: install
                               the release archive after checking its SHA-256
                               against the release's SHA256SUMS (integrity,
                               not proof of who published it).
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

# resolve_latest_tag REPO — print the highest vMAJOR.MINOR.PATCH tag advertised
# by the remote, or nothing when the remote carries no release tag. Uses only
# POSIX tools (git ls-remote, sed, sort -t. -k -n) so the moving-branch default
# is replaced by a pinned-tag default without bashisms. Pure-numeric semver
# only — pre-release / build-metadata tags (v1.2.3-rc1) are intentionally
# excluded so the default never resolves to a non-final release.
resolve_latest_tag() {
    # git ls-remote --tags prints "<sha>\trefs/tags/<tag>" (and "<tag>^{}" for
    # dereferenced annotated tags). Keep only refs/tags/vN.N.N, strip the
    # "^{}" peel suffix and the "refs/tags/" prefix, dedupe, then sort by the
    # three numeric components and take the highest.
    git ls-remote --tags "$1" 2>/dev/null \
        | sed -n 's#.*refs/tags/\(v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)\(\^{}\)\{0,1\}$#\1#p' \
        | sort -u \
        | sort -t. -k1.2,1n -k2,2n -k3,3n \
        | tail -n 1
}

# verify_tag DIR REF — verify the checked-out tag's signature in DIR. Returns 0
# when `git verify-tag` succeeds (a GPG-signed tag whose key is trusted), and
# non-zero on an unsigned / tampered / unknown-key tag. The verifier's output
# is captured in VERIFY_TAG_OUTPUT so callers can tell a missing public key
# (no local trust root yet — remediation: import the maintainer key) from a
# bad or absent signature (hard abort). Callers decide whether a non-zero
# result aborts (default) or downgrades to a warning
# (APOTHEM_ALLOW_UNVERIFIED=1). A branch ref (e.g. main) is not a tag object and
# cannot be verify-tag'd; callers gate on the ref shape before calling this.
VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(git -C "$1" verify-tag "$2" 2>&1)"
}

# verify_tag_missing_key — return 0 when the captured verify-tag output shows
# the signature could not be checked because the signing public key is absent
# from the local keyring ("Can't check signature: No public key"), non-zero
# for any other failure (unsigned tag, BAD signature).
verify_tag_missing_key() {
    case "$VERIFY_TAG_OUTPUT" in
        *"No public key"*|*"public key not found"*) return 0 ;;
        *) return 1 ;;
    esac
}

# is_release_tag REF — return 0 when REF is a strict vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), non-zero otherwise (a branch like main, a SHA, a
# pre-release tag like v1.2.3-rc1, or a malformed form like v1x.2.3). Drives
# whether tag verification applies to the fetched ref. This mirrors the anchored
# `^v[0-9]+\.[0-9]+\.[0-9]+$` regex in install.ps1's Test-ReleaseTag: a POSIX
# `case` glob cannot express "one-or-more digits" or reject trailing junk on its
# own (a bare `v[0-9]*.[0-9]*.[0-9]*` matches v1.2.3-rc1 and v1x.2.3, since `*`
# absorbs any characters). The shape gate below pins each component to start
# with a digit; the negative gate then rejects any REF carrying a character
# outside the strict `v`/digit/dot set, so a pre-release or malformed tag falls
# through to the unverifiable branch — matching install.ps1 exactly.
is_release_tag() {
    case "$1" in
        # Reject anything containing a character outside [v0-9.]; this drops
        # the `-rc1` suffix (hyphen/letters) and the stray `x` in v1x.2.3.
        *[!v0-9.]*) return 1 ;;
    esac
    case "$1" in
        v[0-9]*.[0-9]*.[0-9]*) return 0 ;;
        *) return 1 ;;
    esac
}

bold "Apothem installer"
echo

# Prerequisite: Python >= 3.10 ----------------------------------------------------
#
# Locate a real CPython >= 3.10, rejecting Microsoft Store launcher shims.
# The locator at hooks/lib/find-python.sh is reused when this script runs
# from a source tree; otherwise an inline probe applies the same version
# floor against PATH candidates.

bold "Checking prerequisites"

PY=""
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || true)"
LOCATOR=""
for _cand in \
    "${SCRIPT_DIR}/../../src/apothem/hooks/lib/find-python.sh" \
    "${SCRIPT_DIR}/../../hooks/lib/find-python.sh"; do
    if [ -f "$_cand" ]; then LOCATOR="$_cand"; break; fi
done
if [ -n "$LOCATOR" ]; then
    # shellcheck source=/dev/null
    . "$LOCATOR"
    PY="$(find_real_python 3 10 2>/dev/null || true)"
fi

if [ -z "$PY" ]; then
    for _cand in python3 python python3.14 python3.13 python3.12 python3.11 python3.10; do
        command -v "$_cand" >/dev/null 2>&1 || continue
        if "$_cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1; then
            PY="$_cand"
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
probe_missing_deps() {
    _missing=""
    for _dep in $RUNTIME_DEPS; do
        if ! "$PY" -c "import ${_dep}" >/dev/null 2>&1; then
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
    if ! "$PY" -m pip --version >/dev/null 2>&1; then
        warn "pip is unavailable under ${PY} — install $* manually."
        return 1
    fi
    info "Installing $* under ${PY} (pip)"
    if "$PY" -m pip install "$@"; then
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
#   2. A surrounding local checkout (this script lives in scripts/installer/
#      of an apothem source tree; no fetch; verification skipped).
#   3. A git clone of APOTHEM_REPO into APOTHEM_HOME, pinned to the resolved
#      ref (the latest release tag by default, or an explicit APOTHEM_REF),
#      then signature-verified before materializing (idempotent: an existing
#      clone is fetched and checked out to the ref).

bold "Locating Apothem source"

is_apothem_source() {
    [ -d "$1/src/apothem" ] && { [ -f "$1/pyproject.toml" ] || [ -d "$1/.claude-plugin" ]; }
}

SOURCE=""
if [ -n "${APOTHEM_SOURCE:-}" ]; then
    SOURCE="$(cd "$APOTHEM_SOURCE" 2>/dev/null && pwd || true)"
    [ -n "$SOURCE" ] && is_apothem_source "$SOURCE" \
        || die "APOTHEM_SOURCE is not an apothem source tree: ${APOTHEM_SOURCE}"
    ok "Using explicit source: $SOURCE"
    # The local-source path fetches nothing, so there is no tag to resolve and
    # no signature to verify. State plainly what is being run and skip the
    # tag-resolution + verification gate (which applies only to fetched refs).
    info "Local source — skipping tag resolution and signature verification"
elif [ -n "$SCRIPT_DIR" ]; then
    _walk="$SCRIPT_DIR"
    while [ -n "$_walk" ] && [ "$_walk" != "/" ]; do
        if is_apothem_source "$_walk"; then SOURCE="$_walk"; break; fi
        _walk="$(dirname "$_walk")"
    done
    if [ -n "$SOURCE" ]; then
        ok "Using local checkout: $SOURCE"
        info "Local checkout — skipping tag resolution and signature verification"
    fi
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
    signature|checksum) ;;
    *) die "APOTHEM_VERIFY must be 'signature' or 'checksum' (got '${APOTHEM_VERIFY}')." ;;
esac

# Checksum mode: install the release's platform archive after checking its
# SHA-256 against the release's SHA256SUMS. It replaces the git clone and the
# tag-signature gate below for hosts that do not hold the maintainer's public
# key, and says plainly that a matching digest proves integrity, not origin.
if [ -z "$SOURCE" ] && [ "$APOTHEM_VERIFY" = "checksum" ]; then
    command -v curl >/dev/null 2>&1 || die "curl not found in PATH — needed for APOTHEM_VERIFY=checksum"
    if [ -z "$APOTHEM_REF" ]; then
        command -v git >/dev/null 2>&1 || die "git not found in PATH — needed to resolve the latest release tag"
        info "Resolving latest release tag from ${APOTHEM_REPO}"
        APOTHEM_REF="$(resolve_latest_tag "$APOTHEM_REPO")"
    fi
    is_release_tag "$APOTHEM_REF" \
        || die "APOTHEM_VERIFY=checksum needs a vMAJOR.MINOR.PATCH release tag; got '${APOTHEM_REF}'. Pin one with APOTHEM_REF."
    case "$(uname -s 2>/dev/null)" in
        Darwin) _ck_platform=darwin ;;
        *)      _ck_platform=linux ;;
    esac
    _ck_name="apothem-${APOTHEM_REF}-${_ck_platform}.tar.gz"
    _ck_tmp="$(mktemp -d)"
    info "Downloading ${_ck_name} and SHA256SUMS from the ${APOTHEM_REF} release"
    curl -fsSL "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/${_ck_name}" -o "${_ck_tmp}/${_ck_name}" \
        || die "Could not download ${_ck_name} from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}"
    curl -fsSL "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS" -o "${_ck_tmp}/SHA256SUMS" \
        || die "Could not download SHA256SUMS from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}"
    _ck_expected="$(awk -v n="$_ck_name" '$2 == n || $2 == "*" n { print $1; exit }' "${_ck_tmp}/SHA256SUMS")"
    [ -n "$_ck_expected" ] || die "SHA256SUMS for ${APOTHEM_REF} lists no ${_ck_name}"
    _ck_actual="$(sha256_of "${_ck_tmp}/${_ck_name}")" \
        || die "Neither sha256sum nor shasum is available to check ${_ck_name}"
    if [ "$_ck_actual" != "$_ck_expected" ]; then
        rm -rf "$_ck_tmp"
        die "${_ck_name} does not match the release's SHA256SUMS (expected ${_ck_expected}, got ${_ck_actual}). Aborting before anything is extracted."
    fi
    ok "${_ck_name} matches the release's SHA256SUMS"
    warn "Checksum mode: a matching digest shows the archive is the one the release lists; it does not prove who published it. For signature verification, import the maintainer key named in SECURITY.md and run without APOTHEM_VERIFY=checksum."
    if [ -e "$APOTHEM_HOME" ] && [ -n "$(ls -A "$APOTHEM_HOME" 2>/dev/null)" ]; then
        if [ "$ASSUME_YES" = "1" ]; then
            warn "Replacing existing $APOTHEM_HOME with the ${APOTHEM_REF} archive (--yes)"
            rm -rf "$APOTHEM_HOME"
        else
            rm -rf "$_ck_tmp"
            die "Destination $APOTHEM_HOME is not empty; refusing to replace it. Move it aside, point APOTHEM_HOME at another directory, or re-run with --yes."
        fi
    fi
    mkdir -p "$APOTHEM_HOME"
    tar -xzf "${_ck_tmp}/${_ck_name}" -C "$APOTHEM_HOME" || die "Could not extract ${_ck_name}"
    rm -rf "$_ck_tmp"
    SOURCE="$APOTHEM_HOME"
    is_apothem_source "$SOURCE" || die "Extracted archive is not an apothem source: $SOURCE"
    ok "Source ready at $SOURCE (release archive ${APOTHEM_REF})"
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

    if [ -d "$APOTHEM_HOME/.git" ]; then
        info "Updating existing clone at $APOTHEM_HOME (ref: ${APOTHEM_REF})"
        git -C "$APOTHEM_HOME" fetch --quiet --tags origin
        # Check out the exact ref: a tag/SHA resolves directly; a branch name
        # resolves through its origin/<branch> remote-tracking ref. The
        # detached-HEAD checkout pins a tag without leaving a stale branch tip.
        git -C "$APOTHEM_HOME" checkout --quiet --force "$APOTHEM_REF" \
            || git -C "$APOTHEM_HOME" checkout --quiet --force "origin/${APOTHEM_REF}" \
            || die "Could not check out ${APOTHEM_REF} in $APOTHEM_HOME"
    else
        info "Cloning ${APOTHEM_REPO} into $APOTHEM_HOME"
        mkdir -p "$(dirname "$APOTHEM_HOME")"
        # An existing non-clone path here was not placed by a previous
        # install (no .git), so it is not Apothem's to delete. Refuse unless
        # --yes explicitly authorizes the destructive replacement; a stale
        # empty directory is removed quietly.
        if [ -e "$APOTHEM_HOME" ]; then
            if [ "$ASSUME_YES" = "1" ]; then
                warn "Replacing existing non-clone path at $APOTHEM_HOME (--yes)"
                rm -rf "$APOTHEM_HOME"
            elif [ -d "$APOTHEM_HOME" ] && [ -z "$(ls -A "$APOTHEM_HOME" 2>/dev/null)" ]; then
                rmdir "$APOTHEM_HOME"
            else
                die "Destination $APOTHEM_HOME exists but is not a git clone; refusing to delete it. Move it aside, point APOTHEM_HOME at another directory, or re-run with --yes to replace it."
            fi
        fi
        # Full clone (no --single-branch) so both tags and branches are
        # checkout-able from the placed tree, then pin to the resolved ref.
        git clone --quiet "$APOTHEM_REPO" "$APOTHEM_HOME" \
            || die "git clone failed for $APOTHEM_REPO"
        git -C "$APOTHEM_HOME" checkout --quiet --force "$APOTHEM_REF" \
            || git -C "$APOTHEM_HOME" checkout --quiet --force "origin/${APOTHEM_REF}" \
            || die "Could not check out ${APOTHEM_REF} in $APOTHEM_HOME"
    fi
    SOURCE="$APOTHEM_HOME"
    is_apothem_source "$SOURCE" || die "Fetched tree is not an apothem source: $SOURCE"
    ok "Source ready at $SOURCE (ref: ${APOTHEM_REF})"

    # Fail-closed signature verification — runs BEFORE any materialization.
    # A release tag (vN.N.N) is verify-tag'd; a branch/SHA ref is not a tag
    # object and is reported as unverifiable. On failure the install ABORTS
    # unless APOTHEM_ALLOW_UNVERIFIED=1 downgrades the abort to a warning.
    bold "Verifying source signature"
    if is_release_tag "$APOTHEM_REF"; then
        if verify_tag "$SOURCE" "$APOTHEM_REF"; then
            ok "Tag ${APOTHEM_REF} carries a valid signature"
        elif [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Tag ${APOTHEM_REF} is unsigned or its signature did not verify — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        elif verify_tag_missing_key; then
            die "Tag ${APOTHEM_REF} is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: look up the maintainer signing-key fingerprint in SECURITY.md at the repository root, run 'gpg --recv-keys <fingerprint>', confirm the imported key's fingerprint matches the published value, then re-run this installer."
        else
            die "Tag ${APOTHEM_REF} is unsigned or its signature did not verify (possible tampering). Aborting before any configuration is materialized."
        fi
    else
        # A non-release ref (main, a SHA, a pre-release tag) cannot be
        # verify-tag'd. Treat it as unverified and apply the same fail-closed
        # gate so the moving-branch override is a deliberate, surfaced choice.
        if [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Ref ${APOTHEM_REF} is not a signed release tag — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        else
            die "Ref ${APOTHEM_REF} is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
        fi
    fi
    echo
fi
SRC_PATH="${SOURCE}/src"
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
#
# PYTHONPATH entries are joined with a literal ':' (the POSIX os.pathsep) here
# and in every ${PYTHONPATH:+:${PYTHONPATH}} extension below. This is correct
# for the documented target: a POSIX shell (dash/ash/bash) driving a POSIX
# CPython, where os.pathsep is ':'. It is INTENTIONALLY NOT portable to a
# native Windows CPython, whose os.pathsep is ';' — under Git Bash on Windows a
# ':'-joined PYTHONPATH would not split into two entries and the vendored tree
# would not resolve. Windows operators use install.ps1, which joins with
# [System.IO.Path]::PathSeparator (';') for exactly this reason.
ENGINE_PYPATH="${SRC_PATH}/apothem/_vendor:${SRC_PATH}"
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
PYTHONPATH="${ENGINE_PYPATH}${PYTHONPATH:+:${PYTHONPATH}}" \
    "$PY" -m apothem install --harness "$HARNESS" --profile "$ENGINE_PROFILE" "$@"
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
    if PYTHONPATH="${ENGINE_PYPATH}${PYTHONPATH:+:${PYTHONPATH}}" \
        "$PY" -m apothem verify --harness "$HARNESS"; then
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
# line to add it and falls back to the self-contained form, so it never
# advertises a bare `apothem` command the operator cannot yet resolve.

BIN_DIR="${APOTHEM_BIN_DIR:-$HOME/.local/bin}"
SHIM="${BIN_DIR}/apothem"
PY_ABS="$(command -v "$PY" 2>/dev/null || printf '%s' "$PY")"
SHIM_OK=0
if mkdir -p "$BIN_DIR" 2>/dev/null; then
    if {
        printf '%s\n' '#!/bin/sh'
        printf '%s\n' '# Apothem entry-point shim (generated by install.sh).'
        printf 'PYTHONPATH="%s${PYTHONPATH:+:${PYTHONPATH}}" exec "%s" -m apothem "$@"\n' \
            "$ENGINE_PYPATH" "$PY_ABS"
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
        printf '    export PATH="%s:$PATH"\n' "$BIN_DIR"
        echo
    fi
    cat <<EOF
Run the engine from the bundled source (self-contained — no package installation):
  PYTHONPATH="${ENGINE_PYPATH}" "${PY}" -m apothem <command>

Recommended first step — the guided setup (profile -> preview -> install):
  PYTHONPATH="${ENGINE_PYPATH}" "${PY}" -m apothem quickstart

Or run individual commands:
  PYTHONPATH="${ENGINE_PYPATH}" "${PY}" -m apothem harnesses list   # list harnesses
  PYTHONPATH="${ENGINE_PYPATH}" "${PY}" -m apothem doctor           # system health
  PYTHONPATH="${ENGINE_PYPATH}" "${PY}" -m apothem profile edit     # edit profile

Optional — once the 'apothem' command is on your PATH, enable <TAB> shell
completion (opt-in; appends to your shell rc):
  apothem completion bash >> ~/.bashrc   # or zsh / fish

EOF
fi
