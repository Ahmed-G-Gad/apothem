# SPDX-License-Identifier: MIT

# Gate post-release follow-up work (Windows / PowerShell counterpart of
# check-release-ready.sh). The script is intentionally small and strict:
# follow-up steps must target an existing non-draft release and every
# required repository workflow for the release commit must already be green.
# It also checks the published CycloneDX SBOM for the tag (see the SBOM
# section below). GH_TOKEN must be set: the script reads releases and workflow
# runs with the GitHub CLI, and the release-cycle runbook documents the scope.

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

if ($isDraft -cne 'false') {
    Write-Error "check-release-ready: $Tag is still a draft release"
    exit 1
}
if ($isPrerelease -cne 'false') {
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
    if ($conclusion -cne 'success') {
        $shown = if ($conclusion) { $conclusion } else { 'missing' }
        Write-Error "check-release-ready: $workflow is not green for $commitSha (conclusion: $shown)"
        exit 1
    }
}

# Assert the SBOM describes this tag and enumerates the frozen vendored closure.
# The vendored packages execute at runtime, so a release whose SBOM omits one
# of them ships an incomplete supply-chain record. The release workflow writes
# the CycloneDX 1.6 JSON SBOM to dist/sbom.cdx.json and attaches it to the
# GitHub Release as sbom.cdx.json. build-release-assets writes the same file
# name into dist/release-assets/, the path checked here: download the
# published asset there (see the release-cycle runbook) or build it first.
# The required names must stay in step with VENDORED in
# scripts/release/generate_sbom.py (rpds-py is apothem-authored and absent).
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '..' '..')).Path
$SbomPath = Join-Path -Path $RepoRoot -ChildPath 'dist' 'release-assets' 'sbom.cdx.json'
if (-not (Test-Path -LiteralPath $SbomPath)) {
    Write-Error "check-release-ready: SBOM not found at $SbomPath (download the published sbom.cdx.json there, or run build-release-assets first)"
    exit 1
}
$sbomAssertScript = @'
import json
import sys

sbom_path, version = sys.argv[1], sys.argv[2]
with open(sbom_path, encoding="utf-8") as handle:
    sbom = json.load(handle)
if sbom.get("bomFormat") != "CycloneDX":
    sys.stderr.write("SBOM is not a CycloneDX document\n")
    sys.exit(1)
root = (sbom.get("metadata") or {}).get("component") or {}
if root.get("purl") != f"pkg:pypi/apothem@{version}":
    sys.stderr.write(f"SBOM describes {root.get('purl')!r}, not apothem {version}\n")
    sys.exit(1)
names = {
    str(c.get("name", "")).lower()
    for c in sbom.get("components", [])
    if c.get("type") == "library"
}
required = ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "pyyaml", "typing-extensions")
missing = [pkg for pkg in required if pkg not in names]
if missing:
    sys.stderr.write("vendored packages missing from SBOM: " + ", ".join(missing) + "\n")
    sys.exit(1)
'@
$sbomVersion = $Tag.Substring(1)
$sbomAssertScript | & python - $SbomPath $sbomVersion
if ($LASTEXITCODE -ne 0) {
    Write-Error "check-release-ready: SBOM at $SbomPath fails the release checks"
    exit 1
}

Write-Information -InformationAction Continue "check-release-ready: $Tag release checks are green"
exit 0
