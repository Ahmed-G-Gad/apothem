# SPDX-License-Identifier: MIT

# Purpose: Place the bundled Apothem source tree (self-contained - no
#          package installation) and materialize harness config by running
#          `python -m apothem` directly from that tree (PowerShell parity
#          to install.sh).
# Contract: Idempotent on rerun (a re-run fast-forwards the clone and
#           re-materializes). Throws on unrecoverable error.
#
# Trust model (tag-pinned, verified-by-default; PowerShell parity to
# install.sh): with no APOTHEM_REF set, the installer resolves the latest
# vMAJOR.MINOR.PATCH release tag and checks THAT out - the moving `main` branch
# is no longer the default. Before materializing, the fetched tag is verified
# with `git verify-tag`; an unsigned / tampered / missing-signature tag ABORTS
# before any config is written. APOTHEM_REF=main checks out the branch on
# request; APOTHEM_ALLOW_UNVERIFIED=1 downgrades a verification abort to a loud
# warning. The APOTHEM_SOURCE local-checkout path fetches nothing and skips
# verification (it prints what it is running).
#
# Usage (recommended - tag-pinned, verified):
#   irm https://apothem.ahmedgad.com/install.ps1 | iex
#   # explicit pin:  $env:APOTHEM_REF = 'vMAJOR.MINOR.PATCH'; ... install.ps1
#
# Usage (inspect-first - the one-liner trusts this bootstrap script on first
# use; the fetched source is always signature-verified either way):
#   irm https://apothem.ahmedgad.com/install.ps1 -OutFile install.ps1
#   # review install.ps1, then run:
#   pwsh -NoProfile -File install.ps1
#
# Usage (local install):
#   pwsh -NoProfile -File scripts/installer/install.ps1
#
# Parameters (opt-in clean-slate pass-through to the engine):
#   -Clean / -Fresh  Back up and remove the bounded harness config set, then
#                    materialize fresh (engine `--clean`). The profile is
#                    loaded before removal and restored afterward.
#   -DryRun          Preview only; write nothing (engine `--dry-run`). Skips
#                    post-install verification.
#   -Yes             Non-interactive; skip per-target prompts (engine `--yes`).
#                    Also authorizes replacing an existing non-clone
#                    directory at APOTHEM_HOME.
#
# Environment overrides (set as env vars before running):
#   APOTHEM_HOME             Install destination for the cloned source
#                            (default: $HOME/.apothem)
#   APOTHEM_REPO             Git remote to clone
#                            (default: https://github.com/ahmed-g-gad/apothem)
#   APOTHEM_REF              Git ref to check out. Unset = resolve the latest
#                            release tag; set to a tag to pin, or "main" for
#                            the moving branch.
#   APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a tag-verification failure to a
#                            warning and proceed.
#   APOTHEM_VERIFY           "signature" (default) verifies the release tag's
#                            GPG signature. "checksum" instead downloads the
#                            release's Windows archive and installs it only if
#                            its SHA-256 matches the release's SHA256SUMS:
#                            integrity without proof of the publisher, for
#                            hosts without the maintainer's public key.
#   APOTHEM_RELEASE_BASE     Release download base for checksum mode
#                            (default: <APOTHEM_REPO>/releases/download).
#   APOTHEM_SOURCE           Explicit local source tree (a checkout containing
#                            src/apothem) to use instead of cloning. Skips tag
#                            resolution and verification.
#   APOTHEM_HARNESS          Harness to install (default: claude-code)
#   APOTHEM_PROFILE          Path to shared profile YAML
#   APOTHEM_SKIP_VERIFY      If "1", skip post-install verify
#   APOTHEM_AUTO_INSTALL_DEPS If "1", install missing click / rich prerequisites
#                            automatically (pip) without prompting.

#Requires -Version 5.1
param(
    [switch]$Clean,
    [switch]$Fresh,
    [switch]$DryRun,
    [switch]$Yes
)

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
$ApothemVerify = if ($env:APOTHEM_VERIFY) { $env:APOTHEM_VERIFY } else { 'signature' }
$Harness     = if ($env:APOTHEM_HARNESS) { $env:APOTHEM_HARNESS } else { 'claude-code' }
$ApothemProfile = if ($env:APOTHEM_PROFILE) { $env:APOTHEM_PROFILE } else { [System.IO.Path]::Combine($HOME, '.config', 'apothem', 'profile.yaml') }

