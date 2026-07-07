# SPDX-License-Identifier: MIT

# Purpose: Remove materialized harness config (self-contained - no package
#          to uninstall) and optionally remove the bundled source tree at
#          $APOTHEM_HOME (PowerShell parity to uninstall.sh).
# Usage:   pwsh -NoProfile -File scripts/installer/uninstall.ps1 [-Yes] [-Harness NAME] [-RemoveSource]
#
# Environment overrides:
#   APOTHEM_HOME     Bundled source location (default: $HOME/.apothem)
#   APOTHEM_SOURCE   Explicit local source tree to drive the CLI from
#   APOTHEM_HARNESS  Harness to uninstall (default: claude-code)

#Requires -Version 5.1

param(
    # Windows PowerShell 5.1 (the #Requires floor) has no null-coalescing `??`;
    # use the if/else subexpression that parses on 5.1 and 7+ alike.
    [string]$Harness = $(if ($env:APOTHEM_HARNESS) { $env:APOTHEM_HARNESS } else { 'claude-code' }),
    [switch]$Yes,
    [switch]$RemoveSource
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ApothemHome = if ($env:APOTHEM_HOME) { $env:APOTHEM_HOME } else { Join-Path $HOME '.apothem' }

function Write-Bold { param([string]$Msg) Write-Host "`n$Msg" -ForegroundColor White }
function Write-Ok   { param([string]$Msg) Write-Host "  + $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  ! $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Error "  x $Msg" }

Write-Bold "Apothem uninstaller"

function Test-ApothemSource {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Dir, 'src', 'apothem')))) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Dir 'pyproject.toml')) -or
           (Test-Path -LiteralPath (Join-Path $Dir '.claude-plugin'))
}

# Resolve a Python interpreter >= 3.10.
$PY = $null
foreach ($Cmd in @('python3', 'python', 'python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10')) {
    $Resolved = Get-Command $Cmd -ErrorAction SilentlyContinue
    if (-not $Resolved) { continue }
    if ($Resolved.Source -and $Resolved.Source -match 'WindowsApps') { continue }
    & $Cmd -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>$null
    if ($LASTEXITCODE -eq 0) { $PY = if ($Resolved.Source) { $Resolved.Source } else { $Cmd }; break }
}
if (-not $PY) { Write-Fail "No Python >= 3.10 found in PATH - nothing to uninstall" }

# Locate the bundled source so the CLI can drive the harness uninstall.
$Source = $null
if ($env:APOTHEM_SOURCE) {
    if (-not (Test-Path -LiteralPath $env:APOTHEM_SOURCE) -or -not (Test-ApothemSource $env:APOTHEM_SOURCE)) {
        Write-Fail "APOTHEM_SOURCE is not an apothem source tree: $($env:APOTHEM_SOURCE)"
    }
    $Source = (Resolve-Path -LiteralPath $env:APOTHEM_SOURCE).Path
} elseif (Test-ApothemSource $ApothemHome) {
    $Source = $ApothemHome
}
if (-not $Source) { Write-Fail "No apothem source found at $ApothemHome - nothing to uninstall" }
$SrcPath = Join-Path $Source 'src'

if (-not $Yes) {
    $Ans = Read-Host "  Remove $Harness harness configuration? [y/N]"
    if ($Ans -notmatch '^[Yy]') { Write-Warn "Aborted."; exit 0 }
}

Write-Bold "Uninstalling harness: $Harness"
# Vendor-first PYTHONPATH mirrors the install/update invocations.
$VendorPath = [System.IO.Path]::Combine($SrcPath, 'apothem', '_vendor')
$EnginePyPath = "$VendorPath$([System.IO.Path]::PathSeparator)$SrcPath"
$PriorPyPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($PriorPyPath) { "$EnginePyPath$([System.IO.Path]::PathSeparator)$PriorPyPath" } else { $EnginePyPath }
try {
    & $PY -m apothem uninstall --harness $Harness --yes
    if ($LASTEXITCODE -ne 0) { Write-Fail "Harness uninstall failed for $Harness" }
    Write-Ok "Harness $Harness uninstalled"
}
finally {
    $env:PYTHONPATH = $PriorPyPath
}

# Entry-point shim ------------------------------------------------------------
#
# Remove the `apothem.cmd` PATH shim install.ps1 placed at
# ${APOTHEM_BIN_DIR:-%LOCALAPPDATA%\Microsoft\WindowsApps}\apothem.cmd (same
# dir/filename derivation). The .cmd body carries no marker comment, so match
# its distinctive `-m apothem %*` forwarding line before removing — an
# operator's own `apothem.cmd` on PATH is never touched. Idempotent: absent
# shim is a no-op. Never removes the directory — only the specific shim file.
$DefaultBinDir = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'Microsoft', 'WindowsApps')
$BinDir = if ($env:APOTHEM_BIN_DIR) { $env:APOTHEM_BIN_DIR } else { $DefaultBinDir }
$Shim = Join-Path $BinDir 'apothem.cmd'
if (Test-Path -LiteralPath $Shim) {
    $ShimText = Get-Content -LiteralPath $Shim -Raw -ErrorAction SilentlyContinue
    if ($ShimText -and $ShimText -match '(?m)^"[^"]*"\s+-m apothem %\*') {
        try {
            Remove-Item -Force -LiteralPath $Shim
            Write-Ok "Removed apothem command: $Shim"
        } catch {
            Write-Warn "Could not remove the apothem shim at $Shim - remove it manually."
        }
    }
}

if ($RemoveSource) {
    # Only the managed clone at APOTHEM_HOME is removable; an explicit
    # APOTHEM_SOURCE (operator's own checkout) is never deleted.
    if (($Source -eq $ApothemHome) -and (Test-Path -LiteralPath (Join-Path $ApothemHome '.git'))) {
        $Proceed = $true
        if (-not $Yes) {
            $Ans = Read-Host "  Remove the bundled source at $ApothemHome? [y/N]"
            if ($Ans -notmatch '^[Yy]') { Write-Warn "Kept the bundled source."; $Proceed = $false }
        }
        if ($Proceed) {
            Write-Bold "Removing bundled source"
            Remove-Item -Recurse -Force -LiteralPath $ApothemHome
            Write-Ok "Removed $ApothemHome"
        }
    } else {
        Write-Warn "Source at $Source is operator-owned (not the managed clone) - not removed."
    }
}

Write-Bold "Uninstall complete."
Write-Host @"

Next steps:
  1. Remove another harness:        pwsh -NoProfile -File scripts/installer/uninstall.ps1 -Harness <name>
  2. Remove the bundled source too: pwsh -NoProfile -File scripts/installer/uninstall.ps1 -RemoveSource -Yes
  3. Re-install a harness later:    pwsh -NoProfile -File scripts/installer/install.ps1

"@
