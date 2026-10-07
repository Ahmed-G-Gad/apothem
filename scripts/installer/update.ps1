# SPDX-License-Identifier: MIT

# Purpose: Re-fetch the bundled Apothem source (self-contained - no package
#          installation) and re-materialize harness config (PowerShell
#          parity to update.sh).
# Usage:   pwsh -NoProfile -File scripts/installer/update.ps1
#
# Trust model (tag-pinned, verified-by-default; PowerShell parity to
# update.sh): with no APOTHEM_REF set, the updater resolves the latest
# vMAJOR.MINOR.PATCH release tag and checks THAT out - the moving `main` branch
# is no longer the default. Before re-materializing, the fetched tag is verified
# with `git verify-tag`; an unsigned / tampered / missing-signature tag ABORTS
# before any config is written. APOTHEM_REF=main checks out the branch on
# request; APOTHEM_ALLOW_UNVERIFIED=1 downgrades a verification abort to a loud
# warning. The APOTHEM_SOURCE local-checkout path fetches nothing and skips
# verification.
#
# Environment overrides:
#   APOTHEM_HOME      Cloned source location (default: $HOME/.apothem)
#   APOTHEM_REPO      Git remote (default: https://github.com/ahmed-g-gad/apothem)
#   APOTHEM_REF       Git ref to update to. Unset = resolve the latest release
#                     tag; set to a tag to pin, or "main" for the moving branch.
#   APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a tag-verification failure to a
#                     warning and proceed.
#   APOTHEM_SOURCE    Explicit local source tree to re-materialize from (skips
#                     tag resolution and verification)
#   APOTHEM_HARNESS   Harness to update (default: claude-code)
#   APOTHEM_PROFILE   Path to shared profile YAML
#   APOTHEM_AUTO_INSTALL_DEPS  If "1", install missing click / rich
#                     prerequisites automatically (pip) without prompting.

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ApothemHome = if ($env:APOTHEM_HOME) { $env:APOTHEM_HOME } else { Join-Path $HOME '.apothem' }
$ApothemRepo = if ($env:APOTHEM_REPO) { $env:APOTHEM_REPO } else { 'https://github.com/ahmed-g-gad/apothem' }
# Empty default sentinel: an unset APOTHEM_REF means "resolve the latest
# released tag" (verified-by-default trust model); an explicit value pins a tag
# or the moving `main` branch. Windows PowerShell 5.1 has no `??`, so the
# if/else subexpression supplies the empty-string default.
$ApothemRef  = if ($env:APOTHEM_REF) { $env:APOTHEM_REF } else { '' }
$ApothemAllowUnverified = if ($env:APOTHEM_ALLOW_UNVERIFIED) { $env:APOTHEM_ALLOW_UNVERIFIED } else { '0' }
$Harness     = if ($env:APOTHEM_HARNESS) { $env:APOTHEM_HARNESS } else { 'claude-code' }
$ApothemProfile = if ($env:APOTHEM_PROFILE) { $env:APOTHEM_PROFILE } else { [System.IO.Path]::Combine($HOME, '.config', 'apothem', 'profile.yaml') }

# CLI prerequisites; `yaml` + `jsonschema` ship vendored inside the bundled
# tree (src/apothem/_vendor), so only click + rich come from the host.
$RuntimeDeps = @('click', 'rich')
$VendoringDoc = 'https://apothem.ahmedgad.com/architecture/vendoring-strategy/'

# Colour only an interactive console. NO_COLOR (https://no-color.org/) or
# redirected output (a pipe, a file, a CI log) gets plain text.
$UseColor = (-not $env:NO_COLOR) -and (-not [Console]::IsOutputRedirected)
function Get-ColorParameter {
    param([string]$Color)
    if ($UseColor) { return @{ ForegroundColor = $Color } }
    return @{}
}
function Write-Bold { param([string]$Msg) $c = Get-ColorParameter White;  Write-Host "`n$Msg" @c }
function Write-Info { param([string]$Msg) $c = Get-ColorParameter Cyan;   Write-Host "  . $Msg" @c }
function Write-Ok   { param([string]$Msg) $c = Get-ColorParameter Green;  Write-Host "  + $Msg" @c }
function Write-Warn { param([string]$Msg) $c = Get-ColorParameter Yellow; Write-Host "  ! $Msg" @c }
function Write-Fail { param([string]$Msg) Write-Error "  x $Msg" }

# Test-PythonImport INTERPRETER MODULE - return $true when MODULE imports under
# INTERPRETER, $false otherwise. Localizes $ErrorActionPreference to 'Continue'
# and discards all streams so a missing-module traceback never becomes a
# terminating NativeCommandError (the trap that aborts a prerequisite probe
# under $ErrorActionPreference='Stop').
function Test-PythonImport {
    param([string]$Interpreter, [string]$Module)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Interpreter -c "import $Module" *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $prior
    }
}

