# SPDX-License-Identifier: MIT

# Run this script after a CLI surface change to re-emit the completion scripts;
# byte-identical regeneration is the verification check.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Out = Join-Path $Root "src\apothem\cli\completions"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

# The committed goldens under src/apothem/cli/completions/ are ASCII, BOM-free,
# and LF-terminated. PowerShell's `>` redirection emits UTF-16LE + BOM + CRLF,
# which would diverge from the goldens byte-for-byte; capture stdout instead and
# write it back with an explicit BOM-free UTF-8 encoding and normalized LF EOLs.
#
# Every golden is the SPDX header followed by `apothem completion <shell>`.
# That command pins the `apothem` program name and the _APOTHEM_COMPLETE
# variable, so the emitted script is the same whichever shim runs it. Click's
# `<shell>_source` env-var protocol is not used here: it derives the program
# name from the invocation, so under a `python -m apothem` shim it emitted
# `_python_mapothem_completion` functions bound to `python -m apothem`.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Header = "# SPDX-License-Identifier: MIT`n`n"
$Extensions = [ordered]@{ bash = "bash"; zsh = "zsh"; fish = "fish"; powershell = "ps1" }
foreach ($shell in $Extensions.Keys) {
    $name = "apothem.$($Extensions[$shell])"
    $target = Join-Path $Out $name
    $output = $null
    try {
        $output = & apothem completion $shell
    } catch {
        # Command name did not resolve (apothem not on PATH).
        $LASTEXITCODE = 1
    }
    if ($LASTEXITCODE -ne 0) {
        # Falls back on both an unresolved command name and a non-zero exit, so a
        # broken CLI triggers the python entry point rather than truncating the golden.
        Write-Host "apothem unavailable on PATH; falling back to: python -m apothem"
        $output = & python -m apothem completion $shell
        if ($LASTEXITCODE -ne 0) {
            throw "failed to regenerate $name (apothem off PATH and the python fallback failed; run under PYTHONPATH=src)"
        }
    }
    # Refuse before the write, matching the .sh sibling: a generator that
    # resolves and exits 0 while emitting nothing would otherwise put a
    # header-only file over the committed golden, which the byte-identical
    # verification check then treats as canonical.
    if (-not $output) {
        throw "$name generated empty; refusing to overwrite the golden"
    }
    [System.IO.File]::WriteAllText($target, ($Header + ($output -join "`n") + "`n"), $Utf8NoBom)
    Write-Host "  + $name"
}

Write-Host "Regeneration complete -> $Out"
