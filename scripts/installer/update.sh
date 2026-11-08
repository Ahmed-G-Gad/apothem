#!/bin/sh
# SPDX-License-Identifier: MIT

# Purpose: Re-fetch the bundled Apothem source (self-contained — no package
#          installation) and re-materialize harness configuration.
# Contract: Idempotent. Exits 0 on success, non-zero on failure.
#           POSIX sh only (no bashisms): runs under dash/ash as well as bash.
#
# Trust model (tag-pinned, verified-by-default): mirrors install.sh. With no
# APOTHEM_REF set, the latest signed vMAJOR.MINOR.PATCH release tag is
# resolved, checked out, and verified with `git verify-tag` before
# re-materializing. The signature must be valid and made by the maintainer key
# SECURITY.md publishes (fingerprint 5C8998F9F241720445D3F28B70396FED9C634163);
# an unsigned / tampered tag, or one signed by another key, ABORTS unless
# APOTHEM_ALLOW_UNVERIFIED=1 downgrades the abort to a warning. The
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
#     APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a tag-verification failure to a
#                             warning and proceed.
#     APOTHEM_SOURCE          Explicit local source tree to re-materialize from
#                             (skips tag resolution and verification)
#     APOTHEM_HARNESS         Harness to update (default: claude-code)
#     APOTHEM_PROFILE         Path to shared profile YAML
#     APOTHEM_AUTO_INSTALL_DEPS  If "1", install missing click / rich
#                             prerequisites automatically (pip), no prompt

set -eu

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
VENDORING_DOC="https://apothem.ahmedgad.com/architecture/vendoring-strategy/"

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

# resolve_latest_tag / verify_tag / is_release_tag mirror install.sh; see that
# script's helper comments for the per-function contract. Kept POSIX-clean.
resolve_latest_tag() {
    git ls-remote --tags "$1" 2>/dev/null \
        | sed -n 's#.*refs/tags/\(v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)\(\^{}\)\{0,1\}$#\1#p' \
        | sort -u \
        | sort -t. -k1.2,1n -k2,2n -k3,3n \
        | tail -n 1
}

VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(git -C "$1" verify-tag --raw "$2" 2>&1)"
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

# CLI prerequisite check (robust probe; offers to install the missing deps).
probe_missing_deps() {
    _missing=""
    for _dep in $RUNTIME_DEPS; do
        "$PY" -c "import ${_dep}" >/dev/null 2>&1 || _missing="${_missing:+$_missing }${_dep}"
    done
    printf '%s' "$_missing"
}

install_runtime_deps() {
    if ! "$PY" -m pip --version >/dev/null 2>&1; then
        warn "pip is unavailable under $PY - install $* manually."
        return 1
    fi
    info "Installing $* under $PY (pip)"
    if "$PY" -m pip install "$@"; then
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
elif [ -d "$APOTHEM_HOME/.git" ]; then
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

    if is_release_tag "$APOTHEM_REF" && [ "$APOTHEM_ALLOW_UNVERIFIED" != "1" ] \
        && [ "$(git config --get gpg.format 2>/dev/null || true)" != "ssh" ]; then
        _gpg_prog="$(git config --get gpg.program 2>/dev/null || true)"
        command -v "${_gpg_prog:-gpg}" >/dev/null 2>&1 \
            || die "gpg not found in PATH — needed to check the ${APOTHEM_REF} release tag's signature against the maintainer key. Install GnuPG (https://gnupg.org/download/), then re-run."
    fi

    info "Updating clone at $APOTHEM_HOME (ref: ${APOTHEM_REF})"
    git -C "$APOTHEM_HOME" fetch --quiet --tags origin
    if is_release_tag "$APOTHEM_REF"; then
        # The full refs/tags/ name keeps a branch that shares the tag's name
        # from standing in for it; HEAD must then be the tag's commit.
        git -C "$APOTHEM_HOME" checkout --quiet --force "refs/tags/${APOTHEM_REF}" \
            || die "Could not check out the ${APOTHEM_REF} tag in $APOTHEM_HOME"
        _co_head="$(git -C "$APOTHEM_HOME" rev-parse --verify --quiet HEAD || true)"
        _co_tag="$(git -C "$APOTHEM_HOME" rev-parse --verify --quiet "refs/tags/${APOTHEM_REF}^{commit}" || true)"
        if [ -z "$_co_tag" ] || [ "$_co_head" != "$_co_tag" ]; then
            die "The checkout in $APOTHEM_HOME is at '${_co_head}', not at the ${APOTHEM_REF} tag's commit '${_co_tag}'. Aborting before re-materialization."
        fi
    else
        git -C "$APOTHEM_HOME" checkout --quiet --force "$APOTHEM_REF" \
            || git -C "$APOTHEM_HOME" checkout --quiet --force "origin/${APOTHEM_REF}" \
            || die "Could not check out ${APOTHEM_REF} in $APOTHEM_HOME"
    fi
    SOURCE="$APOTHEM_HOME"
    is_apothem_source "$SOURCE" || die "Updated tree is not an apothem source: $SOURCE"
    ok "Source updated at $SOURCE (ref: ${APOTHEM_REF})"

    # Fail-closed signature verification before re-materializing.
    bold "Verifying source signature"
    if is_release_tag "$APOTHEM_REF"; then
        if verify_tag "$SOURCE" "refs/tags/${APOTHEM_REF}" && verify_tag_by_maintainer; then
            ok "Tag ${APOTHEM_REF} carries a valid signature from the maintainer key ${MAINTAINER_FINGERPRINT}"
        elif [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Tag ${APOTHEM_REF} is unsigned, its signature did not verify, or the maintainer key did not make it — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        elif verify_tag_valid_other_key; then
            die "Tag ${APOTHEM_REF} carries a valid signature, but not from the maintainer key ${MAINTAINER_FINGERPRINT} that SECURITY.md publishes (possible tampering). Aborting before re-materialization."
        elif verify_tag_missing_key; then
            die "Tag ${APOTHEM_REF} is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import', check that 'gpg --fingerprint 70396FED9C634163' shows the fingerprint published in SECURITY.md, then re-run this updater."
        else
            die "Tag ${APOTHEM_REF} is unsigned or its signature did not verify (possible tampering). Aborting before re-materialization."
        fi
    else
        if [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Ref ${APOTHEM_REF} is not a signed release tag — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        else
            die "Ref ${APOTHEM_REF} is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
        fi
    fi
    echo
elif is_apothem_source "$APOTHEM_HOME"; then
    die "$APOTHEM_HOME was installed from a release archive, which has no git clone to update. Re-run install.sh with cosign and gpg on PATH to update it to the latest verified release."
else
    die "No source found at $APOTHEM_HOME — run install.sh first or set APOTHEM_SOURCE"
fi
SRC_PATH="${SOURCE}/src"
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
ENGINE_PYPATH="${SRC_PATH}/apothem/_vendor:${SRC_PATH}"
echo

bold "Re-materializing harness: ${HARNESS}"
[ -f "$PROFILE" ] || die "Profile not found at $PROFILE — run install.sh first or set APOTHEM_PROFILE"
PYTHONPATH="${ENGINE_PYPATH}${PYTHONPATH:+:${PYTHONPATH}}" \
    "$PY" -m apothem update --harness "$HARNESS" --profile "$PROFILE"
ok "Harness ${HARNESS} updated"
echo

bold "Update complete."
