#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Build the full GitHub Releases asset matrix for a apothem version tag.
#
# Emits the following into dist/release-assets/:
#   apothem-v<VERSION>-darwin.tar.gz runtime tarball (re-uses scripts/build_release_tarball.py)
#   apothem-v<VERSION>-linux.tar.gz  runtime tarball (re-uses scripts/build_release_tarball.py)
#   apothem-v<VERSION>-windows.zip   runtime zip (Windows-friendly)
#   apothem-<VERSION>.tar.gz         sdist (copied from dist/; supply-chain evidence)
#   apothem-<VERSION>-py3-none-any.whl wheel (copied from dist/; supply-chain evidence)
#   apothem-v<VERSION>.spdx.json     SBOM (produced by generate-sbom.sh)
#   install.ps1                       Windows installer copy (from dist/install/)
#   SHA256SUMS                        sha256 manifest of every asset above
#   *.cosign.bundle                   Sigstore bundle per asset and for SHA256SUMS (produced by sign-assets.sh)
#
# The sdist + wheel attach to the GitHub Release as supply-chain evidence;
# this script builds them on demand when dist/ does not already carry them.

set -euo pipefail
IFS=$'\n\t'

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly DIST_DIR="${REPO_ROOT}/dist"
readonly ASSETS_DIR="${DIST_DIR}/release-assets"
readonly VERSION="$(
    python - "${REPO_ROOT}/pyproject.toml" <<'PY'
from pathlib import Path
import sys
import tomllib

manifest = Path(sys.argv[1])
metadata = tomllib.loads(manifest.read_text(encoding="utf-8"))
print(metadata["project"]["version"], end="")
PY
)"

if [[ -z "${VERSION}" ]]; then
    printf 'build-release-assets: pyproject.toml project.version is empty\n' >&2
    exit 1
fi

printf 'build-release-assets: building asset matrix for v%s\n' "${VERSION}" >&2

# Clean and recreate the assets directory for a deterministic emission set.
rm -rf "${ASSETS_DIR}"
mkdir -p "${ASSETS_DIR}"

# Platform runtime archives (uses the existing build_release_tarball.py recipe).
if [[ -f "${REPO_ROOT}/scripts/build_release_tarball.py" ]]; then
    for platform in darwin linux windows; do
        python "${REPO_ROOT}/scripts/build_release_tarball.py" \
            --root "${REPO_ROOT}" \
            --out-dir "${ASSETS_DIR}" \
            --name apothem \
            --version "${VERSION}" \
            --platform "${platform}"
    done
fi

# Ensure the sdist + wheel exist; build if absent.
if ! ls "${DIST_DIR}"/apothem-*.tar.gz >/dev/null 2>&1 || ! ls "${DIST_DIR}"/apothem-*-py3-none-any.whl >/dev/null 2>&1; then
    printf 'build-release-assets: sdist + wheel absent; building into %s\n' "${DIST_DIR}" >&2
    if command -v uv >/dev/null 2>&1; then
        (cd "${REPO_ROOT}" && uv build --out-dir "${DIST_DIR}")
    else
        (cd "${REPO_ROOT}" && python -m build --outdir "${DIST_DIR}")
    fi
fi

cp "${DIST_DIR}"/apothem-*.tar.gz "${ASSETS_DIR}/"
cp "${DIST_DIR}"/apothem-*-py3-none-any.whl "${ASSETS_DIR}/"

# Generate SBOM into the assets directory.
if [[ -f "${REPO_ROOT}/scripts/release/generate-sbom.sh" ]]; then
    bash "${REPO_ROOT}/scripts/release/generate-sbom.sh" "${ASSETS_DIR}/apothem-v${VERSION}.spdx.json"
fi

# Copy install.ps1 alongside the assets so the GitHub Release page exposes it.
if [[ -f "${REPO_ROOT}/dist/install/install.ps1" ]]; then
    cp "${REPO_ROOT}/dist/install/install.ps1" "${ASSETS_DIR}/install.ps1"
fi

# Emit the SHA256 manifest spanning every asset. Select the hasher up front so a
# genuine hashing failure surfaces under `set -e` rather than being masked by a
# fallback subshell.
cd "${ASSETS_DIR}"
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -- * > SHA256SUMS
else
    find . -maxdepth 1 -type f ! -name 'SHA256SUMS*' -exec shasum -a 256 {} \; > SHA256SUMS
fi

printf 'build-release-assets: asset matrix emitted at %s\n' "${ASSETS_DIR}" >&2
ls -la "${ASSETS_DIR}" >&2

printf 'build-release-assets: OK (signing deferred to sign-assets.sh)\n' >&2
