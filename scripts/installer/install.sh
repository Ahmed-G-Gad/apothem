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
#   vMAJOR.MINOR.PATCH tag and installs THAT release — the moving `main`
#   branch is no longer the default. How the release is checked depends on
#   APOTHEM_VERIFY, whose default `auto` picks one of two paths:
#     - cosign on PATH ("release"): two checks, both required. The release
#       tag must be signed by the maintainer key (below), and cosign must
#       show that the release workflow signed the release's SHA256SUMS in a
#       run on the commit that tag points at. The platform archive's SHA-256
#       must then match SHA256SUMS. Needs git, gpg and cosign.
#     - no cosign ("signature"): clone the repository and check the tag with
#       `git verify-tag`. Needs git and gpg.
#   Either way the tag signature must be valid AND made by the maintainer key
#   published in SECURITY.md (fingerprint
#   5C8998F9F241720445D3F28B70396FED9C634163); a key the local keyring merely
#   trusts is not enough. A signed git tag names its commit by SHA-1; the
#   release path adds the SHA-256 digest that cosign checks.
#   A failed check ABORTS the install before any config is written.
#   Two explicit opt-outs exist:
#     - APOTHEM_REF=main           checks out the moving branch on request.
#     - APOTHEM_ALLOW_UNVERIFIED=1 downgrades a failed tag check on the clone
#                                  path to a loud warning and proceeds
#                                  (air-gapped or local use, or a release that
#                                  predates tag signing). The release path
#                                  never downgrades.
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
#     --dry-run         Preview only; write nothing. The source is fetched
#                       and checked into a temporary directory, and
#                       APOTHEM_HOME is left as it is.
#     --yes             Non-interactive; skip per-target confirmation prompts.
#                       Also authorizes replacing an existing non-clone
#                       directory at APOTHEM_HOME.
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
#                              from a fatal abort to a loud warning and proceed.
#     APOTHEM_VERIFY           "auto" (default) uses "release" when cosign is
#                              on PATH and "signature" otherwise.
#                              "release" installs the platform archive once
#                              the tag carries the maintainer key's signature,
#                              cosign shows the release workflow signed
#                              SHA256SUMS on the tag's commit, and the
#                              archive's SHA-256 matches it (needs cosign and
#                              gpg). "signature" clones and checks the tag's
#                              GPG signature against the pinned maintainer
#                              key (needs gpg). "checksum" installs the
#                              archive after the SHA-256 check alone:
#                              integrity without proof of the publisher, for
#                              hosts with neither cosign nor the key.
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

APOTHEM_HOME="${APOTHEM_HOME:-$HOME/.apothem}"
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
                    a temporary directory; APOTHEM_HOME is not changed).
  --yes             Non-interactive; skip per-target confirmation prompts.
                    Also authorizes replacing an existing non-clone
                    directory at APOTHEM_HOME.
  -h, --help        Show this help and exit.

Trust model (default): resolves the latest vMAJOR.MINOR.PATCH release and
verifies it before materializing anything. The release tag must carry a
valid signature from the maintainer key in SECURITY.md (needs gpg). With
cosign on PATH it also has cosign show that the release workflow signed
SHA256SUMS in a run on that tag's commit, and installs the release archive
once its SHA-256 matches; without cosign it clones the release tag. Any
check failing aborts the install.

  # default — latest signed tag, verified:
  curl -fsSL https://apothem.ahmedgad.com/install.sh | sh
  # pin a known tag (also verified):
  APOTHEM_REF=vMAJOR.MINOR.PATCH sh install.sh

