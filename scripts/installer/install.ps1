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
# vMAJOR.MINOR.PATCH release tag and installs THAT release - the moving `main`
# branch is no longer the default. APOTHEM_VERIFY's default, `auto`, picks the
# check: with cosign on PATH it downloads the release's Windows archive, has
# cosign confirm that the release workflow at that tag signed SHA256SUMS, and
# checks the archive's SHA-256 against it (nothing here rests on SHA-1);
# without cosign it clones and checks the tag with `git verify-tag`, requiring
# a valid signature made by the maintainer key SECURITY.md publishes
# (fingerprint 5C8998F9F241720445D3F28B70396FED9C634163), not merely one the
# local keyring trusts. A failed check ABORTS before any config is written.
# APOTHEM_REF=main checks out the branch on
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
#   APOTHEM_VERIFY           "auto" (default) uses "release" when cosign is on
#                            PATH and "signature" otherwise. "release"
#                            installs the Windows archive after cosign checks
#                            that the release workflow signed SHA256SUMS and
#                            the archive's SHA-256 matches it (needs cosign).
#                            "signature" clones and checks the tag's GPG
#                            signature against the pinned maintainer key.
#                            "checksum" installs the archive after the SHA-256
#                            check alone: integrity without proof of the
#                            publisher, for hosts with neither cosign nor the
#                            key.
#   APOTHEM_RELEASE_BASE     Release download base for the archive modes
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
$ApothemVerify = if ($env:APOTHEM_VERIFY) { $env:APOTHEM_VERIFY } else { 'auto' }
$Harness     = if ($env:APOTHEM_HARNESS) { $env:APOTHEM_HARNESS } else { 'claude-code' }
$ApothemProfile = if ($env:APOTHEM_PROFILE) { $env:APOTHEM_PROFILE } else { [System.IO.Path]::Combine($HOME, '.config', 'apothem', 'profile.yaml') }

# The trust roots, fixed here rather than read from the environment so that
# nothing outside this script can widen them (mirrors install.sh).
# MaintainerFingerprint is the primary-key fingerprint SECURITY.md publishes; a
# release tag must be signed by it. The cosign identity is the release
# workflow at the tag being installed, in the owner casing GitHub writes into
# the certificate.
$MaintainerFingerprint = '5C8998F9F241720445D3F28B70396FED9C634163'
$CosignIdentityRepo = 'Ahmed-G-Gad/apothem'
$CosignOidcIssuer = 'https://token.actions.githubusercontent.com'
$CosignInstallDoc = 'https://docs.sigstore.dev/cosign/system_config/installation/'

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
        # -cmatch keeps the match case-sensitive, as install.sh's sed filter
        # is: -match ignores case and would also take a V9.9.9 tag, which
        # Test-ReleaseTag rejects. $ is safe here: each line arrives without
        # its newline.
        if ($line -cmatch 'refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)(\^\{\})?$') {
            $tags += $matches[1]
        }
    }
    if ($tags.Count -eq 0) { return $null }
    # @() keeps the result an array when one tag remains. A bare string
    # would make $sorted[-1] its last character.
    $sorted = @($tags | Sort-Object -Unique | Sort-Object { [version]($_.Substring(1)) })
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

# Test-TagSignedByMaintainer - $true when the captured status lines carry at
# least one VALIDSIG line and every VALIDSIG line names $MaintainerFingerprint
# as its primary key, $false otherwise. `git verify-tag` alone accepts a valid
# signature from any key the local keyring holds; this pins the one key that
# signs Apothem releases. VALIDSIG's tenth argument (index 11 here) is the
# primary key's fingerprint; GnuPG leaves it out only for keys too old to have
# one, so the signing key's fingerprint (index 2) stands in then. Only lines
# that start with the status prefix count; GnuPG escapes newlines inside user
# IDs, so a key's name cannot forge one. Mirrors install.sh's
# verify_tag_by_maintainer.
function Test-TagSignedByMaintainer {
    $Seen = $false
    foreach ($Line in ($script:VerifyTagOutput -split "`n")) {
        $Fields = @($Line.Trim() -split '\s+')
        if ($Fields.Count -ge 3 -and $Fields[0] -ceq '[GNUPG:]' -and $Fields[1] -ceq 'VALIDSIG') {
            $Seen = $true
            $Fpr = if ($Fields.Count -ge 12) { $Fields[11] } else { $Fields[2] }
            if ($Fpr.ToUpperInvariant() -ne $MaintainerFingerprint) { return $false }
        }
    }
    return $Seen
}

