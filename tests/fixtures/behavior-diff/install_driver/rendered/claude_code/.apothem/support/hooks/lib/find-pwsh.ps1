# SPDX-License-Identifier: MIT

# Purpose: Locate a real PowerShell >= 7 on PATH for any PowerShell-side
# surface that needs to spawn a pwsh subprocess, rejecting Microsoft Store
# launcher shims (zero-byte stubs at AppData\Local\Microsoft\WindowsApps
# that fail at exec time with "Executable not found").
# Contract: dot-source then call Find-RealPwsh; returns the absolute
# path to a working pwsh interpreter, or $null when none found. Does
# not throw on probe failures — silently skips bad candidates so the
# caller's diagnostic envelope path runs.
# Sibling files in hooks/lib/: find-pwsh.sh (POSIX counterpart),
# find-python.ps1 (PowerShell counterpart for Python — paired-template
# peer), find-python.sh (POSIX counterpart of the Python locator).

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-RealPwsh {
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [int]$MinMajor = 7
    )

    $candidates = @('pwsh', 'pwsh-preview')
    # Build the Windows install-root fallbacks only where those roots exist.
    # Join-Path rejects a null -Path with a terminating
    # ParameterBindingValidationException, and $env:ProgramFiles is unset under
    # pwsh on Linux/macOS — so an unguarded Join-Path here throws and breaks the
    # documented "returns $null, does not throw" contract. The list is built
    # eagerly, before the Phase 1 PATH probe, so the throw would pre-empt even
    # the case where a real pwsh IS on PATH and would have been found.
    $fallbackPaths = @()
    if ($env:ProgramFiles) {
        $fallbackPaths += (Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe')
        $fallbackPaths += (Join-Path $env:ProgramFiles 'PowerShell\7-preview\pwsh.exe')
    }
    if (${env:ProgramFiles(x86)}) {
        $fallbackPaths += (Join-Path ${env:ProgramFiles(x86)} 'PowerShell\7\pwsh.exe')
    }
    $probe = '$PSVersionTable.PSVersion.Major'

    # Phase 1 — PATH probe via Get-Command, rejecting WindowsApps stubs.
    foreach ($name in $candidates) {
        $cmds = @(Get-Command $name -All -ErrorAction SilentlyContinue)
        foreach ($cmd in $cmds) {
            $src = $cmd.Source
            if (-not $src) { continue }
            # Literal substring match (parity with find-python.ps1's `-like`
            # and the POSIX `case *WindowsApps*`); -like avoids the regex
            # semantics of -match, where a metacharacter in the path would
            # change the test.
            if ($src -like '*WindowsApps*') { continue }
            $info = Get-Item -LiteralPath $src -ErrorAction SilentlyContinue
            if (-not $info) { continue }
            if ($info.Length -lt 1024) { continue }

            $output = $null
            try { $output = & $src -NoProfile -Command $probe 2>$null } catch { continue }
            if ($LASTEXITCODE -ne 0) { continue }
            if (-not $output) { continue }
            $trimmed = ($output -join '').Trim()
            $maj = 0
            if (-not [int]::TryParse($trimmed, [ref]$maj)) { continue }
            if ($maj -ge $MinMajor) {
                return $src
            }
        }
    }

    # Phase 2 — canonical Windows install paths.
    foreach ($candidate in $fallbackPaths) {
        if (-not $candidate) { continue }
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $info = Get-Item -LiteralPath $candidate -ErrorAction SilentlyContinue
        if (-not $info) { continue }
        if ($info.Length -lt 1024) { continue }

        $output = $null
        try { $output = & $candidate -NoProfile -Command $probe 2>$null } catch { continue }
        if ($LASTEXITCODE -ne 0) { continue }
        if (-not $output) { continue }
        $trimmed = ($output -join '').Trim()
        $maj = 0
        if (-not [int]::TryParse($trimmed, [ref]$maj)) { continue }
        if ($maj -ge $MinMajor) {
            return $candidate
        }
    }

    return $null
}
