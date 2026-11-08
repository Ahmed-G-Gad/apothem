# SPDX-License-Identifier: MIT

# Purpose: Place the bundled Apothem source tree (self-contained - no
#          package installation) and materialize harness config by running
#          `python -m apothem` directly from that tree (PowerShell parity
#          to install.sh).
# Contract: Idempotent on rerun (a re-run fetches, checks and checks out the
#           clone, then re-materializes). Throws on unrecoverable error.
#
# Trust model (tag-pinned, verified-by-default; PowerShell parity to
# install.sh): with no APOTHEM_REF set, the installer resolves the latest
# vMAJOR.MINOR.PATCH release tag and installs THAT release - the moving `main`
# branch is no longer the default. How the release is checked depends on
# APOTHEM_VERIFY, whose default `auto` picks one of two paths:
#   - cosign on PATH ("release"): two checks, both required. The release tag
#     must carry the maintainer key's signature (below) and name itself as
#     that release, and cosign must show that the release workflow signed the
#     release's SHA256SUMS in a run on the commit that tag points at: cosign
#     compares that commit with the GitHub workflow SHA in the certificate it
#     verified. The Windows archive's SHA-256 must then match SHA256SUMS.
#     Needs git, gpg and cosign.
#   - no cosign ("signature"): clone the repository and check the tag the
#     same way (signature and name) before anything is checked out. Needs git
#     and gpg. An existing clone at APOTHEM_HOME takes this path unless
#     APOTHEM_VERIFY names another mode.
#   Either way the tag signature must be valid AND made by the maintainer key
#   published in SECURITY.md (fingerprint
#   5C8998F9F241720445D3F28B70396FED9C634163); a key the local keyring merely
#   trusts is not enough. A signed git tag names its commit by SHA-1; the
#   release path adds the SHA-256 digest that cosign checks.
#   A failed check ABORTS the install before any config is written.
#   An existing clone is checked before it is fetched: no tracked file may
#   be marked assume-unchanged or skip-worktree, its work tree must be
#   APOTHEM_HOME itself, and its own git config may not set a gpg program,
#   fsmonitor, hooks path or include. Its hooks do not run during the
#   update. A git clone of something other than Apothem counts as a folder
#   that holds no Apothem install.
#   APOTHEM_ALLOW_UNVERIFIED=1 is the one opt-out, and it does two things:
#     - On the clone path it turns a tag that is unsigned, whose signature
#       does not verify, or that another key signed into a loud warning, and
#       lets a ref that is not a release tag (APOTHEM_REF=main, a SHA) be
#       checked out. A tag the maintainer signed for another release and
#       re-pointed at this one still aborts, and the release path never
#       downgrades. Because APOTHEM_ALLOW_UNVERIFIED=1 lets an unsigned
#       tag, or one signed by another key, through, the re-pointed-tag
#       check protects only tags that carry the maintainer key's
#       signature.
#     - It allows APOTHEM_VERIFY=checksum (below), which checks no signature.
#   The APOTHEM_SOURCE local-checkout path fetches nothing, so it skips tag
#   resolution and verification - it prints the source it is running and
#   proceeds.
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
#   -DryRun          Preview only; write nothing (engine `--dry-run`). The
#                    source is fetched and checked in a temporary folder,
#                    APOTHEM_HOME is left as it is, and the same refusals
#                    apply as in a real run. Skips post-install verification.
#   -Yes             Non-interactive; skip per-target prompts (engine `--yes`).
#                    Also lets the installer replace what is at APOTHEM_HOME
#                    when that needs consent: an Apothem git clone replaced
#                    by the release archive, whose tree is then kept at
#                    <APOTHEM_HOME>.before-apothem-<time> (refused while the
#                    clone holds local work: changes, stashes, unpushed
#                    commits, or untracked files in its source tree), an
#                    archive install switched to a clone (the engine's
#                    backups\, state\ and other data the source tree does
#                    not hold are kept either way), or a folder that holds
#                    no Apothem install (a git clone of something else
#                    included), which is moved, unchanged, to
#                    <APOTHEM_HOME>.before-apothem-<time>. A folder that
#                    holds only the engine's data folders (backups\, state\,
#                    plans\ and the like) is installed into without -Yes,
#                    its data kept.
#
# Environment overrides (set as env vars before running):
#   APOTHEM_HOME             Install destination for the source tree
#                            (default: $HOME/.apothem). A symbolic link or
#                            junction there is refused, except when it is an
#                            existing clone updated in place.
#   APOTHEM_REPO             Git remote to clone
#                            (default: https://github.com/ahmed-g-gad/apothem).
#                            A value that starts with - is refused.
#   APOTHEM_REF              Git ref to check out. Unset = resolve the latest
#                            release tag; set to a tag to pin, or "main" for
#                            the moving branch (needs APOTHEM_ALLOW_UNVERIFIED=1).
#   APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a failed tag-signature check on
#                            the clone path to a warning, allow a ref that is
#                            not a release tag, and allow checksum mode. A
#                            re-pointed tag still aborts, but since an
#                            unsigned tag, or one signed by another key, gets
#                            through, that check protects only tags that
#                            carry the maintainer key's signature.
#   APOTHEM_VERIFY           "auto" (default) uses "release" when cosign is on
#                            PATH and "signature" otherwise (and for an
#                            existing clone). "release" installs the Windows
#                            archive once the tag carries the maintainer
#                            key's signature, cosign shows the release
#                            workflow signed SHA256SUMS in a run on the tag's
#                            commit, and the archive's SHA-256 matches it
#                            (needs cosign and gpg). "signature" clones and
#                            checks the tag's GPG signature against the pinned
#                            maintainer key (needs gpg). "checksum" installs
#                            the archive after the SHA-256 check alone, and
#                            only with APOTHEM_ALLOW_UNVERIFIED=1. Checksum
#                            mode does not verify the release. SHA256SUMS
#                            comes from the same release as the archive, so a
#                            match only shows the download isn't damaged;
#                            anyone who can change the release's files can
#                            change both.
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
# A trailing separator would put the folders the installer makes beside
# APOTHEM_HOME inside it instead; a drive root keeps its separator.
if ($ApothemHome.Length -gt 1 -and $ApothemHome -notmatch '^[A-Za-z]:[\\/]$') {
    $ApothemHome = $ApothemHome.TrimEnd('\', '/')
}
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

# A git variable set in the calling shell would point every git command
# below at another repository, work tree, index or object store, add
# settings or another git program, or swap objects through replace refs,
# so they are cleared first; GIT_CONFIG_GLOBAL and GIT_CONFIG_SYSTEM stay
# (mirrors
# install.sh). An APOTHEM_REPO that starts with - would reach git as an
# option.
foreach ($GitVar in @('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR', 'GIT_NAMESPACE', 'GIT_REPLACE_REF_BASE', 'GIT_CEILING_DIRECTORIES', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_EXEC_PATH', 'GIT_TEMPLATE_DIR')) {
    if (Test-Path -LiteralPath "Env:$GitVar") { Remove-Item -LiteralPath "Env:$GitVar" }
}
$env:GIT_NO_REPLACE_OBJECTS = '1'
if ($ApothemRepo.StartsWith('-')) {
    Write-Fail "APOTHEM_REPO must be a repository URL or path, not an option: $ApothemRepo"
}

# The git calls that run in an existing clone (fetch, verify-tag, cat-file,
# checkout) take these arguments, which point core.hooksPath at an empty
# folder made for the run, so none of the clone's hooks runs.
$GitSafe = @()

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
        # The anchor on the object name and tab keeps a tag whose own name
        # holds refs/tags/v... from passing for a release tag. A tag whose
        # numbers do not fit [version] is skipped, not fatal.
        if ($line -cmatch '^[0-9a-f]+\trefs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)(\^\{\})?$') {
            $TagVersion = $null
            if ([version]::TryParse($matches[1].Substring(1), [ref]$TagVersion)) { $tags += $matches[1] }
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
        $Lines = & git @GitSafe -C $Dir verify-tag --raw $Ref 2>&1
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
# of surfacing as a failed signature check. That program is
# gpg.openpgp.program, else gpg.program, when one is set, else gpg on PATH, else the gpg Git for Windows ships under its
# install root (usr\bin\gpg.exe), which git runs although it is not on PATH.
# Apothem release tags carry OpenPGP signatures whatever gpg.format says:
# that setting picks how git signs, not how it verifies (mirrors install.sh's
# require_gpg).
function Assert-GpgAvailable {
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $Prog = & git config --get gpg.openpgp.program 2>$null
        if (-not $Prog) { $Prog = & git config --get gpg.program 2>$null }
        $ExecPath = & git --exec-path 2>$null
    } finally {
        $ErrorActionPreference = $prior
    }
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
# repository at DIR, before anything is checked out, and prints the result.
# The tag passes when the maintainer key signed it and the signed tag object
# names itself REF and points at a commit: a signed tag for another release,
# re-pointed at refs/tags/REF, would otherwise roll an install back to that
# release. A pass returns the commit the tag points at. Any other outcome
# aborts with the reason, unless ALLOW is $true, which downgrades a missing or
# unverifiable signature to a warning and returns $null; a re-pointed tag
# aborts either way.
function Test-MaintainerTag {
    param([string]$Dir, [string]$Ref, [bool]$Allow)
    if ((Test-TagSignature $Dir "refs/tags/$Ref") -and (Test-TagSignedByMaintainer)) {
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $TagLines = @(& git @GitSafe -C $Dir cat-file tag "refs/tags/$Ref" 2>$null)
        } finally {
            $ErrorActionPreference = $prior
        }
        # The tag object's header runs to its first empty line. The last
        # `type` and `tag` lines in it must read exactly `type commit` and
        # `tag REF`, as install.sh's awk check requires.
        $TagType = ''
        $TagName = ''
        foreach ($TagLine in $TagLines) {
            $TagText = [string]$TagLine
            if ($TagText -eq '') { break }
            $TagField = @($TagText.Trim() -split '\s+')[0]
            if ($TagField -ceq 'type') { $TagType = $TagText }
            elseif ($TagField -ceq 'tag') { $TagName = $TagText }
        }
        if (-not ($TagType -ceq 'type commit' -and $TagName -ceq "tag $Ref")) {
            Write-Fail "Tag $Ref carries the maintainer key's signature, but the signed tag object is not the $Ref release tag (it names another tag, or no commit), so it was re-pointed (possible tampering). Aborting before anything is checked out or materialized."
        }
        $Commit = & git @GitSafe -C $Dir rev-parse --verify --quiet "refs/tags/$Ref^{commit}"
        if ($LASTEXITCODE -ne 0 -or -not $Commit) { Write-Fail "Could not read the commit the $Ref tag points at" }
        Write-Ok "Tag $Ref carries a valid signature from the maintainer key $MaintainerFingerprint"
        return ([string]$Commit).Trim()
    }
    if ($Allow) {
        Write-Warn "Tag $Ref is unsigned, its signature did not verify, or the maintainer key did not make it - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        return $null
    }
    if (Test-TagSignedByOtherKey) {
        Write-Fail "Tag $Ref carries a valid signature, but not from the maintainer key $MaintainerFingerprint that SECURITY.md publishes (possible tampering). Aborting before anything is checked out or materialized."
    }
    if (Test-VerifyTagMissingKey) {
        Write-Fail "Tag $Ref is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run & `"$env:ProgramFiles\Git\bin\bash.exe`" -c 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import && gpg --fingerprint 70396FED9C634163' (the gpg that ships with Git for Windows, which git verify-tag uses), check that the fingerprint matches the one published in SECURITY.md, then re-run this installer."
    }
    Write-Fail "Tag $Ref is unsigned or its signature did not verify (possible tampering). Aborting before anything is checked out or materialized."
}

# Assert-FetchedRef DIR - the gate for APOTHEM_REF in the repository at DIR,
# run before it is checked out (mirrors install.sh's check_fetched_ref). A
# release tag goes through Test-MaintainerTag; any other ref (main, a SHA, a
# pre-release tag) cannot be verified, so it is refused unless
# APOTHEM_ALLOW_UNVERIFIED=1.
function Assert-FetchedRef {
    param([string]$Dir)
    if (Test-ReleaseTag $ApothemRef) {
        $null = Test-MaintainerTag $Dir $ApothemRef ($ApothemAllowUnverified -eq '1')
    } elseif ($ApothemAllowUnverified -eq '1') {
        Write-Warn "Ref $ApothemRef is not a signed release tag - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
    } else {
        Write-Fail "Ref $ApothemRef is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
    }
}

# Invoke-CheckoutRef DIR [-InPlace] - check out APOTHEM_REF in the clone at
# DIR, after Assert-FetchedRef has passed (mirrors install.sh's
# checkout_ref). A release tag is checked out detached, as the commit
# refs/tags/<tag>^{commit} names, so neither a branch that shares the tag's
# name nor one named refs/tags/<tag> can stand in for it, and HEAD must then
# be the tag's commit. Any other ref follows origin's branch of that name
# when there is one (a local branch may be stale), and otherwise resolves
# directly, after --end-of-options so a ref cannot pass for an option. No
# --force: a clone with local changes that the checkout would overwrite
# stops instead of losing them. -InPlace marks the clone at APOTHEM_HOME: a
# change to a tracked file stops the update before the checkout, and the
# tracked files must match the ref after it. git reports a refused checkout
# on stderr, which PowerShell before 7.2 turns into a terminating error
# under 'Stop', so the preference is localized as in Test-TagSignature.
function Invoke-CheckoutRef {
    param([string]$Dir, [switch]$InPlace)
    $prior = $ErrorActionPreference
    if ($InPlace) {
        $ErrorActionPreference = 'Continue'
        try {
            & git @GitSafe -C $Dir diff --quiet HEAD
            $DiffCode = $LASTEXITCODE
            & git @GitSafe -C $Dir diff --cached --quiet
            $CachedCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($DiffCode -ne 0 -or $CachedCode -ne 0) {
            Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
        }
    }
    $ErrorActionPreference = 'Continue'
    try {
        if (Test-ReleaseTag $ApothemRef) {
            & git @GitSafe -C $Dir checkout --quiet --detach "refs/tags/$ApothemRef^{commit}"
            $CoCode = $LASTEXITCODE
        } else {
            & git @GitSafe -C $Dir show-ref --verify --quiet "refs/remotes/origin/$ApothemRef"
            if ($LASTEXITCODE -eq 0) {
                & git @GitSafe -C $Dir checkout --quiet --detach "refs/remotes/origin/$ApothemRef"
            } else {
                & git @GitSafe -C $Dir checkout --quiet --end-of-options $ApothemRef
            }
            $CoCode = $LASTEXITCODE
        }
    } finally {
        $ErrorActionPreference = $prior
    }
    if (Test-ReleaseTag $ApothemRef) {
        if ($CoCode -ne 0) { Write-Fail "Could not check out the $ApothemRef tag in $Dir. If it has local changes, commit or stash them, then re-run." }
        $CoHead = & git @GitSafe -C $Dir rev-parse --verify --quiet HEAD
        $CoTag = & git @GitSafe -C $Dir rev-parse --verify --quiet "refs/tags/$ApothemRef^{commit}"
        if (-not $CoTag -or "$CoHead" -ne "$CoTag") {
            Write-Fail "The checkout in $Dir is at '$CoHead', not at the $ApothemRef tag's commit '$CoTag'. Aborting before anything is materialized."
        }
    } elseif ($CoCode -ne 0) {
        Write-Fail "Could not check out $ApothemRef in $Dir. If it has local changes, commit or stash them, then re-run."
    }
    if ($InPlace) {
        $ErrorActionPreference = 'Continue'
        try {
            $CoDirty = @(& git @GitSafe -C $Dir status --porcelain --untracked-files=no 2>$null)
            $CoStatusCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($CoStatusCode -ne 0 -or $CoDirty.Count -gt 0) {
            Write-Fail "The checkout in $Dir does not match $ApothemRef after the update. Aborting before re-materialization."
        }
    }
}

# Test-Entry PATH - $true when something is at PATH, a symbolic link whose
# target is gone included.
function Test-Entry {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) { return $true }
    return [bool](Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
}

# Test-HomeIsLink - $true when APOTHEM_HOME is a symbolic link or a junction,
# by the item's LinkType: a OneDrive placeholder carries the ReparsePoint
# attribute too, so that bit alone does not make a link. The installer replaces APOTHEM_HOME by
# renaming folders beside it, which would replace the link itself, so it
# refuses a link instead (install.sh's home_is_link refuses a symbolic link).
function Test-HomeIsLink {
    $HomeItem = Get-Item -LiteralPath $ApothemHome -Force -ErrorAction SilentlyContinue
    if (-not $HomeItem) { return $false }
    return ($HomeItem.LinkType -in @('SymbolicLink', 'Junction'))
}

# Move-Entry FROM TO - rename the file or folder FROM to TO, which must not
# exist yet. Both sit on one drive, so this is a rename, never a copy. The
# .NET calls fail when TO exists, where Move-Item would move a folder into
# it, and they take full paths, so each one is resolved against the current
# location first.
function Move-Entry {
    param([string]$From, [string]$To)
    $FromFull = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($From)
    $ToFull = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($To)
    if ([System.IO.Directory]::Exists($FromFull)) {
        [System.IO.Directory]::Move($FromFull, $ToFull)
    } else {
        [System.IO.File]::Move($FromFull, $ToFull)
    }
}

# Get-SourceEntry DIR - the top-level names that belong to the Apothem source
# tree at DIR rather than to the engine or the user: .git, the entries a git
# clone tracks, and those an archive install recorded in its
# .apothem-source-entries manifest (mirrors install.sh's source_entries).
# A .git file (a worktree, or a clone with a separate git dir) makes DIR a
# clone as a .git folder does. The engine's data folders ($EngineDataNames)
# are never source, whatever a manifest or the clone says.
$SourceManifest = '.apothem-source-entries'
$EngineDataNames = @('backups', 'state', 'plans', 'memory', 'contexts', 'learning', 'providers')
function Get-SourceEntry {
    param([string]$Dir)
    $Names = @('.git')
    if (Test-Path -LiteralPath (Join-Path $Dir '.git')) {
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $Tracked = @(& git -C $Dir ls-tree --name-only HEAD 2>$null)
            if ($LASTEXITCODE -eq 0) { $Names += @($Tracked | ForEach-Object { [string]$_ }) }
        } finally {
            $ErrorActionPreference = $prior
        }
    }
    $Manifest = Join-Path $Dir $SourceManifest
    if (Test-Path -LiteralPath $Manifest -PathType Leaf) {
        $Names += @(Get-Content -LiteralPath $Manifest | ForEach-Object { ([string]$_).TrimEnd("`r") })
    }
    return , @($Names | Where-Object { $_ -and ($EngineDataNames -cnotcontains $_) })
}

# Write-SourceManifest DIR - write DIR's top-level names, the manifest's own
# name among them, to its manifest, so a later swap can tell this archive
# install's source from the engine's data. One name per line with LF endings
# and no byte-order mark, as install.sh's record_source_entries writes it.
function Write-SourceManifest {
    param([string]$Dir)
    $Names = @(@(Get-ChildItem -LiteralPath $Dir -Force | ForEach-Object { $_.Name }) + $SourceManifest | Sort-Object -Unique -CaseSensitive)
    try {
        $ManifestPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $Dir $SourceManifest))
        [System.IO.File]::WriteAllText($ManifestPath, (($Names -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding $false))
    } catch {
        Write-Fail "Could not record the source entries in $Dir"
    }
}

# Undo-SwapIn NEW OLD TRIED - put back what an unfinished Invoke-SwapIn moved,
# working from what is where rather than from how far the swap got, so an
# interrupt between two steps is undone too. TRIED lists the carried names
# the swap set out to move, each one recorded before its move. Returns $true
# when everything is back where it was.
function Undo-SwapIn {
    param([string]$New, [string]$Old, [string[]]$Tried)
    $OldHome = Join-Path $Old 'home'
    $Stuck = $false
    try {
        if (Test-Entry $OldHome) {
            # The earlier tree is aside and NEW may be in place: undo that.
            if ((Test-Entry $ApothemHome) -and -not (Test-Entry $New)) { Move-Entry $ApothemHome $New }
            if (-not (Test-Entry $ApothemHome)) { Move-Entry $OldHome $ApothemHome }
        }
        # Every carried name is absent from NEW as built, so a tried one
        # found there was moved by the swap. One found in both places cannot
        # go back without overwriting a copy, so the rollback counts as
        # failed and the staging folder, which holds the carried copy, is
        # kept.
        foreach ($Name in $Tried) {
            $Carried = Join-Path $New $Name
            $Origin = Join-Path $ApothemHome $Name
            if (Test-Entry $Carried) {
                if (Test-Entry $Origin) { $Stuck = $true } else { Move-Entry $Carried $Origin }
            }
        }
    } catch {
        return $false
    }
    if ($Stuck -or (Test-Entry $OldHome)) { return $false }
    # The emptied room beside APOTHEM_HOME goes; Delete refuses a folder
    # that still holds anything.
    try { [System.IO.Directory]::Delete($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Old), $false) } catch { $null = $_ }
    return $true
}

