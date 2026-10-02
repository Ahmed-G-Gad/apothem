# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Verify a downloaded apothem GitHub Release asset set.

.DESCRIPTION
    Three verification layers, mirroring verify-provenance.sh:
        1. SHA256          re-compute the platform-archive manifest (SHA256SUMS)
        2. cosign          every signature bundle, against the exact certificate
                           identity of the release workflow at this tag and the
                           GitHub Actions OIDC issuer
        3. slsa-verifier   the SLSA build provenance (provenance.intoto.jsonl)
                           for the wheel and sdist, bound to the source repo
                           and tag

    Identity checks are case-sensitive and the certificates carry the owner as
    GitHub reports it, Ahmed-G-Gad, so the default repository uses that
    casing. The identity is exact, never a regular expression.

    Signature bundles are <asset>.cosign.bundle. Releases up to v1.1.0 named
    the platform-archive and SHA256SUMS bundles <asset>.sig; both are accepted.

    Throws on the first failure, naming the failing layer.

.PARAMETER AssetsDir
    Directory holding the downloaded assets. Defaults to the current directory.

.PARAMETER Tag
    Release tag (vX.Y.Z). Defaults to the tag the wheel file name carries.
#>

[CmdletBinding()]
param(
    [string] $AssetsDir = '.',
    [string] $Tag = $env:APOTHEM_RELEASE_TAG
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$GithubRepo = if ($env:APOTHEM_GITHUB_REPO) { $env:APOTHEM_GITHUB_REPO } else { 'Ahmed-G-Gad/apothem' }
$OidcIssuer = if ($env:APOTHEM_COSIGN_OIDC_ISSUER) { $env:APOTHEM_COSIGN_OIDC_ISSUER } else { 'https://token.actions.githubusercontent.com' }

if (-not (Test-Path -LiteralPath $AssetsDir -PathType Container)) {
    throw "verify-provenance: $AssetsDir not found"
}
Push-Location $AssetsDir
try {
    if (-not $Tag) {
        $wheels = @(Get-ChildItem -File -Filter 'apothem-*-py3-none-any.whl')
        if ($wheels.Count -ne 1) {
            throw 'verify-provenance: cannot derive the release tag from the wheel name; pass -Tag vX.Y.Z'
        }
        $Tag = 'v' + ($wheels[0].Name -replace '^apothem-', '' -replace '-py3-none-any\.whl$', '')
    }
    if ($Tag -notmatch '^v\d+\.\d+\.\d+$') { throw "verify-provenance: tag $Tag is not vMAJOR.MINOR.PATCH" }
    $Identity = "https://github.com/$GithubRepo/.github/workflows/release.yml@refs/tags/$Tag"
    Write-Information "verify-provenance: $Tag, identity $Identity" -InformationAction Continue

    $layersRun = 0

    # Layer 1: sha256 manifest of the platform archives.
    if (Test-Path -LiteralPath 'SHA256SUMS') {
        Write-Information 'verify-provenance: layer 1 — SHA256 manifest' -InformationAction Continue
        foreach ($row in Get-Content -LiteralPath 'SHA256SUMS') {
            if ($row -match '^([0-9a-f]{64})\s+(?:\*)?(.+)$') {
                $expected = $Matches[1]
                $file = $Matches[2]
                $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($expected -ne $actual) { throw "verify-provenance: layer 1: hash mismatch on $file" }
            }
        }
        $layersRun++
    }

    # Layer 2: every release asset must carry a bundle that verifies.
    if (Get-Command -Name cosign -ErrorAction SilentlyContinue) {
        Write-Information 'verify-provenance: layer 2 — cosign verify-blob' -InformationAction Continue
        $candidates = @(Get-ChildItem -File -Filter 'apothem-*') + @(Get-ChildItem -File -Filter 'SHA256SUMS') + @(Get-ChildItem -File -Filter 'sbom.cdx.json')
        $signed = 0
        foreach ($item in $candidates) {
            $asset = $item.Name
            if ($asset -like '*.cosign.bundle' -or $asset -like '*.sig') { continue }
            $bundle = if (Test-Path -LiteralPath "$asset.cosign.bundle") { "$asset.cosign.bundle" }
                      elseif (Test-Path -LiteralPath "$asset.sig") { "$asset.sig" }
                      else { $null }
            if (-not $bundle) {
                # Releases up to v1.1.0 did not sign the SBOM; it is checked when signed.
                if ($asset -eq 'sbom.cdx.json') { continue }
                throw "verify-provenance: layer 2: $asset has no signature bundle ($asset.cosign.bundle)"
            }
            & cosign verify-blob `
                --bundle $bundle `
                --certificate-identity $Identity `
                --certificate-oidc-issuer $OidcIssuer `
                $asset
            if ($LASTEXITCODE -ne 0) { throw "verify-provenance: layer 2: cosign verify-blob failed on $asset" }
            $signed++
        }
        if ($signed -eq 0) { throw "verify-provenance: layer 2: no signed release asset found in $AssetsDir" }
        $layersRun++
    } else {
        Write-Information 'verify-provenance: cosign absent; skipping layer 2' -InformationAction Continue
    }

    # Layer 3: SLSA build provenance for the wheel and sdist (the platform
    # archives are not its subjects).
    if (Get-Command -Name slsa-verifier -ErrorAction SilentlyContinue) {
        Write-Information 'verify-provenance: layer 3 — slsa-verifier' -InformationAction Continue
        if (-not (Test-Path -LiteralPath 'provenance.intoto.jsonl')) {
            throw 'verify-provenance: layer 3: provenance.intoto.jsonl not found'
        }
        $subjects = @(Get-ChildItem -File | Where-Object {
                $_.Name -match '^apothem-\d[^/]*-py3-none-any\.whl$' -or $_.Name -match '^apothem-\d[^/]*\.tar\.gz$'
            } | ForEach-Object { $_.Name })
        if ($subjects.Count -eq 0) { throw 'verify-provenance: layer 3: no wheel or sdist to verify' }
        # From the release that started signing the SBOM, it is a subject too.
        if ((Test-Path -LiteralPath 'sbom.cdx.json') -and (Test-Path -LiteralPath 'sbom.cdx.json.cosign.bundle')) {
            $subjects += 'sbom.cdx.json'
        }
        & slsa-verifier verify-artifact `
            --provenance-path provenance.intoto.jsonl `
            --source-uri "github.com/$GithubRepo" `
            --source-tag $Tag `
            @subjects
        if ($LASTEXITCODE -ne 0) { throw 'verify-provenance: layer 3: slsa-verifier failed' }
        $layersRun++
    } else {
        Write-Information 'verify-provenance: slsa-verifier absent; skipping layer 3' -InformationAction Continue
    }

    if ($layersRun -eq 0) {
        throw 'verify-provenance: no verification performed — no SHA256SUMS manifest, no cosign, no slsa-verifier'
    }
    Write-Information "verify-provenance: chain OK ($layersRun of 3 layers verified)" -InformationAction Continue
} finally {
    Pop-Location
}
