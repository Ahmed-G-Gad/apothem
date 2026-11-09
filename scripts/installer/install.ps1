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
#   Before an existing clone is fetched (or replaced), the run stops when
#   git will not work in it because another user owns it, when its own git
#   config (its config or config.worktree file) sets a key that is not on
#   $CloneConfigAllow (the keys git clone and git init write, and a few
#   that name no program, file or address), or when its info\attributes
#   sets a filter. An update in place, and a dry run, also stop when the
#   clone holds submodules, hides changes from git (assume-unchanged or
#   skip-worktree files), or has a work tree that is not APOTHEM_HOME.
#   Every git command on the clone runs with its hooks, its fsmonitor, the
#   pager and automatic maintenance off, with no ext:: transport, and
#   without going into submodules. A git clone of something other than
#   Apothem counts as a folder that holds no Apothem install.
#   A failure or an interrupt puts the earlier install back unchanged. A
#   forced kill or a power loss can leave folders beside APOTHEM_HOME
#   (.apothem-extract.<name>.*, .apothem-clone.<name>.*,
#   .apothem-old.<name>.*, <name> being APOTHEM_HOME's own folder name):
#   the next fetched install for that APOTHEM_HOME stops, names each one
#   and what it holds, and changes nothing.
#   One install, update or uninstall runs at a time: each holds
#   <APOTHEM_HOME>.lock while it runs, and a second run stops.
#   git, gpg and cosign are the ones found on PATH; they, and the user's own
#   global and system git config, are trusted as found.
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
#   A local tree fetches nothing, so it skips tag resolution and
#   verification - the installer prints the source it is running and
#   proceeds. A local tree is used only when APOTHEM_SOURCE names it, or when
#   this script runs from its own file inside a checkout
#   (scripts\installer\install.ps1 run by path). A piped run (irm | iex) never
#   uses the current folder or its parents. No Python start imports a module
#   from the current folder.
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
# Usage (local install, from inside the checkout; or set APOTHEM_SOURCE):
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
#                    by the release archive, whose tree is then kept in a
#                    new folder <APOTHEM_HOME>.before-apothem-<time>
#                    (refused while the
#                    clone holds local work: changes, stashes, unpushed
#                    commits, or untracked files in its source tree), an
#                    archive install switched to a clone (the engine's
#                    backups\, state\ and other data the source tree does
#                    not hold are kept either way), or a folder that holds
#                    no Apothem install (a git clone of something else
#                    included), which is moved, unchanged and under its
#                    own name, into a new folder
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
# A relative APOTHEM_HOME is resolved once, here, against the current
# file-system folder (never a registry or other location the session sits
# in), so every path built from it (the engine paths in PYTHONPATH and in
# the shim among them) is a full path, never one Python would read against
# whatever folder it starts in. A value that names no file-system path
# stops the run.
$ApothemHomeValue = $ApothemHome
$HomeProvider = $null
try {
    Push-Location -LiteralPath (Get-Location -PSProvider FileSystem).ProviderPath
    try {
        $HomeDrive = $null
        $ApothemHome = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ApothemHomeValue, [ref]$HomeProvider, [ref]$HomeDrive)
    } finally {
        Pop-Location
    }
} catch {
    $HomeProvider = $null
}
if (-not $HomeProvider -or $HomeProvider.Name -ne 'FileSystem') {
    Write-Error "  x APOTHEM_HOME is not a usable folder path: $ApothemHomeValue"
}
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
# settings, read its configuration from other files, use another git
# program, or swap objects through replace refs, so the run clears them
# once it holds the install lock (see the start of the run, below;
# mirrors install.sh). Run by irm | iex, the script shares the caller's
# session, so the caller's values are put back as the run ends, however
# it ends. GIT_CONFIG_NOSYSTEM is left as the caller set it: it only
# stops git reading the system configuration. git still reads the user's
# own global and system configuration from the places it always looks,
# and git, gpg and cosign are the ones PATH finds. An APOTHEM_REPO that
# starts with - would reach git as an option.
if ($ApothemRepo.StartsWith('-')) {
    Write-Fail "APOTHEM_REPO must be a repository URL or path, not an option: $ApothemRepo"
}
# git runs ls-remote and clone from an empty folder (Invoke-GitOutsideRepository),
# so a repository given as a relative path is made a full path first.
if ($ApothemRepo -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://' -and (Test-Path -LiteralPath $ApothemRepo)) {
    $ApothemRepo = (Resolve-Path -LiteralPath $ApothemRepo).ProviderPath
}