# CLI prerequisites the engine imports from the host interpreter. The
# self-contained runtime ships `yaml` + `jsonschema` vendored inside the
# bundled tree (src/apothem/_vendor); only click + rich must be importable
# under the chosen interpreter, and the check fails loud if either is missing.
$RuntimeDeps = @('click', 'rich')
# Pip requirement spec per import name - mirrors [project.dependencies] in
# pyproject.toml (click is pinned exactly there; keep the two surfaces in
# lockstep) so the prerequisite install pulls the same constrained versions
# the engine is tested against, never a bare unconstrained "latest".
$RuntimeDepSpecs = @{ click = 'click==8.4.2'; rich = 'rich>=15.0.0' }
$VendoringDoc = 'https://apothem.ahmedgad.com/docs/architecture/vendoring-strategy/'

# Colour only an interactive console. NO_COLOR (https://no-color.org/) or
# redirected output (a pipe, a file, a CI log) gets plain text.
$UseColor = (-not $env:NO_COLOR) -and (-not [Console]::IsOutputRedirected)
function Get-ColorParameter {
    param([string]$Color)
    if ($UseColor) { return @{ ForegroundColor = $Color } }
    return @{}
}
function Write-Bold  { param([string]$Msg) $c = Get-ColorParameter White;  Write-Host "`n$Msg" @c }
function Write-Info  { param([string]$Msg) $c = Get-ColorParameter Cyan;   Write-Host "  . $Msg" @c }
function Write-Ok    { param([string]$Msg) $c = Get-ColorParameter Green;  Write-Host "  + $Msg" @c }
function Write-Warn  { param([string]$Msg) $c = Get-ColorParameter Yellow; Write-Host "  ! $Msg" @c }
function Write-Fail  { param([string]$Msg) Write-Error "  x $Msg" }

# Test-PythonImport INTERPRETER MODULE - return $true when MODULE imports under
# INTERPRETER, $false otherwise. A missing module makes CPython print an
# ImportError traceback to stderr; under $ErrorActionPreference='Stop' Windows
# PowerShell promotes a native command's stderr write to a TERMINATING
# NativeCommandError even with a `2>$null` redirect - which would abort the
# whole installer on what is meant to be a benign "is this dependency present?"
# probe. Localize the preference to 'Continue' and discard every stream so the
# probe stays a quiet boolean instead of a fatal error.
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

# Confirm-AutoInstall DEPS INTERPRETER - return $true when the operator opts into
# installing the missing prerequisites. `-Yes` or APOTHEM_AUTO_INSTALL_DEPS=1
# auto-confirms; a non-interactive session (no console input) with neither opt-in
# declines, so a piped `irm | iex` install never silently mutates the host
# interpreter. Otherwise prompt, defaulting to No.
function Confirm-AutoInstall {
    param([string[]]$Deps, [string]$Interpreter)
    if ($Yes -or $env:APOTHEM_AUTO_INSTALL_DEPS -eq '1') { return $true }
    if ([System.Console]::IsInputRedirected) { return $false }
    $answer = Read-Host "  Install $($Deps -join ', ') under $Interpreter now? [y/N]"
    return ($answer -match '^(y|yes)$')
}

# Install-RuntimeDependency INTERPRETER DEPS - install the missing prerequisites under
# INTERPRETER with pip and return $true when the install command succeeds.
# Probes `pip --version` first and reports a clear, non-fatal failure (no pip,
# no network, or a PEP 668 externally-managed interpreter) rather than aborting,
# so the caller can fall through to manual-install guidance.
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
    if ($code -eq 0) {
        Write-Ok "Installed $($Deps -join ', ')"
        return $true
    }
    Write-Warn "pip install failed (exit $code) - install $($Deps -join ', ') manually."
    return $false
}