# Get-AsidePath - the sibling <APOTHEM_HOME>.before-apothem-<time> folder
# that an earlier tree is moved to, with -<pid> added when that name is
# taken. When both are taken the run stops before anything moves.
function Get-AsidePath {
    $AsPath = "$ApothemHome.before-apothem-" + (Get-Date -Format 'yyyyMMddHHmmss')
    if (-not (Test-Entry $AsPath)) { return $AsPath }
    if (-not (Test-Entry "$AsPath-$PID")) { return "$AsPath-$PID" }
    Write-Fail "Could not move the existing $ApothemHome aside; nothing was changed"
}

# Invoke-SwapIn NEW MODE - put the checked tree at NEW in place of
# APOTHEM_HOME (mirrors install.sh's swap_in). NEW sits beside APOTHEM_HOME,
# so every move is a rename on one drive.
#   MODE keep:  APOTHEM_HOME holds an earlier Apothem install. Every
#               top-level entry that is not part of its source tree or of NEW
#               (the engine's backups\, state\ and data folders among them)
#               moves into NEW first; then the earlier tree moves aside, NEW
#               moves in, and the earlier source is removed.
#   MODE clone: as keep, for an Apothem git clone that -Yes allowed
#               replacing with the archive: what is left of the clone's
#               tree once its data has moved is not removed but moved to
#               a sibling <APOTHEM_HOME>.before-apothem-<time> folder.
#   MODE aside: APOTHEM_HOME holds something else, and -Yes allowed
#               replacing it. It moves, untouched, to a sibling
#               <APOTHEM_HOME>.before-apothem-<time> folder, and NEW moves in.
# A failure or an interrupt (Ctrl+C) at any step puts everything back where
# it was and says so, or, when that also fails, names where the earlier tree
# was left and keeps the staging folder ($script:SwapKeepStaging), which may
# hold the only copy of the moved data.
$script:SwapKeepStaging = $false
function Invoke-SwapIn {
    param([string]$New, [string]$Mode)
    if (-not (Test-Entry $ApothemHome)) {
        try { Move-Entry $New $ApothemHome }
        catch { Write-Fail "Could not move the new source to $ApothemHome" }
        return
    }
    if ($Mode -eq 'aside') {
        $Aside = Get-AsidePath
        # Both moves run inside try, so an interrupt after either one is
        # undone too, from what is where.
        $SwDone = $false
        $SwFailed = $false
        $SwUntouched = $false
        $SwReason = "Interrupted while replacing $ApothemHome"
        try {
            try { Move-Entry $ApothemHome $Aside }
            catch { $SwFailed = $true; $SwUntouched = $true; $SwReason = "Could not move the existing $ApothemHome aside"; throw }
            try { Move-Entry $New $ApothemHome }
            catch { $SwFailed = $true; $SwReason = "Could not move the new source to $ApothemHome"; throw }
            $SwDone = $true
        } finally {
            if (-not $SwDone) {
                $SwBack = $false
                try {
                    if (Test-Entry $Aside) {
                        if ((Test-Entry $ApothemHome) -and -not (Test-Entry $New)) { Move-Entry $ApothemHome $New }
                        if (-not (Test-Entry $ApothemHome)) { Move-Entry $Aside $ApothemHome }
                    }
                    $SwBack = (Test-Entry $ApothemHome) -and -not (Test-Entry $Aside)
                } catch { $SwBack = $false }
                if ($SwBack -and $SwUntouched) {
                    $SwMessage = "$SwReason; nothing was changed"
                } elseif ($SwBack) {
                    $SwMessage = "$SwReason; the earlier folder is back in place and unchanged"
                } else {
                    $SwMessage = "$SwReason, and moving the earlier folder back also failed: it is at $Aside"
                }
                # See the keep branch below for why an interrupt prints first.
                if (-not $SwFailed) { Write-Host "  x $SwMessage" }
                Write-Fail $SwMessage
            }
        }
        Write-Warn "The earlier contents of $ApothemHome were moved, unchanged, to $Aside"
        return
    }
    # keep and clone: name the folder the clone's tree goes to and list the
    # entries to carry over before anything moves.
    $SwTreeAside = $null
    if ($Mode -eq 'clone') { $SwTreeAside = Get-AsidePath }
    $SourceNames = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($Name in (Get-SourceEntry $ApothemHome)) { $null = $SourceNames.Add($Name) }
    foreach ($Entry in @(Get-ChildItem -LiteralPath $New -Force)) {
        if ($EngineDataNames -cnotcontains $Entry.Name) { $null = $SourceNames.Add($Entry.Name) }
    }
    $SwKeep = @(@(Get-ChildItem -LiteralPath $ApothemHome -Force) | Where-Object { -not $SourceNames.Contains($_.Name) } | ForEach-Object { $_.Name })
    $SwParent = Split-Path -Parent $ApothemHome
    if (-not $SwParent) { $SwParent = (Get-Location).Path }
    $SwOld = Join-Path $SwParent (".apothem-old." + [System.Guid]::NewGuid().ToString('N'))
    try { New-Item -ItemType Directory -Path $SwOld | Out-Null }
    catch { Write-Fail "Could not make room beside $ApothemHome; nothing was changed" }
    $SwOldHome = Join-Path $SwOld 'home'
    $SwDone = $false
    $SwFailed = $false
    $SwReason = "Interrupted while replacing $ApothemHome"
    $SwTried = New-Object 'System.Collections.Generic.List[string]'
    try {
        foreach ($Name in $SwKeep) {
            # Recorded before the move, so an interrupt right after it is
            # undone; a move that failed moved nothing (it is a rename), so
            # its name comes off the list again.
            $SwTried.Add($Name)
            try { Move-Entry (Join-Path $ApothemHome $Name) (Join-Path $New $Name) }
            catch { $SwTried.RemoveAt($SwTried.Count - 1); $SwFailed = $true; $SwReason = "Could not move $Name into the new install"; throw }
        }
        try { Move-Entry $ApothemHome $SwOldHome }
        catch { $SwFailed = $true; $SwReason = "Could not move the existing $ApothemHome aside"; throw }
        try { Move-Entry $New $ApothemHome }
        catch { $SwFailed = $true; $SwReason = "Could not move the new source to $ApothemHome"; throw }
        $SwDone = $true
    } finally {
        if (-not $SwDone) {
            if (Undo-SwapIn $New $SwOld ($SwTried.ToArray())) {
                $SwMessage = "$SwReason; the earlier install at $ApothemHome is back in place and unchanged"
            } else {
                # Keep the staging folder: it may hold the only copy of the data.
                $script:SwapKeepStaging = $true
                $SwWhere = if (Test-Entry $SwOldHome) { $SwOldHome } else { $ApothemHome }
                $SwMessage = "$SwReason, and putting the earlier install back also failed: it is at $SwWhere (with any moved data under $New). Move it back to $ApothemHome by hand."
            }
            # An interrupt stops the run as this block ends, and an error
            # record written then may not be shown, so the outcome goes to
            # the console first.
            if (-not $SwFailed) { Write-Host "  x $SwMessage" }
            Write-Fail $SwMessage
        }
    }
    if ($SwTreeAside) {
        $SwTreeAt = $SwTreeAside
        try { Move-Entry $SwOldHome $SwTreeAside } catch { $SwTreeAt = $SwOldHome }
        if ($SwTreeAt -eq $SwTreeAside) {
            try { [System.IO.Directory]::Delete($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SwOld), $false) } catch { $null = $_ }
        }
        Write-Warn "The earlier clone's tree is kept at $SwTreeAt; delete it once you no longer need it."
        return
    }
    try { Remove-Item -LiteralPath $SwOld -Recurse -Force }
    catch { Write-Warn "Could not remove the earlier source at $SwOld; delete it by hand" }
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
#   3. The release archive, or a git clone of APOTHEM_REPO, pinned to the
#      resolved ref (the latest release tag by default, or an explicit
#      APOTHEM_REF) and checked before it is placed at APOTHEM_HOME. An
#      existing clone is fetched, checked, and only then checked out.
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
# A .git file (a worktree, or a clone with a separate git dir) counts too;
# a clone of something other than Apothem does not.
$HomeIsClone = (Test-Path -LiteralPath (Join-Path $ApothemHome '.git')) -and (Test-ApothemSource $ApothemHome)
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

