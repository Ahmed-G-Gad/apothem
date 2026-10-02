#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Verify a downloaded apothem GitHub Release asset set:
#   1. sha256sum            — re-compute the platform-archive manifest (SHA256SUMS)
#   2. cosign verify-blob   — every signature bundle, against the exact
#                             certificate identity of the release workflow at
#                             this tag and the GitHub Actions OIDC issuer
#   3. slsa-verifier        — the SLSA build provenance (provenance.intoto.jsonl)
#                             for the wheel and sdist, bound to the source repo
#                             and tag
#
# Usage:
#   verify-provenance.sh [--tag vX.Y.Z] [ASSETS_DIR]
#
# ASSETS_DIR defaults to the current directory (where `gh release download`
# puts the assets). The tag defaults to the one named by the wheel file
# (apothem-X.Y.Z-py3-none-any.whl -> vX.Y.Z).
#
# Identity checks are case-sensitive and the certificates carry the owner as
# GitHub reports it, `Ahmed-G-Gad`, so the default repository uses that
# casing. The identity is exact, never a regular expression: an unanchored
# pattern also matches a forged subject that merely contains the repo path.
#
# Signature bundles are `<asset>.cosign.bundle`. Releases up to v1.1.0 named
# the platform-archive and SHA256SUMS bundles `<asset>.sig`; both are accepted.
#
# Returns non-zero on the first failure, naming the failing layer.

set -euo pipefail
IFS=$'\n\t'

GITHUB_REPO="${APOTHEM_GITHUB_REPO:-Ahmed-G-Gad/apothem}"
OIDC_ISSUER="${APOTHEM_COSIGN_OIDC_ISSUER:-https://token.actions.githubusercontent.com}"
TAG="${APOTHEM_RELEASE_TAG:-}"
ASSETS_DIR="."

while (( $# > 0 )); do
    case "$1" in
        --tag) TAG="${2:?--tag needs a value}"; shift 2 ;;
        --tag=*) TAG="${1#--tag=}"; shift ;;
        -h|--help) sed -n '4,27p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) ASSETS_DIR="$1"; shift ;;
    esac
done

fail() { printf 'verify-provenance: %s\n' "$*" >&2; exit 1; }

[[ -d "${ASSETS_DIR}" ]] || fail "${ASSETS_DIR} not found"
cd "${ASSETS_DIR}"
shopt -s nullglob

if [[ -z "${TAG}" ]]; then
    wheels=(apothem-*-py3-none-any.whl)
    (( ${#wheels[@]} == 1 )) \
        || fail "cannot derive the release tag from the wheel name; pass --tag vX.Y.Z"
    version="${wheels[0]#apothem-}"
    TAG="v${version%-py3-none-any.whl}"
fi
[[ "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "tag ${TAG} is not vMAJOR.MINOR.PATCH"
readonly IDENTITY="https://github.com/${GITHUB_REPO}/.github/workflows/release.yml@refs/tags/${TAG}"
printf 'verify-provenance: %s, identity %s\n' "${TAG}" "${IDENTITY}" >&2

# Count the layers that ran. Each layer depends on a tool or file being
# present, and a run that verified nothing must not report success.
layers_run=0

# Layer 1: sha256 manifest of the platform archives. `sha256sum` is absent on
# macOS, where `shasum -a 256` is the equivalent.
if [[ -f SHA256SUMS ]]; then
    printf 'verify-provenance: layer 1 — sha256 manifest\n' >&2
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c SHA256SUMS >&2 || fail "layer 1: sha256 manifest mismatch"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c SHA256SUMS >&2 || fail "layer 1: sha256 manifest mismatch"
    else
        fail "layer 1: neither sha256sum nor shasum found"
    fi
    layers_run=$((layers_run + 1))
fi

# The bundle that signs one asset: the current name, else the legacy one.
bundle_for() {
    if [[ -f "$1.cosign.bundle" ]]; then
        printf '%s\n' "$1.cosign.bundle"
    elif [[ -f "$1.sig" ]]; then
        printf '%s\n' "$1.sig"
    fi
}

# Layer 2: every release asset must carry a bundle, and every bundle must
# verify against the exact workflow identity.
if command -v cosign >/dev/null 2>&1; then
    printf 'verify-provenance: layer 2 — cosign verify-blob\n' >&2
    signed=0
    for asset in apothem-* SHA256SUMS sbom.cdx.json; do
        [[ -f "${asset}" ]] || continue
        case "${asset}" in *.cosign.bundle|*.sig) continue ;; esac
        bundle="$(bundle_for "${asset}")"
        if [[ -z "${bundle}" ]]; then
            # Releases up to v1.1.0 did not sign the SBOM; it is checked when signed.
            [[ "${asset}" == sbom.cdx.json ]] && continue
            fail "layer 2: ${asset} has no signature bundle (${asset}.cosign.bundle)"
        fi
        cosign verify-blob \
            --bundle "${bundle}" \
            --certificate-identity "${IDENTITY}" \
            --certificate-oidc-issuer "${OIDC_ISSUER}" \
            "${asset}" >&2 \
            || fail "layer 2: cosign verify-blob failed on ${asset}"
        signed=$((signed + 1))
    done
    (( signed > 0 )) || fail "layer 2: no signed release asset found in ${ASSETS_DIR}"
    layers_run=$((layers_run + 1))
else
    printf 'verify-provenance: cosign absent; skipping layer 2\n' >&2
fi

# Layer 3: SLSA build provenance. One provenance file covers the build job's
# outputs (wheel and sdist); the platform archives are not its subjects.
if command -v slsa-verifier >/dev/null 2>&1; then
    printf 'verify-provenance: layer 3 — slsa-verifier\n' >&2
    [[ -f provenance.intoto.jsonl ]] || fail "layer 3: provenance.intoto.jsonl not found"
    subjects=(apothem-[0-9]*-py3-none-any.whl apothem-[0-9]*.tar.gz)
    (( ${#subjects[@]} > 0 )) || fail "layer 3: no wheel or sdist to verify"
    slsa-verifier verify-artifact \
        --provenance-path provenance.intoto.jsonl \
        --source-uri "github.com/${GITHUB_REPO}" \
        --source-tag "${TAG}" \
        "${subjects[@]}" >&2 \
        || fail "layer 3: slsa-verifier failed"
    layers_run=$((layers_run + 1))
else
    printf 'verify-provenance: slsa-verifier absent; skipping layer 3\n' >&2
fi

(( layers_run > 0 )) \
    || fail "no verification performed — no SHA256SUMS manifest, no cosign, no slsa-verifier"

printf 'verify-provenance: chain OK (%d of 3 layers verified)\n' "${layers_run}" >&2