# Resolve-LatestTag REPO - return the highest vMAJOR.MINOR.PATCH tag advertised
# by the remote, or $null when none. PowerShell parity to install.sh's
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
# key) from a bad or absent signature (hard abort).
$script:VerifyTagOutput = ''
function Test-TagSignature {
    param([string]$Dir, [string]$Ref)
    $Lines = & git -C $Dir verify-tag $Ref 2>&1
    $script:VerifyTagOutput = ($Lines | ForEach-Object { $_.ToString() }) -join "`n"
    return ($LASTEXITCODE -eq 0)
}

# Test-VerifyTagMissingKey - $true when the captured verify-tag output shows
# the signature could not be checked because the signing public key is absent
# from the local keyring, $false for any other failure (unsigned tag, BAD
# signature).
function Test-VerifyTagMissingKey {
    return ($script:VerifyTagOutput -match 'No public key|public key not found')
}

# Test-ReleaseTag REF - return $true when REF is a vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), $false otherwise (a branch, a SHA, a pre-release).
function Test-ReleaseTag {
    param([string]$Ref)
    return ($Ref -match '^v[0-9]+\.[0-9]+\.[0-9]+$')
}

Write-Bold "Apothem installer"

# Prerequisite: Python >= 3.10 ------------------------------------------------
#
# Locate a real CPython >= 3.10, rejecting Microsoft Store launcher shims.
# The locator at hooks/lib/find-python.ps1 is reused when this script runs
# from a source tree; otherwise an inline probe applies the same floor.
Write-Bold "Checking prerequisites"

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$PY = $null
$Locator = $null
foreach ($Cand in @(
    ([System.IO.Path]::Combine($ScriptDir, '..', '..', 'src', 'apothem', 'hooks', 'lib', 'find-python.ps1')),
    ([System.IO.Path]::Combine($ScriptDir, '..', '..', 'hooks', 'lib', 'find-python.ps1')))) {
    if (Test-Path -LiteralPath $Cand) { $Locator = $Cand; break }
}
if ($Locator) {
    . $Locator
    try { $PY = Find-RealPython -MinMajor 3 -MinMinor 10 } catch { $PY = $null }
}

if (-not $PY) {
    foreach ($Cmd in @('python3', 'python', 'python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10')) {
        $Resolved = Get-Command $Cmd -ErrorAction SilentlyContinue
        if (-not $Resolved) { continue }
        if ($Resolved.Source -and $Resolved.Source -match 'WindowsApps') { continue }
        & $Cmd -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $PY = if ($Resolved.Source) { $Resolved.Source } else { $Cmd }; break }
    }
}

if (-not $PY) { Write-Fail "No Python >= 3.10 found in PATH" }
# NOTE: keep this `-c` program free of embedded double quotes. Windows
# PowerShell 5.1 strips embedded quotes when passing an argument to a native
# executable, so `".".join(...)` would reach python as `..join(...)` and raise
# a SyntaxError. `platform.python_version()` returns the same MAJOR.MINOR.MICRO
# string with no quoting.
$PyVer = & $PY -c 'import platform; print(platform.python_version())'
Write-Ok "$PY ($PyVer)"

# Prerequisite: CLI prerequisites importable ----------------------------------
#
# The bundled engine ships `yaml` + `jsonschema` vendored, but imports `click` +
# `rich` from the host interpreter. A fresh CPython that lacks them must not
# crash the probe (Test-PythonImport keeps a missing-module traceback from
# becoming a terminating NativeCommandError); the installer reports the gap and
# offers to install the two prerequisites under the chosen interpreter.
$MissingDeps = @($RuntimeDeps | Where-Object { -not (Test-PythonImport $PY $_) })
if ($MissingDeps.Count -gt 0) {
    Write-Warn "Missing Python prerequisites under ${PY}: $($MissingDeps -join ', ')"
    if (Confirm-AutoInstall -Deps $MissingDeps -Interpreter $PY) {
        $MissingSpecs = @($MissingDeps | ForEach-Object { $RuntimeDepSpecs[$_] })
        if (Install-RuntimeDependency -Interpreter $PY -Deps $MissingSpecs) {
            $MissingDeps = @($RuntimeDeps | Where-Object { -not (Test-PythonImport $PY $_) })
        }
    }
}
if ($MissingDeps.Count -gt 0) {
    $MissingSpecs = @($MissingDeps | ForEach-Object { $RuntimeDepSpecs[$_] })
    Write-Fail "Missing prerequisites under ${PY}: $($MissingDeps -join ', '). Install them with: '${PY}' -m pip install $($MissingSpecs -join ' ') - or re-run with -Yes (or set APOTHEM_AUTO_INSTALL_DEPS=1) to install automatically. See $VendoringDoc for the vendoring strategy."
}
Write-Ok "Prerequisites present: $($RuntimeDeps -join ', ')"