# Checksum mode verifies nothing about who published the release, so it runs
# only with APOTHEM_ALLOW_UNVERIFIED=1, and says so before downloading.
$ChecksumCaveat = "Checksum mode does not verify the release. SHA256SUMS comes from the same release as the archive, so a match only shows the download isn't damaged; anyone who can change the release's files can change both."
if (-not $Source -and $VerifyMode -eq 'checksum') {
    if ($ApothemAllowUnverified -ne '1') {
        Write-Fail "$ChecksumCaveat Set APOTHEM_ALLOW_UNVERIFIED=1 as well to install this way anyway, or install gpg (and cosign) and run without APOTHEM_VERIFY=checksum."
    }
    Write-Warn "$ChecksumCaveat Proceeding because APOTHEM_ALLOW_UNVERIFIED=1."
}

# Test-CloneHasLocalWork DIR - $true when the git clone at DIR holds work
# that replacing it with an archive would lose: a change to a tracked file, a
# stash, a commit on a branch that no remote has, or an untracked path inside
# a top-level name the clone tracks (its source tree). A git command that
# fails counts as local work, so a clone git cannot read is not replaced.
# Untracked top-level entries (the engine's backups\ and state\) are carried
# over by the swap, so they do not count (mirrors install.sh).
function Test-CloneHasLocalWork {
    param([string]$Dir)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $LwChanged = @(& git -C $Dir status --porcelain --untracked-files=no 2>$null)
        if ($LASTEXITCODE -ne 0 -or $LwChanged.Count -gt 0) { return $true }
        $LwStashes = @(& git -C $Dir stash list 2>$null)
        if ($LASTEXITCODE -ne 0 -or $LwStashes.Count -gt 0) { return $true }
        $LwUnpushed = @(& git -C $Dir log --branches --not --remotes --oneline 2>$null)
        if ($LASTEXITCODE -ne 0 -or $LwUnpushed.Count -gt 0) { return $true }
        $LwTracked = @(& git -C $Dir -c core.quotePath=false ls-tree --name-only HEAD 2>$null | ForEach-Object { [string]$_ })
        if ($LASTEXITCODE -ne 0) { return $true }
        $LwStatus = @(& git -C $Dir -c core.quotePath=false status --porcelain 2>$null)
        if ($LASTEXITCODE -ne 0) { return $true }
    } finally {
        $ErrorActionPreference = $prior
    }
    foreach ($LwLine in $LwStatus) {
        $LwText = [string]$LwLine
        if (-not $LwText.StartsWith('?? ', [System.StringComparison]::Ordinal)) { continue }
        $LwTop = @($LwText.Substring(3).TrimStart('"') -split '/', 2)[0]
        if ($LwTracked -ccontains $LwTop) { return $true }
    }
    return $false
}

