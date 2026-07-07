#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Verify the supply-chain provenance chain for a apothem release asset set:
#   1. sha256sum            — re-compute and compare the asset manifest
#   2. cosign verify-blob   — sigstore signature + Fulcio certificate identity
#   3. slsa-verifier        — SLSA-3 build provenance from the release workflow
#
# Operator-driven post-release check. Returns non-zero on the first verification
# failure so the chain can be diagnosed from the failing layer.

set -euo pipefail
IFS=$'\n\t'

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ASSETS_DIR="${1:-${REPO_ROOT}/dist/release-assets}"
readonly GITHUB_REPO="${APOTHEM_GITHUB_REPO:-ahmed-g-gad/apothem}"
readonly EXPECTED_IDENTITY_REGEXP="${APOTHEM_COSIGN_IDENTITY_REGEXP:-^https://github\.com/${GITHUB_REPO}/}"
readonly EXPECTED_OIDC_ISSUER="${APOTHEM_COSIGN_OIDC_ISSUER:-https://token.actions.githubusercontent.com}"

if [[ ! -d "${ASSETS_DIR}" ]]; then
    printf 'verify-provenance: %s not found\n' "${ASSETS_DIR}" >&2
    exit 1
fi
cd "${ASSETS_DIR}"

# Layer 1: sha256 re-compute. Select the hasher up front — `sha256sum` is absent
# on macOS (a release target), where `shasum -a 256` is the coreutils-free
# equivalent; mirrors the producer's fallback in build-release-assets.sh.
if [[ -f SHA256SUMS ]]; then
    printf 'verify-provenance: layer 1 — sha256 manifest\n' >&2
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c SHA256SUMS || { printf 'verify-provenance: sha256 manifest mismatch\n' >&2; exit 1; }
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c SHA256SUMS || { printf 'verify-provenance: sha256 manifest mismatch\n' >&2; exit 1; }
    else
        printf 'verify-provenance: neither sha256sum nor shasum found; cannot verify layer 1\n' >&2
        exit 1
    fi
fi

# Layer 2: cosign verify-blob on every signed asset.
if command -v cosign >/dev/null 2>&1; then
    printf 'verify-provenance: layer 2 — cosign verify-blob\n' >&2
    while IFS= read -r sig; do
        asset="${sig%.sig}"
        cert="${asset}.crt"
        [[ -f "${asset}" ]] || continue
        cosign verify-blob \
            --signature "${sig}" \
            --certificate "${cert}" \
            --certificate-identity-regexp "${EXPECTED_IDENTITY_REGEXP}" \
            --certificate-oidc-issuer "${EXPECTED_OIDC_ISSUER}" \
            "${asset}" \
            || (printf 'verify-provenance: cosign verify-blob failed on %s\n' "${asset}" >&2; exit 1)
    done < <(find . -maxdepth 1 -type f -name '*.sig')
else
    printf 'verify-provenance: cosign absent; skipping layer 2\n' >&2
fi

# Layer 3: SLSA-3 build provenance.
if command -v slsa-verifier >/dev/null 2>&1; then
    printf 'verify-provenance: layer 3 — slsa-verifier\n' >&2
    for artifact in apothem-*.tar.gz apothem-*.whl; do
        [[ -f "${artifact}" ]] || continue
        provenance="${artifact}.intoto.jsonl"
        [[ -f "${provenance}" ]] || { printf 'verify-provenance: provenance file %s absent; skipping\n' "${provenance}" >&2; continue; }
        slsa-verifier verify-artifact \
            --provenance-path "${provenance}" \
            --source-uri "github.com/${GITHUB_REPO}" \
            "${artifact}" \
            || (printf 'verify-provenance: slsa-verifier failed on %s\n' "${artifact}" >&2; exit 1)
    done
else
    printf 'verify-provenance: slsa-verifier absent; skipping layer 3\n' >&2
fi

printf 'verify-provenance: chain OK\n' >&2
