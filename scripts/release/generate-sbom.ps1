# SPDX-License-Identifier: MIT

#Requires -Version 7.0
<#
.SYNOPSIS
    Generate the CycloneDX SBOM for the built apothem distributions.

.DESCRIPTION
    A thin wrapper around generate_sbom.py, the same generator the release
    workflow runs. It reads the wheel and sdist in -DistDir, lists every
    package vendored under apothem/_vendor (the vendor.txt pins, checked
    against the wheel) and the declared runtime requirements, and records each
    distribution's SHA-256. It describes what ships, not the checkout: build
    the distributions first (python -m build).

.PARAMETER OutputPath
    Destination path for the CycloneDX JSON document. Defaults to
    dist/release-assets/sbom.cdx.json.

.PARAMETER DistDir
    Directory holding the wheel and sdist. Defaults to dist/.
#>

[CmdletBinding()]
param(
    [string] $OutputPath,
    [string] $DistDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..' '..')).Path
if (-not $DistDir) { $DistDir = Join-Path $RepoRoot 'dist' }
if (-not $OutputPath) { $OutputPath = Join-Path $RepoRoot 'dist' 'release-assets' 'sbom.cdx.json' }

$python = Get-Command -Name python3, python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'generate-sbom: no python3 or python on PATH' }

& $python.Source (Join-Path $RepoRoot 'scripts' 'release' 'generate_sbom.py') `
    --dist $DistDir `
    --output $OutputPath
if ($LASTEXITCODE -ne 0) { throw 'generate-sbom: generate_sbom.py failed' }
