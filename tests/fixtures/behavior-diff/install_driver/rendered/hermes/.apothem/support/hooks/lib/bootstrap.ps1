# SPDX-License-Identifier: MIT

# Purpose: PowerShell bootstrap stub for apothem hook events. Resolves
# the project root, locates a real CPython >= 3.10 via find-python.ps1,
# then invokes hooks/dispatch.py with the event name (and optional
# context-file relative to project root).
# Contract: stdout passthrough; exit 0 always (fail-open) so hook failures
# never stall the host harness; missing interpreter or dispatcher emits a JSON
# diagnostic envelope on stdout.
# Sibling files in hooks/lib/: bootstrap.sh (POSIX counterpart),
# find-python.ps1 (interpreter locator this stub dot-sources),
# find-python.sh (POSIX counterpart of the locator).
#
# Invocation contract (event name + optional context file are positional; the
# event also binds via -HookEvent, with -Event retained as an alias):
#   powershell -NoProfile -ExecutionPolicy Bypass -File `
#     "<root>\hooks\lib\bootstrap.ps1" <event> [<context-file>]
#
# Root discovery order:
#   1. $env:CLAUDE_PROJECT_DIR if it points at a directory containing hooks\.
#   2. $env:LLM_PROJECT_DIR (vendor-neutral alias) if it points at a
#      directory containing hooks\.
#   3. Upward walk from $PWD looking for hooks\dispatch.py.
#   4. The directory two levels above this script (i.e. $HOME\.claude when
#      this lives at $HOME\.claude\hooks\lib\bootstrap.ps1).
#   5. $HOME\.claude as final fallback (Claude Code harness root).
#
# Divergence from lib/resolve_root.py (deliberate, not accidental): this stub
# and bootstrap.sh use env -> $PWD-walk -> script-relative -> $HOME order and a
# runtime marker of hooks\dispatch.py (an installed, dispatch-ready root),
# whereas resolve_root.py uses env -> script-relative -> cwd-walk -> $HOME
# order and a directory-marker set (hooks\+rules\ in HOOKS mode, or CLAUDE.md
# in MARKER mode). The bootstrap needs the concrete dispatcher present before
# it invokes it, so it keys on the dispatch file directly and prefers the
# running $PWD over the script location; resolve_root.py serves scripts that
# may run before dispatch.py exists (scaffolding), so it keys on directory
# markers and prefers the script's own location. Keep the three in step when
# the marker or order changes: bootstrap.sh, bootstrap.ps1, resolve_root.py.

[CmdletBinding()]
param(
    # Renamed away from the PowerShell automatic Event variable (populated
    # inside event/job scriptblocks) for collision-safety, and to match the
    # POSIX bootstrap.sh's neutral `event`. The -Event alias preserves the
    # documented flag form; the canonical hooks.json invocation passes the
    # event positionally, which binds here regardless of the parameter name.
    [Parameter(Mandatory = $true)]
    [Alias('Event')]
    [string]$HookEvent,
    [Parameter(Mandatory = $false)][string]$ContextFile
)

# Why 'Continue' (not 'Stop'): the dispatch contract is fail-open — any
# blocking error must surface as a JSON envelope on stdout with exit 0 so
# the host harness never stalls. 'Stop' would short-circuit the explicit
# diagnostic-envelope branches below before they can render. The trap on
# the next line catches truly unexpected exceptions and routes them
# through the same envelope path.
$ErrorActionPreference = 'Continue'

function Write-DiagnosticEnvelope {
    param([string]$Message)
    $payload = @{ systemMessage = $Message } | ConvertTo-Json -Compress
    Write-Output $payload
}

trap {
    # The JSON envelope is the hook-runtime contract and goes to STDOUT
    # (matching bootstrap.sh and this stub's stated stdout contract); stderr
    # is reserved for the human-readable diagnostic line only. The script line
    # number mirrors bootstrap.sh's `at line $LINENO` for canonical-pair
    # diagnostic parity; the exception message is the platform-available detail.
    $line = $_.InvocationInfo.ScriptLineNumber
    $message = "hook bootstrap: unexpected error at line ${line}: $($_.Exception.Message)"
    Write-DiagnosticEnvelope -Message $message
    [Console]::Error.WriteLine($message)
    exit 0
}

# --- Resolve project root ----------------------------------------------------
$root = $env:CLAUDE_PROJECT_DIR
if (-not $root -or -not (Test-Path -LiteralPath (Join-Path $root 'hooks'))) {
    $root = $env:LLM_PROJECT_DIR
}
if (-not $root -or -not (Test-Path -LiteralPath (Join-Path $root 'hooks'))) {
    $cursor = $PWD.Path
    $root = $null
    while ($cursor) {
        if (Test-Path -LiteralPath (Join-Path $cursor 'hooks\dispatch.py')) {
            $root = $cursor
            break
        }
        $parent = Split-Path -Parent $cursor
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}
if (-not $root) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $candidate = Resolve-Path (Join-Path $scriptDir '..\..') -ErrorAction SilentlyContinue
    if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate.Path 'hooks\dispatch.py'))) {
        $root = $candidate.Path
    }
}
if (-not $root) {
    $root = Join-Path $HOME '.claude'
}

# --- Locate Python via the locator stub --------------------------------------
$locator = Join-Path $root 'hooks\lib\find-python.ps1'
if (-not (Test-Path -LiteralPath $locator)) {
    Write-DiagnosticEnvelope -Message ("hook {0} skipped: locator stub missing at {1}" -f $HookEvent, $locator)
    exit 0
}
. $locator
# find-python.ps1 sets `Set-StrictMode -Version Latest` and
# `$ErrorActionPreference = 'Stop'` at its top level; dot-sourcing runs those
# in THIS scope, silently overriding the justified fail-open 'Continue'
# preference set above. Re-assert bootstrap's preferences so a later
# non-terminating error still reaches the diagnostic-envelope branches rather
# than aborting the fail-open stub.
$ErrorActionPreference = 'Continue'
Set-StrictMode -Off

$py = $null
try {
    $py = Find-RealPython
} catch {
    Write-DiagnosticEnvelope -Message ("hook {0} skipped: locator raised {1}" -f $HookEvent, $_.Exception.Message)
    exit 0
}
if (-not $py) {
    Write-DiagnosticEnvelope -Message ("hook {0} skipped: no Python interpreter found" -f $HookEvent)
    exit 0
}

$dispatch = Join-Path $root 'hooks\dispatch.py'
if (-not (Test-Path -LiteralPath $dispatch)) {
    Write-DiagnosticEnvelope -Message ("hook {0} skipped: dispatch missing at {1}" -f $HookEvent, $dispatch)
    exit 0
}

# --- Hand off to dispatch.py -------------------------------------------------
if ($ContextFile) {
    & $py $dispatch --event-name $HookEvent --context-file $ContextFile
} else {
    & $py $dispatch --event-name $HookEvent
}
exit $LASTEXITCODE
