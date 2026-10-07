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
# re-materializing; an unsigned / tampered tag ABORTS unless
# APOTHEM_ALLOW_UNVERIFIED=1 downgrades the abort to a warning. The
# APOTHEM_SOURCE local-checkout path fetches nothing and skips verification.
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

verify_tag_missing_key() {
    case "$VERIFY_TAG_OUTPUT" in
        *"[GNUPG:] NO_PUBKEY "*) return 0 ;;
        *) return 1 ;;
    esac
}

is_release_tag() {
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

# Resolve a Python interpreter >= 3.10.
PY=""
for _cand in python3 python python3.14 python3.13 python3.12 python3.11 python3.10; do
    command -v "$_cand" >/dev/null 2>&1 || continue
    if "$_cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1; then
        PY="$_cand"
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

    info "Updating clone at $APOTHEM_HOME (ref: ${APOTHEM_REF})"
    git -C "$APOTHEM_HOME" fetch --quiet --tags origin
    git -C "$APOTHEM_HOME" checkout --quiet --force "$APOTHEM_REF" \
        || git -C "$APOTHEM_HOME" checkout --quiet --force "origin/${APOTHEM_REF}" \
        || die "Could not check out ${APOTHEM_REF} in $APOTHEM_HOME"
    SOURCE="$APOTHEM_HOME"
    is_apothem_source "$SOURCE" || die "Updated tree is not an apothem source: $SOURCE"
    ok "Source updated at $SOURCE (ref: ${APOTHEM_REF})"

    # Fail-closed signature verification before re-materializing.
    bold "Verifying source signature"
    if is_release_tag "$APOTHEM_REF"; then
        if verify_tag "$SOURCE" "$APOTHEM_REF"; then
            ok "Tag ${APOTHEM_REF} carries a valid signature"
        elif [ "$APOTHEM_ALLOW_UNVERIFIED" = "1" ]; then
            warn "Tag ${APOTHEM_REF} is unsigned or its signature did not verify — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        elif verify_tag_missing_key; then
            die "Tag ${APOTHEM_REF} is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: look up the maintainer signing-key fingerprint in SECURITY.md at the repository root, run 'gpg --recv-keys <fingerprint>', confirm the imported key's fingerprint matches the published value, then re-run this updater."
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