# Every git command on a clone takes $GitNoProgram: git never runs the
# clone's fsmonitor program (core.fsmonitor is emptied) or a pager
# (--no-pager), never starts automatic maintenance (gc.auto=0,
# maintenance.auto=false), uses only the file, git, http, https and ssh
# transports (protocol.allow=never with those five allowed), so an
# address in the clone's config cannot make git run a program (ext::,
# or <name>:: for a git-remote-<name> found on PATH), writes a path
# longer than Windows' usual limit at checkout (core.longpaths=true)
# instead of leaving the file out, and does not go into submodules:
# fetch and checkout leave
# them alone, and diff and status skip them (diff.ignoreSubmodules=all),
# so the settings of a repository nested in the clone, which nothing
# here checks, are never read. An update in place refuses a clone that
# holds submodules anyway (Assert-CleanClone). The calls of an update
# (fetch, verify-tag, cat-file, checkout and the rest) take $GitSafe,
# which adds core.hooksPath pointing at an empty folder made for the
# run, so none of the clone's hooks runs either. core.sshCommand is left
# alone: setting it would also override the user's own GIT_SSH (mirrors
# install.sh's cgit).
$GitNoProgram = @('--no-pager', '-c', 'core.fsmonitor=', '-c', 'protocol.ext.allow=never', '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=always', '-c', 'protocol.git.allow=always', '-c', 'protocol.http.allow=always', '-c', 'protocol.https.allow=always', '-c', 'protocol.ssh.allow=always', '-c', 'submodule.recurse=false', '-c', 'fetch.recurseSubmodules=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'diff.ignoreSubmodules=all', '-c', 'core.longpaths=true')
$GitSafe = @()

# The current folder must never shadow the engine's modules (mirrors
# install.sh). Python puts '' (the working directory) first on sys.path for
# `-c`, and `-m` puts the working directory there, so a click.py, rich\ or
# apothem\ in the folder the installer (or the shim) runs from would run
# instead of the real package. `-P` / PYTHONSAFEPATH does not exist on
# Python 3.10, and `-I` would also drop PYTHONPATH and the user site (where
# click and rich may be installed). So every such start sets
# PYTHONSAFEPATH=1 (3.11+ then adds nothing) and runs a `-c` program whose
# first statement drops a leading ''. Only sys.path changes; the working
# directory and the arguments do not. The programs hold no double quote,
# which Windows PowerShell 5.1 strips from a native command's argument.
$DropCwdFromPath = "import sys; sys.path[:1] = [] if sys.path[:1] == [''] else sys.path[:1]"
$EngineProgram = "$DropCwdFromPath; import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"
$PipProgram = "$DropCwdFromPath; import runpy; runpy.run_module('pip', run_name='__main__', alter_sys=True)"
# The apothem.cmd shim's program. A batch file cannot tell a full path from a
# relative one, so the shim sets PYTHONPATH to the engine paths only and
# hands the caller's value over in APOTHEM_USER_PYTHONPATH. This program
# keeps that value's full-path entries (the Test-AbsolutePath rule below),
# inserts them on sys.path right after the engine paths (skipping any that
# repeat one), puts them back into PYTHONPATH after the engine paths so
# child processes see what the other launchers give them, drops the
# hand-over variable, then runs the engine. Empty and relative entries,
# which Python would read as the current folder, are left out. The kept
# entries join sys.path after startup, so neither a .pth file nor a
# sitecustomize.py in them runs. The program holds no double quote and no
# percent sign, which the batch file would read.
$ShimProgram = "$DropCwdFromPath; import os, re; e = os.environ.get('PYTHONPATH', ''); n = len(e.split(os.pathsep)) if e else 0; k = [p for p in dict.fromkeys(os.environ.pop('APOTHEM_USER_PYTHONPATH', '').split(os.pathsep)) if re.match('([A-Za-z]:[\\\\/]|[\\\\/]{2})', p) and p not in sys.path[:n]]; sys.path[n:n] = k; os.environ['PYTHONPATH'] = os.pathsep.join(([e] if e else []) + k); import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"

# Test-AbsolutePath PATH - $true when PATH is a full path. On Windows that is
# a drive letter and a separator (X:\ or X:/) or two separators (a \\server
# or //server share); elsewhere a leading /. A drive-relative C:x or a
# rooted \x is not. Every launcher, and $ShimProgram, uses this one rule.
function Test-AbsolutePath {
    param([string]$Path)
    if (-not $Path) { return $false }
    if ([System.IO.Path]::PathSeparator -eq ';') { return ($Path -match '^([A-Za-z]:[\\/]|[\\/]{2})') }
    return $Path.StartsWith('/')
}

# ConvertTo-PsLiteral TEXT - TEXT as a single-quoted PowerShell string for a
# command the banner prints: each quote PowerShell reads as a single quote
# (the ASCII one and the typographic U+2018-U+201B) is doubled.
function ConvertTo-PsLiteral {
    param([string]$Text)
    return "'" + ($Text -replace "['\u2018\u2019\u201A\u201B]", '$0$0') + "'"
}

# Get-SafePythonPath LEAD USER - the PYTHONPATH a Python start gets: LEAD
# (the engine's paths, or nothing) followed by the entries of USER (the
# caller's PYTHONPATH) that are full paths. Python reads an empty entry, or a
# relative one such as `.`, as the current folder before any -c program runs
# and whatever PYTHONSAFEPATH says, so a sitecustomize.py there would run;
# those entries are dropped (mirrors install.sh). $null when nothing is left.
function Get-SafePythonPath {
    param([string]$Lead, [string]$UserPath)
    $Sep = [System.IO.Path]::PathSeparator
    $Kept = @()
    if ($Lead) { $Kept += $Lead }
    if ($UserPath) { $Kept += @($UserPath.Split($Sep) | Where-Object { Test-AbsolutePath $_ }) }
    if ($Kept.Count -eq 0) { return $null }
    return ($Kept -join $Sep)
}

# Invoke-GitOutsideRepository BLOCK - run BLOCK, whose git commands work on
# no repository of their own (ls-remote, clone, init, config lookups), from
# an empty folder made for the call, with GIT_CEILING_DIRECTORIES set to that
# folder's parent. git then finds no repository in the current folder or its
# parents, whose .git\config could otherwise run a command (an ext:: URL
# rewrite, core.sshCommand). The location and the variable are restored and
# the folder removed afterwards (mirrors install.sh). Paths BLOCK passes to
# git must be full paths. BLOCKARGS are passed to BLOCK.
function Invoke-GitOutsideRepository {
    param([scriptblock]$Block, [object[]]$BlockArgs = @())
    $GoEmpty = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-git-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $GoEmpty -ErrorAction Stop | Out-Null
    $GoCeiling = $env:GIT_CEILING_DIRECTORIES
    Push-Location -LiteralPath $GoEmpty
    try {
        $env:GIT_CEILING_DIRECTORIES = Split-Path -Parent $GoEmpty
        & $Block @BlockArgs
    } finally {
        $env:GIT_CEILING_DIRECTORIES = $GoCeiling
        Pop-Location
        Remove-Item -LiteralPath $GoEmpty -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Save-Download URI FILE - download URI to FILE. A download from an https://
# address may only be redirected to another https:// one, at every step,
# as install.sh's curl --proto-redir =https allows. PowerShell 7 does not
# follow a redirect from https to plain http, and the address the response
# finally came from is checked as well. Windows PowerShell 5.1 does follow
# one, and would accept a chain that goes through http and back to https,
# so there each redirect is followed by hand (at most 10) and the first
# one to an address that is not https:// stops the download. A file that
# came from anywhere else is removed and the download fails, with the
# reason in the error. A base of another scheme (an http:// mirror on the
# local network) is used as given, as in install.sh.
function Save-Download {
    param([string]$Uri, [string]$OutFile)
    $FromHttps = $Uri.StartsWith('https://', [System.StringComparison]::OrdinalIgnoreCase)
    if ($FromHttps -and $PSVersionTable.PSVersion.Major -lt 6) {
        $DlAt = [uri]$Uri
        foreach ($DlHop in 0..10) {
            # 5.1 returns a redirect's response, with its Location, only when
            # its own error for it is silenced; a failed request still throws.
            $DlError = $null
            $DlResponse = Invoke-WebRequest -UseBasicParsing -Uri $DlAt -OutFile $OutFile -PassThru -MaximumRedirection 0 -ErrorAction SilentlyContinue -ErrorVariable DlError
            if (-not $DlResponse) {
                Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
                throw "$DlAt gave no response ($(@($DlError | ForEach-Object { $_.ToString() }) -join ' '))"
            }
            $DlCode = [int]$DlResponse.StatusCode
            if ($DlCode -lt 300 -or $DlCode -ge 400) { return }
            Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
            $DlLocation = [string]$DlResponse.Headers['Location']
            if (@(301, 302, 303, 307, 308) -notcontains $DlCode -or -not $DlLocation) {
                throw "$DlAt answered $DlCode with no address to go to"
            }
            $DlNext = New-Object System.Uri -ArgumentList $DlAt, $DlLocation
            if ($DlNext.Scheme -ne 'https') {
                throw "$Uri was redirected to $DlNext, which is not an https:// address"
            }
            $DlAt = $DlNext
        }
        throw "$Uri was redirected more than 10 times"
    }
    $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $OutFile -PassThru
    if (-not $FromHttps) { return }
    $Base = $Response.BaseResponse
    $Final = $null
    if ($Base -and $Base.PSObject.Properties['ResponseUri']) {
        $Final = $Base.ResponseUri
    } elseif ($Base -and $Base.PSObject.Properties['RequestMessage'] -and $Base.RequestMessage) {
        $Final = $Base.RequestMessage.RequestUri
    }
    if (-not $Final -or $Final.Scheme -ne 'https') {
        Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
        throw "$Uri was redirected to $Final, which is not an https:// address"
    }
}

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
    $priorSafePath = $env:PYTHONSAFEPATH
    $env:PYTHONSAFEPATH = '1'
    try {
        & $Interpreter -c "$DropCwdFromPath; import $Module" *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $env:PYTHONSAFEPATH = $priorSafePath
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
    # pip starts through the same guarded -c program as the engine, so a
    # pip\ in the current folder never runs in its place.
    $priorSafePath = $env:PYTHONSAFEPATH
    $env:PYTHONSAFEPATH = '1'
    try {
        & $Interpreter -c $PipProgram --version *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "pip is unavailable under $Interpreter - install $($Deps -join ', ') manually."
            return $false
        }
        Write-Info "Installing $($Deps -join ', ') under $Interpreter (pip)"
        & $Interpreter -c $PipProgram install @Deps
        $code = $LASTEXITCODE
    } finally {
        $env:PYTHONSAFEPATH = $priorSafePath
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
    $raw = Invoke-GitOutsideRepository { param($LsRepo) & git ls-remote --tags $LsRepo 2>$null } @($Repo)
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

# Get-TagSigner - the primary-key fingerprints, other than
# $MaintainerFingerprint, of the valid signatures in the captured status
# lines, each once and upper-case, as the message names them: "the key X",
# or "the keys X, Y" (mirrors install.sh's verify_tag_other_keys and
# other_key_message).
function Get-TagSigner {
    $Signers = @()
    foreach ($Line in ($script:VerifyTagOutput -split "`n")) {
        $Fields = @($Line.Trim() -split '\s+')
        if ($Fields.Count -ge 3 -and $Fields[0] -ceq '[GNUPG:]' -and $Fields[1] -ceq 'VALIDSIG') {
            $Fpr = if ($Fields.Count -ge 12) { $Fields[11] } else { $Fields[2] }
            $Fpr = $Fpr.ToUpperInvariant()
            if ($Fpr -ne $MaintainerFingerprint -and $Signers -cnotcontains $Fpr) { $Signers += $Fpr }
        }
    }
    if ($Signers.Count -gt 1) { return "the keys $($Signers -join ', ')" }
    return "the key $($Signers -join ', ')"
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
        $Prog = Invoke-GitOutsideRepository { & git config --get gpg.openpgp.program 2>$null }
        if (-not $Prog) { $Prog = Invoke-GitOutsideRepository { & git config --get gpg.program 2>$null } }
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
# The tag ref is read once: the signature, the signed tag object's own name
# and the commit are all read from that one tag object, and the commit it
# returns is checked out by its ID (Invoke-CheckoutRef), so a tag ref moved
# after the check cannot change what is installed. The tag passes when the
# maintainer key signed it and the signed tag object names itself REF and
# points at a commit: a signed tag for another release, re-pointed at
# refs/tags/REF, would otherwise roll an install back to that release. A
# pass returns that commit. Any other outcome aborts with the reason, unless
# ALLOW is $true, which downgrades a missing or unverifiable signature to a
# warning and returns the commit the tag pointed at when it was read ($null
# when there is none); a re-pointed tag aborts either way.
function Test-MaintainerTag {
    param([string]$Dir, [string]$Ref, [bool]$Allow)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $TagObject = "$(& git @GitSafe -C $Dir rev-parse --verify --quiet "refs/tags/$Ref" 2>$null)".Trim()
        if ($LASTEXITCODE -ne 0) { $TagObject = '' }
    } finally {
        $ErrorActionPreference = $prior
    }
    $script:VerifyTagOutput = ''
    if ($TagObject -and (Test-TagSignature $Dir $TagObject) -and (Test-TagSignedByMaintainer)) {
        $ErrorActionPreference = 'Continue'
        try {
            $TagLines = @(& git @GitSafe -C $Dir cat-file tag $TagObject 2>$null)
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
        $Commit = & git @GitSafe -C $Dir rev-parse --verify --quiet "$TagObject^{commit}"
        if ($LASTEXITCODE -ne 0 -or -not $Commit) { Write-Fail "Could not read the commit the $Ref tag points at" }
        Write-Ok "Tag $Ref carries a valid signature from the maintainer key $MaintainerFingerprint"
        return ([string]$Commit).Trim()
    }
    if ($Allow) {
        $Commit = ''
        if ($TagObject) {
            $ErrorActionPreference = 'Continue'
            try {
                $Commit = "$(& git @GitSafe -C $Dir rev-parse --verify --quiet "$TagObject^{commit}" 2>$null)".Trim()
                if ($LASTEXITCODE -ne 0) { $Commit = '' }
            } finally {
                $ErrorActionPreference = $prior
            }
        }
        Write-Warn "Tag $Ref is unsigned, its signature did not verify, or the maintainer key did not make it - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        if (-not $Commit) { return $null }
        return $Commit
    }
    if (Test-TagSignedByOtherKey) {
        $Signers = Get-TagSigner
        Write-Fail "Tag $Ref is signed by $Signers. A release tag must be signed by the maintainer key $MaintainerFingerprint that SECURITY.md publishes, and by no other key (possible tampering). Aborting before anything is checked out or materialized."
    }
    if (Test-VerifyTagMissingKey) {
        Write-Fail "Tag $Ref is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run & `"$env:ProgramFiles\Git\bin\bash.exe`" -c 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import && gpg --fingerprint 70396FED9C634163' (the gpg that ships with Git for Windows, which git verify-tag uses), check that the fingerprint matches the one published in SECURITY.md, then re-run this installer."
    }
    Write-Fail "Tag $Ref is unsigned or its signature did not verify (possible tampering). Aborting before anything is checked out or materialized."
}

# Assert-FetchedRef DIR - the gate for APOTHEM_REF in the repository at DIR,
# run before it is checked out (mirrors install.sh's check_fetched_ref). A
# release tag goes through Test-MaintainerTag, and the commit it returns is
# kept in $script:TagCommit for Invoke-CheckoutRef; any other ref (main, a
# SHA, a pre-release tag) cannot be verified, so it is refused unless
# APOTHEM_ALLOW_UNVERIFIED=1.
$script:TagCommit = $null
function Assert-FetchedRef {
    param([string]$Dir)
    $script:TagCommit = $null
    if (Test-ReleaseTag $ApothemRef) {
        $script:TagCommit = Test-MaintainerTag $Dir $ApothemRef ($ApothemAllowUnverified -eq '1')
    } elseif ($ApothemAllowUnverified -eq '1') {
        Write-Warn "Ref $ApothemRef is not a signed release tag - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
    } else {
        Write-Fail "Ref $ApothemRef is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
    }
}

# Invoke-CheckoutRef DIR [-InPlace] - check out APOTHEM_REF in the clone at
# DIR, after Assert-FetchedRef has passed (mirrors install.sh's
# checkout_ref). A release tag is checked out, detached, by the commit ID
# Assert-FetchedRef recorded when it checked the tag ($script:TagCommit),
# never by its name again: a tag ref moved since, or a branch that shares
# the tag's name, cannot change what is checked out, and HEAD must then be
# that commit. Any other ref follows origin's branch of that name when there
# is one (a local branch may be stale), and otherwise resolves directly,
# after --end-of-options so a ref cannot pass for an option. No --force: a
# clone with local changes that the checkout would overwrite stops instead
# of losing them. Submodules are left alone. -InPlace marks the clone at
# APOTHEM_HOME: a change to a tracked file stops the update before the
# checkout, and the tracked files must match the ref after it. git reports
# a refused checkout on stderr, which PowerShell before 7.2 turns into a
# terminating error under 'Stop', so the preference is localized as in
# Test-TagSignature.
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
    if ((Test-ReleaseTag $ApothemRef) -and -not $script:TagCommit) {
        Write-Fail "Could not check out the $ApothemRef tag in $Dir. If it has local changes, commit or stash them, then re-run."
    }
    $ErrorActionPreference = 'Continue'
    try {
        if (Test-ReleaseTag $ApothemRef) {
            & git @GitSafe -C $Dir checkout --quiet --detach $script:TagCommit
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
        $CoTag = $script:TagCommit
        if ("$CoHead" -ne "$CoTag") {
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
# The file a keep or clone swap writes into its staging folder, beside the
# new tree, before it moves anything: the names it is about to move from
# APOTHEM_HOME into that tree, one per line, so the leftover report can
# name them after a forced kill (see Get-CarriedEntry).
$CarryList = '.apothem-carried-entries'
$EngineDataNames = @('backups', 'state', 'plans', 'memory', 'contexts', 'learning', 'providers')
function Get-SourceEntry {
    param([string]$Dir)
    $Names = @('.git')
    if (Test-Path -LiteralPath (Join-Path $Dir '.git')) {
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $Tracked = @(& git @GitNoProgram -C $Dir ls-tree --name-only HEAD 2>$null)
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

# New-AsideFolder STAGE - make the new folder an earlier tree is moved into,
# and return its path: <APOTHEM_HOME>.before-apothem-<time>, or
# <time>-<pid> when that name is taken (mirrors install.sh's claim_aside).
# A fresh folder with a name no one can guess is made inside STAGE, the
# run's own staging folder beside APOTHEM_HOME, and renamed to that name;
# the rename fails when the name is already there, so the folder is always
# an empty one this run made. The earlier tree then moves inside it under
# its own name: it is never moved into a folder someone else made, or to a
# name checked first and used later. $null, having made nothing, when both
# names are taken.
function New-AsideFolder {
    param([string]$Stage)
    $AfName = "$ApothemHome.before-apothem-" + (Get-Date -Format 'yyyyMMddHHmmss')
    try {
        $AfTemp = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $Stage ('aside.' + [System.Guid]::NewGuid().ToString('N'))))
        $null = [System.IO.Directory]::CreateDirectory($AfTemp)
    } catch {
        return $null
    }
    foreach ($AfTry in @($AfName, "$AfName-$PID")) {
        try {
            [System.IO.Directory]::Move($AfTemp, $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($AfTry))
            return $AfTry
        } catch {
            $null = $_
        }
    }
    try { [System.IO.Directory]::Delete($AfTemp, $false) } catch { $null = $_ }
    return $null
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
#               tree once its data has moved is not removed but moved into
#               a new sibling <APOTHEM_HOME>.before-apothem-<time> folder
#               (see New-AsideFolder).
#   MODE aside: APOTHEM_HOME holds something else, and -Yes allowed
#               replacing it. It moves, untouched and under its own name,
#               into a new sibling <APOTHEM_HOME>.before-apothem-<time>
#               folder (see New-AsideFolder), and NEW moves in.
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
    $SwLeaf = Split-Path -Leaf $ApothemHome
    $SwStage = Split-Path -Parent $New
    if ($Mode -eq 'aside') {
        $Aside = $null
        $AsideItem = $null
        # The folder is made and both moves run inside try, so an interrupt
        # after any of them is undone too, from what is where.
        $SwDone = $false
        $SwFailed = $false
        $SwUntouched = $false
        $SwReason = "Interrupted while replacing $ApothemHome"
        try {
            $Aside = New-AsideFolder $SwStage
            if (-not $Aside) { $SwFailed = $true; $SwUntouched = $true; $SwReason = "Could not move the existing $ApothemHome aside"; throw $SwReason }
            $AsideItem = Join-Path $Aside $SwLeaf
            try { Move-Entry $ApothemHome $AsideItem }
            catch { $SwFailed = $true; $SwUntouched = $true; $SwReason = "Could not move the existing $ApothemHome aside"; throw }
            try { Move-Entry $New $ApothemHome }
            catch { $SwFailed = $true; $SwReason = "Could not move the new source to $ApothemHome"; throw }
            $SwDone = $true
        } finally {
            if (-not $SwDone) {
                $SwBack = $false
                try {
                    if ($AsideItem -and (Test-Entry $AsideItem)) {
                        if ((Test-Entry $ApothemHome) -and -not (Test-Entry $New)) { Move-Entry $ApothemHome $New }
                        if (-not (Test-Entry $ApothemHome)) { Move-Entry $AsideItem $ApothemHome }
                    }
                    $SwBack = (Test-Entry $ApothemHome) -and -not ($AsideItem -and (Test-Entry $AsideItem))
                } catch { $SwBack = $false }
                # The folder it was moved into is then empty, and goes.
                if ($SwBack -and $Aside) {
                    try { [System.IO.Directory]::Delete($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Aside), $false) } catch { $null = $_ }
                }
                if ($SwBack -and $SwUntouched) {
                    $SwMessage = "$SwReason; nothing was changed"
                } elseif ($SwBack) {
                    $SwMessage = "$SwReason; the earlier folder is back in place and unchanged"
                } else {
                    $SwMessage = "$SwReason, and moving the earlier folder back also failed: it is at $AsideItem"
                }
                # See the keep branch below for why an interrupt prints first.
                if (-not $SwFailed) { Write-Host "  x $SwMessage" }
                Write-Fail $SwMessage
            }
        }
        Write-Warn "The earlier contents of $ApothemHome were moved, unchanged, to $AsideItem"
        return
    }
    # keep and clone: list the entries to carry over before anything moves.
    $SourceNames = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($Name in (Get-SourceEntry $ApothemHome)) { $null = $SourceNames.Add($Name) }
    foreach ($Entry in @(Get-ChildItem -LiteralPath $New -Force)) {
        if ($EngineDataNames -cnotcontains $Entry.Name) { $null = $SourceNames.Add($Entry.Name) }
    }
    $SwKeep = @(@(Get-ChildItem -LiteralPath $ApothemHome -Force) | Where-Object { -not $SourceNames.Contains($_.Name) } | ForEach-Object { $_.Name })
    # The names about to move, sorted ordinally, go into the staging folder
    # first ($CarryList), so a forced kill during the moves leaves a record
    # of what came from APOTHEM_HOME.
    $SwCarry = [string[]]@($SwKeep)
    [Array]::Sort($SwCarry, [System.StringComparer]::Ordinal)
    try {
        $SwCarryPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $SwStage $CarryList))
        [System.IO.File]::WriteAllText($SwCarryPath, (@($SwCarry | ForEach-Object { "$_`n" }) -join ''), (New-Object System.Text.UTF8Encoding $false))
    } catch {
        Write-Fail "Could not make room beside $ApothemHome; nothing was changed"
    }
    $SwParent = Split-Path -Parent $ApothemHome
    if (-not $SwParent) { $SwParent = (Get-Location).Path }
    $SwOld = Join-Path $SwParent (".apothem-old.$SwLeaf." + [System.Guid]::NewGuid().ToString('N'))
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
    if ($Mode -eq 'clone') {
        # The clone's tree (history and source, the carried entries aside) is
        # kept in a new <APOTHEM_HOME>.before-apothem-<time> folder, not
        # deleted; when no such folder can be made, it stays where it is.
        $SwTreeAt = $SwOldHome
        $SwClaim = New-AsideFolder $SwStage
        if ($SwClaim) {
            try {
                Move-Entry $SwOldHome (Join-Path $SwClaim $SwLeaf)
                $SwTreeAt = Join-Path $SwClaim $SwLeaf
            } catch {
                try { [System.IO.Directory]::Delete($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SwClaim), $false) } catch { $null = $_ }
            }
        }
        if ($SwTreeAt -ne $SwOldHome) {
            try { [System.IO.Directory]::Delete($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SwOld), $false) } catch { $null = $_ }
        }
        Write-Warn "The earlier clone's tree is kept at $SwTreeAt; delete it once you no longer need it."
        return
    }
    try { Remove-Item -LiteralPath $SwOld -Recurse -Force }
    catch { Write-Warn "Could not remove the earlier source at $SwOld; delete it by hand" }
}

# Lock-ApothemHome - take the install lock: an install, update or uninstall
# holds <APOTHEM_HOME>.lock for its whole run, so two runs never change
# APOTHEM_HOME, or the folders beside it, at the same time (mirrors
# install.sh's take_lock). The lock is a file opened with no sharing, so a
# second open fails while this run holds it; Windows closes it when the run
# ends, a forced kill included, which frees the lock and deletes the file.
# install.sh, update.sh and uninstall.sh use a folder of the same name that
# holds the process ID of the run that made it. That ID cannot be checked
# from here (under Git Bash it is not a Windows process ID), so such a
# folder is reported, with how to remove it, and never taken over.
$script:HomeLock = $null
$HomeLockPath = "$ApothemHome.lock"
function Lock-ApothemHome {
    $LkParent = Split-Path -Parent $ApothemHome
    if (-not $LkParent) { return }
    if (-not (Test-Path -LiteralPath $LkParent -PathType Container)) {
        # Nothing is at APOTHEM_HOME or beside it yet. A dry run writes
        # nothing, so it goes on without the lock; a real run makes the
        # parent folder it would make anyway.
        if ($DryRun) { return }
        try { New-Item -ItemType Directory -Force -Path $LkParent | Out-Null }
        catch { Write-Fail "Could not create the parent directory of $ApothemHome" }
        if (-not (Test-Path -LiteralPath $LkParent -PathType Container)) {
            Write-Fail "Could not create the parent directory of $ApothemHome"
        }
    }
    $LkItem = Get-Item -LiteralPath $HomeLockPath -Force -ErrorAction SilentlyContinue
    if ($LkItem -and ($LkItem.LinkType -or $LkItem.PSIsContainer)) {
        $LkPid = ''
        if ($LkItem.PSIsContainer -and -not $LkItem.LinkType) {
            try { $LkPid = ([System.IO.File]::ReadAllText((Join-Path $LkItem.FullName 'pid'))).Trim() } catch { $LkPid = '' }
        }
        if ($LkPid -notmatch '^[0-9]+$') {
            Write-Fail "$HomeLockPath exists but names no running process; an Apothem run may have left it when it was stopped. Check that no Apothem install, update or uninstall is running, remove $HomeLockPath, then re-run."
        }
        Write-Fail "Another Apothem install, update or uninstall is running on $ApothemHome. Wait for it to finish, then re-run. If none is running, remove $HomeLockPath, then re-run."
    }
    try {
        $script:HomeLock = New-Object System.IO.FileStream -ArgumentList $HomeLockPath, ([System.IO.FileMode]::OpenOrCreate), ([System.IO.FileAccess]::ReadWrite), ([System.IO.FileShare]::None), 4096, ([System.IO.FileOptions]::DeleteOnClose)
    } catch {
        # A sharing violation means another run holds the file; a folder
        # that cannot be written to is a failure of its own.
        $LkError = $_.Exception.GetBaseException()
        if ($LkError -is [System.IO.IOException] -and $LkError -isnot [System.IO.DirectoryNotFoundException] -and $LkError -isnot [System.IO.FileNotFoundException] -and $LkError -isnot [System.IO.PathTooLongException]) {
            Write-Fail "Another Apothem install, update or uninstall is running on $ApothemHome. Wait for it to finish, then re-run. If none is running, remove $HomeLockPath, then re-run."
        }
        Write-Fail "Could not create the lock $HomeLockPath beside $ApothemHome. Check that you can write to $LkParent, then re-run."
    }
}

# Unlock-ApothemHome - let the install lock go: closing the file frees it
# and deletes it.
function Unlock-ApothemHome {
    if ($script:HomeLock) {
        $script:HomeLock.Dispose()
        $script:HomeLock = $null
    }
}

# Test-RealFolder ITEM - $true when ITEM (from Get-Item or Get-ChildItem) is
# a folder, not a symbolic link or junction to one; Test-RealFolderPath PATH
# says the same of what is at PATH.
function Test-RealFolder {
    param($Item)
    return [bool]($Item -and $Item.PSIsContainer -and -not $Item.LinkType)
}
function Test-RealFolderPath {
    param([string]$Path)
    return (Test-RealFolder (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue))
}

# Get-LeftoverEntry DIR - the names in the leftover folder DIR, sorted
# ordinally, or $null when DIR cannot be listed. An empty folder named
# aside.<32 hex digits> is left out: it is New-AsideFolder's temporary
# folder, left by a kill between its creation and its rename.
function Get-LeftoverEntry {
    param([string]$Dir)
    try {
        $LeItems = @(Get-ChildItem -LiteralPath $Dir -Force -ErrorAction Stop)
    } catch {
        return $null
    }
    $LeNames = New-Object 'System.Collections.Generic.List[string]'
    foreach ($LeItem in $LeItems) {
        if ($LeItem.Name -cmatch '^aside\.[0-9a-f]{32}\z' -and (Test-RealFolder $LeItem) -and @(Get-ChildItem -LiteralPath $LeItem.FullName -Force -ErrorAction SilentlyContinue).Count -eq 0) { continue }
        $LeNames.Add($LeItem.Name)
    }
    $LeArray = $LeNames.ToArray()
    [Array]::Sort($LeArray, [System.StringComparer]::Ordinal)
    return , $LeArray
}

# Get-CarriedEntry DIR TREE - the entries a swap moved from APOTHEM_HOME
# into TREE, the new tree in the staging folder DIR. The run that made DIR
# listed them in DIR's $CarryList before its first move; those still in
# TREE are named, in the list's order. With no list (a folder an earlier
# installer made, or a kill before the list was written), an archive's tree
# names what its .apothem-source-entries manifest does not list, and any
# other tree names the engine's data folders it holds, sorted ordinally.
function Get-CarriedEntry {
    param([string]$Dir, [string]$Tree)
    $CeListItem = Get-Item -LiteralPath (Join-Path $Dir $CarryList) -Force -ErrorAction SilentlyContinue
    if ($CeListItem -and -not $CeListItem.PSIsContainer -and -not $CeListItem.LinkType) {
        try { $CeLines = @([System.IO.File]::ReadAllText($CeListItem.FullName).Split("`n")) } catch { $CeLines = @() }
        return , @($CeLines | Where-Object { $_ -and (Test-Entry (Join-Path $Tree $_)) })
    }
    $CeManifest = Join-Path $Tree $SourceManifest
    if ((Split-Path -Leaf $Dir).StartsWith('.apothem-extract.', [System.StringComparison]::Ordinal) -and (Test-Path -LiteralPath $CeManifest -PathType Leaf)) {
        $CeListed = @(Get-Content -LiteralPath $CeManifest | ForEach-Object { ([string]$_).TrimEnd("`r") })
        $CeNames = [string[]]@(Get-ChildItem -LiteralPath $Tree -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.Name } | Where-Object { $CeListed -cnotcontains $_ })
    } else {
        $CeNames = [string[]]@($EngineDataNames | Where-Object { Test-Entry (Join-Path $Tree $_) })
    }
    [Array]::Sort($CeNames, [System.StringComparer]::Ordinal)
    return , $CeNames
}

# Get-LeftoverLine DIR OLDNAME - one line saying what the leftover folder DIR
# holds (see Assert-NoLeftover; mirrors install.sh). Names are sorted
# ordinally and joined with ", ". OLDNAME marks a folder whose name does not
# say which APOTHEM_HOME it was made for.
function Get-LeftoverLine {
    param([string]$Dir, [bool]$OldName)
    $LlNames = Get-LeftoverEntry $Dir
    if ($null -eq $LlNames) {
        $LlText = "${Dir}: could not be read (check its owner and permissions)"
    } elseif ($LlNames.Count -eq 0) {
        $LlText = "${Dir}: empty"
    } else {
        $LlText = "${Dir}: files from that run ($($LlNames -join ', '))"
        if ((Split-Path -Leaf $Dir).StartsWith('.apothem-old.', [System.StringComparison]::Ordinal)) {
            if ($LlNames.Count -eq 1 -and $LlNames[0] -ceq 'home' -and (Test-RealFolderPath (Join-Path $Dir 'home'))) {
                $LlText = "${Dir}: the earlier install that was being replaced, in $(Join-Path $Dir 'home')"
            }
        } else {
            $LlListItem = Get-Item -LiteralPath (Join-Path $Dir $CarryList) -Force -ErrorAction SilentlyContinue
            $LlListIsFile = [bool]($LlListItem -and -not $LlListItem.PSIsContainer -and -not $LlListItem.LinkType)
            $LlTreeNames = @($LlNames | Where-Object { -not ($LlListIsFile -and $_ -ceq $CarryList) })
            if ($LlTreeNames.Count -eq 1 -and (Test-RealFolderPath (Join-Path $Dir $LlTreeNames[0]))) {
                $LlTree = Join-Path $Dir $LlTreeNames[0]
                $LlText = "${Dir}: the new source that was being installed, in $LlTree"
                $LlCarried = Get-CarriedEntry $Dir $LlTree
                if ($LlCarried.Count -gt 0) {
                    $LlText += ", with these entries moved into it from ${ApothemHome}: $($LlCarried -join ', ')"
                }
            }
        }
    }
    if ($OldName) {
        $LlText += " (made by an earlier installer that did not record which home it was for, so it may belong to any Apothem home in $(Split-Path -Parent $ApothemHome): check what it holds before you move or remove it)"
    }
    return $LlText
}

# Assert-NoLeftover - stop, before anything is fetched or swapped, when a run
# that was stopped part-way left folders beside APOTHEM_HOME (mirrors
# install.sh's check_leftovers): .apothem-extract.<name>.* and
# .apothem-clone.<name>.* (a new source being installed, perhaps with
# entries of APOTHEM_HOME already moved into it) or .apothem-old.<name>.*
# (the earlier install being replaced), <name> being APOTHEM_HOME's own
# folder name. Every other way out of a run puts things back and removes
# them, so they are there only after a forced kill or a power loss. Only
# real folders count, only this APOTHEM_HOME's (the install lock keeps any
# other run on it from using them now; another APOTHEM_HOME's run may be
# using its own), and folders an earlier installer made, whose names hold
# no <name>, which are reported with a note that they may belong to any
# Apothem home in that folder. They may hold the earlier install or its
# data, so nothing is moved or removed here: the folder lines go to the
# error stream, one per line, this home's first, then the older ones, each
# group sorted ordinally, and the run stops with what to do. When
# APOTHEM_HOME itself is missing, the folders it may have been moved into
# (<APOTHEM_HOME>.before-apothem-<time>) are named too.
function Assert-NoLeftover {
    $LoParent = Split-Path -Parent $ApothemHome
    if (-not $LoParent -or -not (Test-Path -LiteralPath $LoParent -PathType Container)) { return }
    $LoLeaf = Split-Path -Leaf $ApothemHome
    $LoAside = '^' + [regex]::Escape($LoLeaf) + '\.before-apothem-[0-9]{14}(-[0-9]+)?\z'
    $LoMine = New-Object 'System.Collections.Generic.List[string]'
    $LoOld = New-Object 'System.Collections.Generic.List[string]'
    $LoAsides = New-Object 'System.Collections.Generic.List[string]'
    foreach ($LoItem in @(Get-ChildItem -LiteralPath $LoParent -Force -ErrorAction SilentlyContinue)) {
        if (-not (Test-RealFolder $LoItem)) { continue }
        $LoName = $LoItem.Name
        foreach ($LoPrefix in @('.apothem-old.', '.apothem-extract.', '.apothem-clone.')) {
            if (-not $LoName.StartsWith($LoPrefix, [System.StringComparison]::Ordinal)) { continue }
            # The suffix after the last dot holds no dot, so the part before
            # it is the home's folder name, dots and all.
            $LoRest = $LoName.Substring($LoPrefix.Length)
            $LoDot = $LoRest.LastIndexOf('.')
            if ($LoDot -lt 0) {
                $LoOld.Add($LoName)
            } elseif ($LoDot -lt $LoRest.Length - 1 -and $LoRest.Substring(0, $LoDot) -ceq $LoLeaf) {
                $LoMine.Add($LoName)
            }
        }
        if ($LoName -cmatch $LoAside) { $LoAsides.Add($LoName) }
    }
    if ($LoMine.Count + $LoOld.Count -eq 0) { return }
    $LoLines = New-Object 'System.Collections.Generic.List[string]'
    foreach ($LoGroup in @(@($LoMine.ToArray(), $false), @($LoOld.ToArray(), $true))) {
        $LoNames = [string[]]$LoGroup[0]
        [Array]::Sort($LoNames, [System.StringComparer]::Ordinal)
        foreach ($LoName in $LoNames) { $LoLines.Add((Get-LeftoverLine (Join-Path $LoParent $LoName) $LoGroup[1])) }
    }
    if (-not (Test-Entry $ApothemHome)) {
        $LoAsideNames = $LoAsides.ToArray()
        [Array]::Sort($LoAsideNames, [System.StringComparer]::Ordinal)
        foreach ($LoName in $LoAsideNames) {
            $LoAt = Join-Path $LoParent $LoName
            $LoIn = Join-Path $LoAt $LoLeaf
            if (-not (Test-RealFolderPath $LoIn)) { $LoIn = $LoAt }
            $LoLines.Add("${LoAt}: the earlier contents of $ApothemHome, moved aside, in $LoIn")
        }
    }
    [Console]::Error.WriteLine("  x An earlier run was stopped part-way and left these folders beside ${ApothemHome}:")
    foreach ($LoLine in $LoLines) { [Console]::Error.WriteLine("    $LoLine") }
    Write-Fail "Nothing was changed. If $ApothemHome is missing, move the earlier install back to it first. Then move every entry listed above as moved from $ApothemHome back into it, remove the folders listed above, and re-run."
}

Write-Bold "Apothem installer"

# One install, update or uninstall at a time on APOTHEM_HOME (see
# Lock-ApothemHome); the finally block at the end lets the lock go.
Lock-ApothemHome
try {
# The git variables described at the top are cleared for the run: each
# one set now is kept in $SavedGitEnv, with GIT_NO_REPLACE_OBJECTS as it
# was, and the finally block at the end puts them all back.
$SavedGitEnv = @{ GIT_NO_REPLACE_OBJECTS = $env:GIT_NO_REPLACE_OBJECTS }
try {
foreach ($GitVar in @('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR', 'GIT_NAMESPACE', 'GIT_REPLACE_REF_BASE', 'GIT_CEILING_DIRECTORIES', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_EXEC_PATH', 'GIT_TEMPLATE_DIR', 'GIT_CONFIG', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM')) {
    if (Test-Path -LiteralPath "Env:$GitVar") {
        $SavedGitEnv[$GitVar] = [string](Get-Item -LiteralPath "Env:$GitVar").Value
        Remove-Item -LiteralPath "Env:$GitVar"
    }
}
$env:GIT_NO_REPLACE_OBJECTS = '1'

# Prerequisite: Python >= 3.10 ------------------------------------------------
#
# Locate a real CPython >= 3.10, rejecting Microsoft Store launcher shims.
# The locator at src\apothem\hooks\lib\find-python.ps1 is reused when a
# local tree is in use (see Get-OwnCheckout below); otherwise an inline probe
# applies the same floor.
Write-Bold "Checking prerequisites"

function Test-ApothemSource {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Dir, 'src', 'apothem')))) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Dir 'pyproject.toml')) -or
           (Test-Path -LiteralPath (Join-Path $Dir '.claude-plugin'))
}

