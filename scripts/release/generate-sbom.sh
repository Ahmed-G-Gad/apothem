#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Generate an SPDX-JSON Software Bill of Materials for the apothem source tree.
#
# Uses Anchore's `syft` (https://github.com/anchore/syft) as the canonical
# generator. Output path defaults to dist/release-assets/apothem-v<VERSION>.spdx.json
# unless the first positional argument supplies an alternative.
#
# The SBOM enumerates every Python package declared in pyproject.toml plus the
# host-discovered transitive set; consumers verify the SBOM against
# the SLSA build provenance and the sigstore signature to establish a complete
# supply-chain provenance chain.

set -euo pipefail
IFS=$'\n\t'

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly VERSION="$(
    python - "${REPO_ROOT}/pyproject.toml" <<'PY'
from pathlib import Path
import re
import sys

manifest = Path(sys.argv[1])
text = manifest.read_text(encoding="utf-8")

try:
    import tomllib
except ModuleNotFoundError:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', text)
    if match is None:
        raise SystemExit("pyproject.toml project.version not found")
    print(match.group(1), end="")
else:
    metadata = tomllib.loads(text)
    print(metadata["project"]["version"], end="")
PY
)"
readonly DEFAULT_OUT="${REPO_ROOT}/dist/release-assets/apothem-v${VERSION}.spdx.json"
readonly OUT_PATH="${1:-${DEFAULT_OUT}}"

if [[ -z "${VERSION}" ]]; then
    printf 'generate-sbom: pyproject.toml project.version is empty\n' >&2
    exit 1
fi

if ! command -v syft >/dev/null 2>&1; then
    printf 'generate-sbom: syft not installed; see https://github.com/anchore/syft#installation\n' >&2
    exit 1
fi

mkdir -p "$(dirname "${OUT_PATH}")"
printf 'generate-sbom: emitting SPDX-JSON for %s -> %s\n' "${REPO_ROOT}" "${OUT_PATH}" >&2

syft packages "dir:${REPO_ROOT}" \
    --exclude "./.audit/**" \
    --exclude "./.apothem/**" \
    --exclude "./.plans/**" \
    --exclude "./projects/**" \
    --exclude "./memory/**" \
    --exclude "./node_modules/**" \
    --exclude "./.git/**" \
    -o "spdx-json=${OUT_PATH}"

# Enumerate the FROZEN vendored closure (src/apothem/_vendor/) in the SBOM.
#
# The vendored tree is a flattened source vendoring with no *.dist-info /
# METADATA, so syft's dir-scan above does NOT catalog attrs / jsonschema /
# referencing / jsonschema_specifications / PyYAML / typing_extensions (the
# `rpds` shim is apothem-authored, not an upstream distribution). The pinned
# closure is recorded in requirements form at src/apothem/_vendor/vendor.txt;
# syft's python-package-cataloger recognises a requirements file by its name
# glob, so the closure is staged under a recognised name, scanned, and its
# package entries merged into the main SBOM. This keeps the SBOM's supply-chain
# picture complete: the versions that actually execute at runtime are listed.
readonly VENDOR_REQ="${REPO_ROOT}/src/apothem/_vendor/vendor.txt"
readonly STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR}"' EXIT
cp "${VENDOR_REQ}" "${STAGE_DIR}/requirements.txt"

readonly VENDOR_SBOM="${STAGE_DIR}/vendor.spdx.json"
syft packages "dir:${STAGE_DIR}" -o "spdx-json=${VENDOR_SBOM}"

# Merge the vendored package entries into the main SBOM (dedup by name+version;
# skip the synthetic directory artifact syft emits for the staging source).
python - "${OUT_PATH}" "${VENDOR_SBOM}" <<'PY'
import json
import sys

main_path, vendor_path = sys.argv[1], sys.argv[2]
with open(main_path, encoding="utf-8") as handle:
    main = json.load(handle)
with open(vendor_path, encoding="utf-8") as handle:
    vendor = json.load(handle)

main_packages = main.setdefault("packages", [])
seen = {(p.get("name"), p.get("versionInfo")) for p in main_packages}
added = []
for pkg in vendor.get("packages", []):
    # Real Python packages carry a versionInfo; skip the synthetic dir artifact.
    if not pkg.get("versionInfo"):
        continue
    key = (pkg.get("name"), pkg.get("versionInfo"))
    if key in seen:
        continue
    seen.add(key)
    main_packages.append(pkg)
    added.append(pkg["name"])

with open(main_path, "w", encoding="utf-8") as handle:
    json.dump(main, handle, indent=2)

sys.stderr.write(
    "generate-sbom: merged vendored packages: %s\n" % (", ".join(sorted(added)) or "(none)")
)
PY

# Sanity-check that the output is non-empty JSON with expected SPDX shape AND
# that every vendored distribution is enumerated.
if ! python -c "import json,sys; d=json.load(open(sys.argv[1])); assert d.get('spdxVersion','').startswith('SPDX'), 'not an SPDX document'; assert d.get('packages'), 'no packages enumerated'; names={p.get('name','').lower() for p in d['packages']}; missing=[v for v in ('attrs','jsonschema','jsonschema-specifications','referencing','pyyaml','typing-extensions') if v not in names]; assert not missing, 'vendored packages missing from SBOM: '+', '.join(missing)" "${OUT_PATH}" 2>/dev/null; then
    printf 'generate-sbom: emitted SBOM failed shape/vendored-package validation\n' >&2
    exit 1
fi

printf 'generate-sbom: OK (%s)\n' "${OUT_PATH}" >&2
