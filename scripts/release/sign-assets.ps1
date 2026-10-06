# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Cosign keyless-OIDC sign-blob recipe for the GitHub Releases asset matrix.

.DESCRIPTION
    Signs every file in dist/release-assets/ via Sigstore cosign in keyless
    mode (Fulcio-issued short-lived certificate; Rekor transparency-log entry).
    Each asset gets one Sigstore bundle, <asset>.cosign.bundle (signature,
    Fulcio certificate and Rekor entry), matching what release.yml publishes.
    The manifest SHA256SUMS is also signed.

.EXAMPLE
    pwsh -NoProfile -File scripts/release/sign-assets.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot  = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..' '..')).Path
$AssetsDir = Join-Path $RepoRoot 'dist' 'release-assets'

if (-not (Get-Command -Name cosign -ErrorAction SilentlyContinue)) {
    throw 'sign-assets: cosign not installed; see https://docs.sigstore.dev/cosign/installation/'
}
if (-not (Test-Path -LiteralPath $AssetsDir)) {
    throw "sign-assets: $AssetsDir not found; run build-release-assets.ps1 first"
}

Push-Location $AssetsDir
try {
    $env:COSIGN_EXPERIMENTAL = '1'
    # SHA256SUMS is excluded here because the block below signs it on its own.
    # Each keyless sign-blob mints a fresh Fulcio certificate and a Rekor
    # transparency-log entry, so enumerating the manifest in both places would
    # overwrite its outputs and strand one Rekor entry per release.
    $assets = @(Get-ChildItem -LiteralPath $AssetsDir -File | Where-Object {
        $_.Name -notlike '*.cosign.bundle' -and $_.Name -notlike '*.sig' -and $_.Name -notlike '*.crt' -and
        $_.Name -ne 'SHA256SUMS'
    })

    foreach ($asset in $assets) {
        Write-Information "sign-assets: signing $($asset.Name)" -InformationAction Continue
        & cosign sign-blob --yes `
            --bundle "$($asset.Name).cosign.bundle" `
            $asset.Name
        if ($LASTEXITCODE -ne 0) { throw "cosign sign-blob failed on $($asset.Name)" }
    }

    $signed = $assets.Count
    if (Test-Path -LiteralPath 'SHA256SUMS') {
        Write-Information 'sign-assets: signing SHA256SUMS' -InformationAction Continue
        & cosign sign-blob --yes `
            --bundle 'SHA256SUMS.cosign.bundle' `
            'SHA256SUMS'
        if ($LASTEXITCODE -ne 0) { throw 'cosign sign-blob failed on SHA256SUMS' }
        $signed++
    }

    Write-Information "sign-assets: signed $signed artifacts" -InformationAction Continue
    Write-Information 'sign-assets: OK' -InformationAction Continue
} finally {
    Pop-Location
}