Overrides:
  APOTHEM_REF=main             check out the moving branch (needs
                               APOTHEM_ALLOW_UNVERIFIED=1; aborts otherwise).
  APOTHEM_ALLOW_UNVERIFIED=1   downgrade a failed tag check on the clone path
                               to a warning (air-gapped or local use, or a
                               release that predates tag signing).
  APOTHEM_SOURCE=<path>        run a local checkout (fetches nothing; no
                               verification).
  APOTHEM_VERIFY=release       require the tag signature, the cosign check on
                               the tag's commit and the SHA-256 archive check
                               (fails when cosign is missing).
  APOTHEM_VERIFY=signature     always clone and check the tag signature
                               against the maintainer key.
  APOTHEM_VERIFY=checksum      with neither cosign nor the maintainer key:
                               install the release archive after checking its
                               SHA-256 against the release's SHA256SUMS
                               (integrity, not proof of who published it).
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
# bad or absent signature (hard abort). `--raw` captures GnuPG's status lines
# ("[GNUPG:] KEYWORD ...") instead of its human-readable messages, which GnuPG
# translates into the host's language. Callers decide whether a non-zero
# result aborts (default) or downgrades to a warning
# (APOTHEM_ALLOW_UNVERIFIED=1). A branch ref (e.g. main) is not a tag object and
# cannot be verify-tag'd; callers gate on the ref shape before calling this.
VERIFY_TAG_OUTPUT=""
verify_tag() {
    VERIFY_TAG_OUTPUT="$(git -C "$1" verify-tag --raw "$2" 2>&1)"
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
# signature (gpg.program, else gpg) is on PATH, so a missing GnuPG is named
# as such instead of surfacing as a failed signature check.
require_gpg() {
    if [ "$(git config --get gpg.format 2>/dev/null || true)" = "ssh" ]; then
        return 0
    fi
    _rg_prog="$(git config --get gpg.program 2>/dev/null || true)"
    command -v "${_rg_prog:-gpg}" >/dev/null 2>&1 \
        || die "gpg not found in PATH — needed to check the ${APOTHEM_REF} release tag's signature against the maintainer key. Install GnuPG (https://gnupg.org/download/), then re-run."
}

# check_release_tag DIR REF ALLOW — the key-pinned tag gate. Checks the tag
# refs/tags/REF in the repository at DIR and prints the result. A tag signed
# by the maintainer key passes; any other outcome aborts with the reason,
# unless ALLOW is 1, which downgrades the abort to a warning and returns 1.
# On a pass, TAG_COMMIT holds the commit the tag points at.
TAG_COMMIT=""
check_release_tag() {
    TAG_COMMIT=""
    if verify_tag "$1" "refs/tags/$2" && verify_tag_by_maintainer; then
        TAG_COMMIT="$(git -C "$1" rev-parse --verify --quiet "refs/tags/$2^{commit}")" \
            || die "Could not read the commit the $2 tag points at"
        ok "Tag $2 carries a valid signature from the maintainer key ${MAINTAINER_FINGERPRINT}"
        return 0
    fi
    if [ "$3" = "1" ]; then
        warn "Tag $2 is unsigned, its signature did not verify, or the maintainer key did not make it — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        return 1
    fi
    if verify_tag_valid_other_key; then
        die "Tag $2 carries a valid signature, but not from the maintainer key ${MAINTAINER_FINGERPRINT} that SECURITY.md publishes (possible tampering). Aborting before any configuration is materialized."
    elif verify_tag_missing_key; then
        die "Tag $2 is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import', check that 'gpg --fingerprint 70396FED9C634163' shows the fingerprint published in SECURITY.md, then re-run this installer."
    fi
    die "Tag $2 is unsigned or its signature did not verify (possible tampering). Aborting before any configuration is materialized."
}

# checkout_ref DIR — check out APOTHEM_REF in the clone at DIR. A release tag
# is checked out by its full refs/tags/ name, so a branch that shares the
# tag's name cannot stand in for it, and HEAD must then be the tag's commit.
# Any other ref resolves directly or through its origin/<branch> name.
checkout_ref() {
    if is_release_tag "$APOTHEM_REF"; then
        git -C "$1" checkout --quiet --force "refs/tags/${APOTHEM_REF}" \
            || die "Could not check out the ${APOTHEM_REF} tag in $1"
        _co_head="$(git -C "$1" rev-parse --verify --quiet HEAD || true)"
        _co_tag="$(git -C "$1" rev-parse --verify --quiet "refs/tags/${APOTHEM_REF}^{commit}" || true)"
        if [ -z "$_co_tag" ] || [ "$_co_head" != "$_co_tag" ]; then
            die "The checkout in $1 is at '${_co_head}', not at the ${APOTHEM_REF} tag's commit '${_co_tag}'. Aborting before anything is verified or materialized."
        fi
    else
        git -C "$1" checkout --quiet --force "$APOTHEM_REF" \
            || git -C "$1" checkout --quiet --force "origin/${APOTHEM_REF}" \
            || die "Could not check out ${APOTHEM_REF} in $1"
    fi
}

# cert_source_commit BUNDLE — print the commit that the Sigstore signing
# certificate in BUNDLE names in its source-repository-digest extension (OID
# 1.3.6.1.4.1.57264.1.19, a DER UTF8String), or fail when the bundle holds no
# certificate or the certificate has no such extension. It reads cosign's own
# bundle ("cert": a base64 PEM) and the Sigstore bundle format
# (verificationMaterial). Run only after cosign has verified the bundle, so
# the certificate it reads is the one cosign checked.
cert_source_commit() {
    "$PY" -I -c '
import base64, json, re, sys

OID = bytes.fromhex("2b0601040183bf300113")


def tlv(buf, i):
    tag, size = buf[i], buf[i + 1]
    i += 2
    if size & 0x80:
        count = size & 0x7F
        size = int.from_bytes(buf[i:i + count], "big")
        i += count
    return tag, buf[i:i + size], i + size


def children(buf):
    i = 0
    while i < len(buf):
        tag, value, i = tlv(buf, i)
        yield tag, value


try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        bundle = json.load(handle)
    if "cert" in bundle:
        pem = base64.b64decode(bundle["cert"]).decode("ascii")
        body = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", pem, re.S)
        der = base64.b64decode("".join(body.group(1).split()))
    else:
        material = bundle["verificationMaterial"]
        cert = material.get("certificate") or material["x509CertificateChain"]["certificates"][0]
        der = base64.b64decode(cert["rawBytes"])
    tbs = tlv(tlv(der, 0)[1], 0)[1]
    for tag, value in children(tbs):
        if tag != 0xA3:
            continue
        for _, extension in children(tlv(value, 0)[1]):
            parts = list(children(extension))
            if parts[0] == (0x06, OID):
                digest = parts[-1][1]
                if digest[:1] == b"\x0c":
                    digest = tlv(digest, 0)[1]
                print(digest.decode("ascii"))
                sys.exit(0)
except Exception:
    pass
sys.exit(1)
' "$1"
}

# swap_in NEW DROP — put the tree at NEW in place of APOTHEM_HOME. NEW sits
# beside APOTHEM_HOME, so each move is a rename on one filesystem. The earlier
# APOTHEM_HOME moves aside first and comes back if NEW cannot move in. Then
# every top-level entry of the earlier tree that NEW does not ship moves into
# the new tree, except DROP (.git when an archive replaces a clone): that
# keeps the engine's rollback backups (backups/) and install ledgers (state/),
# which live in APOTHEM_HOME too. The rest of the earlier tree is removed.
swap_in() {
    if [ ! -e "$APOTHEM_HOME" ] && [ ! -L "$APOTHEM_HOME" ]; then
        mv "$1" "$APOTHEM_HOME" || die "Could not move the new source to $APOTHEM_HOME"
        return 0
    fi
    _sw_old="$(mktemp -d "$(dirname "$APOTHEM_HOME")/.apothem-old.XXXXXX")" \
        || die "Could not make room beside $APOTHEM_HOME"
    if ! mv "$APOTHEM_HOME" "${_sw_old}/home"; then
        rmdir "$_sw_old"
        die "Could not move the existing $APOTHEM_HOME aside; nothing was changed"
    fi
    if ! mv "$1" "$APOTHEM_HOME"; then
        mv "${_sw_old}/home" "$APOTHEM_HOME" && rmdir "$_sw_old"
        die "Could not move the new source to $APOTHEM_HOME; the earlier install is back in place"
    fi
    if [ -d "${_sw_old}/home" ] && [ ! -L "${_sw_old}/home" ]; then
        for _sw_entry in "${_sw_old}/home"/* "${_sw_old}/home"/.[!.]* "${_sw_old}/home"/..?*; do
            [ -e "$_sw_entry" ] || [ -L "$_sw_entry" ] || continue
            _sw_base="${_sw_entry##*/}"
            [ "$_sw_base" = "$2" ] && continue
            if [ -e "${APOTHEM_HOME}/${_sw_base}" ] || [ -L "${APOTHEM_HOME}/${_sw_base}" ]; then
                continue
            fi
            mv "$_sw_entry" "${APOTHEM_HOME}/${_sw_base}" \
                || die "Could not move ${_sw_base} into the new $APOTHEM_HOME; the earlier install is kept at ${_sw_old}/home"
        done
    fi
    rm -rf "$_sw_old"
}