# Locate or fetch the bundled source ------------------------------------------
#
# Source precedence:
#   1. APOTHEM_SOURCE - an explicit local source tree (no fetch; verification
#      skipped because nothing is fetched).
#   2. A surrounding local checkout (this script lives in scripts/installer/;
#      no fetch; verification skipped).
#   3. A git clone of APOTHEM_REPO into APOTHEM_HOME, pinned to the resolved ref
#      (the latest release tag by default, or an explicit APOTHEM_REF), then
#      signature-verified before materializing.
Write-Bold "Locating Apothem source"

function Test-ApothemSource {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Dir, 'src', 'apothem')))) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Dir 'pyproject.toml')) -or
           (Test-Path -LiteralPath (Join-Path $Dir '.claude-plugin'))
}

$Source = $null
if ($env:APOTHEM_SOURCE) {
    if (-not (Test-Path -LiteralPath $env:APOTHEM_SOURCE) -or -not (Test-ApothemSource $env:APOTHEM_SOURCE)) {
        Write-Fail "APOTHEM_SOURCE is not an apothem source tree: $($env:APOTHEM_SOURCE)"
    }
    $Source = (Resolve-Path -LiteralPath $env:APOTHEM_SOURCE).Path
    Write-Ok "Using explicit source: $Source"
    Write-Info "Local source - skipping tag resolution and signature verification"
} else {
    $Walk = $ScriptDir
    while ($Walk) {
        if (Test-ApothemSource $Walk) { $Source = $Walk; break }
        $Parent = Split-Path -Parent $Walk
        if (-not $Parent -or $Parent -eq $Walk) { break }
        $Walk = $Parent
    }
    if ($Source) {
        Write-Ok "Using local checkout: $Source"
        Write-Info "Local checkout - skipping tag resolution and signature verification"
    }
}

if ($ApothemVerify -ne 'signature' -and $ApothemVerify -ne 'checksum') {
    Write-Fail "APOTHEM_VERIFY must be 'signature' or 'checksum' (got '$ApothemVerify')."
}
$ApothemReleaseBase = if ($env:APOTHEM_RELEASE_BASE) { $env:APOTHEM_RELEASE_BASE } else { "$ApothemRepo/releases/download" }

