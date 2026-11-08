# SPDX-License-Identifier: MIT

# Purpose: Locate a real CPython >= 3.10 on PATH for the PowerShell
# bootstrap stub, rejecting Microsoft Store launcher shims (zero-byte
# stubs at AppData\Local\Microsoft\WindowsApps).
# Contract: dot-source then call Find-RealPython; returns the absolute
# path to a working interpreter, or $null when none found. Does not
# throw on probe failures — silently skips bad candidates.
# Sibling files in hooks/lib/: find-python.sh (POSIX counterpart),
# bootstrap.ps1 (the script that dot-sources this locator),
# bootstrap.sh (POSIX counterpart of the bootstrap stub).

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-RealPython {
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [int]$MinMajor = 3,
        [int]$MinMinor = 10
    )

    $candidates = @('python', 'python3', 'python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10')
    $probe = 'import sys; sys.stdout.write(str(sys.version_info.major) + chr(32) + str(sys.version_info.minor))'

    foreach ($name in $candidates) {
        # PATH resolution: Get-Command searches only the non-empty directories
        # in $env:PATH and never the current directory implicitly, so an empty
        # PATH segment (a doubled ';;' or a leading/trailing separator) yields
        # no candidate here. The cwd-from-empty-segment footgun closed in the
        # sibling find-python.sh / python_resolver.py PATH walks does not arise
        # in this stub. Do NOT replace Get-Command with a manual PATH walk that
        # maps empty segments to cwd: an explicit '.' entry on PATH is honored,
        # an empty one is not. (Verified against Windows PowerShell.)
        $cmds = @(Get-Command $name -All -ErrorAction SilentlyContinue)
        foreach ($cmd in $cmds) {
            $src = $cmd.Source
            if (-not $src) { continue }
            # Literal substring match (parity with the POSIX `${v#*WindowsApps}`
            # prefix-strip in find-python.sh); -like avoids regex semantics.
            if ($src -like '*WindowsApps*') { continue }
            $info = Get-Item -LiteralPath $src -ErrorAction SilentlyContinue
            if (-not $info) { continue }
            if ($info.Length -lt 1024) { continue }

            $output = $null
            try { $output = & $src -c $probe 2>$null } catch { continue }
            if ($LASTEXITCODE -ne 0) { continue }
            if (-not $output) { continue }
            $trimmed = ($output -join '').Trim()
            $parts = $trimmed.Split(' ')
            if ($parts.Count -lt 2) { continue }
            $maj = 0; $min = 0
            if (-not [int]::TryParse($parts[0], [ref]$maj)) { continue }
            if (-not [int]::TryParse($parts[1], [ref]$min)) { continue }
            if ($maj -gt $MinMajor -or ($maj -eq $MinMajor -and $min -ge $MinMinor)) {
                return $src
            }
        }
    }
    return $null
}
