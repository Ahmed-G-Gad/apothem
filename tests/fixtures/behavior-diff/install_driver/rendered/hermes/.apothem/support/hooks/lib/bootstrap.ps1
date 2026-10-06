# SPDX-License-Identifier: MIT

# Purpose: PowerShell bootstrap stub for apothem hook events. Resolves
# the project root, locates a real CPython >= 3.10 via find-python.ps1,
# then invokes hooks/dispatch.py with the event name (and optional
# context-file relative to project root).
# Contract: stdout passthrough; every bootstrap-owned failure branch (missing
# event, missing locator/dispatch, no interpreter, unexpected error) emits a
# JSON diagnostic envelope on stdout and exits 0 (fail-open) so hook failures
# never stall the host harness. Once control reaches the dispatch invocation at
# the end, dispatch.py owns the exit code and this stub propagates it verbatim
# via $LASTEXITCODE — dispatch.py is itself fail-open, so the effective
# disposition remains exit 0. This mirrors bootstrap.sh, which reaches the same
# disposition by exec'ing dispatch.py and letting it replace the process.
# Sibling files in hooks/lib/: bootstrap.sh (POSIX counterpart),
# find-python.ps1 (interpreter locator this stub dot-sources),
# find-python.sh (POSIX counterpart of the locator).
#
# Invocation contract (event name + optional context file are positional; the
# event also binds via -HookEvent, with -Event retained as an alias):
#   powershell -NoProfile -ExecutionPolicy Bypass -File `
#     "<root>\hooks\lib\bootstrap.ps1" <event> [<context-file>]
#
# Root discovery: the directory two levels above this script, i.e. the
# installed tree that ships this stub (<root>\hooks\lib\bootstrap.ps1). That
# root holds hooks\lib\find-python.ps1 and hooks\dispatch.py. The stub never
# derives its root from the opened project ($env:CLAUDE_PROJECT_DIR,
# $env:LLM_PROJECT_DIR) or from $PWD: the locator is dot-sourced and the
# dispatcher is executed, so taking either from the project would run
# project-supplied code inside every hook. Handlers that need project data
# (plan suites, memory) read the project directory from the hook payload and
# the environment themselves, as data, never as code.
#
# Divergence from lib/resolve_root.py (deliberate): resolve_root.py locates a
# project root for scripts that read project files; this stub locates only its
# own installed tree. Keep both headers in step when either rule changes:
# bootstrap.sh, bootstrap.ps1, and resolve_root.py's docstring.

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

# --- Resolve the installed tree that ships this stub ------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidate = Resolve-Path (Join-Path $scriptDir '..\..') -ErrorAction SilentlyContinue
$root = $null
if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate.Path 'hooks\dispatch.py'))) {
    $root = $candidate.Path
}
if (-not $root) {
    Write-DiagnosticEnvelope -Message ("hook {0} skipped: dispatch missing beside the bootstrap stub" -f $HookEvent)
    exit 0
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