# Checksum mode: install the release's Windows archive after checking its
# SHA-256 against the release's SHA256SUMS. It replaces the git clone and the
# tag-signature gate below for hosts that do not hold the maintainer's public
# key, and says plainly that a matching digest proves integrity, not origin.
if (-not $Source -and $ApothemVerify -eq 'checksum') {
    if (-not $ApothemRef) {
        if (-not (Get-Command 'git' -ErrorAction SilentlyContinue)) {
            Write-Fail "git not found in PATH - needed to resolve the latest release tag"
        }
        Write-Info "Resolving latest release tag from $ApothemRepo"
        $ApothemRef = Resolve-LatestTag $ApothemRepo
    }
    if (-not (Test-ReleaseTag $ApothemRef)) {
        Write-Fail "APOTHEM_VERIFY=checksum needs a vMAJOR.MINOR.PATCH release tag; got '$ApothemRef'. Pin one with APOTHEM_REF."
    }
    $CkName = "apothem-$ApothemRef-windows.zip"
    $CkTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $CkTmp -Force | Out-Null
    $CkExtract = $null
    # Everything from here to the move into APOTHEM_HOME runs inside try, so
    # the download and the staging folder are removed on every path, success,
    # failure or interrupt.
    try {
        $CkArchive = Join-Path $CkTmp $CkName
        $CkSums = Join-Path $CkTmp 'SHA256SUMS'
        Write-Info "Downloading $CkName and SHA256SUMS from the $ApothemRef release"
        try { Invoke-WebRequest -UseBasicParsing -Uri "$ApothemReleaseBase/$ApothemRef/$CkName" -OutFile $CkArchive }
        catch { Write-Fail "Could not download $CkName from $ApothemReleaseBase/$ApothemRef" }
        try { Invoke-WebRequest -UseBasicParsing -Uri "$ApothemReleaseBase/$ApothemRef/SHA256SUMS" -OutFile $CkSums }
        catch { Write-Fail "Could not download SHA256SUMS from $ApothemReleaseBase/$ApothemRef" }
        $CkExpected = $null
        foreach ($Line in Get-Content -LiteralPath $CkSums) {
            $Fields = $Line -split '\s+', 2
            if ($Fields.Count -eq 2 -and ($Fields[1] -eq $CkName -or $Fields[1] -eq "*$CkName")) {
                $CkExpected = $Fields[0]
                break
            }
        }
        if (-not $CkExpected) { Write-Fail "SHA256SUMS for $ApothemRef lists no $CkName" }
        $CkActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $CkArchive).Hash
        if ($CkActual -ne $CkExpected) {
            Write-Fail "$CkName does not match the release's SHA256SUMS (expected $CkExpected, got $CkActual). Aborting before anything is extracted."
        }
        Write-Ok "$CkName matches the release's SHA256SUMS"
        Write-Warn "Checksum mode: a matching digest shows the archive is the one the release lists; it does not prove who published it. For signature verification, import the maintainer key named in SECURITY.md and run without APOTHEM_VERIFY=checksum."
        if ((Test-Path -LiteralPath $ApothemHome) -and (Get-ChildItem -LiteralPath $ApothemHome -Force | Select-Object -First 1)) {
            if ($Yes) {
                Write-Warn "Replacing existing $ApothemHome with the $ApothemRef archive (-Yes)"
                try { Remove-Item -LiteralPath $ApothemHome -Recurse -Force }
                catch { Write-Fail "Could not remove the existing $ApothemHome" }
            } else {
                Write-Fail "Destination $ApothemHome is not empty; refusing to replace it. Move it aside, point APOTHEM_HOME at another directory, or re-run with -Yes."
            }
        }
        # The release archive roots every file under apothem-<tag>\ (see
        # scripts/build_release_tarball.py). It is extracted into a staging
        # folder beside APOTHEM_HOME, because Windows PowerShell 5.1's Move-Item
        # moves a directory only within one drive; the root is then required and
        # moved into place.
        $CkParent = Split-Path -Parent $ApothemHome
        if (-not $CkParent) { $CkParent = (Get-Location).Path }
        try { New-Item -ItemType Directory -Path $CkParent -Force | Out-Null }
        catch { Write-Fail "Could not create the parent directory of $ApothemHome" }
        if (-not (Test-Path -LiteralPath $CkParent -PathType Container)) {
            Write-Fail "Could not create the parent directory of $ApothemHome"
        }
        $CkExtract = Join-Path $CkParent (".apothem-extract-" + [System.Guid]::NewGuid().ToString('N'))
        try { Expand-Archive -LiteralPath $CkArchive -DestinationPath $CkExtract -Force }
        catch { Write-Fail "Could not extract $CkName" }
        $CkRoot = Join-Path $CkExtract "apothem-$ApothemRef"
        if (-not (Test-ApothemSource $CkRoot)) { Write-Fail "$CkName does not hold an apothem source under apothem-$ApothemRef\" }
        if (Test-Path -LiteralPath $ApothemHome) {
            try { Remove-Item -LiteralPath $ApothemHome -Recurse -Force }
            catch { Write-Fail "Could not remove the existing $ApothemHome" }
        }
        try { Move-Item -LiteralPath $CkRoot -Destination $ApothemHome }
        catch { Write-Fail "Could not move the extracted source to $ApothemHome" }
    } finally {
        if ($CkExtract -and (Test-Path -LiteralPath $CkExtract)) { Remove-Item -LiteralPath $CkExtract -Recurse -Force }
        if (Test-Path -LiteralPath $CkTmp) { Remove-Item -LiteralPath $CkTmp -Recurse -Force }
    }
    $Source = $ApothemHome
    Write-Ok "Source ready at $Source (release archive $ApothemRef)"
}

