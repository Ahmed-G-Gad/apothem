# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
    apothem — PowerShell subcommand router (paired with scripts/apothem POSIX sibling).

.DESCRIPTION
    Dispatches `apothem <subcommand>` to the matching PowerShell script
    in the release-archive root first, then falls back to scripts/installer/
    inside a source checkout. Two metadata subcommands are served inline:
    --help and --version.

.NOTES
    Cross-shell parity: scripts/apothem (POSIX bash) and scripts/apothem.cmd
    (CMD wrapper) are the parallel siblings.
#>

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($PSScriptRoot) {
    $Script:ScriptDir = $PSScriptRoot
} elseif ($PSCommandPath) {
    $Script:ScriptDir = Split-Path -Path $PSCommandPath -Parent
} else {
    $Script:ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
}
$Script:RepoRoot  = Split-Path -Path $Script:ScriptDir -Parent
$Script:PyProject = Join-Path -Path $Script:RepoRoot -ChildPath 'pyproject.toml'

function Show-Usage {
    @'
Usage: apothem <subcommand> [options]

Subcommands:
  install       Install or re-install apothem (idempotent)
  update        Check for upstream updates; --apply to fast-forward
  uninstall     Uninstall apothem (with confirmation prompt and timestamped backup default)
  --help        Show this help text
  --version     Show installed version

Documentation: https://apothem.ahmedgad.com
Source: https://github.com/ahmed-g-gad/apothem
'@
}

function Get-ProjectVersion {
    if (-not (Test-Path -LiteralPath $Script:PyProject)) {
        Write-Error -Message "apothem: pyproject.toml unreadable at $($Script:PyProject)" -Category ResourceUnavailable
        exit 2
    }
    $line = Select-String -LiteralPath $Script:PyProject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $line) {
        Write-Error -Message "apothem: version field absent from $($Script:PyProject)" -Category ObjectNotFound
        exit 2
    }
    $version = $line.Matches[0].Groups[1].Value
    Write-Output "apothem $version"
}

function Invoke-Subscript {
    param(
        [Parameter(Mandatory=$true)][string]$ScriptName,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Forwarded
    )
    $target = Join-Path -Path $Script:RepoRoot -ChildPath $ScriptName
    if (-not (Test-Path -LiteralPath $target)) {
        $target = Join-Path -Path $Script:RepoRoot -ChildPath (Join-Path -Path 'scripts/installer' -ChildPath $ScriptName)
    }
    if (-not (Test-Path -LiteralPath $target)) {
        Write-Error -Message "apothem: $ScriptName missing at $target" -Category ObjectNotFound
        exit 2
    }
    $argsToPass = @()
    if ($null -ne $Forwarded) { $argsToPass = $Forwarded }
    & $target @argsToPass
    exit $LASTEXITCODE
}

function Invoke-Main {
    param([string[]]$Argv)
    if ($null -eq $Argv -or $Argv.Count -eq 0) {
        Show-Usage
        return
    }
    $sub = $Argv[0]
    $rest = @()
    if ($Argv.Count -gt 1) { $rest = $Argv[1..($Argv.Count - 1)] }
    switch ($sub) {
        'install'   { Invoke-Subscript -ScriptName 'install.ps1'   @rest }
        'update'    { Invoke-Subscript -ScriptName 'update.ps1'    @rest }
        'uninstall' { Invoke-Subscript -ScriptName 'uninstall.ps1' @rest }
        '-h'        { Show-Usage }
        '--help'    { Show-Usage }
        'help'      { Show-Usage }
        '-V'        { Get-ProjectVersion }
        '--version' { Get-ProjectVersion }
        default {
            [Console]::Error.WriteLine("apothem: unknown subcommand '$sub'`n")
            [Console]::Error.WriteLine((Show-Usage))
            exit 64
        }
    }
}

Invoke-Main -Argv $args