bold "Apothem installer"
echo

# Prerequisite: Python >= 3.10 ----------------------------------------------------
#
# Locate a real CPython >= 3.10, rejecting Microsoft Store launcher shims.
# The locator at hooks/lib/find-python.sh is reused when this script runs
# from a source tree; otherwise an inline probe applies the same version
# floor and the same Store-shim rejection against PATH candidates.

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
    elif [ -d "$APOTHEM_HOME/.git" ]; then
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

# Archive modes: install the release's platform archive after checking its
# SHA-256 against the release's SHA256SUMS. They replace the git clone below.
# `release` checks two things before it trusts the digest, and both must
# pass: the release tag is signed by the maintainer key, and cosign shows
# that the release workflow signed SHA256SUMS in a run on the commit that tag
# points at. Either alone is not enough: anyone who can push a tag can make
# the workflow sign a release, and a signed tag says nothing about the
# archive. `checksum` skips both, for hosts with neither cosign nor the
# maintainer key, and says plainly that a matching digest proves integrity,
# not origin.
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
    case "$(uname -s 2>/dev/null)" in
        Darwin) _ck_platform=darwin ;;
        *)      _ck_platform=linux ;;
    esac
    _ck_name="apothem-${APOTHEM_REF}-${_ck_platform}.tar.gz"
    _ck_tmp="$(mktemp -d)"
    _ck_stage=""
    # Remove the downloads and the extraction on every way out of this block:
    # a die, a failing command under set -e, or an interrupt. A dry run keeps
    # the trap, since the engine previews from the extracted tree.
    trap 'rm -rf "$_ck_tmp" ${_ck_stage:+"$_ck_stage"}' EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    if [ "$VERIFY_MODE" = "release" ]; then
        command -v git >/dev/null 2>&1 || die "git not found in PATH — needed to check the ${APOTHEM_REF} release tag"
        require_gpg
        bold "Verifying the ${APOTHEM_REF} release tag"
        # Only the tag and the commit it points at are fetched, into a
        # throwaway repository; the source itself comes from the archive.
        git init --quiet --bare "${_ck_tmp}/tag.git" \
            || die "Could not create a scratch repository to check the ${APOTHEM_REF} tag"
        git -C "${_ck_tmp}/tag.git" fetch --quiet --depth=1 --no-tags "$APOTHEM_REPO" \
            "+refs/tags/${APOTHEM_REF}:refs/tags/${APOTHEM_REF}" >"${_ck_tmp}/fetch.log" 2>&1 \
            || die "Could not fetch the ${APOTHEM_REF} tag from ${APOTHEM_REPO}: $(tail -n 2 "${_ck_tmp}/fetch.log" | tr '\n' ' ')"
        check_release_tag "${_ck_tmp}/tag.git" "$APOTHEM_REF" 0
        _ck_tag_commit="$TAG_COMMIT"
    fi
    info "Downloading ${_ck_name} and SHA256SUMS from the ${APOTHEM_REF} release"
    curl -fsSL "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/${_ck_name}" -o "${_ck_tmp}/${_ck_name}" \
        || die "Could not download ${_ck_name} from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}"
    curl -fsSL "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS" -o "${_ck_tmp}/SHA256SUMS" \
        || die "Could not download SHA256SUMS from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}"
    if [ "$VERIFY_MODE" = "release" ]; then
        # The certificate identity is exact, never a pattern: a regular
        # expression would also match a forged subject that merely contains
        # the repository path. It names the tag being installed, so a bundle
        # signed for another release does not verify here.
        _ck_identity="https://github.com/${COSIGN_IDENTITY_REPO}/.github/workflows/release.yml@refs/tags/${APOTHEM_REF}"
        # Early releases published the same Sigstore bundle as SHA256SUMS.sig
        # (scripts/release/verify-provenance.sh accepts both names).
        curl -fsSL "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS.cosign.bundle" -o "${_ck_tmp}/SHA256SUMS.cosign.bundle" 2>/dev/null \
            || curl -fsSL "${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}/SHA256SUMS.sig" -o "${_ck_tmp}/SHA256SUMS.cosign.bundle" \
            || die "Could not download SHA256SUMS.cosign.bundle, or SHA256SUMS.sig as early releases name it, from ${APOTHEM_RELEASE_BASE}/${APOTHEM_REF}. Set APOTHEM_VERIFY=signature to check the release tag alone."
        if cosign verify-blob \
            --bundle "${_ck_tmp}/SHA256SUMS.cosign.bundle" \
            --certificate-identity "$_ck_identity" \
            --certificate-oidc-issuer "$COSIGN_OIDC_ISSUER" \
            "${_ck_tmp}/SHA256SUMS" >"${_ck_tmp}/cosign.log" 2>&1; then
            ok "cosign: SHA256SUMS is signed by the ${APOTHEM_REF} release workflow"
        else
            _ck_said="$(tail -n 3 "${_ck_tmp}/cosign.log" | tr '\n' ' ')"
            die "cosign could not confirm that the ${APOTHEM_REF} release workflow (${_ck_identity}) signed SHA256SUMS (possible tampering). Aborting before anything is extracted. cosign said: ${_ck_said} If cosign could not reach Sigstore (offline or behind a proxy), set APOTHEM_VERIFY=signature to check the release tag alone."
        fi
        # The workflow run that signed SHA256SUMS must have run on the commit
        # the maintainer signed. Fulcio writes that run's commit into the
        # certificate; a certificate without it cannot be tied to the tag.
        _ck_cert_commit="$(cert_source_commit "${_ck_tmp}/SHA256SUMS.cosign.bundle")" \
            || die "The ${APOTHEM_REF} signing certificate names no source commit (extension 1.3.6.1.4.1.57264.1.19), so it cannot be tied to the signed tag. Aborting before anything is extracted."
        if [ "$(printf '%s' "$_ck_cert_commit" | tr 'A-F' 'a-f')" != "$_ck_tag_commit" ]; then
            die "The ${APOTHEM_REF} release was signed in a workflow run on commit ${_ck_cert_commit}, but the maintainer-signed tag points at ${_ck_tag_commit} (possible tampering). Aborting before anything is extracted."
        fi
        ok "The signing workflow ran on the tag's commit ${_ck_tag_commit}"
    fi
    _ck_expected="$(awk -v n="$_ck_name" '$2 == n || $2 == "*" n { print $1; exit }' "${_ck_tmp}/SHA256SUMS")"
    [ -n "$_ck_expected" ] || die "SHA256SUMS for ${APOTHEM_REF} lists no ${_ck_name}"
    _ck_actual="$(sha256_of "${_ck_tmp}/${_ck_name}")" \
        || die "Neither sha256sum nor shasum is available to check ${_ck_name}"
    if [ "$_ck_actual" != "$_ck_expected" ]; then
        die "${_ck_name} does not match the release's SHA256SUMS (expected ${_ck_expected}, got ${_ck_actual}). Aborting before anything is extracted."
    fi
    ok "${_ck_name} matches the release's SHA256SUMS"
    if [ "$VERIFY_MODE" = "checksum" ]; then
        warn "Checksum mode: a matching digest shows the archive is the one the release lists; it does not prove who published it. For proof of the publisher, install cosign and gpg and run without APOTHEM_VERIFY=checksum."
    fi
    # Who owns what is already at APOTHEM_HOME decides whether --yes is
    # needed. An earlier archive install is Apothem's own and is updated
    # without asking. A git clone (history, branches, local work) or anything
    # else needs --yes. swap_in keeps every entry the archive does not ship,
    # the engine's backups/ and state/ among them.
    _ck_drop=""
    if [ -e "$APOTHEM_HOME" ] && [ -n "$(ls -A "$APOTHEM_HOME" 2>/dev/null)" ]; then
        if [ -d "$APOTHEM_HOME/.git" ]; then
            if [ "$ASSUME_YES" = "1" ]; then
                warn "Replacing the git clone's source at $APOTHEM_HOME with the ${APOTHEM_REF} archive; its git history is removed, its backups/ and state/ are kept (--yes)"
                _ck_drop=".git"
            else
                die "Destination $APOTHEM_HOME is a git clone; refusing to replace it with the ${APOTHEM_REF} archive, which would remove its history. Set APOTHEM_VERIFY=signature to update the clone, move it aside, or re-run with --yes."
            fi
        elif is_apothem_source "$APOTHEM_HOME"; then
            info "Updating the earlier install at $APOTHEM_HOME to the ${APOTHEM_REF} archive"
        elif [ "$ASSUME_YES" = "1" ]; then
            warn "Writing the ${APOTHEM_REF} archive into the existing $APOTHEM_HOME; files it does not ship are kept (--yes)"
        else
            die "Destination $APOTHEM_HOME is not empty and holds no Apothem install; refusing to replace it. Move it aside, point APOTHEM_HOME at another directory, or re-run with --yes."
        fi
    fi
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
        swap_in "$_ck_root" "$_ck_drop"
        rm -rf "$_ck_tmp" "$_ck_stage"
        trap - EXIT HUP INT TERM
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

    # An existing clone is updated in place. Otherwise the clone is made in a
    # fresh staging directory, checked, and only then swapped in by swap_in,
    # which keeps the engine's backups/ and state/ from an earlier archive
    # install. A dry run clones into a scratch directory and leaves
    # APOTHEM_HOME alone.
    _cl_stage=""
    if [ -d "$APOTHEM_HOME/.git" ] && [ "$DRY_RUN" != "1" ]; then
        info "Updating existing clone at $APOTHEM_HOME (ref: ${APOTHEM_REF})"
        git -C "$APOTHEM_HOME" fetch --quiet --tags origin
        checkout_ref "$APOTHEM_HOME"
        _cl_tree="$APOTHEM_HOME"
    else
        # An existing non-clone path here may not be Apothem's, so replacing
        # it needs --yes; a stale empty directory is replaced quietly.
        if [ "$DRY_RUN" != "1" ] && [ -e "$APOTHEM_HOME" ] && [ -n "$(ls -A "$APOTHEM_HOME" 2>/dev/null)" ]; then
            if [ "$ASSUME_YES" = "1" ]; then
                warn "Replacing the existing non-clone $APOTHEM_HOME with a clone of ${APOTHEM_REF}; files the clone does not ship, such as backups/ and state/, are kept (--yes)"
            else
                die "Destination $APOTHEM_HOME exists but is not a git clone; refusing to replace it. If it is an earlier archive install, install cosign and gpg and re-run to update it in place, or re-run with --yes to switch it to a clone (its backups/ and state/ are kept). Otherwise move it aside or point APOTHEM_HOME at another directory."
            fi
        fi
        if [ "$DRY_RUN" = "1" ]; then
            _cl_stage="$(mktemp -d)" || die "Could not create a scratch directory for the dry run"
        else
            mkdir -p "$(dirname "$APOTHEM_HOME")" \
                || die "Could not create the parent directory of $APOTHEM_HOME"
            _cl_stage="$(mktemp -d "$(dirname "$APOTHEM_HOME")/.apothem-clone.XXXXXX")" \
                || die "Could not create a staging directory beside $APOTHEM_HOME"
        fi
        trap 'rm -rf "$_cl_stage"' EXIT
        trap 'exit 129' HUP
        trap 'exit 130' INT
        trap 'exit 143' TERM
        _cl_tree="${_cl_stage}/apothem"
        info "Cloning ${APOTHEM_REPO}"
        # Full clone (no --single-branch) so both tags and branches are
        # checkout-able from the placed tree, then pin to the resolved ref.
        git clone --quiet "$APOTHEM_REPO" "$_cl_tree" \
            || die "git clone failed for $APOTHEM_REPO"
        checkout_ref "$_cl_tree"
    fi
    is_apothem_source "$_cl_tree" || die "Fetched tree is not an apothem source: $_cl_tree"

    # Fail-closed signature verification — runs BEFORE the clone is swapped
    # in and before any materialization. A release tag (vN.N.N) must carry
    # the maintainer key's signature; a branch/SHA ref is not a tag object
    # and is reported as unverifiable. On failure the install ABORTS unless
    # APOTHEM_ALLOW_UNVERIFIED=1 downgrades the abort to a warning.
    bold "Verifying source signature"
    if is_release_tag "$APOTHEM_REF"; then
        check_release_tag "$_cl_tree" "$APOTHEM_REF" "$APOTHEM_ALLOW_UNVERIFIED" || true
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
    if [ -z "$_cl_stage" ]; then
        SOURCE="$APOTHEM_HOME"
        ok "Source ready at $SOURCE (ref: ${APOTHEM_REF})"
    elif [ "$DRY_RUN" = "1" ]; then
        SOURCE="$_cl_tree"
        ok "Source ready at $SOURCE (ref: ${APOTHEM_REF}; dry run, so $APOTHEM_HOME is not changed)"
    else
        swap_in "$_cl_tree" ""
        rm -rf "$_cl_stage"
        trap - EXIT HUP INT TERM
        SOURCE="$APOTHEM_HOME"
        ok "Source ready at $SOURCE (ref: ${APOTHEM_REF})"
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