if (-not $Source) {
    if (-not (Get-Command 'git' -ErrorAction SilentlyContinue)) {
        Write-Fail "git not found in PATH - needed to fetch $ApothemRepo"
    }

    # Resolve the ref to fetch. An unset APOTHEM_REF defaults to the latest
    # release tag (verified-by-default) rather than the moving `main` branch.
    if (-not $ApothemRef) {
        Write-Info "Resolving latest release tag from $ApothemRepo"
        $ApothemRef = Resolve-LatestTag $ApothemRepo
        if (-not $ApothemRef) {
            Write-Fail "No vMAJOR.MINOR.PATCH release tag found at $ApothemRepo. Pin a ref explicitly with `$env:APOTHEM_REF = '<tag|main>'`, or set APOTHEM_SOURCE to a local checkout."
        }
        Write-Ok "Latest release tag: $ApothemRef"
    }

    if (Test-Path -LiteralPath (Join-Path $ApothemHome '.git')) {
        Write-Info "Updating existing clone at $ApothemHome (ref: $ApothemRef)"
        & git -C $ApothemHome fetch --quiet --tags origin
        & git -C $ApothemHome checkout --quiet --force $ApothemRef
        if ($LASTEXITCODE -ne 0) { & git -C $ApothemHome checkout --quiet --force "origin/$ApothemRef" }
        if ($LASTEXITCODE -ne 0) { Write-Fail "Could not check out $ApothemRef in $ApothemHome" }
    } else {
        Write-Info "Cloning $ApothemRepo into $ApothemHome"
        $ParentDir = Split-Path -Parent $ApothemHome
        if ($ParentDir) { New-Item -ItemType Directory -Force -Path $ParentDir | Out-Null }
        # An existing non-clone path here was not placed by a previous
        # install (no .git), so it is not Apothem's to delete. Refuse unless
        # -Yes explicitly authorizes the destructive replacement; a stale
        # empty directory is removed quietly.
        if (Test-Path -LiteralPath $ApothemHome) {
            if ($Yes) {
                Write-Warn "Replacing existing non-clone path at $ApothemHome (-Yes)"
                Remove-Item -Recurse -Force -LiteralPath $ApothemHome
            } elseif ((Test-Path -LiteralPath $ApothemHome -PathType Container) -and -not (Get-ChildItem -LiteralPath $ApothemHome -Force | Select-Object -First 1)) {
                Remove-Item -LiteralPath $ApothemHome
            } else {
                Write-Fail "Destination $ApothemHome exists but is not a git clone; refusing to delete it. Move it aside, point APOTHEM_HOME at another directory, or re-run with -Yes to replace it."
            }
        }
        # Full clone (no --single-branch) so both tags and branches are
        # checkout-able, then pin to the resolved ref.
        & git clone --quiet $ApothemRepo $ApothemHome
        if ($LASTEXITCODE -ne 0) { Write-Fail "git clone failed for $ApothemRepo" }
        & git -C $ApothemHome checkout --quiet --force $ApothemRef
        if ($LASTEXITCODE -ne 0) { & git -C $ApothemHome checkout --quiet --force "origin/$ApothemRef" }
        if ($LASTEXITCODE -ne 0) { Write-Fail "Could not check out $ApothemRef in $ApothemHome" }
    }
    $Source = $ApothemHome
    if (-not (Test-ApothemSource $Source)) { Write-Fail "Fetched tree is not an apothem source: $Source" }
    Write-Ok "Source ready at $Source (ref: $ApothemRef)"

    # Fail-closed signature verification - runs BEFORE any materialization.
    Write-Bold "Verifying source signature"
    if (Test-ReleaseTag $ApothemRef) {
        if (Test-TagSignature $Source $ApothemRef) {
            Write-Ok "Tag $ApothemRef carries a valid signature"
        } elseif ($ApothemAllowUnverified -eq '1') {
            Write-Warn "Tag $ApothemRef is unsigned or its signature did not verify - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        } elseif (Test-VerifyTagMissingKey) {
            Write-Fail "Tag $ApothemRef is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: look up the maintainer signing-key fingerprint in SECURITY.md at the repository root, run 'gpg --recv-keys <fingerprint>', confirm the imported key's fingerprint matches the published value, then re-run this installer."
        } else {
            Write-Fail "Tag $ApothemRef is unsigned or its signature did not verify (possible tampering). Aborting before any configuration is materialized."
        }
    } else {
        if ($ApothemAllowUnverified -eq '1') {
            Write-Warn "Ref $ApothemRef is not a signed release tag - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        } else {
            Write-Fail "Ref $ApothemRef is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
        }
    }
}
$SrcPath = Join-Path $Source 'src'
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
$VendorPath = [System.IO.Path]::Combine($SrcPath, 'apothem', '_vendor')
$EnginePyPath = "$VendorPath$([System.IO.Path]::PathSeparator)$SrcPath"