# Assert-CleanClone DIR - refuse, before anything is fetched, an existing
# clone at DIR whose check the update could not trust (mirrors install.sh's
# require_clean_clone). Its own git config may not set a program or file the
# update's git calls would run or read (gpg.program, gpg.openpgp.program,
# core.fsmonitor, core.hooksPath, include. and includeIf. entries); this is
# read first, as the other checks run git in the clone. Its work tree must
# be DIR itself, not one core.worktree or a .git file names: git must place
# DIR inside the work tree, at its top. And no tracked file may be marked
# assume-unchanged or skip-worktree (git ls-files -v prints a lower-case
# letter or S for one), since git then hides a change to it.
function Assert-CleanClone {
    param([string]$Dir)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $CcConfig = @(& git -C $Dir config --local --name-only --get-regexp . 2>$null | ForEach-Object { [string]$_ })
    } finally {
        $ErrorActionPreference = $prior
    }
    foreach ($CcKey in $CcConfig) {
        $CcLower = $CcKey.ToLowerInvariant()
        if ((@('gpg.program', 'gpg.openpgp.program', 'core.fsmonitor', 'core.hookspath') -ccontains $CcLower) -or $CcLower.StartsWith('include.', [System.StringComparison]::Ordinal) -or $CcLower.StartsWith('includeif.', [System.StringComparison]::Ordinal)) {
            Write-Fail "$Dir's own git config sets $CcKey, which the update would trust. Remove it from $Dir/.git/config, then re-run."
        }
    }
    $ErrorActionPreference = 'Continue'
    try {
        $CcInside = [string](& git -C $Dir rev-parse --is-inside-work-tree 2>$null)
        $CcInsideCode = $LASTEXITCODE
        $CcPrefix = [string](& git -C $Dir rev-parse --show-prefix 2>$null)
        $CcPrefixCode = $LASTEXITCODE
        $CcFlags = @(& git -C $Dir ls-files -v 2>$null | ForEach-Object { [string]$_ })
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($CcInsideCode -ne 0 -or $CcInside.Trim() -cne 'true' -or $CcPrefixCode -ne 0 -or $CcPrefix.Trim() -ne '') {
        Write-Fail "$Dir is not the work tree of its git clone (core.worktree is set, or its .git points elsewhere). Remove that setting, then re-run."
    }
    foreach ($CcLine in $CcFlags) {
        if ($CcLine.Length -gt 0 -and ([char]::IsLower($CcLine[0]) -or $CcLine[0] -ceq 'S')) {
            Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
        }
    }
}