# Get-OwnCheckout - return the checkout this script file belongs to, or $null.
# It is found by the script's own path and nothing else (mirrors install.sh's
# own_checkout): $PSCommandPath must name an existing file install.ps1 in a
# scripts\installer folder whose ..\.. is an Apothem source. A piped run
# (irm | iex) has no $PSCommandPath, so it never matches, and the current
# folder and its parents are never searched: a folder shaped like an Apothem
# tree there could otherwise put its own code in front of an unverified
# install.
function Get-OwnCheckout {
    $Self = $PSCommandPath
    if (-not $Self -or -not (Test-Path -LiteralPath $Self -PathType Leaf)) { return $null }
    if ((Split-Path -Leaf $Self) -ne 'install.ps1') { return $null }
    $SelfDir = Split-Path -Parent $Self
    if ((Split-Path -Leaf $SelfDir) -ne 'installer') { return $null }
    if ((Split-Path -Leaf (Split-Path -Parent $SelfDir)) -ne 'scripts') { return $null }
    $Root = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($SelfDir, '..', '..'))
    if (-not (Test-ApothemSource $Root)) { return $null }
    # A symbolic link or junction in the script's path would make ..\.. a
    # folder other than the one the file really sits in, so such a run is not
    # taken as a local checkout. Judged by LinkType, as Test-HomeIsLink does:
    # a OneDrive placeholder carries the ReparsePoint attribute too.
    $OcPath = $Self
    while ($OcPath) {
        $OcItem = Get-Item -LiteralPath $OcPath -Force -ErrorAction SilentlyContinue
        if ($OcItem -and $OcItem.LinkType -in @('SymbolicLink', 'Junction')) {
            Write-Info "Not using $Root as a local checkout: $OcPath is a symbolic link or junction. Run install.ps1 from the checkout's real path, or set APOTHEM_SOURCE, to install from it."
            return $null
        }
        $OcPath = Split-Path -Parent $OcPath
    }
    return $Root
}