# Profile setup ---------------------------------------------------------------
# A first run with no profile creates one from the example and carries on to
# materialize and verify in the same run (the engine only warns about the
# placeholder identity). A dry run writes nothing, so it previews with the
# example profile in place instead of copying it.
Write-Bold "Profile setup"
$EngineProfile = $ApothemProfile
if (Test-Path $ApothemProfile) {
    Write-Ok "Found profile at $ApothemProfile"
} else {
    $ExamplePath = [System.IO.Path]::Combine($Source, 'src', 'apothem', 'schemas', 'profile.example.yaml')
    if (-not (Test-Path -LiteralPath $ExamplePath)) {
        Write-Fail "Could not locate profile.example.yaml - create $ApothemProfile manually"
    }
    if ($DryRun) {
        Write-Info "No profile at $ApothemProfile - the dry run previews with the example profile and writes nothing"
        $EngineProfile = $ExamplePath
    } else {
        Write-Info "No profile at $ApothemProfile - creating it from the example"
        New-Item -ItemType Directory -Force -Path (Split-Path $ApothemProfile) | Out-Null
        Copy-Item $ExamplePath $ApothemProfile
        Write-Ok "Created $ApothemProfile from the example profile"
        Write-Warn "Its identity fields are placeholders. Edit $ApothemProfile, then run 'apothem update --harness $Harness' to apply your identity."
    }
}

# Materialize harness ---------------------------------------------------------
#
# Run the bundled engine directly from the source tree - self-contained, no
# package installation: the engine and its vendored dependencies resolve
# because the tree's vendor and src/ directories are prepended to PYTHONPATH.
Write-Bold "Installing harness: $Harness"

# Opt-in clean-slate pass-through flags for the engine. `-Clean` / `-Fresh`
# both request the engine's bounded backup-and-remove cycle; the engine loads
# the profile before removal and restores it afterward.
$EngineFlags = @()
if ($Clean -or $Fresh) { $EngineFlags += '--clean' }
if ($DryRun)           { $EngineFlags += '--dry-run' }
if ($Yes)              { $EngineFlags += '--yes' }

$PriorPyPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($PriorPyPath) { "$EnginePyPath$([System.IO.Path]::PathSeparator)$PriorPyPath" } else { $EnginePyPath }
try {
    & $PY -m apothem install --harness $Harness --profile $EngineProfile @EngineFlags
    if ($LASTEXITCODE -ne 0) { Write-Fail "Harness materialization failed for $Harness" }

    if ($DryRun) {
        # Dry-run previews only; skip the verify block and banner so no
        # post-install action runs. The finally block still restores PYTHONPATH.
        Write-Bold "Dry-run complete - no changes were made."
    } else {
        Write-Ok "Harness $Harness installed"

        # Verify --------------------------------------------------------------
        if ($env:APOTHEM_SKIP_VERIFY -ne '1') {
            Write-Bold "Verifying installation"
            & $PY -m apothem verify --harness $Harness
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "verify reported issues - run the verify command below for details"
            } else {
                Write-Ok "verify passed"
            }
        } else {
            Write-Warn "APOTHEM_SKIP_VERIFY=1 - skipping verification"
        }
    }
}
finally {
    $env:PYTHONPATH = $PriorPyPath
}

