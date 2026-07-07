# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Verify the supply-chain provenance chain for a apothem release asset set.

.DESCRIPTION
    Three verification layers:
        1. SHA256                re-compute and compare the asset manifest
        2. cosign verify-blob    sigstore signature + Fulcio certificate identity
        3. slsa-verifier         SLSA-3 build provenance from the release workflow

    Returns non-zero on the first verification failure so the chain can be
    diagnosed from the failing layer.

.PARAMETER AssetsDir
    Asset directory to verify. Defaults to dist/release-assets/.
#>

[CmdletBinding()]
param(
    [string] $AssetsDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..' '..')).Path
if (-not $AssetsDir) { $AssetsDir = Join-Path $RepoRoot 'dist' 'release-assets' }

$GithubRepo              = if ($env:APOTHEM_GITHUB_REPO)              { $env:APOTHEM_GITHUB_REPO }              else { 'ahmed-g-gad/apothem' }
$ExpectedIdentityRegexp  = if ($env:APOTHEM_COSIGN_IDENTITY_REGEXP)   { $env:APOTHEM_COSIGN_IDENTITY_REGEXP }   else { "^https://github\.com/$GithubRepo/" }
$ExpectedOidcIssuer      = if ($env:APOTHEM_COSIGN_OIDC_ISSUER)       { $env:APOTHEM_COSIGN_OIDC_ISSUER }       else { 'https://token.actions.githubusercontent.com' }

if (-not (Test-Path -LiteralPath $AssetsDir)) {
    throw "verify-provenance: $AssetsDir not found"
}
Push-Location $AssetsDir
try {
    # Layer 1: sha256 re-compute against manifest.
    if (Test-Path -LiteralPath 'SHA256SUMS') {
        Write-Information 'verify-provenance: layer 1 — SHA256 manifest' -InformationAction Continue
        $rows = Get-Content -LiteralPath 'SHA256SUMS'
        foreach ($row in $rows) {
            if ($row -match '^([0-9a-f]{64})\s+(?:\*)?(.+)$') {
                $expected = $Matches[1]
                $file     = $Matches[2]
                $actual   = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($expected -ne $actual) { throw "verify-provenance: hash mismatch on $file" }
            }
        }
    }

    # Layer 2: cosign verify-blob.
    if (Get-Command -Name cosign -ErrorAction SilentlyContinue) {
        Write-Information 'verify-provenance: layer 2 — cosign verify-blob' -InformationAction Continue
        Get-ChildItem -LiteralPath $AssetsDir -Filter '*.sig' -File | ForEach-Object {
            $sig    = $_.Name
            $asset  = $sig.Substring(0, $sig.Length - 4)
            $cert   = "$asset.crt"
            if (-not (Test-Path -LiteralPath $asset)) { return }
            & cosign verify-blob `
                --signature $sig `
                --certificate $cert `
                --certificate-identity-regexp $ExpectedIdentityRegexp `
                --certificate-oidc-issuer $ExpectedOidcIssuer `
                $asset
            if ($LASTEXITCODE -ne 0) { throw "verify-provenance: cosign verify-blob failed on $asset" }
        }
    } else {
        Write-Information 'verify-provenance: cosign absent; skipping layer 2' -InformationAction Continue
    }

    # Layer 3: SLSA-3 build provenance.
    if (Get-Command -Name slsa-verifier -ErrorAction SilentlyContinue) {
        Write-Information 'verify-provenance: layer 3 — slsa-verifier' -InformationAction Continue
        $pyArtifacts = @(Get-ChildItem -LiteralPath $AssetsDir -Filter 'apothem-*.tar.gz' -File) + @(Get-ChildItem -LiteralPath $AssetsDir -Filter 'apothem-*.whl' -File)
        foreach ($artifact in $pyArtifacts) {
            $provenance = "$($artifact.FullName).intoto.jsonl"
            if (-not (Test-Path -LiteralPath $provenance)) {
                Write-Information "verify-provenance: provenance file $provenance absent; skipping" -InformationAction Continue
                continue
            }
            & slsa-verifier verify-artifact `
                --provenance-path $provenance `
                --source-uri "github.com/$GithubRepo" `
                $artifact.FullName
            if ($LASTEXITCODE -ne 0) { throw "verify-provenance: slsa-verifier failed on $($artifact.Name)" }
        }
    } else {
        Write-Information 'verify-provenance: slsa-verifier absent; skipping layer 3' -InformationAction Continue
    }

    Write-Information 'verify-provenance: chain OK' -InformationAction Continue
} finally {
    Pop-Location
}
