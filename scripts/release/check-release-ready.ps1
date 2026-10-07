# SPDX-License-Identifier: MIT

# Gate post-release follow-up work (Windows / PowerShell counterpart of
# check-release-ready.sh). The script is intentionally small and strict:
# follow-up steps must target an existing non-draft release and every
# required repository workflow for the release commit must already be green.

#Requires -Version 7.0

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Tag
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY }
        elseif ($env:APOTHEM_GITHUB_REPO) { $env:APOTHEM_GITHUB_REPO }
        else { 'ahmed-g-gad/apothem' }

if (-not $env:GH_TOKEN) {
    Write-Error 'check-release-ready: GH_TOKEN is required'
    exit 1
}

if ($Tag -cnotmatch '^v[0-9]+\.[0-9]+\.[0-9]+\z') {
    Write-Error "check-release-ready: $Tag is not a vMAJOR.MINOR.PATCH tag"
    exit 1
}

$releaseState = gh release view $Tag --repo $Repo `
    --json isDraft,isPrerelease,tagName `
    --jq '[.isDraft, .isPrerelease] | @tsv'
$isDraft, $isPrerelease = $releaseState -split "`t"

if ($isDraft -ne 'false') {
    Write-Error "check-release-ready: $Tag is still a draft release"
    exit 1
}
if ($isPrerelease -ne 'false') {
    Write-Error "check-release-ready: $Tag is marked prerelease"
    exit 1
}

$commitSha = (git rev-list -n 1 $Tag).Trim()
if (-not $commitSha) {
    Write-Error "check-release-ready: cannot resolve commit for $Tag"
    exit 1
}

$requiredWorkflows = @(
    'ci.yml'
    'ci-matrix.yml'
    'clean-install-gate.yml'
    'codeql.yml'
    'conformity.yml'
    'harness-matrix.yml'
    'license-audit.yml'
    'pip-audit.yml'
    'publish-static-site.yml'
    'release.yml'
    'scorecard.yml'
)

foreach ($workflow in $requiredWorkflows) {
    $conclusion = gh run list --repo $Repo --workflow $workflow `
        --commit $commitSha --limit 20 `
        --json conclusion,status `
        --jq 'map(select(.status == "completed")) | first | .conclusion // ""'
    if ($conclusion -ne 'success') {
        $shown = if ($conclusion) { $conclusion } else { 'missing' }
        Write-Error "check-release-ready: $workflow is not green for $commitSha (conclusion: $shown)"
        exit 1
    }
}

# Assert the built SBOM enumerates the frozen vendored closure. The vendored
# packages execute at runtime, so a release whose SBOM omits one of them ships
# an incomplete supply-chain record. generate-sbom emits the SBOM into
# dist/release-assets/apothem-<Tag>.spdx.json.
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '..' '..')).Path
$SbomPath = Join-Path -Path $RepoRoot -ChildPath 'dist' 'release-assets' "apothem-$Tag.spdx.json"
if (-not (Test-Path -LiteralPath $SbomPath)) {
    Write-Error "check-release-ready: built SBOM not found at $SbomPath (run build-release-assets first)"
    exit 1
}
$sbomAssertScript = @'
import json
import sys

sbom = json.load(open(sys.argv[1], encoding="utf-8"))
names = {p.get("name", "").lower() for p in sbom.get("packages", [])}
required = ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "pyyaml", "typing-extensions")
missing = [pkg for pkg in required if pkg not in names]
if missing:
    sys.stderr.write("vendored packages missing from SBOM: " + ", ".join(missing) + "\n")
    sys.exit(1)
'@
& python -c $sbomAssertScript $SbomPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "check-release-ready: SBOM at $SbomPath omits one or more vendored packages"
    exit 1
}

Write-Information -InformationAction Continue "check-release-ready: $Tag release checks are green"
exit 0