# Get-HomeMode WHAT - decide what a swap into APOTHEM_HOME may do with what
# is there now, refusing what -Yes has not allowed, and return the
# Invoke-SwapIn mode (keep or aside). WHAT names the new source ("the vX
# archive", "a clone of vX") for the messages. A folder that is empty, or
# holds only the engine's data folders ($EngineDataNames), is updated like
# no folder at all, its data carried over. A dry run applies the same
# refusals, so it fails where the real run would (mirrors install.sh's
# home_mode).
function Get-HomeMode {
    param([string]$What)
    if (Test-HomeIsLink) {
        Write-Fail "Destination $ApothemHome is a symbolic link. Point APOTHEM_HOME at the folder it links to, then re-run."
    }
    $HomeNames = @()
    if (Test-Entry $ApothemHome) { $HomeNames = @(Get-ChildItem -LiteralPath $ApothemHome -Force | ForEach-Object { $_.Name }) }
    if (@($HomeNames | Where-Object { $EngineDataNames -cnotcontains $_ }).Count -eq 0) {
        return 'keep'
    }
    if ((Test-Path -LiteralPath (Join-Path $ApothemHome '.git')) -and (Test-ApothemSource $ApothemHome)) {
        if (-not $Yes) {
            Write-Fail "Destination $ApothemHome is a git clone; refusing to replace it with $What, which would remove its history. Set APOTHEM_VERIFY=signature to update the clone, move it aside, or re-run with -Yes."
        }
        if (Test-CloneHasLocalWork $ApothemHome) {
            Write-Fail "$ApothemHome is a git clone with local work that replacing it would lose (changes, stashes, unpushed commits, or untracked files in its source tree). Commit and push that work, or move it elsewhere, then re-run."
        }
        # The folder the clone's tree goes to must be free now, in a dry run
        # too; Get-AsidePath stops the run when it is not.
        $null = Get-AsidePath
        $HmLeaf = Split-Path -Leaf $ApothemHome
        if ($DryRun) {
            Write-Warn "Would replace the git clone at $ApothemHome with $What; the files the clone does not track (the engine's backups\ and state\ among them) would move into the new install, and the clone's own tree would be moved to a sibling folder named $HmLeaf.before-apothem-<time> (-Yes)"
        } else {
            Write-Warn "Replacing the git clone at $ApothemHome with $What; the files the clone does not track (the engine's backups\ and state\ among them) move into the new install, and the clone's own tree will be moved to a sibling folder named $HmLeaf.before-apothem-<time> (-Yes)"
        }
        return 'clone'
    }
    if (Test-ApothemSource $ApothemHome) {
        if ($What.StartsWith('a clone of', [System.StringComparison]::Ordinal)) {
            if (-not $Yes) {
                Write-Fail "Destination $ApothemHome is a release-archive install, not a git clone; refusing to replace it. Install cosign and gpg and re-run to update it in place, or re-run with -Yes to switch it to a clone (its backups\ and state\ are kept)."
            }
            if ($DryRun) {
                Write-Warn "Would switch the release-archive install at $ApothemHome to $What; the engine's backups\, state\ and other data would be kept (-Yes)"
            } else {
                Write-Warn "Switching the release-archive install at $ApothemHome to $What; the engine's backups\, state\ and other data are kept (-Yes)"
            }
        } elseif ($DryRun) {
            Write-Info "Would update the earlier install at $ApothemHome to $What"
        } else {
            Write-Info "Updating the earlier install at $ApothemHome to $What"
        }
        return 'keep'
    }
    if (-not $Yes) {
        Write-Fail "Destination $ApothemHome is not empty and holds no Apothem install; refusing to replace it. Move it aside, point APOTHEM_HOME at another directory, or re-run with -Yes to have it moved aside for you."
    }
    if ($DryRun) {
        Write-Warn "$ApothemHome holds no Apothem install; it would be moved, unchanged, to a sibling folder named $(Split-Path -Leaf $ApothemHome).before-apothem-<time> (-Yes)"
    } else {
        Write-Warn "$ApothemHome holds no Apothem install; it will be moved, unchanged, to a sibling folder named $(Split-Path -Leaf $ApothemHome).before-apothem-<time> (-Yes)"
    }
    return 'aside'
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
# points at. cosign itself checks that commit, against the GitHub workflow
# SHA its verified certificate carries, so no other code reads the bundle.
# Either check alone is not enough: anyone who can push a tag can make the
# workflow sign a release, and a signed tag says nothing about the archive.
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
    # What may happen to APOTHEM_HOME is settled before anything downloads.
    $CkMode = Get-HomeMode "the $ApothemRef archive"
    $CkName = "apothem-$ApothemRef-windows.zip"
    $CkTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-" + [System.Guid]::NewGuid().ToString('N'))
    $CkExtract = $null
    $CkOk = $false
    # Everything from here to the swap into APOTHEM_HOME runs inside try, so
    # the download and the staging folder are removed on every path, success,
    # failure or interrupt. A dry run keeps the scratch folder for the
    # engine's preview once this block has finished (a dry run stopped
    # partway, Ctrl+C included, removes it too), and a swap whose rollback
    # failed keeps the staging folder, which may hold the only copy of the
    # moved data.
    try {
        New-Item -ItemType Directory -Path $CkTmp -Force | Out-Null
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
            # so a bundle signed for another release does not verify here,
            # and --certificate-github-workflow-sha makes cosign require that
            # the certificate it verified was issued to a run on the signed
            # tag's commit.
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
                $CkCosignOut = & cosign verify-blob --bundle $CkBundle --certificate-identity $CkIdentity --certificate-oidc-issuer $CosignOidcIssuer --certificate-github-workflow-sha $CkTagCommit $CkSums 2>&1
                $CkCosignCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $prior
            }
            if ($CkCosignCode -ne 0) {
                $CkSaid = (@($CkCosignOut | Where-Object { $null -ne $_ } | ForEach-Object { $_.ToString() }) | Select-Object -Last 3) -join ' '
                Write-Fail "cosign could not confirm that the $ApothemRef release workflow ($CkIdentity) signed SHA256SUMS in a run on the signed tag's commit $CkTagCommit (possible tampering). Aborting before anything is extracted. cosign said: $CkSaid If cosign could not reach Sigstore (offline or behind a proxy), set APOTHEM_VERIFY=signature to check the release tag alone."
            }
            Write-Ok "cosign: SHA256SUMS is signed by the $ApothemRef release workflow, in a run on the tag's commit $CkTagCommit"
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
        # The release archive roots every file under apothem-<tag>\ (see
        # scripts/build_release_tarball.py). A real install extracts it into
        # a staging folder beside APOTHEM_HOME, so Invoke-SwapIn's moves are
        # renames on one drive; a dry run extracts it into the scratch folder
        # and leaves APOTHEM_HOME alone.
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
            Write-SourceManifest $CkRoot
            Invoke-SwapIn $CkRoot $CkMode
            $Source = $ApothemHome
        }
        $CkOk = $true
    } finally {
        if ($CkExtract -and -not $DryRun -and -not $script:SwapKeepStaging -and (Test-Path -LiteralPath $CkExtract)) { Remove-Item -LiteralPath $CkExtract -Recurse -Force }
        if ((-not $DryRun -or -not $CkOk) -and (Test-Path -LiteralPath $CkTmp)) { Remove-Item -LiteralPath $CkTmp -Recurse -Force }
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

    # An existing clone is fetched, its tag is checked, and only then is it
    # checked out, so a failed check leaves the clone as it was; a change to
    # a tracked file stops the update before the checkout. Otherwise
    # the clone is made in a fresh staging folder, checked and checked out
    # there, and swapped in by Invoke-SwapIn, which keeps the engine's
    # backups\ and state\ from an earlier archive install. A dry run clones
    # into a scratch folder and leaves APOTHEM_HOME alone. An existing
    # clone is checked by Assert-CleanClone first, in a dry run too.
    if ($HomeIsClone) { Assert-CleanClone $ApothemHome }
    $ClStage = $null
    if ($HomeIsClone -and -not $DryRun) {
        $ClTree = $ApothemHome
    } else {
        if ($HomeIsClone) {
            $ClMode = 'keep'
        } else {
            $ClMode = Get-HomeMode "a clone of $ApothemRef"
        }
        if ($DryRun) {
            $ClStage = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-" + [System.Guid]::NewGuid().ToString('N'))
            $script:DryRunScratch = $ClStage
        } else {
            $ClParent = Split-Path -Parent $ApothemHome
            if (-not $ClParent) { $ClParent = (Get-Location).Path }
            try { New-Item -ItemType Directory -Force -Path $ClParent | Out-Null }
            catch { Write-Fail "Could not create the parent directory of $ApothemHome" }
            $ClStage = Join-Path $ClParent (".apothem-clone." + [System.Guid]::NewGuid().ToString('N'))
        }
        try { New-Item -ItemType Directory -Path $ClStage | Out-Null }
        catch { Write-Fail "Could not create a staging directory beside $ApothemHome" }
        $ClTree = Join-Path $ClStage 'apothem'
    }
    # A dry run keeps its scratch clone for the engine's preview only once
    # this block has finished; one stopped partway (Ctrl+C included)
    # removes it.
    $ClOk = $false
    $NoHooksDir = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-nohooks-" + [System.Guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $NoHooksDir | Out-Null
        $GitSafe = @('-c', "core.hooksPath=$NoHooksDir")
        if (-not $ClStage) {
            Write-Info "Updating existing clone at $ApothemHome (ref: $ApothemRef)"
            # git reports a failed fetch on stderr; see Invoke-CheckoutRef.
            $prior = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                & git @GitSafe -C $ApothemHome fetch --quiet --tags origin
                $ClFetchCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $prior
            }
            if ($ClFetchCode -ne 0) {
                Write-Fail "Could not fetch from the origin of $ApothemHome. If a local tag differs from origin's, delete it with 'git -C $ApothemHome tag -d <tag>', then re-run."
            }
            Write-Bold "Verifying source signature"
            Assert-FetchedRef $ApothemHome
            Invoke-CheckoutRef $ApothemHome -InPlace
        } else {
            Write-Info "Cloning $ApothemRepo"
            # Full clone (no --single-branch) so both tags and branches are
            # checkout-able, with nothing checked out until the gate passes.
            & git clone --quiet --no-checkout $ApothemRepo $ClTree
            if ($LASTEXITCODE -ne 0) { Write-Fail "git clone failed for $ApothemRepo" }
            Write-Bold "Verifying source signature"
            Assert-FetchedRef $ClTree
            Invoke-CheckoutRef $ClTree
        }
        if (-not (Test-ApothemSource $ClTree)) { Write-Fail "Fetched tree is not an apothem source: $ClTree" }
        if (-not $ClStage) {
            $Source = $ApothemHome
            Write-Ok "Source ready at $Source (ref: $ApothemRef)"
        } elseif ($DryRun) {
            $Source = $ClTree
            Write-Ok "Source ready at $Source (ref: $ApothemRef; dry run, so $ApothemHome is not changed)"
        } else {
            Invoke-SwapIn $ClTree $ClMode
            $Source = $ApothemHome
            Write-Ok "Source ready at $Source (ref: $ApothemRef)"
        }
        $ClOk = $true
    } finally {
        $GitSafe = @()
        if (Test-Path -LiteralPath $NoHooksDir) { Remove-Item -LiteralPath $NoHooksDir -Recurse -Force }
        if ($ClStage -and (-not $DryRun -or -not $ClOk) -and -not $script:SwapKeepStaging -and (Test-Path -LiteralPath $ClStage)) { Remove-Item -LiteralPath $ClStage -Recurse -Force }
    }
}
$SrcPath = Join-Path $Source 'src'
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
$VendorPath = [System.IO.Path]::Combine($SrcPath, 'apothem', '_vendor')
$EnginePyPath = "$VendorPath$([System.IO.Path]::PathSeparator)$SrcPath"

# The profile setup and the engine run share one try, so a dry run's
# scratch folder is removed however the run stops, Ctrl+C included.
$PriorPyPath = $env:PYTHONPATH
try {
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

    $env:PYTHONPATH = if ($PriorPyPath) { "$EnginePyPath$([System.IO.Path]::PathSeparator)$PriorPyPath" } else { $EnginePyPath }
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