# Confirm-AutoInstall DEPS INTERPRETER - opt-in for installing the missing
# prerequisites. APOTHEM_AUTO_INSTALL_DEPS=1 auto-confirms; a non-interactive
# session declines; otherwise prompt, defaulting to No.
function Confirm-AutoInstall {
    param([string[]]$Deps, [string]$Interpreter)
    if ($env:APOTHEM_AUTO_INSTALL_DEPS -eq '1') { return $true }
    if ([System.Console]::IsInputRedirected) { return $false }
    $answer = Read-Host "  Install $($Deps -join ', ') under $Interpreter now? [y/N]"
    return ($answer -match '^(y|yes)$')
}

# Install-RuntimeDependency INTERPRETER DEPS - pip-install the missing prerequisites;
# returns $true on success and reports a clear, non-fatal failure otherwise.
function Install-RuntimeDependency {
    param([string]$Interpreter, [string[]]$Deps)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Interpreter -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "pip is unavailable under $Interpreter - install $($Deps -join ', ') manually."
            return $false
        }
        Write-Info "Installing $($Deps -join ', ') under $Interpreter (pip)"
        & $Interpreter -m pip install @Deps
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($code -eq 0) { Write-Ok "Installed $($Deps -join ', ')"; return $true }
    Write-Warn "pip install failed (exit $code) - install $($Deps -join ', ') manually."
    return $false
}

# Resolve-LatestTag REPO - return the highest vMAJOR.MINOR.PATCH tag advertised
# by the remote, or $null when none. PowerShell parity to update.sh's
# resolve_latest_tag; pre-release / build-metadata tags are excluded so the
# default never resolves to a non-final release. Sorts by the three numeric
# components via a [version] cast on the stripped "v" prefix.
function Resolve-LatestTag {
    param([string]$Repo)
    $raw = & git ls-remote --tags $Repo 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    $tags = @()
    foreach ($line in $raw) {
        # Each line is "<sha>\trefs/tags/<tag>"; annotated tags also emit a
        # "<tag>^{}" peel line. Match the final-release shape and strip "^{}".
        if ($line -match 'refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)(\^\{\})?$') {
            $tags += $matches[1]
        }
    }
    if ($tags.Count -eq 0) { return $null }
    $sorted = $tags | Sort-Object -Unique | Sort-Object { [version]($_.Substring(1)) }
    return $sorted[-1]
}

# Test-TagSignature DIR REF - return $true when `git verify-tag` succeeds in
# DIR (a GPG-signed tag whose key is trusted), $false otherwise. The verifier's
# output is captured in $script:VerifyTagOutput so callers can tell a missing
# public key (no local trust root yet - remediation: import the maintainer
# key) from a bad or absent signature (hard abort). `--raw` captures GnuPG's
# status lines ("[GNUPG:] KEYWORD ...") instead of its human-readable
# messages, which GnuPG translates into the host's language. git writes both
# to stderr, which Windows PowerShell (and PowerShell before 7.2) turns into
# a TERMINATING NativeCommandError under $ErrorActionPreference='Stop' once it
# is redirected - for a valid signature too - so the preference is localized
# to 'Continue' around the call, as in Test-PythonImport.
$script:VerifyTagOutput = ''
function Test-TagSignature {
    param([string]$Dir, [string]$Ref)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $Lines = & git -C $Dir verify-tag --raw $Ref 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    $script:VerifyTagOutput = ($Lines | ForEach-Object { $_.ToString() }) -join "`n"
    return ($code -eq 0)
}

# Test-VerifyTagMissingKey - $true when the captured status lines show the
# signing public key is absent from the local keyring, so the signature was
# not checked (GnuPG's NO_PUBKEY status), $false for any other failure
# (unsigned tag, BAD signature).
function Test-VerifyTagMissingKey {
    return ($script:VerifyTagOutput -match '\[GNUPG:\] NO_PUBKEY ')
}

# Test-ReleaseTag REF - return $true when REF is a vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), $false otherwise (a branch, a SHA, a pre-release).
function Test-ReleaseTag {
    param([string]$Ref)
    return ($Ref -match '^v[0-9]+\.[0-9]+\.[0-9]+$')
}

Write-Bold "Apothem updater"

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
if (-not $PY) { Write-Fail "No Python >= 3.10 found in PATH" }

# CLI prerequisite check (robust probe; offers to install the missing deps).
$MissingDeps = @($RuntimeDeps | Where-Object { -not (Test-PythonImport $PY $_) })
if ($MissingDeps.Count -gt 0) {
    Write-Warn "Missing Python prerequisites under ${PY}: $($MissingDeps -join ', ')"
    if (Confirm-AutoInstall -Deps $MissingDeps -Interpreter $PY) {
        if (Install-RuntimeDependency -Interpreter $PY -Deps $MissingDeps) {
            $MissingDeps = @($RuntimeDeps | Where-Object { -not (Test-PythonImport $PY $_) })
        }
    }
}
if ($MissingDeps.Count -gt 0) {
    Write-Fail "Missing prerequisites under ${PY}: $($MissingDeps -join ', '). Install them with: '${PY}' -m pip install $($MissingDeps -join ' ') - or set APOTHEM_AUTO_INSTALL_DEPS=1 to install automatically. See $VendoringDoc for the vendoring strategy."
}

