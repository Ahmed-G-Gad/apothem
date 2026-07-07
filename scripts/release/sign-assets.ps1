# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Cosign keyless-OIDC sign-blob recipe for the GitHub Releases asset matrix.

.DESCRIPTION
    Signs every file in dist/release-assets/ via Sigstore cosign in keyless
    mode (Fulcio-issued short-lived certificate; Rekor transparency-log entry).
    Per-asset outputs: <asset>.sig (sigstore bundle), <asset>.crt (Fulcio chain).
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
    $assets = @(Get-ChildItem -LiteralPath $AssetsDir -File | Where-Object {
        $_.Name -notlike '*.sig' -and $_.Name -notlike '*.crt'
    })

    foreach ($asset in $assets) {
        Write-Information "sign-assets: signing $($asset.Name)" -InformationAction Continue
        & cosign sign-blob --yes `
            --output-signature "$($asset.Name).sig" `
            --output-certificate "$($asset.Name).crt" `
            $asset.Name
        if ($LASTEXITCODE -ne 0) { throw "cosign sign-blob failed on $($asset.Name)" }
    }

    if (Test-Path -LiteralPath 'SHA256SUMS') {
        & cosign sign-blob --yes `
            --output-signature 'SHA256SUMS.sig' `
            --output-certificate 'SHA256SUMS.crt' `
            'SHA256SUMS'
        if ($LASTEXITCODE -ne 0) { throw 'cosign sign-blob failed on SHA256SUMS' }
    }

    Write-Information "sign-assets: signed $($assets.Count) artifacts" -InformationAction Continue
    Write-Information 'sign-assets: OK' -InformationAction Continue
} finally {
    Pop-Location
}
