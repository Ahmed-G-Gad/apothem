# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Build the full GitHub Releases asset matrix for a apothem version tag.

.DESCRIPTION
    Emits into dist/release-assets/:
        apothem-v<VERSION>-darwin.tar.gz     runtime tarball
        apothem-v<VERSION>-linux.tar.gz      runtime tarball
        apothem-v<VERSION>-windows.zip       runtime zip
        apothem-<VERSION>.tar.gz             sdist (supply-chain evidence)
        apothem-<VERSION>-py3-none-any.whl   wheel (supply-chain evidence)
        sbom.cdx.json                        CycloneDX SBOM of the wheel and sdist
        install.ps1                           Windows installer copy
        SHA256SUMS                            sha256 manifest

    The sdist + wheel attach to the GitHub Release as supply-chain evidence;
    this script builds them on demand when dist/ does not already carry them.

.EXAMPLE
    pwsh -NoProfile -File scripts/release/build-release-assets.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot   = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..' '..')).Path
$DistDir    = Join-Path $RepoRoot 'dist'
$AssetsDir  = Join-Path $DistDir 'release-assets'
$Version    = (& python -c 'import pathlib, sys, tomllib; data = tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")); print(data["project"]["version"], end="")' (Join-Path $RepoRoot 'pyproject.toml')).Trim()
if ($LASTEXITCODE -ne 0) {
    throw 'build-release-assets: failed to read pyproject.toml project.version'
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw 'build-release-assets: pyproject.toml project.version is empty'
}
Write-Information "build-release-assets: building asset matrix for v$Version" -InformationAction Continue

if (Test-Path -LiteralPath $AssetsDir) {
    Remove-Item -LiteralPath $AssetsDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $AssetsDir | Out-Null

$tarballScript = Join-Path $RepoRoot 'scripts' 'build_release_tarball.py'
if (Test-Path -LiteralPath $tarballScript) {
    foreach ($platform in @('darwin', 'linux', 'windows')) {
        & python $tarballScript `
            --root $RepoRoot `
            --out-dir $AssetsDir `
            --name apothem `
            --version $Version `
            --platform $platform
    }
}

$sdist = @(Get-ChildItem -LiteralPath $DistDir -Filter 'apothem-*.tar.gz'           -File -ErrorAction SilentlyContinue)
$wheel = @(Get-ChildItem -LiteralPath $DistDir -Filter 'apothem-*-py3-none-any.whl' -File -ErrorAction SilentlyContinue)
if ($sdist.Count -eq 0 -or $wheel.Count -eq 0) {
    Write-Information "build-release-assets: sdist + wheel absent; building into $DistDir" -InformationAction Continue
    Push-Location $RepoRoot
    try {
        if (Get-Command -Name uv -ErrorAction SilentlyContinue) {
            & uv build --out-dir $DistDir
        } else {
            & python -m build --outdir $DistDir
        }
        if ($LASTEXITCODE -ne 0) { throw "build-release-assets: package build failed (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
    $sdist = @(Get-ChildItem -LiteralPath $DistDir -Filter 'apothem-*.tar.gz'           -File)
    $wheel = @(Get-ChildItem -LiteralPath $DistDir -Filter 'apothem-*-py3-none-any.whl' -File)
}
$sdist | Copy-Item -Destination $AssetsDir
$wheel | Copy-Item -Destination $AssetsDir

$sbomScript = Join-Path $RepoRoot 'scripts' 'release' 'generate-sbom.ps1'
if (Test-Path -LiteralPath $sbomScript) {
    $sbomOut = Join-Path $AssetsDir 'sbom.cdx.json'
    & pwsh -NoProfile -File $sbomScript -OutputPath $sbomOut -DistDir $AssetsDir
}

$installScript = Join-Path $RepoRoot 'dist' 'install' 'install.ps1'
if (Test-Path -LiteralPath $installScript) {
    Copy-Item -LiteralPath $installScript -Destination (Join-Path $AssetsDir 'install.ps1')
}

# Emit SHA256 manifest.
$manifestPath = Join-Path $AssetsDir 'SHA256SUMS'
$rows = Get-ChildItem -LiteralPath $AssetsDir -File | Where-Object { $_.Name -notlike 'SHA256SUMS*' } | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($_.Name)"
}
Set-Content -LiteralPath $manifestPath -Value $rows -Encoding utf8

Write-Information "build-release-assets: asset matrix emitted at $AssetsDir" -InformationAction Continue
Get-ChildItem -LiteralPath $AssetsDir | Format-Table Name, Length | Out-String | Write-Information -InformationAction Continue
Write-Information 'build-release-assets: OK (signing deferred to sign-assets.ps1)' -InformationAction Continue
