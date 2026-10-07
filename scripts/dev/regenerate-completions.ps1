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
# variable, so the emitted script does not depend on how the interpreter was
# invoked. Click's `<shell>_source` env-var protocol is not used here: it
# derives the program name from the invocation, so under a `python -m apothem`
# shim it emitted `_python_mapothem_completion` functions bound to
# `python -m apothem`.
#
# The command always runs from this checkout: src/ goes first on PYTHONPATH and
# nothing is resolved from PATH. An `apothem` on PATH is usually the installer's
# shim, which puts the installed engine's src/ first on PYTHONPATH, so the
# goldens would come from whatever release is installed rather than from the
# tree being committed. APOTHEM_PYTHON overrides the interpreter, as it does for
# the npm shim. PYTHONPATH is restored on exit because $env: changes outlive the
# script in the calling session.
$Python = if ($env:APOTHEM_PYTHON) { $env:APOTHEM_PYTHON } else { "python" }
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Header = "# SPDX-License-Identifier: MIT`n`n"
$Extensions = [ordered]@{ bash = "bash"; zsh = "zsh"; fish = "fish"; powershell = "ps1" }
$SavedPythonPath = $env:PYTHONPATH
$SrcDir = Join-Path $Root "src"
$env:PYTHONPATH = if ($SavedPythonPath) {
    $SrcDir + [System.IO.Path]::PathSeparator + $SavedPythonPath
} else {
    $SrcDir
}
try {
    foreach ($shell in $Extensions.Keys) {
        $name = "apothem.$($Extensions[$shell])"
        $target = Join-Path $Out $name
        $output = $null
        try {
            $output = & $Python -m apothem completion $shell
        } catch {
            throw "failed to regenerate $name ($Python could not run: $($_.Exception.Message); set APOTHEM_PYTHON to an interpreter that provides click and rich)"
        }
        if ($LASTEXITCODE -ne 0) {
            throw "failed to regenerate $name ($Python -m apothem completion $shell exited $LASTEXITCODE; set APOTHEM_PYTHON to an interpreter that provides click and rich)"
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
} finally {
    $env:PYTHONPATH = $SavedPythonPath
}

Write-Host "Regeneration complete -> $Out"