# Entry-point shim ------------------------------------------------------------
#
# Place an `apothem` command on PATH so the operator runs `apothem <command>`
# instead of the verbose self-contained form (PowerShell parity to install.sh).
# The shim is a `.cmd` (resolvable as a bare `apothem` via PATHEXT) that forwards
# to the bundled engine with the vendored PYTHONPATH. It defaults into
# %LOCALAPPDATA%\Microsoft\WindowsApps - a user-owned directory already on the
# default Windows user PATH - so the shim resolves WITHOUT modifying PATH (the
# installer manages no PATH entry; see the self-contained invocation model).
# Override the directory with APOTHEM_BIN_DIR. Dry-run writes nothing. The banner
# advertises a bare `apothem` command only when its directory is on PATH;
# otherwise it prints how to add the directory and falls back to the
# self-contained form, so it never promises a command the run did not resolve.
$ShimOnPath = $false
if (-not $DryRun) {
    $DefaultBinDir = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'Microsoft', 'WindowsApps')
    $BinDir = if ($env:APOTHEM_BIN_DIR) { $env:APOTHEM_BIN_DIR } else { $DefaultBinDir }
    $Shim = Join-Path $BinDir 'apothem.cmd'
    try {
        New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
        $ShimBody = @"
@echo off
setlocal
set "PYTHONPATH=$EnginePyPath;%PYTHONPATH%"
"$PY" -m apothem %*
"@
        Set-Content -LiteralPath $Shim -Value $ShimBody -Encoding ascii
        Write-Ok "Installed apothem command: $Shim"

        # Resolve $BinDir against the current process PATH WITHOUT editing PATH.
        $Sep = [System.IO.Path]::PathSeparator
        $BinNorm = $BinDir.TrimEnd('\').ToLowerInvariant()
        $OnPath = @($env:Path.Split($Sep) | ForEach-Object { $_.TrimEnd('\').ToLowerInvariant() })
        if ($OnPath -contains $BinNorm) {
            $ShimOnPath = $true
        } else {
            Write-Info "Add $BinDir to your PATH to use the 'apothem' command directly."
        }
    } catch {
        Write-Warn "Could not place an apothem shim in $BinDir - use the self-contained form below."
    }
}

# Next-step banner ------------------------------------------------------------
Write-Bold "Installation complete."
if ($ShimOnPath) {
    Write-Host @"

The 'apothem' command is installed.

Recommended first step - the guided setup (profile -> preview -> install):
  apothem quickstart

Or run individual commands:
  apothem harnesses list        # list all harnesses
  apothem doctor                # check system health
  apothem profile edit          # edit your profile

Optional - enable <TAB> shell completion (opt-in; appends to your profile):
  apothem completion powershell >> `$PROFILE   # PowerShell
  apothem completion bash >> ~/.bashrc         # bash / zsh / fish also supported

"@
} else {
    Write-Host @"

Run the engine from the bundled source (self-contained - no package installation):
  `$env:PYTHONPATH = '$EnginePyPath'; & '$PY' -m apothem <command>

Recommended first step - the guided setup (profile -> preview -> install):
  `$env:PYTHONPATH = '$EnginePyPath'; & '$PY' -m apothem quickstart

Or run individual commands:
  `$env:PYTHONPATH = '$EnginePyPath'; & '$PY' -m apothem harnesses list   # list harnesses
  `$env:PYTHONPATH = '$EnginePyPath'; & '$PY' -m apothem doctor           # system health
  `$env:PYTHONPATH = '$EnginePyPath'; & '$PY' -m apothem profile edit     # edit profile

Optional - once the 'apothem' command is on your PATH, enable <TAB> shell
completion (opt-in; appends to your profile):
  apothem completion powershell >> `$PROFILE   # or bash / zsh / fish

"@
}