# Test-TagSignedByOtherKey - $true when GnuPG reported a valid signature (a
# VALIDSIG line) that Test-TagSignedByMaintainer rejects: the signature is
# sound, but another key made it.
function Test-TagSignedByOtherKey {
    if ($script:VerifyTagOutput -notmatch '(?m)^\s*\[GNUPG:\] VALIDSIG ') { return $false }
    return (-not (Test-TagSignedByMaintainer))
}

# Test-VerifyTagMissingKey - $true when the captured status lines show the
# signature could not be checked because the signing public key is absent
# from the local keyring (GnuPG's NO_PUBKEY status), $false for any other
# failure (unsigned tag, BAD signature).
function Test-VerifyTagMissingKey {
    return ($script:VerifyTagOutput -match '\[GNUPG:\] NO_PUBKEY ')
}

# Test-ReleaseTag REF - return $true when REF is a vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), $false otherwise (a branch, a SHA, a pre-release).
# -cmatch keeps the match case-sensitive, as install.sh's is_release_tag is:
# -match ignores case and would also accept V1.2.3. \z matches only at the
# end of the string: $ also matches before a final newline, so it would
# accept "v1.2.3`n", which is_release_tag rejects.
function Test-ReleaseTag {
    param([string]$Ref)
    return ($Ref -cmatch '^v[0-9]+\.[0-9]+\.[0-9]+\z')
}

# Assert-GpgAvailable - fail unless the program `git verify-tag` runs for an
# OpenPGP signature is present, so a missing GnuPG is named as such instead
# of surfacing as a failed signature check. That program is gpg.program when
# it is set, else gpg on PATH, else the gpg Git for Windows ships under its
# install root (usr\bin\gpg.exe), which git runs although it is not on PATH.
function Assert-GpgAvailable {
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $Format = & git config --get gpg.format 2>$null
        $Prog = & git config --get gpg.program 2>$null
        $ExecPath = & git --exec-path 2>$null
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($Format -eq 'ssh') { return }
    if ($Prog) {
        if ((Test-Path -LiteralPath $Prog -PathType Leaf) -or (Get-Command $Prog -ErrorAction SilentlyContinue)) { return }
    } else {
        if (Get-Command 'gpg' -ErrorAction SilentlyContinue) { return }
        if ($ExecPath) {
            $GitRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ExecPath))
            if ($GitRoot -and (Test-Path -LiteralPath (Join-Path $GitRoot 'usr\bin\gpg.exe'))) { return }
        }
    }
    Write-Fail "gpg not found - needed to check the $ApothemRef release tag's signature against the maintainer key. Install Git for Windows (it ships gpg) or GnuPG (https://gnupg.org/download/), then re-run."
}