# The local tree, if any: APOTHEM_SOURCE when set (its messages follow under
# "Locating Apothem source"), else this script's own checkout.
$LocalTree = $null
$LocalKind = $null
if ($env:APOTHEM_SOURCE) {
    if (-not (Test-Path -LiteralPath $env:APOTHEM_SOURCE) -or -not (Test-ApothemSource $env:APOTHEM_SOURCE)) {
        Write-Fail "APOTHEM_SOURCE is not an apothem source tree: $($env:APOTHEM_SOURCE)"
    }
    $LocalTree = (Resolve-Path -LiteralPath $env:APOTHEM_SOURCE).Path
    $LocalKind = 'explicit'
} else {
    $LocalTree = Get-OwnCheckout
    if ($LocalTree) { $LocalKind = 'checkout' }
}

# A fetched install swaps folders beside APOTHEM_HOME, so it stops first on
# any that a run stopped part-way left there (see Assert-NoLeftover). A local
# tree is run where it is and leaves APOTHEM_HOME alone.
if (-not $LocalKind) { Assert-NoLeftover }

# Every Python start from here to the prerequisite check gets the caller's
# PYTHONPATH without its empty and relative entries (Get-SafePythonPath); the
# caller's value is restored afterwards.
$PriorProbePyPath = $env:PYTHONPATH
$env:PYTHONPATH = Get-SafePythonPath '' $PriorProbePyPath
try {
$PY = $null
$Locator = $null
if ($LocalTree) {
    $Cand = [System.IO.Path]::Combine($LocalTree, 'src', 'apothem', 'hooks', 'lib', 'find-python.ps1')
    if (Test-Path -LiteralPath $Cand -PathType Leaf) { $Locator = $Cand }
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
# a SyntaxError. The %-format prints the same MAJOR.MINOR.MICRO string with no
# quoting, and only the built-in sys module is imported, so nothing in the
# current folder can stand in for it (a platform.py there would).
$PyVer = & $PY -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
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
} finally {
    $env:PYTHONPATH = $PriorProbePyPath
}

# Locate or fetch the bundled source ------------------------------------------
#
# Source precedence:
#   1. APOTHEM_SOURCE - an explicit local source tree (no fetch; verification
#      skipped because nothing is fetched).
#   2. This script's own checkout (it was run by path from
#      scripts\installer\ of an apothem source tree; no fetch; verification
#      skipped). The current folder and its parents are never used.
#   3. The release archive, or a git clone of APOTHEM_REPO, pinned to the
#      resolved ref (the latest release tag by default, or an explicit
#      APOTHEM_REF) and checked before it is placed at APOTHEM_HOME. An
#      existing clone is fetched, checked, and only then checked out.
Write-Bold "Locating Apothem source"

$Source = $null
if ($LocalKind -eq 'explicit') {
    $Source = $LocalTree
    Write-Ok "Using explicit source: $Source"
    Write-Info "Local source - skipping tag resolution and signature verification"
} elseif ($LocalKind -eq 'checkout') {
    $Source = $LocalTree
    Write-Ok "Using local checkout: $Source"
    Write-Info "Local checkout - skipping tag resolution and signature verification"
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

# $CloneConfigAllow - the only keys a clone's own git config (its config
# and config.worktree files) may set for an update to go on: the keys
# git clone and git init write on any git 2.x and system, the branch
# keys checkout and editors write, the user's name and email, and the
# keys git maintenance and git pull's own advice write. None of them
# names a program, a file or folder git reads settings, hooks,
# attributes or objects from, a URL rewrite, or another work tree.
# remote.origin.url names the address the fetch needs (a file in the
# git folder's remotes or branches folder can name an address too,
# which gives no more than that key does). An address can name a
# transport whose helper git runs (<name>::...), so $GitNoProgram
# allows only the file, git, http, https and ssh transports, and the
# tag check decides what is checked out. Any other key, whatever
# program or file it would
# name, stops the run (Test-AllowedConfigKey; the user's global and
# system settings are not read here and stay trusted). install.sh,
# update.sh, install.ps1 and update.ps1 each hold this same list.
# clone-config-allow-list begin
$CloneConfigAllow = @(
    'core.repositoryformatversion'
    'core.filemode'
    'core.bare'
    'core.logallrefupdates'
    'core.symlinks'
    'core.ignorecase'
    'core.precomposeunicode'
    'core.longpaths'
    'core.partialclonefilter'
    'extensions.objectformat'
    'extensions.refstorage'
    'extensions.partialclone'
    'extensions.worktreeconfig'
    'remote.origin.url'
    'remote.origin.fetch'
    'remote.origin.tagopt'
    'remote.origin.promisor'
    'remote.origin.partialclonefilter'
    'branch.*.*'
    'user.name'
    'user.email'
    'maintenance.auto'
    'maintenance.strategy'
    'pull.rebase'
    'pull.ff'
)
# clone-config-allow-list end

# Test-AllowedConfigKey KEY - $true when KEY, a name as git config
# --name-only prints it, matches an entry of $CloneConfigAllow. The
# section is the text before the first dot and the key the text after
# the last; both compare without regard to case. The subsection, the
# text between them, compares exactly, character by character: -ceq
# can treat an invisible character such as a soft hyphen as absent
# and pass "ori<soft hyphen>gin" as origin. A two-part entry matches only a
# name with no subsection, a three-part entry only one with a
# subsection, where * stands for any non-empty subsection or any key
# (mirrors install.sh).
function Test-AllowedConfigKey {
    param([string]$Key)
    $AkFirst = $Key.IndexOf('.')
    $AkLast = $Key.LastIndexOf('.')
    if ($AkFirst -lt 1 -or $AkLast -ge $Key.Length - 1) { return $false }
    $AkSection = $Key.Substring(0, $AkFirst).ToLowerInvariant()
    $AkName = $Key.Substring($AkLast + 1).ToLowerInvariant()
    $AkSub = $null
    if ($AkLast -gt $AkFirst) { $AkSub = $Key.Substring($AkFirst + 1, $AkLast - $AkFirst - 1) }
    $AkOrdinal = [System.StringComparison]::Ordinal
    foreach ($AkEntry in $CloneConfigAllow) {
        $AkParts = $AkEntry.Split('.')
        if (-not [string]::Equals($AkParts[0], $AkSection, $AkOrdinal)) { continue }
        if ($AkParts.Count -eq 2) {
            if ($null -eq $AkSub -and [string]::Equals($AkParts[1], $AkName, $AkOrdinal)) { return $true }
        } elseif ($AkSub) {
            $AkSubOk = [string]::Equals($AkParts[1], '*', $AkOrdinal) -or [string]::Equals($AkParts[1], $AkSub, $AkOrdinal)
            $AkNameOk = [string]::Equals($AkParts[2], '*', $AkOrdinal) -or [string]::Equals($AkParts[2], $AkName, $AkOrdinal)
            if ($AkSubOk -and $AkNameOk) { return $true }
        }
    }
    return $false
}

# Assert-CloneGit DIR - stop, saying what to do, when git will not work in
# the clone at DIR (mirrors install.sh's clone_git_ok). git refuses a
# repository another user owns ("dubious ownership"), and its own advice, to
# mark the folder safe, would trust whatever that user put in its git
# config, so the message gives the safer ways out. git runs in the C
# locale here, so its message reads the same in every language.
function Assert-CloneGit {
    param([string]$Dir)
    $prior = $ErrorActionPreference
    $priorLcAll = $env:LC_ALL
    $ErrorActionPreference = 'Continue'
    $env:LC_ALL = 'C'
    try {
        $CgOut = @(& git @GitNoProgram -C $Dir rev-parse --git-dir 2>&1)
        $CgCode = $LASTEXITCODE
    } finally {
        $env:LC_ALL = $priorLcAll
        $ErrorActionPreference = $prior
    }
    if ($CgCode -eq 0) { return }
    $CgErr = @($CgOut | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { $_.ToString() })
    if (($CgErr -join "`n").Contains('dubious ownership')) {
        Write-Fail "$Dir is owned by someone else, so git refuses to work in it (git reports `"dubious ownership`"). Run this as the user who owns $Dir, take ownership of it, or point APOTHEM_HOME at a folder you own, then re-run."
    }
    $CgFirst = if ($CgErr.Count -gt 0) { $CgErr[0] } else { '' }
    Write-Fail "git could not read the clone at $Dir ($CgFirst). Repair it or move it aside, then re-run."
}

# Get-ClonePath DIR NAME - where the clone at DIR keeps NAME, as a full
# path, or $null when git cannot say: config and info\ sit in the git folder
# all its worktrees share, config.worktree in the worktree's own (mirrors
# install.sh's git_path).
function Get-ClonePath {
    param([string]$Dir, [string]$Name)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $GpPath = "$(& git @GitNoProgram -C $Dir rev-parse --git-path $Name 2>$null)"
        $GpCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($GpCode -ne 0 -or -not $GpPath) { return $null }
    if ($GpPath -match '^(/|[A-Za-z]:[\\/])') { return $GpPath }
    return "$Dir/$GpPath"
}

# Assert-CloneConfig DIR - stop when the clone's own git config at DIR (its
# config file or, for a worktree, its config.worktree) sets a key that is
# not on $CloneConfigAllow (Test-AllowedConfigKey), or sets
# extensions.refStorage to anything but files or reftable (a value of
# another form names a folder git reads refs from), or when its
# info\attributes sets a filter, whose program checkout and diff run
# (mirrors install.sh's check_clone_config). Each file is listed alone, so
# its include lines are not followed (include is not on the list); the
# first name in file order that fails stops the run, config first, and
# the message names it and its file. This runs before any git command
# that reads the clone's index or could run one of its programs.
function Assert-CloneConfig {
    param([string]$Dir)
    foreach ($CfName in @('config', 'config.worktree')) {
        $CfFile = Get-ClonePath $Dir $CfName
        if (-not $CfFile) { Write-Fail "Could not read the git config of $Dir." }
        if (-not (Test-Path -LiteralPath $CfFile)) { continue }
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $CfKeys = @(& git @GitNoProgram -C $Dir config --file $CfFile --name-only --list 2>$null | ForEach-Object { [string]$_ })
            $CfCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($CfCode -ne 0) { Write-Fail "Could not read the git config of $Dir at $CfFile." }
        foreach ($CfKey in $CfKeys) {
            $CfBad = -not (Test-AllowedConfigKey $CfKey)
            if (-not $CfBad -and $CfKey.ToLowerInvariant() -ceq 'extensions.refstorage') {
                # Every value, each ended by a NUL byte (a value may hold a
                # line break), must read exactly files or reftable.
                $ErrorActionPreference = 'Continue'
                try {
                    $CfValues = (@(& git @GitNoProgram -C $Dir config --file $CfFile --null --get-all extensions.refstorage 2>$null | ForEach-Object { [string]$_ }) -join "`n")
                    $CfValueCode = $LASTEXITCODE
                } finally {
                    $ErrorActionPreference = $prior
                }
                $CfParts = @($CfValues.Split([char]0))
                $CfBad = $CfValueCode -ne 0 -or $CfParts.Count -lt 2 -or $CfParts[-1] -ne ''
                if (-not $CfBad) {
                    foreach ($CfValue in $CfParts[0..($CfParts.Count - 2)]) {
                        if ($CfValue -cne 'files' -and $CfValue -cne 'reftable') { $CfBad = $true }
                    }
                }
            }
            if ($CfBad) {
                Write-Fail "$Dir's own git config sets $CfKey, which an update in place does not accept in a clone's own config. Remove it from $CfFile, then re-run."
            }
        }
    }
    $CfFile = Get-ClonePath $Dir 'info/attributes'
    if (-not $CfFile) { Write-Fail "Could not read the git config of $Dir." }
    if (Test-Path -LiteralPath $CfFile -PathType Leaf) {
        try {
            $CfLines = @([System.IO.File]::ReadAllLines($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CfFile)))
        } catch {
            $CfLines = @()
        }
        foreach ($CfLine in $CfLines) {
            if ($CfLine -notmatch '^\s*#' -and $CfLine.Contains('filter=')) {
                Write-Fail "$Dir's own git attributes set a filter (filter=), which the update would trust. Remove it from $CfFile, then re-run."
            }
        }
    }
}

