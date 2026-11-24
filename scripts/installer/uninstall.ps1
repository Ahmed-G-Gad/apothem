# SPDX-License-Identifier: MIT

# Purpose: Remove materialized harness config (self-contained - no package
#          to uninstall) and optionally remove the bundled source tree at
#          $APOTHEM_HOME (PowerShell parity to uninstall.sh).
# Usage:   pwsh -NoProfile -File scripts/installer/uninstall.ps1 [-Yes] [-Harness NAME] [-RemoveSource]
#
# One run at a time: the uninstaller holds <APOTHEM_HOME>.lock while it runs,
# as install.ps1 and update.ps1 do, and a second run stops.
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
# A relative APOTHEM_HOME is resolved once, here, against the current
# file-system folder (never a registry or other location the session sits
# in), so every path built from it (the engine paths in PYTHONPATH and in
# the shim among them) is a full path, never one Python would read against
# whatever folder it starts in. A value that names no file-system path
# stops the run.
$ApothemHomeValue = $ApothemHome
$HomeProvider = $null
try {
    Push-Location -LiteralPath (Get-Location -PSProvider FileSystem).ProviderPath
    try {
        $HomeDrive = $null
        $ApothemHome = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ApothemHomeValue, [ref]$HomeProvider, [ref]$HomeDrive)
    } finally {
        Pop-Location
    }
} catch {
    $HomeProvider = $null
}
if (-not $HomeProvider -or $HomeProvider.Name -ne 'FileSystem') {
    Write-Error "  x APOTHEM_HOME is not a usable folder path: $ApothemHomeValue"
}
# A trailing separator would put the lock file beside APOTHEM_HOME inside it
# instead (install.ps1 trims it the same way); a drive root keeps its
# separator.
if ($ApothemHome.Length -gt 1 -and $ApothemHome -notmatch '^[A-Za-z]:[\\/]$') {
    $ApothemHome = $ApothemHome.TrimEnd('\', '/')
}

# Colour only an interactive console. NO_COLOR (https://no-color.org/) or
# redirected output (a pipe, a file, a CI log) gets plain text.
$UseColor = (-not $env:NO_COLOR) -and (-not [Console]::IsOutputRedirected)
function Get-ColorParameter {
    param([string]$Color)
    if ($UseColor) { return @{ ForegroundColor = $Color } }
    return @{}
}
function Write-Bold { param([string]$Msg) $c = Get-ColorParameter White;  Write-Host "`n$Msg" @c }
function Write-Ok   { param([string]$Msg) $c = Get-ColorParameter Green;  Write-Host "  + $Msg" @c }
function Write-Warn { param([string]$Msg) $c = Get-ColorParameter Yellow; Write-Host "  ! $Msg" @c }
function Write-Fail { param([string]$Msg) Write-Error "  x $Msg" }

# Get-LockHome - the path the install lock is named after: APOTHEM_HOME, or,
# when APOTHEM_HOME is a symbolic link or a junction to a folder, that
# folder's own path with every link on the way followed, as install.sh's
# take_lock gets it with cd -P. A run through the link, a run through the
# folder's own path, and a Git Bash run on either then take the same lock.
# The messages still name APOTHEM_HOME as given.
function Get-LockHome {
    $LhKinds = @('SymbolicLink', 'Junction')
    $LhItem = Get-Item -LiteralPath $ApothemHome -Force -ErrorAction SilentlyContinue
    if (-not $LhItem -or $LhKinds -notcontains [string]$LhItem.LinkType) { return $ApothemHome }
    $LhPath = $ApothemHome
    # Each turn follows the first link on the path, from its root; 64 turns
    # stop a loop of links.
    for ($LhTurn = 0; $LhTurn -lt 64; $LhTurn++) {
        $LhRoot = [System.IO.Path]::GetPathRoot($LhPath)
        $LhParts = @($LhPath.Substring($LhRoot.Length).Split([char[]]@([char]'\', [char]'/'), [System.StringSplitOptions]::RemoveEmptyEntries))
        $LhAt = $LhRoot
        $LhFollowed = $false
        for ($LhIndex = 0; $LhIndex -lt $LhParts.Count; $LhIndex++) {
            $LhNext = [System.IO.Path]::Combine($LhAt, $LhParts[$LhIndex])
            $LhStep = Get-Item -LiteralPath $LhNext -Force -ErrorAction SilentlyContinue
            if (-not $LhStep) { return $ApothemHome }
            if ($LhKinds -contains [string]$LhStep.LinkType) {
                $LhTarget = [string]@($LhStep.Target)[0]
                if (-not $LhTarget) { return $ApothemHome }
                if ($LhTarget.StartsWith('\??\', [System.StringComparison]::Ordinal)) { $LhTarget = $LhTarget.Substring(4) }
                # A relative target is read from the folder the link is in.
                $LhJoin = [string[]](@($LhAt, $LhTarget) + @($LhParts | Select-Object -Skip ($LhIndex + 1)))
                $LhPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($LhJoin))
                $LhFollowed = $true
                break
            }
            $LhAt = $LhNext
        }
        if (-not $LhFollowed) {
            if (Test-Path -LiteralPath $LhPath -PathType Container) { return $LhPath.TrimEnd('\', '/') }
            return $ApothemHome
        }
    }
    return $ApothemHome
}

# Lock-ApothemHome - take the install lock: an install, update or uninstall
# holds <APOTHEM_HOME>.lock for its whole run, so two runs never change
# APOTHEM_HOME, or the folders beside it, at the same time (mirrors
# uninstall.sh's take_lock). The lock is a file opened with no sharing, so a
# second open fails while this run holds it; Windows closes it when the run
# ends, a forced kill included, which frees the lock and deletes the file.
# install.sh, update.sh and uninstall.sh use a folder of the same name that
# holds the process ID of the run that made it. That ID cannot be checked
# from here (under Git Bash it is not a Windows process ID), so such a
# folder is reported, with how to remove it, and never taken over. When
# APOTHEM_HOME is a link, the lock sits beside the folder it leads to (see
# Get-LockHome).
$script:HomeLock = $null
$HomeLockPath = "$(Get-LockHome).lock"
function Lock-ApothemHome {
    $LkParent = Split-Path -Parent $HomeLockPath
    # With no folder to hold APOTHEM_HOME there is nothing to work on, and
    # the run stops below without the lock.
    if (-not $LkParent -or -not (Test-Path -LiteralPath $LkParent -PathType Container)) { return }
    $LkItem = Get-Item -LiteralPath $HomeLockPath -Force -ErrorAction SilentlyContinue
    if ($LkItem -and ($LkItem.LinkType -or $LkItem.PSIsContainer)) {
        $LkPid = ''
        if ($LkItem.PSIsContainer -and -not $LkItem.LinkType) {
            try { $LkPid = ([System.IO.File]::ReadAllText((Join-Path $LkItem.FullName 'pid'))).Trim() } catch { $LkPid = '' }
            if ($LkPid -notmatch '^[0-9]+$') {
                # A POSIX run that has just made the lock folder writes
                # its process ID a moment later; look again before
                # calling the lock stale.
                Start-Sleep -Seconds 1
                try { $LkPid = ([System.IO.File]::ReadAllText((Join-Path $LkItem.FullName 'pid'))).Trim() } catch { $LkPid = '' }
            }
        }
        if ($LkPid -notmatch '^[0-9]+$') {
            Write-Fail "$HomeLockPath exists but names no running process; an Apothem run may have left it when it was stopped. Check that no Apothem install, update or uninstall is running, remove $HomeLockPath, then re-run."
        }
        Write-Fail "Another Apothem install, update or uninstall is running on $ApothemHome. Wait for it to finish, then re-run. If none is running, remove $HomeLockPath, then re-run."
    }
    try {
        $script:HomeLock = New-Object System.IO.FileStream -ArgumentList $HomeLockPath, ([System.IO.FileMode]::OpenOrCreate), ([System.IO.FileAccess]::ReadWrite), ([System.IO.FileShare]::None), 4096, ([System.IO.FileOptions]::DeleteOnClose)
    } catch {
        # A sharing violation means another run holds the file; a folder
        # that cannot be written to is a failure of its own.
        $LkError = $_.Exception.GetBaseException()
        if ($LkError -is [System.IO.IOException] -and $LkError -isnot [System.IO.DirectoryNotFoundException] -and $LkError -isnot [System.IO.FileNotFoundException] -and $LkError -isnot [System.IO.PathTooLongException]) {
            Write-Fail "Another Apothem install, update or uninstall is running on $ApothemHome. Wait for it to finish, then re-run. If none is running, remove $HomeLockPath, then re-run."
        }
        # A folder or link made there since the look above (a Git Bash run
        # taking its lock) makes the open fail as a folder does.
        $LkItem = Get-Item -LiteralPath $HomeLockPath -Force -ErrorAction SilentlyContinue
        if ($LkItem -and ($LkItem.LinkType -or $LkItem.PSIsContainer)) {
            Write-Fail "Another Apothem install, update or uninstall is running on $ApothemHome. Wait for it to finish, then re-run. If none is running, remove $HomeLockPath, then re-run."
        }
        Write-Fail "Could not create the lock $HomeLockPath. Check that you can write to $LkParent, then re-run."
    }
}

# Unlock-ApothemHome - let the install lock go: closing the file frees it
# and deletes it.
function Unlock-ApothemHome {
    if ($script:HomeLock) {
        $script:HomeLock.Dispose()
        $script:HomeLock = $null
    }
}

Write-Bold "Apothem uninstaller"
Lock-ApothemHome
try {

# The current folder must never shadow the engine's modules (mirrors
# install.ps1): the engine starts with PYTHONSAFEPATH=1 and a `-c` program
# whose first statement drops a leading '' from sys.path, never with
# `-m apothem`, which puts the working directory first. The programs hold no
# double quote, which Windows PowerShell 5.1 strips from a native command's
# argument.
$DropCwdFromPath = "import sys; sys.path[:1] = [] if sys.path[:1] == [''] else sys.path[:1]"
$EngineProgram = "$DropCwdFromPath; import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"

# Test-AbsolutePath PATH - $true when PATH is a full path. On Windows that is
# a drive letter and a separator (X:\ or X:/) or two separators (a \\server
# or //server share); elsewhere a leading /. A drive-relative C:x or a
# rooted \x is not. Every launcher uses this one rule.
function Test-AbsolutePath {
    param([string]$Path)
    if (-not $Path) { return $false }
    if ([System.IO.Path]::PathSeparator -eq ';') { return ($Path -match '^([A-Za-z]:[\\/]|[\\/]{2})') }
    return $Path.StartsWith('/')
}

# Get-SafePythonPath LEAD USER - LEAD followed by the entries of USER (the
# caller's PYTHONPATH) that are full paths. Python reads an empty or relative
# entry as the current folder, whatever PYTHONSAFEPATH says, so those are
# dropped (mirrors install.ps1). $null when nothing is left.
function Get-SafePythonPath {
    param([string]$Lead, [string]$UserPath)
    $Sep = [System.IO.Path]::PathSeparator
    $Kept = @()
    if ($Lead) { $Kept += $Lead }
    if ($UserPath) { $Kept += @($UserPath.Split($Sep) | Where-Object { Test-AbsolutePath $_ }) }
    if ($Kept.Count -eq 0) { return $null }
    return ($Kept -join $Sep)
}

function Test-ApothemSource {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Dir, 'src', 'apothem')))) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Dir 'pyproject.toml')) -or
           (Test-Path -LiteralPath (Join-Path $Dir '.claude-plugin'))
}

# Resolve a Python interpreter >= 3.10. The probes get the caller's
# PYTHONPATH without its empty and relative entries.
$PY = $null
$PriorProbePyPath = $env:PYTHONPATH
$env:PYTHONPATH = Get-SafePythonPath '' $PriorProbePyPath
try {
    foreach ($Cmd in @('python3', 'python', 'python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10')) {
        $Resolved = Get-Command $Cmd -ErrorAction SilentlyContinue
        if (-not $Resolved) { continue }
        if ($Resolved.Source -and $Resolved.Source -match 'WindowsApps') { continue }
        & $Cmd -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $PY = if ($Resolved.Source) { $Resolved.Source } else { $Cmd }; break }
    }
} finally {
    $env:PYTHONPATH = $PriorProbePyPath
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
$PriorSafePath = $env:PYTHONSAFEPATH
$env:PYTHONPATH = Get-SafePythonPath $EnginePyPath $PriorPyPath
$env:PYTHONSAFEPATH = '1'
try {
    & $PY -c $EngineProgram uninstall --harness $Harness --yes
    if ($LASTEXITCODE -ne 0) { Write-Fail "Harness uninstall failed for $Harness" }
    Write-Ok "Harness $Harness uninstalled"
}
finally {
    $env:PYTHONPATH = $PriorPyPath
    $env:PYTHONSAFEPATH = $PriorSafePath
}

# Entry-point shim ------------------------------------------------------------
#
# Remove the `apothem.cmd` PATH shim install.ps1 placed at
# ${APOTHEM_BIN_DIR:-%LOCALAPPDATA%\Microsoft\WindowsApps}\apothem.cmd (same
# dir/filename derivation). It is removed only when it is Apothem's: the
# shim install.ps1 writes now carries the line
# `rem Apothem entry-point shim (generated by install.ps1).`, and the one
# releases 1.0.1 to 1.5.0 wrote ends in the forwarding line `"<python>" -m
# apothem %*`. An operator's own `apothem.cmd` on PATH is never touched.
# Idempotent: absent shim is a no-op. Never removes the directory, only the
# specific shim file.
$DefaultBinDir = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'Microsoft', 'WindowsApps')
$BinDir = if ($env:APOTHEM_BIN_DIR) { $env:APOTHEM_BIN_DIR } else { $DefaultBinDir }
$Shim = Join-Path $BinDir 'apothem.cmd'
if (Test-Path -LiteralPath $Shim) {
    $ShimText = Get-Content -LiteralPath $Shim -Raw -ErrorAction SilentlyContinue
    $ShimIsOurs = $ShimText -and (
        ($ShimText -match '(?m)^rem Apothem entry-point shim \(generated by install\.ps1\)\.\r?$') -or
        ($ShimText -match '(?m)^"[^"]*"\s+-m apothem %\*'))
    if ($ShimIsOurs) {
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
} finally {
    Unlock-ApothemHome
}