# Test-MaintainerTag DIR REF ALLOW - the key-pinned tag gate (mirrors
# install.sh's check_release_tag). Checks the tag refs/tags/REF in the
# repository at DIR and prints the result. A tag signed by the maintainer key
# returns the commit it points at; any other outcome aborts with the reason,
# unless ALLOW is $true, which downgrades the abort to a warning and returns
# $null.
function Test-MaintainerTag {
    param([string]$Dir, [string]$Ref, [bool]$Allow)
    if ((Test-TagSignature $Dir "refs/tags/$Ref") -and (Test-TagSignedByMaintainer)) {
        $Commit = & git -C $Dir rev-parse --verify --quiet "refs/tags/$Ref^{commit}"
        if ($LASTEXITCODE -ne 0 -or -not $Commit) { Write-Fail "Could not read the commit the $Ref tag points at" }
        Write-Ok "Tag $Ref carries a valid signature from the maintainer key $MaintainerFingerprint"
        return ([string]$Commit).Trim()
    }
    if ($Allow) {
        Write-Warn "Tag $Ref is unsigned, its signature did not verify, or the maintainer key did not make it - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        return $null
    }
    if (Test-TagSignedByOtherKey) {
        Write-Fail "Tag $Ref carries a valid signature, but not from the maintainer key $MaintainerFingerprint that SECURITY.md publishes (possible tampering). Aborting before any configuration is materialized."
    }
    if (Test-VerifyTagMissingKey) {
        Write-Fail "Tag $Ref is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run & `"$env:ProgramFiles\Git\bin\bash.exe`" -c 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import && gpg --fingerprint 70396FED9C634163' (the gpg that ships with Git for Windows, which git verify-tag uses), check that the fingerprint matches the one published in SECURITY.md, then re-run this installer."
    }
    Write-Fail "Tag $Ref is unsigned or its signature did not verify (possible tampering). Aborting before any configuration is materialized."
}

# Invoke-CheckoutRef DIR - check out APOTHEM_REF in the clone at DIR. A
# release tag is checked out by its full refs/tags/ name, so a branch that
# shares the tag's name cannot stand in for it, and HEAD must then be the
# tag's commit. Any other ref resolves directly or through origin/<branch>.
function Invoke-CheckoutRef {
    param([string]$Dir)
    if (Test-ReleaseTag $ApothemRef) {
        & git -C $Dir checkout --quiet --force "refs/tags/$ApothemRef"
        if ($LASTEXITCODE -ne 0) { Write-Fail "Could not check out the $ApothemRef tag in $Dir" }
        $CoHead = & git -C $Dir rev-parse --verify --quiet HEAD
        $CoTag = & git -C $Dir rev-parse --verify --quiet "refs/tags/$ApothemRef^{commit}"
        if (-not $CoTag -or "$CoHead" -ne "$CoTag") {
            Write-Fail "The checkout in $Dir is at '$CoHead', not at the $ApothemRef tag's commit '$CoTag'. Aborting before anything is verified or materialized."
        }
    } else {
        & git -C $Dir checkout --quiet --force $ApothemRef
        if ($LASTEXITCODE -ne 0) { & git -C $Dir checkout --quiet --force "origin/$ApothemRef" }
        if ($LASTEXITCODE -ne 0) { Write-Fail "Could not check out $ApothemRef in $Dir" }
    }
}

# Read-DerItem BUF AT - decode the DER item at offset AT of BUF into its tag,
# its value bytes and the offset just past it.
function Read-DerItem {
    param([byte[]]$Buf, [int]$At)
    $Tag = [int]$Buf[$At]
    $Size = [int]$Buf[$At + 1]
    $At += 2
    if ($Size -band 0x80) {
        $Count = $Size -band 0x7F
        $Size = 0
        for ($k = 0; $k -lt $Count; $k++) { $Size = ($Size * 256) + [int]$Buf[$At + $k] }
        $At += $Count
    }
    if ($At + $Size -gt $Buf.Length) { throw 'truncated DER item' }
    $Value = New-Object byte[] $Size
    [System.Array]::Copy($Buf, $At, $Value, 0, $Size)
    return @{ Tag = $Tag; Value = $Value; Next = $At + $Size }
}

# Get-DerContent BUF - the DER items that BUF holds, one after another.
function Get-DerContent {
    param([byte[]]$Buf)
    $Items = @()
    $At = 0
    while ($At -lt $Buf.Length) {
        $Item = Read-DerItem $Buf $At
        $Items += , $Item
        $At = $Item.Next
    }
    return , $Items
}

# Get-CertSourceCommit BUNDLE - the commit that the Sigstore signing
# certificate in BUNDLE names in its source-repository-digest extension (OID
# 1.3.6.1.4.1.57264.1.19, a DER UTF8String), or $null when the bundle holds
# no certificate or the certificate has no such extension. It reads cosign's
# own bundle ("cert": a base64 PEM) and the Sigstore bundle format
# (verificationMaterial), and walks the DER as install.sh does. Run only
# after cosign has verified the bundle, so the certificate it reads is the
# one cosign checked.
function Get-CertSourceCommit {
    param([string]$Bundle)
    try {
        $Json = Get-Content -LiteralPath $Bundle -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if ($Json.PSObject.Properties.Name -contains 'cert') {
            $Pem = [System.Text.Encoding]::ASCII.GetString([System.Convert]::FromBase64String($Json.cert))
            $Body = [regex]::Match($Pem, '-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----', [System.Text.RegularExpressions.RegexOptions]::Singleline)
            if (-not $Body.Success) { return $null }
            $Der = [System.Convert]::FromBase64String(($Body.Groups[1].Value -replace '\s', ''))
        } else {
            $Material = $Json.verificationMaterial
            $CertEntry = if ($Material.certificate) { $Material.certificate } else { @($Material.x509CertificateChain.certificates)[0] }
            $Der = [System.Convert]::FromBase64String($CertEntry.rawBytes)
        }
        $Tbs = (Read-DerItem (Read-DerItem $Der 0).Value 0).Value
        foreach ($Field in (Get-DerContent $Tbs)) {
            if ($Field.Tag -ne 0xA3) { continue }
            foreach ($Extension in (Get-DerContent (Read-DerItem $Field.Value 0).Value)) {
                $Parts = Get-DerContent $Extension.Value
                if ($Parts.Count -ge 2 -and $Parts[0].Tag -eq 6 -and [System.BitConverter]::ToString($Parts[0].Value) -ceq '2B-06-01-04-01-83-BF-30-01-13') {
                    $Digest = $Parts[$Parts.Count - 1].Value
                    if ($Digest.Length -gt 0 -and $Digest[0] -eq 0x0C) { $Digest = (Read-DerItem $Digest 0).Value }
                    return [System.Text.Encoding]::ASCII.GetString($Digest)
                }
            }
        }
    } catch {
        return $null
    }
    return $null
}

# Invoke-SwapIn NEW DROP - put the tree at NEW in place of APOTHEM_HOME
# (mirrors install.sh's swap_in). NEW sits beside APOTHEM_HOME, so each move
# stays on one drive. The earlier APOTHEM_HOME moves aside first and comes
# back if NEW cannot move in. Then every top-level entry of the earlier tree
# that NEW does not ship moves into the new tree, except DROP (.git when an
# archive replaces a clone): that keeps the engine's rollback backups
# (backups\) and install ledgers (state\), which live in APOTHEM_HOME too.
# The rest of the earlier tree is removed.
function Invoke-SwapIn {
    param([string]$New, [string]$Drop)
    if (-not (Test-Path -LiteralPath $ApothemHome)) {
        try { Move-Item -LiteralPath $New -Destination $ApothemHome }
        catch { Write-Fail "Could not move the new source to $ApothemHome" }
        return
    }
    $SwParent = Split-Path -Parent $ApothemHome
    if (-not $SwParent) { $SwParent = (Get-Location).Path }
    $SwOld = Join-Path $SwParent (".apothem-old." + [System.Guid]::NewGuid().ToString('N'))
    try { New-Item -ItemType Directory -Path $SwOld | Out-Null }
    catch { Write-Fail "Could not make room beside $ApothemHome" }
    $SwOldHome = Join-Path $SwOld 'home'
    try { Move-Item -LiteralPath $ApothemHome -Destination $SwOldHome }
    catch {
        Remove-Item -LiteralPath $SwOld -Force
        Write-Fail "Could not move the existing $ApothemHome aside; nothing was changed"
    }
    try { Move-Item -LiteralPath $New -Destination $ApothemHome }
    catch {
        Move-Item -LiteralPath $SwOldHome -Destination $ApothemHome
        Remove-Item -LiteralPath $SwOld -Force
        Write-Fail "Could not move the new source to $ApothemHome; the earlier install is back in place"
    }
    if (Test-Path -LiteralPath $SwOldHome -PathType Container) {
        foreach ($SwEntry in @(Get-ChildItem -LiteralPath $SwOldHome -Force)) {
            if ($Drop -and $SwEntry.Name -eq $Drop) { continue }
            $SwTarget = Join-Path $ApothemHome $SwEntry.Name
            if (Test-Path -LiteralPath $SwTarget) { continue }
            try { Move-Item -LiteralPath $SwEntry.FullName -Destination $SwTarget }
            catch { Write-Fail "Could not move $($SwEntry.Name) into the new $ApothemHome; the earlier install is kept at $SwOldHome" }
        }
    }
    Remove-Item -LiteralPath $SwOld -Recurse -Force
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

if (@('auto', 'release', 'signature', 'checksum') -cnotcontains $ApothemVerify) {
    Write-Fail "APOTHEM_VERIFY must be 'auto', 'release', 'signature' or 'checksum' (got '$ApothemVerify')."
}
$ApothemReleaseBase = if ($env:APOTHEM_RELEASE_BASE) { $env:APOTHEM_RELEASE_BASE } else { "$ApothemRepo/releases/download" }

# Pick the verification path for a fetched source (mirrors install.sh). `auto`
# takes the release path when cosign is on PATH and the key-pinned tag check
# otherwise. A ref that is not a release tag (main, a SHA) has no release
# archive, so it goes to the clone path, whose gate refuses it unless
# APOTHEM_ALLOW_UNVERIFIED=1. An existing git clone at APOTHEM_HOME stays a
# clone: replacing it with an archive would drop its history and any local
# work, so it is updated through the clone path's key-pinned tag check.
$VerifyMode = $ApothemVerify
$HasCosign = [bool](Get-Command 'cosign' -ErrorAction SilentlyContinue)
$HomeIsClone = Test-Path -LiteralPath (Join-Path $ApothemHome '.git')
if (-not $Source -and $VerifyMode -eq 'auto') {
    if ($ApothemRef -and -not (Test-ReleaseTag $ApothemRef)) {
        $VerifyMode = 'signature'
    } elseif ($HomeIsClone) {
        $VerifyMode = 'signature'
        Write-Info "$ApothemHome is a git clone - updating it and checking the release tag's signature. To use the cosign-checked release archive instead, move the clone aside first."
    } elseif ($HasCosign) {
        $VerifyMode = 'release'
        Write-Info "cosign found - installing the release archive once both the release tag's signature and cosign's check of its SHA-256 digest pass"
    } else {
        $VerifyMode = 'signature'
        Write-Info "cosign not found - checking the release tag's signature only. Install cosign ($CosignInstallDoc) to also check the release archive's signed SHA-256 digest."
    }
}
if (-not $Source -and $VerifyMode -eq 'release' -and -not $HasCosign) {
    Write-Fail "APOTHEM_VERIFY=release needs cosign on PATH ($CosignInstallDoc). Install it, or set APOTHEM_VERIFY=signature to check the release tag against the maintainer key alone."
}

# A dry run fetches and checks the source in a scratch folder and leaves
# APOTHEM_HOME alone; the folder is removed once the engine's preview ends,
# or by this trap when the run stops early on a terminating error.
$script:DryRunScratch = $null
# A trap covers its whole scope, including the lines above this one, so the
# variable is read in a way that tolerates its not being set yet.
trap {
    $TrapScratch = Get-Variable -Name DryRunScratch -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    if ($TrapScratch -and (Test-Path -LiteralPath $TrapScratch)) {
        Remove-Item -LiteralPath $TrapScratch -Recurse -Force -ErrorAction SilentlyContinue
    }
    break
}

# Archive modes: install the release's Windows archive after checking its
# SHA-256 against the release's SHA256SUMS. They replace the git clone below.
# `release` checks two things before it trusts the digest, and both must
# pass: the release tag is signed by the maintainer key, and cosign shows
# that the release workflow signed SHA256SUMS in a run on the commit that tag
# points at. Either alone is not enough: anyone who can push a tag can make
# the workflow sign a release, and a signed tag says nothing about the
# archive. `checksum` skips both, for hosts with neither cosign nor the
# maintainer key, and says plainly that a matching digest proves integrity,
# not origin.
if (-not $Source -and ($VerifyMode -eq 'checksum' -or $VerifyMode -eq 'release')) {
    if (-not $ApothemRef) {
        if (-not (Get-Command 'git' -ErrorAction SilentlyContinue)) {
            Write-Fail "git not found in PATH - needed to resolve the latest release tag"
        }
        Write-Info "Resolving latest release tag from $ApothemRepo"
        $ApothemRef = Resolve-LatestTag $ApothemRepo
        if (-not $ApothemRef) {
            Write-Fail "No vMAJOR.MINOR.PATCH release tag found at $ApothemRepo. Pin one with APOTHEM_REF, or set APOTHEM_SOURCE to a local checkout."
        }
    }
    if (-not (Test-ReleaseTag $ApothemRef)) {
        Write-Fail "APOTHEM_VERIFY=$VerifyMode needs a vMAJOR.MINOR.PATCH release tag; got '$ApothemRef'. Pin one with APOTHEM_REF."
    }
    $CkName = "apothem-$ApothemRef-windows.zip"
    $CkTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $CkTmp -Force | Out-Null
    $CkExtract = $null
    # Everything from here to the swap into APOTHEM_HOME runs inside try, so
    # the download and the staging folder are removed on every path, success,
    # failure or interrupt. A dry run keeps the scratch folder for the
    # engine's preview.
    try {
        $CkTagCommit = $null
        if ($VerifyMode -eq 'release') {
            if (-not (Get-Command 'git' -ErrorAction SilentlyContinue)) {
                Write-Fail "git not found in PATH - needed to check the $ApothemRef release tag"
            }
            Assert-GpgAvailable
            Write-Bold "Verifying the $ApothemRef release tag"
            # Only the tag and the commit it points at are fetched, into a
            # throwaway repository; the source itself comes from the archive.
            $CkTagGit = Join-Path $CkTmp 'tag.git'
            & git init --quiet --bare $CkTagGit
            if ($LASTEXITCODE -ne 0) { Write-Fail "Could not create a scratch repository to check the $ApothemRef tag" }
            $prior = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                $CkFetchOut = & git -C $CkTagGit fetch --quiet --depth=1 --no-tags $ApothemRepo "+refs/tags/${ApothemRef}:refs/tags/${ApothemRef}" 2>&1
                $CkFetchCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $prior
            }
            if ($CkFetchCode -ne 0) {
                $CkSaid = (@($CkFetchOut | Where-Object { $null -ne $_ } | ForEach-Object { $_.ToString() }) | Select-Object -Last 2) -join ' '
                Write-Fail "Could not fetch the $ApothemRef tag from ${ApothemRepo}: $CkSaid"
            }
            $CkTagCommit = Test-MaintainerTag $CkTagGit $ApothemRef $false
        }
        $CkArchive = Join-Path $CkTmp $CkName
        $CkSums = Join-Path $CkTmp 'SHA256SUMS'
        Write-Info "Downloading $CkName and SHA256SUMS from the $ApothemRef release"
        try { Invoke-WebRequest -UseBasicParsing -Uri "$ApothemReleaseBase/$ApothemRef/$CkName" -OutFile $CkArchive }
        catch { Write-Fail "Could not download $CkName from $ApothemReleaseBase/$ApothemRef" }
        try { Invoke-WebRequest -UseBasicParsing -Uri "$ApothemReleaseBase/$ApothemRef/SHA256SUMS" -OutFile $CkSums }
        catch { Write-Fail "Could not download SHA256SUMS from $ApothemReleaseBase/$ApothemRef" }
        if ($VerifyMode -eq 'release') {
            # The certificate identity is exact, never a pattern: a regular
            # expression would also match a forged subject that merely
            # contains the repository path. It names the tag being installed,
            # so a bundle signed for another release does not verify here.
            $CkIdentity = "https://github.com/$CosignIdentityRepo/.github/workflows/release.yml@refs/tags/$ApothemRef"
            $CkBundle = Join-Path $CkTmp 'SHA256SUMS.cosign.bundle'
            # Early releases published the same Sigstore bundle as
            # SHA256SUMS.sig (scripts/release/verify-provenance.sh accepts both).
            try { Invoke-WebRequest -UseBasicParsing -Uri "$ApothemReleaseBase/$ApothemRef/SHA256SUMS.cosign.bundle" -OutFile $CkBundle }
            catch {
                try { Invoke-WebRequest -UseBasicParsing -Uri "$ApothemReleaseBase/$ApothemRef/SHA256SUMS.sig" -OutFile $CkBundle }
                catch { Write-Fail "Could not download SHA256SUMS.cosign.bundle, or SHA256SUMS.sig as early releases name it, from $ApothemReleaseBase/$ApothemRef. Set APOTHEM_VERIFY=signature to check the release tag alone." }
            }
            # cosign reports on stderr, which PowerShell before 7.2 turns into
            # a terminating error under 'Stop' once redirected, so the
            # preference is localized as in Test-TagSignature.
            $prior = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            # A wrapper that never sets $LASTEXITCODE must not pass as success.
            $global:LASTEXITCODE = 1
            try {
                $CkCosignOut = & cosign verify-blob --bundle $CkBundle --certificate-identity $CkIdentity --certificate-oidc-issuer $CosignOidcIssuer $CkSums 2>&1
                $CkCosignCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $prior
            }
            if ($CkCosignCode -ne 0) {
                $CkSaid = (@($CkCosignOut | Where-Object { $null -ne $_ } | ForEach-Object { $_.ToString() }) | Select-Object -Last 3) -join ' '
                Write-Fail "cosign could not confirm that the $ApothemRef release workflow ($CkIdentity) signed SHA256SUMS (possible tampering). Aborting before anything is extracted. cosign said: $CkSaid If cosign could not reach Sigstore (offline or behind a proxy), set APOTHEM_VERIFY=signature to check the release tag alone."
            }
            Write-Ok "cosign: SHA256SUMS is signed by the $ApothemRef release workflow"
            # The workflow run that signed SHA256SUMS must have run on the
            # commit the maintainer signed. Fulcio writes that run's commit
            # into the certificate; a certificate without it cannot be tied to
            # the tag.
            $CkCertCommit = Get-CertSourceCommit $CkBundle
            if (-not $CkCertCommit) {
                Write-Fail "The $ApothemRef signing certificate names no source commit (extension 1.3.6.1.4.1.57264.1.19), so it cannot be tied to the signed tag. Aborting before anything is extracted."
            }
            if ($CkCertCommit.ToLowerInvariant() -cne $CkTagCommit) {
                Write-Fail "The $ApothemRef release was signed in a workflow run on commit $CkCertCommit, but the maintainer-signed tag points at $CkTagCommit (possible tampering). Aborting before anything is extracted."
            }
            Write-Ok "The signing workflow ran on the tag's commit $CkTagCommit"
        }
        $CkExpected = $null
        foreach ($Line in Get-Content -LiteralPath $CkSums) {
            $Fields = $Line -split '\s+', 2
            if ($Fields.Count -eq 2 -and ($Fields[1] -ceq $CkName -or $Fields[1] -ceq "*$CkName")) {
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
        if ($VerifyMode -eq 'checksum') {
            Write-Warn "Checksum mode: a matching digest shows the archive is the one the release lists; it does not prove who published it. For proof of the publisher, install cosign and gpg and run without APOTHEM_VERIFY=checksum."
        }
        # Who owns what is already at APOTHEM_HOME decides whether -Yes is
        # needed (mirrors install.sh). An earlier archive install is
        # Apothem's own and is updated without asking. A git clone (history,
        # branches, local work) or anything else needs -Yes. Invoke-SwapIn
        # keeps every entry the archive does not ship, the engine's backups\
        # and state\ among them.
        $CkDrop = ''
        if ((Test-Path -LiteralPath $ApothemHome) -and (Get-ChildItem -LiteralPath $ApothemHome -Force | Select-Object -First 1)) {
            if ($HomeIsClone) {
                if ($Yes) {
                    Write-Warn "Replacing the git clone's source at $ApothemHome with the $ApothemRef archive; its git history is removed, its backups\ and state\ are kept (-Yes)"
                    $CkDrop = '.git'
                } else {
                    Write-Fail "Destination $ApothemHome is a git clone; refusing to replace it with the $ApothemRef archive, which would remove its history. Set APOTHEM_VERIFY=signature to update the clone, move it aside, or re-run with -Yes."
                }
            } elseif (Test-ApothemSource $ApothemHome) {
                Write-Info "Updating the earlier install at $ApothemHome to the $ApothemRef archive"
            } elseif ($Yes) {
                Write-Warn "Writing the $ApothemRef archive into the existing $ApothemHome; files it does not ship are kept (-Yes)"
            } else {
                Write-Fail "Destination $ApothemHome is not empty and holds no Apothem install; refusing to replace it. Move it aside, point APOTHEM_HOME at another directory, or re-run with -Yes."
            }
        }
        # The release archive roots every file under apothem-<tag>\ (see
        # scripts/build_release_tarball.py). A real install extracts it into
        # a staging folder beside APOTHEM_HOME, because Windows PowerShell
        # 5.1's Move-Item moves a directory only within one drive; a dry run
        # extracts it into the scratch folder and leaves APOTHEM_HOME alone.
        if ($DryRun) {
            $CkExtract = Join-Path $CkTmp 'extract'
        } else {
            $CkParent = Split-Path -Parent $ApothemHome
            if (-not $CkParent) { $CkParent = (Get-Location).Path }
            try { New-Item -ItemType Directory -Path $CkParent -Force | Out-Null }
            catch { Write-Fail "Could not create the parent directory of $ApothemHome" }
            if (-not (Test-Path -LiteralPath $CkParent -PathType Container)) {
                Write-Fail "Could not create the parent directory of $ApothemHome"
            }
            $CkExtract = Join-Path $CkParent (".apothem-extract." + [System.Guid]::NewGuid().ToString('N'))
        }
        try { Expand-Archive -LiteralPath $CkArchive -DestinationPath $CkExtract -Force }
        catch { Write-Fail "Could not extract $CkName" }
        $CkRoot = Join-Path $CkExtract "apothem-$ApothemRef"
        if (-not (Test-ApothemSource $CkRoot)) { Write-Fail "$CkName does not hold an apothem source under apothem-$ApothemRef\" }
        if ($DryRun) {
            $script:DryRunScratch = $CkTmp
            $Source = $CkRoot
        } else {
            Invoke-SwapIn $CkRoot $CkDrop
            $Source = $ApothemHome
        }
    } finally {
        if ($CkExtract -and -not $DryRun -and (Test-Path -LiteralPath $CkExtract)) { Remove-Item -LiteralPath $CkExtract -Recurse -Force }
        if (-not $script:DryRunScratch -and (Test-Path -LiteralPath $CkTmp)) { Remove-Item -LiteralPath $CkTmp -Recurse -Force }
    }
    if ($DryRun) {
        Write-Ok "Source ready at $Source (release archive $ApothemRef; dry run, so $ApothemHome is not changed)"
    } else {
        Write-Ok "Source ready at $Source (release archive $ApothemRef)"
    }
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
    if ((Test-ReleaseTag $ApothemRef) -and $ApothemAllowUnverified -ne '1') { Assert-GpgAvailable }

    # An existing clone is updated in place. Otherwise the clone is made in a
    # fresh staging folder, checked, and only then swapped in by
    # Invoke-SwapIn, which keeps the engine's backups\ and state\ from an
    # earlier archive install. A dry run clones into a scratch folder and
    # leaves APOTHEM_HOME alone.
    $ClStage = $null
    if ($HomeIsClone -and -not $DryRun) {
        Write-Info "Updating existing clone at $ApothemHome (ref: $ApothemRef)"
        & git -C $ApothemHome fetch --quiet --tags origin
        Invoke-CheckoutRef $ApothemHome
        $ClTree = $ApothemHome
    } else {
        # An existing non-clone path here may not be Apothem's, so replacing
        # it needs -Yes; a stale empty folder is replaced quietly.
        if (-not $DryRun -and (Test-Path -LiteralPath $ApothemHome) -and (Get-ChildItem -LiteralPath $ApothemHome -Force | Select-Object -First 1)) {
            if ($Yes) {
                Write-Warn "Replacing the existing non-clone $ApothemHome with a clone of $ApothemRef; files the clone does not ship, such as backups\ and state\, are kept (-Yes)"
            } else {
                Write-Fail "Destination $ApothemHome exists but is not a git clone; refusing to replace it. If it is an earlier archive install, install cosign and gpg and re-run to update it in place, or re-run with -Yes to switch it to a clone (its backups\ and state\ are kept). Otherwise move it aside or point APOTHEM_HOME at another directory."
            }
        }
        if ($DryRun) {
            $ClStage = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-" + [System.Guid]::NewGuid().ToString('N'))
            $script:DryRunScratch = $ClStage
        } else {
            $ClParent = Split-Path -Parent $ApothemHome
            if (-not $ClParent) { $ClParent = (Get-Location).Path }
            New-Item -ItemType Directory -Force -Path $ClParent | Out-Null
            $ClStage = Join-Path $ClParent (".apothem-clone." + [System.Guid]::NewGuid().ToString('N'))
        }
        New-Item -ItemType Directory -Path $ClStage | Out-Null
        $ClTree = Join-Path $ClStage 'apothem'
    }
    try {
        if ($ClStage) {
            Write-Info "Cloning $ApothemRepo"
            # Full clone (no --single-branch) so both tags and branches are
            # checkout-able, then pin to the resolved ref.
            & git clone --quiet $ApothemRepo $ClTree
            if ($LASTEXITCODE -ne 0) { Write-Fail "git clone failed for $ApothemRepo" }
            Invoke-CheckoutRef $ClTree
        }
        if (-not (Test-ApothemSource $ClTree)) { Write-Fail "Fetched tree is not an apothem source: $ClTree" }

        # Fail-closed signature verification - runs BEFORE the clone is
        # swapped in and before any materialization.
        Write-Bold "Verifying source signature"
        if (Test-ReleaseTag $ApothemRef) {
            $null = Test-MaintainerTag $ClTree $ApothemRef ($ApothemAllowUnverified -eq '1')
        } else {
            if ($ApothemAllowUnverified -eq '1') {
                Write-Warn "Ref $ApothemRef is not a signed release tag - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
            } else {
                Write-Fail "Ref $ApothemRef is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
            }
        }
        if (-not $ClStage) {
            $Source = $ApothemHome
            Write-Ok "Source ready at $Source (ref: $ApothemRef)"
        } elseif ($DryRun) {
            $Source = $ClTree
            Write-Ok "Source ready at $Source (ref: $ApothemRef; dry run, so $ApothemHome is not changed)"
        } else {
            Invoke-SwapIn $ClTree ''
            $Source = $ApothemHome
            Write-Ok "Source ready at $Source (ref: $ApothemRef)"
        }
    } finally {
        if ($ClStage -and -not $DryRun -and (Test-Path -LiteralPath $ClStage)) { Remove-Item -LiteralPath $ClStage -Recurse -Force }
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
    if ($script:DryRunScratch -and (Test-Path -LiteralPath $script:DryRunScratch)) {
        Remove-Item -LiteralPath $script:DryRunScratch -Recurse -Force
    }
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