# Test-CloneHasLocalWork DIR - $true when the git clone at DIR holds work
# that replacing it with an archive would lose: a change to a tracked file, a
# stash, a commit on a branch that no remote has, or an untracked path inside
# a top-level name the clone tracks (its source tree). A git command that
# fails counts as local work, so a clone git cannot read is not replaced.
# Untracked top-level entries (the engine's backups\ and state\) are carried
# over by the swap, so they do not count (mirrors install.sh). The caller
# has run Assert-CloneConfig first, git runs here with $GitNoProgram (no
# fsmonitor program, and git status does not go into submodules), and git
# status takes none of its optional locks.
function Test-CloneHasLocalWork {
    param([string]$Dir)
    $prior = $ErrorActionPreference
    $priorLocks = $env:GIT_OPTIONAL_LOCKS
    $ErrorActionPreference = 'Continue'
    $env:GIT_OPTIONAL_LOCKS = '0'
    try {
        $LwChanged = @(& git @GitNoProgram -C $Dir status --porcelain --untracked-files=no 2>$null)
        if ($LASTEXITCODE -ne 0 -or $LwChanged.Count -gt 0) { return $true }
        $LwStashes = @(& git @GitNoProgram -C $Dir stash list 2>$null)
        if ($LASTEXITCODE -ne 0 -or $LwStashes.Count -gt 0) { return $true }
        $LwUnpushed = @(& git @GitNoProgram -C $Dir log --branches --not --remotes --oneline 2>$null)
        if ($LASTEXITCODE -ne 0 -or $LwUnpushed.Count -gt 0) { return $true }
        $LwTracked = @(& git @GitNoProgram -C $Dir -c core.quotePath=false ls-tree --name-only HEAD 2>$null | ForEach-Object { [string]$_ })
        if ($LASTEXITCODE -ne 0) { return $true }
        $LwStatus = @(& git @GitNoProgram -C $Dir -c core.quotePath=false status --porcelain 2>$null)
        if ($LASTEXITCODE -ne 0) { return $true }
    } finally {
        $env:GIT_OPTIONAL_LOCKS = $priorLocks
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
# check_clone_setup). git must work in it (Assert-CloneGit), and its own
# settings and attributes must pass Assert-CloneConfig; both run first,
# before any git command that reads the clone's index. It may hold no
# submodules: no folder where git keeps their repositories (.git\modules,
# or wherever git rev-parse --git-path modules points) and no gitlink in
# its index (git ls-files -s mode 160000). A release tree has none, and
# the settings and attributes of a repository inside the clone are not
# checked. Its work tree must be DIR itself, not one core.worktree or a
# .git file names: git must place DIR inside the work tree, at its top.
# And no tracked file may be marked assume-unchanged or skip-worktree (git
# ls-files -v prints a lower-case letter or S for one), since git then
# hides a change to it. Nothing here writes, so a dry run runs it too.
function Assert-CleanClone {
    param([string]$Dir)
    Assert-CloneGit $Dir
    Assert-CloneConfig $Dir
    $CcModules = Get-ClonePath $Dir 'modules'
    if ($CcModules -and (Test-Path -LiteralPath $CcModules -PathType Container)) {
        Write-Fail "$Dir keeps submodule repositories in $CcModules. A release tree has no submodules, and the update would run git inside them. Remove the submodules and $CcModules, then re-run."
    }
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $CcInside = "$(& git @GitNoProgram -C $Dir rev-parse --is-inside-work-tree 2>$null)"
        $CcInsideCode = $LASTEXITCODE
        $CcPrefix = "$(& git @GitNoProgram -C $Dir rev-parse --show-prefix 2>$null)"
        $CcPrefixCode = $LASTEXITCODE
        $CcStages = @(& git @GitNoProgram -C $Dir ls-files -s 2>$null | ForEach-Object { [string]$_ })
        $CcStagesCode = $LASTEXITCODE
        $CcFlags = @(& git @GitNoProgram -C $Dir ls-files -v 2>$null | ForEach-Object { [string]$_ })
        $CcFlagsCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($CcInsideCode -ne 0 -or $CcInside.Trim() -cne 'true' -or $CcPrefixCode -ne 0 -or $CcPrefix.Trim() -ne '') {
        Write-Fail "$Dir is not the work tree of its git clone (git finds no work tree there, as when its git config sets core.bare to true). Set core.bare to false, then re-run."
    }
    # An index git cannot read fails here as in install.sh, not only at the
    # checkout after the fetch, so a dry run stops where the real run would.
    if ($CcStagesCode -ne 0) {
        Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
    }
    foreach ($CcLine in $CcStages) {
        if ($CcLine.StartsWith('160000 ', [System.StringComparison]::Ordinal)) {
            $CcPath = @($CcLine -split "`t", 2)[-1]
            Write-Fail "$Dir holds a submodule at $CcPath (its index records a git repository there). A release tree has none, and the update would run git inside it. Remove the submodule from the clone, then re-run."
        }
    }
    if ($CcFlagsCode -ne 0) {
        Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
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
        # git status reads the clone's index, so the clone's own settings
        # are checked first, as for an update in place.
        Assert-CloneGit $ApothemHome
        Assert-CloneConfig $ApothemHome
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
            Invoke-GitOutsideRepository { & git init --quiet --bare $CkTagGit }
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
        try { Save-Download "$ApothemReleaseBase/$ApothemRef/$CkName" $CkArchive }
        catch { Write-Fail "Could not download $CkName from $ApothemReleaseBase/$ApothemRef ($($_.Exception.Message))" }
        try { Save-Download "$ApothemReleaseBase/$ApothemRef/SHA256SUMS" $CkSums }
        catch { Write-Fail "Could not download SHA256SUMS from $ApothemReleaseBase/$ApothemRef ($($_.Exception.Message))" }
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
            try { Save-Download "$ApothemReleaseBase/$ApothemRef/SHA256SUMS.cosign.bundle" $CkBundle }
            catch {
                try { Save-Download "$ApothemReleaseBase/$ApothemRef/SHA256SUMS.sig" $CkBundle }
                catch { Write-Fail "Could not download SHA256SUMS.cosign.bundle, or SHA256SUMS.sig as early releases name it, from $ApothemReleaseBase/$ApothemRef ($($_.Exception.Message)). Set APOTHEM_VERIFY=signature to check the release tag alone." }
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
            $CkExtract = Join-Path $CkParent (".apothem-extract.$(Split-Path -Leaf $ApothemHome)." + [System.Guid]::NewGuid().ToString('N'))
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
            $ClStage = Join-Path $ClParent (".apothem-clone.$(Split-Path -Leaf $ApothemHome)." + [System.Guid]::NewGuid().ToString('N'))
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
        $GitSafe = @($GitNoProgram + @('-c', "core.hooksPath=$NoHooksDir"))
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
            $ClTree = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ClTree)
            Invoke-GitOutsideRepository { & git clone --quiet --no-checkout $ApothemRepo $ClTree }
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
$PriorSafePath = $env:PYTHONSAFEPATH
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

    $env:PYTHONPATH = Get-SafePythonPath $EnginePyPath $PriorPyPath
    $env:PYTHONSAFEPATH = '1'
    & $PY -c $EngineProgram install --harness $Harness --profile $EngineProfile @EngineFlags
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
            & $PY -c $EngineProgram verify --harness $Harness
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
    $env:PYTHONSAFEPATH = $PriorSafePath
    if ($script:DryRunScratch -and (Test-Path -LiteralPath $script:DryRunScratch)) {
        Remove-Item -LiteralPath $script:DryRunScratch -Recurse -Force
    }
}

# Entry-point shim ------------------------------------------------------------
#
# Place an `apothem` command on PATH so the operator runs `apothem <command>`
# instead of the verbose self-contained form (PowerShell parity to install.sh).
# The shim is a `.cmd` (resolvable as a bare `apothem` via PATHEXT) that forwards
# to the bundled engine with the vendored PYTHONPATH, keeping the current
# folder off sys.path (PYTHONSAFEPATH=1 and $ShimProgram above), so a
# module in the folder it runs from never shadows the engine. PYTHONPATH
# holds the engine paths only; the caller's PYTHONPATH travels in
# APOTHEM_USER_PYTHONPATH, and $ShimProgram puts its full-path entries right
# after the engine paths (on sys.path and in the PYTHONPATH child processes
# get), leaving out the empty and relative ones Python would read as the
# current folder. It turns delayed expansion off, so a `!` in PYTHONPATH or
# in an argument passes through as written even under cmd /v:on. Its first
# rem line marks it as Apothem's for uninstall.ps1. It defaults into
# %LOCALAPPDATA%\Microsoft\WindowsApps - a user-owned directory already on the
# default Windows user PATH - so the shim resolves WITHOUT modifying PATH (the
# installer manages no PATH entry; see the self-contained invocation model).
# Override the directory with APOTHEM_BIN_DIR. Dry-run writes nothing. The banner
# advertises a bare `apothem` command only when its directory is on PATH;
# otherwise it prints how to add the directory and the shim's full path, or,
# with no shim, the self-contained form (mirrors install.sh), so it never
# promises a command the run did not resolve.
$ShimOnPath = $false
$ShimPlaced = $false
if (-not $DryRun) {
    $DefaultBinDir = [System.IO.Path]::Combine($env:LOCALAPPDATA, 'Microsoft', 'WindowsApps')
    $BinDir = if ($env:APOTHEM_BIN_DIR) { $env:APOTHEM_BIN_DIR } else { $DefaultBinDir }
    $Shim = Join-Path $BinDir 'apothem.cmd'
    try {
        New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
        $ShimBody = @"
@echo off
setlocal DisableDelayedExpansion
rem Apothem entry-point shim (generated by install.ps1).
rem The current folder is kept off sys.path, so its modules never shadow the engine.
rem Your PYTHONPATH's full-path entries follow the engine paths on sys.path
rem and in the PYTHONPATH child processes get; its empty and relative
rem entries are left out.
set "PYTHONSAFEPATH=1"
set "APOTHEM_USER_PYTHONPATH=%PYTHONPATH%"
set "PYTHONPATH=$EnginePyPath"
"$PY" -c "$ShimProgram" %*
"@
        Set-Content -LiteralPath $Shim -Value $ShimBody -Encoding ascii
        Write-Ok "Installed apothem command: $Shim"
        $ShimPlaced = $true

        # Resolve $BinDir against the current process PATH WITHOUT editing PATH.
        $Sep = [System.IO.Path]::PathSeparator
        $BinNorm = $BinDir.TrimEnd('\').ToLowerInvariant()
        $OnPath = @($env:Path.Split($Sep) | ForEach-Object { $_.TrimEnd('\').ToLowerInvariant() })
        if ($OnPath -contains $BinNorm) { $ShimOnPath = $true }
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
    # The self-contained form keeps the current folder off sys.path the way
    # the shim does: PYTHONSAFEPATH=1 and the -c program, never -m apothem.
    # Every path the banner prints goes through ConvertTo-PsLiteral, so one
    # holding a quote still pastes as a working command.
    if ($ShimPlaced) {
        Write-Info "Add $BinDir to your PATH, then run the guided setup: apothem quickstart"
        Write-Host "    `$env:Path = $(ConvertTo-PsLiteral "$BinDir;") + `$env:Path"
        $RunHeader = 'Until then, run the apothem command by its full path:'
        $RunCmd = "& $(ConvertTo-PsLiteral $Shim)"
    } else {
        $RunHeader = 'Run the engine from the bundled source (self-contained - no package installation; the current folder is kept off sys.path):'
        # A one-shot block: the variables it sets are put back as they were
        # when the command ends, so the session keeps its own values.
        $RunCmd = "& { `$PriorPath = `$env:PYTHONPATH; `$PriorSafe = `$env:PYTHONSAFEPATH; `$env:PYTHONSAFEPATH = '1'; `$env:PYTHONPATH = $(ConvertTo-PsLiteral $EnginePyPath); try { & $(ConvertTo-PsLiteral $PY) -c `"$EngineProgram`" @args } finally { `$env:PYTHONPATH = `$PriorPath; `$env:PYTHONSAFEPATH = `$PriorSafe } }"
    }
    Write-Host @"

$RunHeader
  $RunCmd <command>

Recommended first step - the guided setup (profile -> preview -> install):
  $RunCmd quickstart

Or run individual commands:
  $RunCmd harnesses list   # list harnesses
  $RunCmd doctor           # system health
  $RunCmd profile edit     # edit profile

Optional - once the 'apothem' command is on your PATH, enable <TAB> shell
completion (opt-in; appends to your profile):
  apothem completion powershell >> `$PROFILE   # or bash / zsh / fish

"@
}
} finally {
    # The caller's git variables, as they were before the run.
    foreach ($GitVar in @($SavedGitEnv.Keys)) {
        if ($null -eq $SavedGitEnv[$GitVar]) {
            Remove-Item -LiteralPath "Env:$GitVar" -ErrorAction SilentlyContinue
        } else {
            Set-Item -LiteralPath "Env:$GitVar" -Value $SavedGitEnv[$GitVar]
        }
    }
}
} finally {
    Unlock-ApothemHome
}