# Locate or fetch the source.
Write-Bold "Updating Apothem source"
$Source = $null
if ($env:APOTHEM_SOURCE) {
    if (-not (Test-Path -LiteralPath $env:APOTHEM_SOURCE) -or -not (Test-ApothemSource $env:APOTHEM_SOURCE)) {
        Write-Fail "APOTHEM_SOURCE is not an apothem source tree: $($env:APOTHEM_SOURCE)"
    }
    $Source = (Resolve-Path -LiteralPath $env:APOTHEM_SOURCE).Path
    Write-Ok "Using explicit source: $Source"
    Write-Info "Local source - skipping tag resolution and signature verification"
} elseif (Test-Path -LiteralPath (Join-Path $ApothemHome '.git')) {
    if (-not (Get-Command 'git' -ErrorAction SilentlyContinue)) { Write-Fail "git not found in PATH" }

    # Resolve the ref to update to. An unset APOTHEM_REF defaults to the latest
    # release tag (verified-by-default) rather than the moving `main` branch.
    if (-not $ApothemRef) {
        Write-Info "Resolving latest release tag from $ApothemRepo"
        $ApothemRef = Resolve-LatestTag $ApothemRepo
        if (-not $ApothemRef) {
            Write-Fail "No vMAJOR.MINOR.PATCH release tag found at $ApothemRepo. Pin a ref explicitly with `$env:APOTHEM_REF = '<tag|main>'`."
        }
        Write-Ok "Latest release tag: $ApothemRef"
    }

    Write-Info "Updating clone at $ApothemHome (ref: $ApothemRef)"
    & git -C $ApothemHome fetch --quiet --tags origin
    & git -C $ApothemHome checkout --quiet --force $ApothemRef
    if ($LASTEXITCODE -ne 0) { & git -C $ApothemHome checkout --quiet --force "origin/$ApothemRef" }
    if ($LASTEXITCODE -ne 0) { Write-Fail "Could not check out $ApothemRef in $ApothemHome" }
    $Source = $ApothemHome
    if (-not (Test-ApothemSource $Source)) { Write-Fail "Updated tree is not an apothem source: $Source" }
    Write-Ok "Source updated at $Source (ref: $ApothemRef)"

    # Fail-closed signature verification - runs BEFORE any re-materialization.
    Write-Bold "Verifying source signature"
    if (Test-ReleaseTag $ApothemRef) {
        if (Test-TagSignature $Source $ApothemRef) {
            Write-Ok "Tag $ApothemRef carries a valid signature"
        } elseif ($ApothemAllowUnverified -eq '1') {
            Write-Warn "Tag $ApothemRef is unsigned or its signature did not verify - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        } elseif (Test-VerifyTagMissingKey) {
            Write-Fail "Tag $ApothemRef is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: look up the maintainer signing-key fingerprint in SECURITY.md at the repository root, run 'gpg --recv-keys <fingerprint>', confirm the imported key's fingerprint matches the published value, then re-run this updater."
        } else {
            Write-Fail "Tag $ApothemRef is unsigned or its signature did not verify (possible tampering). Aborting before re-materialization."
        }
    } else {
        if ($ApothemAllowUnverified -eq '1') {
            Write-Warn "Ref $ApothemRef is not a signed release tag - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        } else {
            Write-Fail "Ref $ApothemRef is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
        }
    }
} else {
    Write-Fail "No source found at $ApothemHome - run install.ps1 first or set APOTHEM_SOURCE"
}
$SrcPath = Join-Path $Source 'src'
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
$VendorPath = [System.IO.Path]::Combine($SrcPath, 'apothem', '_vendor')
$EnginePyPath = "$VendorPath$([System.IO.Path]::PathSeparator)$SrcPath"

Write-Bold "Re-materializing harness: $Harness"
if (-not (Test-Path $ApothemProfile)) { Write-Fail "Profile not found at $ApothemProfile" }
$PriorPyPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($PriorPyPath) { "$EnginePyPath$([System.IO.Path]::PathSeparator)$PriorPyPath" } else { $EnginePyPath }
try {
    & $PY -m apothem update --harness $Harness --profile $ApothemProfile
    if ($LASTEXITCODE -ne 0) { Write-Fail "Harness re-materialization failed for $Harness" }
    Write-Ok "Harness $Harness updated"
}
finally {
    $env:PYTHONPATH = $PriorPyPath
}

Write-Bold "Update complete."
