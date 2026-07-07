# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Generate an SPDX-JSON Software Bill of Materials for the apothem source tree.

.DESCRIPTION
    Uses Anchore's `syft` as the canonical generator. The SBOM enumerates every
    Python package declared in pyproject.toml plus the host-discovered transitive
    set; consumers verify the SBOM against the SLSA build provenance and the
    sigstore signature to establish a complete supply-chain provenance chain.

.PARAMETER OutputPath
    Destination path for the SPDX-JSON document. Defaults to
    dist/release-assets/apothem-v<VERSION>.spdx.json.
#>

[CmdletBinding()]
param(
    [string] $OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ParentDir = Join-Path -Path $PSScriptRoot -ChildPath '..'
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $ParentDir -ChildPath '..')).Path
$versionScript = @'
import pathlib
import re
import sys

manifest = pathlib.Path(sys.argv[1])
text = manifest.read_text(encoding="utf-8")

try:
    import tomllib
except ModuleNotFoundError:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', text)
    if match is None:
        raise SystemExit("pyproject.toml project.version not found")
    print(match.group(1), end="")
else:
    data = tomllib.loads(text)
    print(data["project"]["version"], end="")
'@
$Version  = (& python -c $versionScript (Join-Path -Path $RepoRoot -ChildPath 'pyproject.toml')).Trim()
if (-not $Version) {
    throw 'generate-sbom: pyproject.toml project.version is empty'
}

if (-not $OutputPath) {
    $DistDir = Join-Path -Path $RepoRoot -ChildPath 'dist'
    $ReleaseAssetsDir = Join-Path -Path $DistDir -ChildPath 'release-assets'
    $OutputPath = Join-Path -Path $ReleaseAssetsDir -ChildPath "apothem-v$Version.spdx.json"
}

if (-not (Get-Command -Name syft -ErrorAction SilentlyContinue)) {
    throw 'generate-sbom: syft not installed; see https://github.com/anchore/syft#installation'
}

$OutDir = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
}
Write-Information "generate-sbom: emitting SPDX-JSON for $RepoRoot -> $OutputPath" -InformationAction Continue

& syft packages "dir:$RepoRoot" `
    --exclude './.audit/**' `
    --exclude './.apothem/**' `
    --exclude './.plans/**' `
    --exclude './projects/**' `
    --exclude './memory/**' `
    --exclude './node_modules/**' `
    --exclude './.git/**' `
    -o "spdx-json=$OutputPath"
if ($LASTEXITCODE -ne 0) { throw "syft failed (exit $LASTEXITCODE)" }

# Enumerate the FROZEN vendored closure (src/apothem/_vendor/) in the SBOM.
# The vendored tree is a flattened source vendoring with no *.dist-info, so the
# dir-scan above does NOT catalog attrs / jsonschema / referencing /
# jsonschema_specifications / PyYAML / typing_extensions. The pinned closure is
# recorded in requirements form at src/apothem/_vendor/vendor.txt; syft's
# python-package-cataloger recognises a requirements file by its name glob, so
# the closure is staged under a recognised name, scanned, and its package
# entries merged into the main SBOM.
$VendorReq = Join-Path -Path $RepoRoot -ChildPath 'src/apothem/_vendor/vendor.txt'
$StageDir = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath ([System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
try {
    Copy-Item -LiteralPath $VendorReq -Destination (Join-Path -Path $StageDir -ChildPath 'requirements.txt')
    $VendorSbom = Join-Path -Path $StageDir -ChildPath 'vendor.spdx.json'
    & syft packages "dir:$StageDir" -o "spdx-json=$VendorSbom"
    if ($LASTEXITCODE -ne 0) { throw "syft (vendored closure) failed (exit $LASTEXITCODE)" }

    $mergeScript = @'
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

sys.stderr.write("generate-sbom: merged vendored packages: %s\n" % (", ".join(sorted(added)) or "(none)"))
'@
    & python -c $mergeScript $OutputPath $VendorSbom
    if ($LASTEXITCODE -ne 0) { throw 'generate-sbom: vendored-package merge failed' }
}
finally {
    Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
}

$validateScript = @'
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d.get("spdxVersion", "").startswith("SPDX"), "not an SPDX document"
assert d.get("packages"), "no packages enumerated"
names = {p.get("name", "").lower() for p in d["packages"]}
required = ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "pyyaml", "typing-extensions")
missing = [pkg for pkg in required if pkg not in names]
assert not missing, "vendored packages missing from SBOM: " + ", ".join(missing)
'@
& python -c $validateScript $OutputPath
if ($LASTEXITCODE -ne 0) { throw 'generate-sbom: emitted SBOM failed shape/vendored-package validation' }

Write-Information "generate-sbom: OK ($OutputPath)" -InformationAction Continue
