# SPDX-License-Identifier: MIT

# Purpose: Re-fetch the bundled Apothem source (self-contained - no package
#          installation) and re-materialize harness config (PowerShell
#          parity to update.sh).
# Usage:   pwsh -NoProfile -File scripts/installer/update.ps1
# Contract: When the engine ends as partial (exit code 2: it left some
#           files as they are, or it stopped after it had written some),
#           the update still finishes, then ends with code 2 (see the
#           end of this script).
#
# Trust model (tag-pinned, verified-by-default; PowerShell parity to
# update.sh): with no APOTHEM_REF set, the updater resolves the latest
# vMAJOR.MINOR.PATCH release tag and checks THAT out - the moving `main` branch
# is no longer the default. The clone is fetched and the tag is checked before
# anything is checked out, so a failed check leaves the clone where it was:
# `git verify-tag` must pass, the signature must be made by the maintainer key
# SECURITY.md publishes (fingerprint 5C8998F9F241720445D3F28B70396FED9C634163),
# and the signed tag object must name itself as that release. Only then is
# the tag's commit checked out, without --force: a change to a tracked file
# stops the update before the checkout, and other local changes the
# checkout would overwrite stop it too, instead of being lost. An unsigned /
# tampered / missing-signature tag, or one signed by another key, ABORTS
# before any config is written unless APOTHEM_ALLOW_UNVERIFIED=1 downgrades
# the abort to a loud warning; a tag the maintainer signed for another
# release and re-pointed here aborts either way. Because
# APOTHEM_ALLOW_UNVERIFIED=1 lets an unsigned tag, or one signed by another
# key, through, the re-pointed-tag check protects only tags that carry the
# maintainer key's signature, and the tag's commit is checked out by its ID,
# so a tag ref moved after the check changes nothing. Before the clone is
# fetched it is checked: git must work in it (a clone another user owns is
# refused), its own git config (its config or config.worktree file) may set
# only the keys on $CloneConfigAllow (the keys git clone and git init write,
# and a few that name no program, file or address), its info\attributes
# may not name a filter or diff driver, it may not borrow objects from
# another repository, it may hold no submodules and no git repository
# git does not track, no tracked file may be marked assume-unchanged or
# skip-worktree, its work tree must be APOTHEM_HOME itself, no
# .gitattributes file there may be untracked, differ from the index, or
# have a committed copy git cannot read or that names a filter or diff
# driver, and no file under src may be untracked. After the checkout
# the Python cache folders under src are removed. Every git command on
# the clone runs with its hooks, its fsmonitor, the pager and automatic
# maintenance off, with only the file, git, http, https and ssh
# transports, with no fetch of a missing object, and without going into
# submodules, and a clone of something
# other than Apothem is not updated. One install, update or uninstall runs
# at a time: each holds <APOTHEM_HOME>.lock while it runs, and a second run
# stops. git and gpg are the ones found on PATH; they, and the user's own
# global and system git config, are trusted as found.
# APOTHEM_REF=main checks out the branch on request (it needs
# APOTHEM_ALLOW_UNVERIFIED=1). The APOTHEM_SOURCE local-checkout path fetches
# nothing and skips verification. An install made from a release archive
# (install.ps1's cosign or checksum path) has no git clone to update; re-run
# install.ps1.
#
# Environment overrides:
#   APOTHEM_HOME      Cloned source location (default: $HOME/.apothem)
#   APOTHEM_REPO      Git remote (default: https://github.com/ahmed-g-gad/apothem).
#                     A value that starts with - is refused.
#   APOTHEM_REF       Git ref to update to. Unset = resolve the latest release
#                     tag; set to a tag to pin, or "main" for the moving branch.
#   APOTHEM_ALLOW_UNVERIFIED If "1", downgrade a failed tag-signature check to a
#                     warning and proceed, and allow a ref that is not a
#                     release tag. A re-pointed tag still aborts, but since
#                     an unsigned tag, or one signed by another key, gets
#                     through, that check protects only tags that carry the
#                     maintainer key's signature.
#   APOTHEM_SOURCE    Explicit local source tree to re-materialize from (skips
#                     tag resolution and verification)
#   APOTHEM_HARNESS   Harness to update (default: claude-code)
#   APOTHEM_PROFILE   Path to shared profile YAML
#   APOTHEM_AUTO_INSTALL_DEPS  If "1", install missing click / rich
#                     prerequisites automatically (pip) without prompting.

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# A caller's $PSNativeCommandUseErrorActionPreference = $true (PowerShell
# 7.4+) would make any non-zero exit code of a program stop the run, the
# engine's partial exit code 2 among them, so the run turns it off. A piped
# run shares the caller's scope, so the caller's value is put back as the
# run ends: by the finally block at the end, or by this trap when the run
# stops on an error (before it takes the install lock, too). The trap's
# own scope is a child of the run's, hence -Scope 1.
$HadNativeErrorPref = Test-Path -LiteralPath 'Variable:PSNativeCommandUseErrorActionPreference'
$SavedNativeErrorPref = if ($HadNativeErrorPref) { $PSNativeCommandUseErrorActionPreference } else { $null }
$PSNativeCommandUseErrorActionPreference = $false
trap {
    if ($HadNativeErrorPref) { Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $SavedNativeErrorPref -Scope 1 } else { Remove-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -ErrorAction SilentlyContinue }
    break
}

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
# A trailing separator would put the lock beside APOTHEM_HOME inside it
# instead (install.ps1 trims it the same way); a drive root keeps its
# separator.
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
$Harness     = if ($env:APOTHEM_HARNESS) { $env:APOTHEM_HARNESS } else { 'claude-code' }
$ApothemProfile = if ($env:APOTHEM_PROFILE) { $env:APOTHEM_PROFILE } else { [System.IO.Path]::Combine($HOME, '.config', 'apothem', 'profile.yaml') }
# The primary-key fingerprint SECURITY.md publishes; mirrors install.ps1.
$MaintainerFingerprint = '5C8998F9F241720445D3F28B70396FED9C634163'

# CLI prerequisites; `yaml` + `jsonschema` ship vendored inside the bundled
# tree (src/apothem/_vendor), so only click + rich come from the host.
$RuntimeDeps = @('click', 'rich')
$PrereqDoc = 'https://apothem.ahmedgad.com/docs/architecture/vendoring-strategy/'

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

# A git variable set in the calling shell would point every git command
# below at another repository, work tree, index or object store, add
# settings, read its configuration from other files or attributes from
# another tree, use another git program, or swap objects through replace
# refs, so the run clears them once it holds the install lock (see the
# start of the run, below;
# mirrors update.sh). It also sets GIT_NO_LAZY_FETCH=1, so git never starts
# a fetch of its own for an object the clone lacks (the clone's settings
# would shape that fetch), GIT_ALLOW_PROTOCOL to the five transports
# $GitNoProgram allows, since a value from the calling shell would win
# over those settings, and GIT_ATTR_NOSYSTEM=1, so git reads no system
# attributes file (see $GitNoProgram). Run by irm | iex, the script
# shares the caller's session, so the caller's values are put back as
# the run ends, however
# it ends. GIT_CONFIG_NOSYSTEM is left as the caller set it: it only
# stops git reading the system configuration. git still reads the user's
# own global and system configuration from the places it always looks,
# and git, gpg and cosign are the ones PATH finds. An APOTHEM_REPO that
# starts with - would reach git as an option.
if ($ApothemRepo.StartsWith('-')) {
    Write-Fail "APOTHEM_REPO must be a repository URL or path, not an option: $ApothemRepo"
}
# git runs ls-remote from an empty folder (Invoke-GitOutsideRepository),
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
# instead of leaving the file out, reads attributes from the clone's own
# files only (attr.tree and core.attributesFile are emptied, and the run
# sets GIT_ATTR_NOSYSTEM: a user's own attr.tree would name another tree,
# and a macro in the user's or the system's attributes file could name a
# filter the clone's files do not show), and does not go into
# submodules: fetch and checkout leave them alone, and diff and status
# skip them (diff.ignoreSubmodules=all),
# so the settings of a repository nested in the clone, which nothing
# here checks, are never read. An update in place refuses a clone that
# holds submodules anyway (Assert-CleanClone). The calls of an update
# (fetch, verify-tag, cat-file, checkout and the rest) take $GitSafe,
# which adds core.hooksPath pointing at an empty folder made for the
# run, so none of the clone's hooks runs either. core.sshCommand is left
# alone: setting it would also override the user's own GIT_SSH (mirrors
# update.sh's cgit).
$GitNoProgram = @('--no-pager', '-c', 'core.fsmonitor=', '-c', 'protocol.ext.allow=never', '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=always', '-c', 'protocol.git.allow=always', '-c', 'protocol.http.allow=always', '-c', 'protocol.https.allow=always', '-c', 'protocol.ssh.allow=always', '-c', 'submodule.recurse=false', '-c', 'fetch.recurseSubmodules=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'diff.ignoreSubmodules=all', '-c', 'core.longpaths=true', '-c', 'attr.tree=', '-c', 'core.attributesFile=')
$GitSafe = @()

# Every git call that reads or writes the clone's files (the fetch, the
# checkout and the checks around it) takes these arguments. A release can
# hold paths longer than Windows' 260-character limit at APOTHEM_HOME, which
# Git for Windows writes and reads only with core.longpaths set; git
# elsewhere ignores the setting (mirrors update.sh's cgit).
$GitLongPaths = @('-c', 'core.longpaths=true')

# The current folder must never shadow the engine's modules (mirrors
# update.sh). Python puts '' (the working directory) first on sys.path for
# `-c`, and `-m` puts the working directory there, so a click.py, rich\ or
# apothem\ in the folder the updater runs from would run
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

# Test-AbsolutePath PATH - $true when PATH is a full path. On Windows that is
# a drive letter and a separator (X:\ or X:/) or two separators (a \\server
# or //server share); elsewhere a leading /. A drive-relative C:x or a
# rooted \x is not. Every launcher uses this one rule.
function Test-AbsolutePath {
    param([string]$Path)
    if (-not $Path) { return $false }
    if ([System.IO.Path]::PathSeparator -eq ';') { return ($Path -match '^([A-Za-z]:[\\/]|[\\/]{2})') }
    return $Path.StartsWith('/')
}

# Get-SafePythonPath LEAD USER - the PYTHONPATH a Python start gets: LEAD
# (the engine's paths, or nothing) followed by the entries of USER (the
# caller's PYTHONPATH) that are full paths. Python reads an empty entry, or a
# relative one such as `.`, as the current folder before any -c program runs
# and whatever PYTHONSAFEPATH says, so a sitecustomize.py there would run;
# those entries are dropped (mirrors update.sh). $null when nothing is left.
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
# the folder removed afterwards (mirrors update.sh). Paths BLOCK passes to
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

# Test-PythonImport INTERPRETER MODULE - return $true when MODULE imports under
# INTERPRETER, $false otherwise. Localizes $ErrorActionPreference to 'Continue'
# and discards all streams so a missing-module traceback never becomes a
# terminating NativeCommandError (the trap that aborts a prerequisite probe
# under $ErrorActionPreference='Stop').
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
    $raw = Invoke-GitOutsideRepository { param($LsRepo) & git ls-remote --tags $LsRepo 2>$null } @($Repo)
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    $tags = @()
    foreach ($line in $raw) {
        # Each line is "<sha>\trefs/tags/<tag>"; annotated tags also emit a
        # "<tag>^{}" peel line. Match the final-release shape and strip "^{}".
        # -cmatch keeps the match case-sensitive, as update.sh's sed filter
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
        $Lines = & git @GitLongPaths @GitSafe -C $Dir verify-tag --raw $Ref 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    $script:VerifyTagOutput = ($Lines | ForEach-Object { $_.ToString() }) -join "`n"
    return ($code -eq 0)
}

# Test-TagSignedByMaintainer / Test-TagSignedByOtherKey mirror install.ps1,
# which documents why a valid signature alone is not enough.
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

function Test-TagSignedByOtherKey {
    if ($script:VerifyTagOutput -notmatch '(?m)^\s*\[GNUPG:\] VALIDSIG ') { return $false }
    return (-not (Test-TagSignedByMaintainer))
}

# Get-TagSigner - the primary-key fingerprints, other than
# $MaintainerFingerprint, of the valid signatures in the captured status
# lines, each once and upper-case, as the message names them: "the key X",
# or "the keys X, Y" (mirrors update.sh's verify_tag_other_keys and
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
# signing public key is absent from the local keyring, so the signature was
# not checked (GnuPG's NO_PUBKEY status), $false for any other failure
# (unsigned tag, BAD signature).
function Test-VerifyTagMissingKey {
    return ($script:VerifyTagOutput -match '\[GNUPG:\] NO_PUBKEY ')
}

# Test-ReleaseTag REF - return $true when REF is a vMAJOR.MINOR.PATCH release
# tag (the verifiable shape), $false otherwise (a branch, a SHA, a pre-release).
# -cmatch keeps the match case-sensitive, as update.sh's is_release_tag is:
# -match ignores case and would also accept V1.2.3. \z matches only at the
# end of the string: $ also matches before a final newline, so it would
# accept "v1.2.3`n", which is_release_tag rejects.
function Test-ReleaseTag {
    param([string]$Ref)
    return ($Ref -cmatch '^v[0-9]+\.[0-9]+\.[0-9]+\z')
}

# $CloneConfigAllow - the only keys a clone's own git config (its config
# and config.worktree files) may set for an update to go on: the keys
# git clone and git init write on any git 2.x and system, the branch
# keys checkout and editors write, the user's name and email, and the
# keys git maintenance and git pull's own advice write. None of them
# names a program, a file or folder git reads settings, hooks,
# attributes or objects from, a URL rewrite, or another work tree. No
# partial-clone key is on it: an installer clone is a full clone, and git
# fetches an object a partial clone lacks through a fetch the clone's
# settings shape (the run also sets GIT_NO_LAZY_FETCH). The value of
# branch.*.remote and branch.*.pushremote must be origin
# (Assert-CloneConfig).
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
    'extensions.objectformat'
    'extensions.refstorage'
    'extensions.worktreeconfig'
    'remote.origin.url'
    'remote.origin.fetch'
    'remote.origin.tagopt'
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
# (mirrors update.sh).
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
# the clone at DIR (mirrors update.sh's clone_git_ok). git refuses a
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
# install.sh's git_path). git writes the path in UTF-8, so it is read as
# UTF-8: in the console's code page a non-ASCII folder name would read as
# a path that does not exist, and the checks of that file would be skipped.
function Get-ClonePath {
    param([string]$Dir, [string]$Name)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $GpEncoding = $null
    try { $GpEncoding = [Console]::OutputEncoding; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { $GpEncoding = $null }
    try {
        $GpPath = "$(& git @GitNoProgram -C $Dir rev-parse --git-path $Name 2>$null)"
        $GpCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
        if ($GpEncoding) { try { [Console]::OutputEncoding = $GpEncoding } catch { $GpEncoding = $null } }
    }
    if ($GpCode -ne 0 -or -not $GpPath) { return $null }
    if ($GpPath -match '^(/|[A-Za-z]:[\\/])') { return $GpPath }
    return "$Dir/$GpPath"
}

# Assert-ClonePlainFile DIR FILE - stop when FILE, in the git folder of
# the clone at DIR, exists or is a link but is not a plain file: from a
# pipe git could read other text than the check read (mirrors install.sh's
# need_plain_file). On Windows a link counts as not plain; elsewhere test -f
# decides, following links as install.sh does.
function Assert-ClonePlainFile {
    param([string]$Dir, [string]$File)
    $PfItem = Get-Item -LiteralPath $File -Force -ErrorAction SilentlyContinue
    if (-not $PfItem) { return }
    if ((Get-Variable IsWindows -ValueOnly -ErrorAction SilentlyContinue) -ne $false) {
        $PfPlain = $PfItem -is [System.IO.FileInfo] -and ($PfItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0
    } else {
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & test -f $File
            $PfPlain = $LASTEXITCODE -eq 0
        } finally {
            $ErrorActionPreference = $prior
        }
    }
    if (-not $PfPlain) {
        Write-Fail "$Dir's git folder holds $File, which is not a plain file, so git could read other text from it than this check reads. Make it a plain file or remove it, then re-run."
    }
}

# Test-AttributeDriver LINES - $true when git attributes text, given as
# lines, names a filter or diff driver (filter= or diff=; git diff runs a
# diff driver's textconv) outside comments. NUL characters are dropped (as
# install.sh's sets_driver does), and a line is a comment only where #
# follows nothing but spaces, tabs or CR.
function Test-AttributeDriver {
    param([string[]]$Lines)
    foreach ($TfLine in $Lines) {
        $TfText = $TfLine.Replace([string][char]0, '')
        if ($TfText -cnotmatch '^[ \t\r]*#' -and $TfText -cmatch '(filter|diff)=') { return $true }
    }
    return $false
}

# Assert-CloneConfig DIR - stop when the clone's own git config at DIR (its
# config file or, for a worktree, its config.worktree) has a key whose
# name holds a line break, sets a key that is not on $CloneConfigAllow
# (Test-AllowedConfigKey), sets extensions.refStorage to anything but
# files or reftable (a value of another form names a folder git reads
# refs from), or sets branch.<name>.remote or branch.<name>.pushremote to
# anything but origin; when the clone borrows objects from another
# repository (objects\info\alternates or http-alternates); or when its
# info\attributes names a filter or diff driver (Test-AttributeDriver),
# whose program git runs while it reads the clone (mirrors update.sh's
# check_clone_config). Each file is listed alone, so
# its include lines are not followed (include is not on the list), and
# each name and value is read up to the NUL byte that ends it:
# PowerShell ends a line of a program's output at CR as well as LF, and
# git keeps a CR inside a quoted subsection, so a name read line by line
# could pass as two allowed ones. The first name in file order that fails
# stops the run, config first, and the message names it and its file.
# This runs before any git command that reads the clone's index or
# objects or could run one of its programs.
function Assert-CloneConfig {
    param([string]$Dir)
    foreach ($CfName in @('config', 'config.worktree')) {
        $CfFile = Get-ClonePath $Dir $CfName
        if (-not $CfFile) { Write-Fail "Could not read the git config of $Dir." }
        Assert-ClonePlainFile $Dir $CfFile
        if (-not (Test-Path -LiteralPath $CfFile)) { continue }
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $CfNames = (@(& git @GitNoProgram -C $Dir config --file $CfFile --null --name-only --list 2>$null | ForEach-Object { [string]$_ }) -join "`n")
            $CfCode = $LASTEXITCODE
            $CfRecords = (@(& git @GitNoProgram -C $Dir config --file $CfFile --null --list 2>$null | ForEach-Object { [string]$_ }) -join "`n")
            $CfRecordCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        $CfKeys = $CfNames.Split([char]0)
        $CfRecordParts = $CfRecords.Split([char]0)
        if ($CfCode -ne 0 -or $CfRecordCode -ne 0 -or $CfKeys[-1] -ne '' -or $CfRecordParts[-1] -ne '') {
            Write-Fail "Could not read the git config of $Dir at $CfFile."
        }
        $CfKeys = @($CfKeys | Select-Object -First ($CfKeys.Count - 1))
        # git never puts a line feed in a name, so a line break in one was
        # a CR. The name is not printed.
        foreach ($CfKey in $CfKeys) {
            if ($CfKey.Contains("`n") -or $CfKey.Contains("`r")) {
                Write-Fail "$Dir's own git config has a setting whose name holds a line break, which an update in place does not accept. Remove it from $CfFile, then re-run."
            }
        }
        # Each record is a name, then a line break and its value (none for
        # a key with no value). Every value of a branch's remote and
        # pushremote must read exactly origin: another, such as . for the
        # clone itself, would point a fetch git starts on its own elsewhere.
        $CfBadValue = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
        foreach ($CfRecord in @($CfRecordParts | Select-Object -First ($CfRecordParts.Count - 1))) {
            $CfBreak = $CfRecord.IndexOf("`n")
            $CfRecordKey = if ($CfBreak -ge 0) { $CfRecord.Substring(0, $CfBreak) } else { $CfRecord }
            $CfFirst = $CfRecordKey.IndexOf('.')
            $CfLast = $CfRecordKey.LastIndexOf('.')
            if ($CfFirst -lt 1 -or $CfLast -le $CfFirst + 1) { continue }
            if ($CfRecordKey.Substring(0, $CfFirst).ToLowerInvariant() -cne 'branch') { continue }
            if (@('remote', 'pushremote') -cnotcontains $CfRecordKey.Substring($CfLast + 1).ToLowerInvariant()) { continue }
            if ($CfBreak -lt 0 -or -not [string]::Equals($CfRecord.Substring($CfBreak + 1), 'origin', [System.StringComparison]::Ordinal)) {
                [void]$CfBadValue.Add($CfRecordKey)
            }
        }
        foreach ($CfKey in $CfKeys) {
            $CfBad = (-not (Test-AllowedConfigKey $CfKey)) -or $CfBadValue.Contains($CfKey)
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
    foreach ($CfName in @('objects/info/alternates', 'objects/info/http-alternates')) {
        $CfFile = Get-ClonePath $Dir $CfName
        if (-not $CfFile) { Write-Fail "Could not read the git config of $Dir." }
        if (Test-Path -LiteralPath $CfFile) {
            Write-Fail "$Dir borrows objects from another repository ($CfFile names it). A release clone does not, and the update would run git in that repository under settings nothing here checks. Run 'git -C $Dir repack -a -d' to copy the objects in, remove $CfFile, then re-run."
        }
    }
    $CfFile = Get-ClonePath $Dir 'info/attributes'
    if (-not $CfFile) { Write-Fail "Could not read the git config of $Dir." }
    Assert-ClonePlainFile $Dir $CfFile
    if (Test-Path -LiteralPath $CfFile -PathType Leaf) {
        # Read as git reads it, byte by byte, lines ended by LF only. Read
        # as text, a UTF-16 byte-order mark would turn every line into
        # other characters while git still applies them.
        try {
            $CfBytes = [System.IO.File]::ReadAllBytes($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CfFile))
            $CfLines = @([System.Text.Encoding]::GetEncoding(28591).GetString($CfBytes).Split([char]10))
        } catch {
            $CfLines = @()
        }
        if (Test-AttributeDriver $CfLines) {
            Write-Fail "$Dir's own git attributes name a filter or diff driver (filter= or diff=), which the update would trust. Remove the setting from $CfFile, then re-run."
        }
    }
}

# Get-CloneRecord DIR ARGS - run git ARGS (a listing with -z) in the clone
# at DIR and return its records, each ended by a NUL byte, in git's order;
# a line break inside one reads as LF. git writes paths in UTF-8, so the
# listing is read as UTF-8 (see Get-ClonePath). A failed git command stops
# the run (mirrors install.sh's git_z).
function Get-CloneRecord {
    param([string]$Dir, [string[]]$GitArgs)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $GrEncoding = $null
    try { $GrEncoding = [Console]::OutputEncoding; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { $GrEncoding = $null }
    try {
        $GrText = (@(& git @GitNoProgram -C $Dir @GitArgs 2>$null | ForEach-Object { [string]$_ }) -join "`n")
        $GrCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
        if ($GrEncoding) { try { [Console]::OutputEncoding = $GrEncoding } catch { $GrEncoding = $null } }
    }
    $GrParts = $GrText.Split([char]0)
    if ($GrCode -ne 0 -or $GrParts[-1] -ne '') {
        Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
    }
    if ($GrParts.Count -gt 1) { return $GrParts[0..($GrParts.Count - 2)] }
}

# Read-CloneBlob DIR ID - the lines of the object ID in the clone at DIR
# (git cat-file blob, which runs no filter), read from git's output as
# bytes and ended by LF only, as git reads attributes: PowerShell's reader
# of a program's output also ends a line at a lone CR, which would hide
# the rest of a line from Test-AttributeDriver. git is the program `& git`
# runs, through an alias to it; when the first git is a function or a
# script (a wrapper in a profile, say), which cannot be read from as
# bytes, it is the first git program on PATH, and with none the run stops
# with a message that says so. The bytes must hash to ID as git hashes a
# blob (SHA-1, or SHA-256 for a 64-digit ID): git does not check that as
# it reads an object, so a replaced object file could hand the check
# other text than the committed one (mirrors install.sh's
# check_clone_attributes). Any other failure, git's own included, gives
# $null; an empty blob gives one empty line.
function Read-CloneBlob {
    param([string]$Dir, [string]$Id)
    $RbGit = $null
    try {
        $RbGit = Get-Command git -ErrorAction Stop | Select-Object -First 1
        if ($RbGit -is [System.Management.Automation.AliasInfo]) { $RbGit = $RbGit.ResolvedCommand }
        if ($RbGit -isnot [System.Management.Automation.ApplicationInfo]) { $RbGit = Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1 }
    } catch {
        $RbGit = $null
    }
    if ($RbGit -isnot [System.Management.Automation.ApplicationInfo]) {
        Write-Fail "Could not run git to read the committed .gitattributes files in $Dir. In this PowerShell session, git is a function or a script, and no git program is on PATH. Add git's folder to PATH, then re-run."
    }
    $RbRun = $null
    $RbBytes = $null
    $RbHash = $null
    try {
        $RbArgs = @($GitNoProgram + @('-C', $Dir, 'cat-file', 'blob', $Id))
        $RbInfo = [System.Diagnostics.ProcessStartInfo]::new($RbGit.Path)
        if ($RbInfo.PSObject.Properties['ArgumentList']) {
            foreach ($RbArg in $RbArgs) { $RbInfo.ArgumentList.Add($RbArg) }
        } else {
            # Windows PowerShell's .NET has no ArgumentList: each argument
            # is quoted as the C runtime reads a command line.
            $RbInfo.Arguments = @($RbArgs | ForEach-Object { if ($_ -eq '' -or $_ -match '[\s"]') { '"' + ($_ -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"' } else { $_ } }) -join ' '
        }
        # git -C picks the clone; git starts in it too, so a current folder
        # that is gone does not matter.
        $RbInfo.WorkingDirectory = $Dir
        $RbInfo.UseShellExecute = $false
        $RbInfo.RedirectStandardOutput = $true
        $RbInfo.RedirectStandardError = $true
        $RbInfo.CreateNoWindow = $true
        $RbRun = [System.Diagnostics.Process]::Start($RbInfo)
        $RbError = $RbRun.StandardError.ReadToEndAsync()
        $RbBytes = [System.IO.MemoryStream]::new()
        $RbRun.StandardOutput.BaseStream.CopyTo($RbBytes)
        $RbRun.WaitForExit()
        [void]$RbError.Result
        if ($RbRun.ExitCode -ne 0) { return $null }
        $RbData = $RbBytes.ToArray()
        $RbHash = if ($Id.Length -eq 64) { [System.Security.Cryptography.SHA256]::Create() } else { [System.Security.Cryptography.SHA1]::Create() }
        $RbHead = [System.Text.Encoding]::ASCII.GetBytes("blob $($RbData.Length)`0")
        [void]$RbHash.TransformBlock($RbHead, 0, $RbHead.Length, $null, 0)
        [void]$RbHash.TransformFinalBlock($RbData, 0, $RbData.Length)
        if ((-join @($RbHash.Hash | ForEach-Object { $_.ToString('x2') })) -cne $Id) { return $null }
        # The comma keeps the lines one array, however few there are.
        return , ([System.Text.Encoding]::GetEncoding(28591).GetString($RbData).Split([char]10))
    } catch {
        return $null
    } finally {
        if ($RbRun) { $RbRun.Dispose() }
        if ($RbBytes) { $RbBytes.Dispose() }
        if ($RbHash) { $RbHash.Dispose() }
    }
}

# Assert-CloneAttributeFile DIR - stop when the work tree of the clone at DIR
# holds a .gitattributes file (in any ASCII case) that git does not
# track, or a tracked one that differs from HEAD or the index, is not a
# plain file, whose index copy git cannot read (or reads as bytes that do
# not hash to its ID), or whose index or work-tree copy names a filter or
# diff driver (each read as bytes; the index copy with git cat-file,
# which runs no filter: Read-CloneBlob): git status, diff and checkout
# would apply it, and it can name a driver the user's own config defines.
# Tracked files come first, in index order, then untracked ones, ignored
# files and files in untracked folders included; last, a git repository
# git does not track (git lists it as one path ending in /, and nothing
# inside it), whose attributes git would apply to what a release adds
# there. Untracked paths in one of the engine's data folders (backups,
# state, plans, memory, contexts, learning, providers), where no release
# writes, are skipped when git tracks nothing in that folder, its name in
# any ASCII case. A tracked file missing from the work tree is left to
# the check for changes (git then reads the index copy). Files are
# compared without filters (git hash-object --no-filters), so nothing
# here runs one (mirrors install.sh's check_clone_attributes).
function Assert-CloneAttributeFile {
    param([string]$Dir)
    $CaIndex = @(Get-CloneRecord $Dir @('ls-files', '-s', '-z'))
    $CaHead = @(Get-CloneRecord $Dir @('ls-tree', '-r', '-z', 'HEAD'))
    $CaOther = @(Get-CloneRecord $Dir @('ls-files', '-o', '-z'))
    $CaTracked = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($CaRecord in @($CaHead + $CaIndex)) {
        $CaTop = $CaRecord.Substring($CaRecord.IndexOf("`t") + 1).Split('/')[0]
        [void]$CaTracked.Add([regex]::Replace($CaTop, '[A-Z]', { param($CaLetter) $CaLetter.Value.ToLowerInvariant() }))
    }
    $CaOther = @($CaOther | Where-Object { $CaTracked.Contains($_.Split('/')[0]) -or @('backups', 'state', 'plans', 'memory', 'contexts', 'learning', 'providers') -cnotcontains $_.Split('/')[0] })
    $CaIsAttributes = { param([string]$Path) $Path.Substring($Path.LastIndexOf('/') + 1) -cmatch '^\.[Gg][Ii][Tt][Aa][Tt][Tt][Rr][Ii][Bb][Uu][Tt][Ee][Ss]\z' }
    $CaChanged = { param([string]$Path) Write-Fail "$Dir has a changed .gitattributes file at $Dir/$Path. git would apply it while it reads the clone. Undo the change, then re-run." }
    $CaDriver = { param([string]$Path) Write-Fail "$Dir has a .gitattributes file at $Dir/$Path that names a filter or diff driver (filter= or diff=). git would run that driver while it reads the clone. Remove the setting and commit that change, then re-run." }
    # HEAD's entries read <mode> <type> <id><TAB><path>, the index's
    # <mode> <id> <stage><TAB><path>.
    $CaHeadEntry = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    foreach ($CaRecord in $CaHead) {
        $CaTab = $CaRecord.IndexOf("`t")
        if ($CaTab -lt 0 -or -not (& $CaIsAttributes $CaRecord.Substring($CaTab + 1))) { continue }
        $CaField = $CaRecord.Substring(0, $CaTab).Split(' ')
        $CaHeadEntry[$CaRecord.Substring($CaTab + 1)] = "$($CaField[0]) $($CaField[-1])"
    }
    $CaSeen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($CaRecord in $CaIndex) {
        $CaTab = $CaRecord.IndexOf("`t")
        if ($CaTab -lt 0) { continue }
        $CaPath = $CaRecord.Substring($CaTab + 1)
        if (-not (& $CaIsAttributes $CaPath) -or -not $CaSeen.Add($CaPath)) { continue }
        $CaField = $CaRecord.Substring(0, $CaTab).Split(' ')
        $CaWant = $null
        [void]$CaHeadEntry.TryGetValue($CaPath, [ref]$CaWant)
        if ($CaField[-1] -cne '0' -or $CaWant -cne "$($CaField[0]) $($CaField[1])" -or $CaPath.Contains("`n")) { & $CaChanged $CaPath }
        $CaLines = Read-CloneBlob $Dir $CaField[1]
        if ($null -eq $CaLines) {
            Write-Fail "$Dir has a .gitattributes file at $Dir/$CaPath whose committed copy git could not read. Repair the clone or move it aside, then re-run."
        }
        if (Test-AttributeDriver $CaLines) { & $CaDriver $CaPath }
        try {
            $CaAttr = [System.IO.File]::GetAttributes("$Dir/$CaPath")
        } catch [System.IO.FileNotFoundException], [System.IO.DirectoryNotFoundException] {
            continue
        } catch {
            & $CaChanged $CaPath
        }
        if (($CaAttr -band ([System.IO.FileAttributes]::ReparsePoint -bor [System.IO.FileAttributes]::Directory)) -ne 0) { & $CaChanged $CaPath }
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $CaId = "$(& git @GitNoProgram -C $Dir hash-object --no-filters -- $CaPath 2>$null)".Trim()
            $CaIdCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($CaIdCode -ne 0 -or $CaId -cne $CaField[1]) { & $CaChanged $CaPath }
        # git applies the work-tree copy, so its own bytes are read too
        # (lines ended by LF only): only the ID ties them to the index copy
        # read above.
        try {
            $CaWork = [System.Text.Encoding]::GetEncoding(28591).GetString([System.IO.File]::ReadAllBytes("$Dir/$CaPath")).Split([char]10)
        } catch {
            $CaWork = @()
        }
        if (Test-AttributeDriver $CaWork) { & $CaDriver $CaPath }
    }
    foreach ($CaPath in $CaHeadEntry.Keys) {
        if (-not $CaSeen.Contains($CaPath)) { & $CaChanged $CaPath }
    }
    foreach ($CaPath in $CaOther) {
        if (& $CaIsAttributes $CaPath) {
            Write-Fail "$Dir has a .gitattributes file that git does not track, at $Dir/$CaPath. git would apply it while it reads the clone. Remove it, then re-run."
        }
    }
    foreach ($CaPath in $CaOther) {
        if ($CaPath.EndsWith('/', [System.StringComparison]::Ordinal)) {
            Write-Fail "$Dir holds a git repository that git does not track, at $Dir/$($CaPath.Substring(0, $CaPath.Length - 1)). A release tree has none, and git would read the attributes in it. Move it out of $Dir, then re-run."
        }
    }
}

# Assert-SourceTracked DIR - stop, listing them, when the clone at DIR
# holds paths under src (in any ASCII case: a file system that ignores
# case finds Src as src) that git does not track (ignored files and a
# nested repository included), other than files inside a __pycache__
# folder, which Remove-SourceCache removes: the engine runs with src on
# its path and could load them. Before the fetch these are the files the
# engine would find after the checkout, which writes only tracked files,
# so a refusal here leaves the clone as it was (mirrors update.sh's
# check_clone_src).
function Assert-SourceTracked {
    param([string]$Dir)
    $StFound = [System.Collections.Generic.List[string]]::new()
    foreach ($StPath in @(Get-CloneRecord $Dir @('ls-files', '-o', '-z'))) {
        if ($StPath -cnotmatch '^[Ss][Rr][Cc]/') { continue }
        $StParts = $StPath.TrimEnd('/').Split('/')
        if (@($StParts[0..($StParts.Count - 2)] | Where-Object { $_ -ceq '__pycache__' }).Count -gt 0) { continue }
        $StFound.Add($StPath)
    }
    if ($StFound.Count -eq 0) { return }
    [Console]::Error.WriteLine("  x $Dir has files under src that git does not track, and the engine could load them:")
    foreach ($StPath in @($StFound | Select-Object -First 20)) { [Console]::Error.WriteLine("    $Dir/$StPath") }
    if ($StFound.Count -gt 20) { [Console]::Error.WriteLine("    and $($StFound.Count - 20) more") }
    Write-Fail "Nothing was changed. Move these files out of $Dir/src, then re-run."
}

# Remove-SourceCache DIR - remove every __pycache__ folder under DIR\src
# after the checkout, before the engine first runs, so no bytecode the
# release did not make loads (mirrors update.sh's remove_source_caches).
# The walk enters no link or junction: a __pycache__ that is one loses the
# link only, and so does one inside a cache folder, so nothing it leads to
# is removed. Each entry is removed on its own, deepest first: Windows
# PowerShell 5.1's Remove-Item -Recurse follows a junction inside the
# folder, and .NET's recursive Directory.Delete stops at one.
function Remove-SourceCache {
    param([string]$Dir)
    $RsLink = [System.IO.FileAttributes]::ReparsePoint
    $RsRoot = [System.IO.Path]::Combine($Dir, 'src')
    try {
        # Folders still to read, each marked as inside a cache folder or
        # not, and what to remove, every entry after the folder holding it.
        $RsWalk = [System.Collections.Generic.Stack[object]]::new()
        $RsGone = [System.Collections.Generic.List[System.IO.FileSystemInfo]]::new()
        if ([System.IO.Directory]::Exists($RsRoot)) { $RsWalk.Push(@([System.IO.DirectoryInfo]::new($RsRoot), $false)) }
        while ($RsWalk.Count -gt 0) {
            $RsFolder, $RsInCache = $RsWalk.Pop()
            if ($RsInCache) {
                foreach ($RsChild in $RsFolder.GetFileSystemInfos()) {
                    $RsGone.Add($RsChild)
                    if ($RsChild -is [System.IO.DirectoryInfo] -and ($RsChild.Attributes -band $RsLink) -eq 0) { $RsWalk.Push(@($RsChild, $true)) }
                }
                continue
            }
            foreach ($RsChild in $RsFolder.GetDirectories()) {
                $RsIsLink = ($RsChild.Attributes -band $RsLink) -ne 0
                if ([string]::Equals($RsChild.Name, '__pycache__', [System.StringComparison]::Ordinal)) {
                    $RsGone.Add($RsChild)
                    if (-not $RsIsLink) { $RsWalk.Push(@($RsChild, $true)) }
                } elseif (-not $RsIsLink) {
                    $RsWalk.Push(@($RsChild, $false))
                }
            }
        }
        # A folder is empty by its turn; a link (to a folder or a file) is
        # removed as a link.
        for ($RsAt = $RsGone.Count - 1; $RsAt -ge 0; $RsAt--) {
            $RsEntry = $RsGone[$RsAt]
            if ($RsEntry -is [System.IO.DirectoryInfo]) {
                [System.IO.Directory]::Delete($RsEntry.FullName)
            } else {
                if (($RsEntry.Attributes -band $RsLink) -eq 0) { $RsEntry.Attributes = $RsEntry.Attributes -band -bnot [System.IO.FileAttributes]::ReadOnly }
                [System.IO.File]::Delete($RsEntry.FullName)
            }
        }
    } catch {
        Write-Fail "Could not remove the Python cache folders (__pycache__) under $Dir/src. Remove them, then re-run."
    }
}

# Assert-CloneModuleFolder DIR - stop when the clone at DIR keeps
# submodule repositories (.git\modules, or wherever git rev-parse
# --git-path modules points), where git would run under settings nothing
# here checks (mirrors install.sh's check_clone_modules). Reads no index.
function Assert-CloneModuleFolder {
    param([string]$Dir)
    $CmModules = Get-ClonePath $Dir 'modules'
    if ($CmModules -and (Test-Path -LiteralPath $CmModules -PathType Container)) {
        Write-Fail "$Dir keeps submodule repositories in $CmModules. A release tree has no submodules, and the update would run git inside them. Remove the submodules and $CmModules, then re-run."
    }
}

# Assert-CloneGitlink DIR - stop when the index of the clone at DIR records
# a git repository in its tree (a gitlink, git ls-files -s mode 160000),
# which git status and diff would run git inside (mirrors install.sh's
# check_clone_gitlinks). An index git cannot read stops the run here too,
# not only at the checkout after the fetch, so a dry run stops where the
# real run would.
function Assert-CloneGitlink {
    param([string]$Dir)
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $GlStages = @(& git @GitNoProgram -C $Dir ls-files -s 2>$null | ForEach-Object { [string]$_ })
        $GlCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($GlCode -ne 0) {
        Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
    }
    foreach ($GlLine in $GlStages) {
        if ($GlLine.StartsWith('160000 ', [System.StringComparison]::Ordinal)) {
            $GlPath = @($GlLine -split "`t", 2)[-1]
            Write-Fail "$Dir holds a submodule at $GlPath (its index records a git repository there). A release tree has none, and the update would run git inside it. Remove the submodule from the clone, then re-run."
        }
    }
}

# Assert-CleanClone DIR - refuse, before anything is fetched, an existing
# clone at DIR whose check the update could not trust (mirrors update.sh's
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
# hides a change to it. Last, no .gitattributes file in its work tree
# may be untracked, differ from the index, or have a committed copy git
# cannot read or that names a driver, no git repository git does not
# track may be in it (Assert-CloneAttributeFile), and no file under src
# may be untracked (Assert-SourceTracked).
function Assert-CleanClone {
    param([string]$Dir)
    Assert-CloneGit $Dir
    Assert-CloneConfig $Dir
    Assert-CloneModuleFolder $Dir
    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $CcInside = "$(& git @GitNoProgram -C $Dir rev-parse --is-inside-work-tree 2>$null)"
        $CcInsideCode = $LASTEXITCODE
        $CcPrefix = "$(& git @GitNoProgram -C $Dir rev-parse --show-prefix 2>$null)"
        $CcPrefixCode = $LASTEXITCODE
        $CcFlags = @(& git @GitNoProgram -C $Dir ls-files -v 2>$null | ForEach-Object { [string]$_ })
        $CcFlagsCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prior
    }
    if ($CcInsideCode -ne 0 -or $CcInside.Trim() -cne 'true' -or $CcPrefixCode -ne 0 -or $CcPrefix.Trim() -ne '') {
        Write-Fail "$Dir is not the work tree of its git clone (git finds no work tree there, as when its git config sets core.bare to true). Set core.bare to false, then re-run."
    }
    Assert-CloneGitlink $Dir
    if ($CcFlagsCode -ne 0) {
        Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
    }
    foreach ($CcLine in $CcFlags) {
        if ($CcLine.Length -gt 0 -and ([char]::IsLower($CcLine[0]) -or $CcLine[0] -ceq 'S')) {
            Write-Fail "$Dir has changes to tracked files. Commit or stash them, then re-run."
        }
    }
    Assert-CloneAttributeFile $Dir
    Assert-SourceTracked $Dir
}

# Get-LockHome - the path the install lock is named after: APOTHEM_HOME, or,
# when APOTHEM_HOME is a symbolic link or a junction to a folder, that
# folder's own path with every link on the way followed, as install.sh's
# take_lock gets it with cd -P. A run through the link, a run through the
# folder's own path, and a Git Bash run on either then take the same lock.
# The messages still name APOTHEM_HOME as given.
function Get-LockHome {
    $LhKinds = @('SymbolicLink', 'Junction')
    $LhItem = Get-Item -LiteralPath $ApothemHome -Force -ErrorAction SilentlyContinue
    if (-not $LhItem -or $LhKinds -notcontains [string]$LhItem.LinkType) { return $ApothemHome }
    $LhPath = $ApothemHome
    # Each turn follows the first link on the path, from its root; 64 turns
    # stop a loop of links.
    for ($LhTurn = 0; $LhTurn -lt 64; $LhTurn++) {
        $LhRoot = [System.IO.Path]::GetPathRoot($LhPath)
        $LhParts = @($LhPath.Substring($LhRoot.Length).Split([char[]]@([char]'\', [char]'/'), [System.StringSplitOptions]::RemoveEmptyEntries))
        $LhAt = $LhRoot
        $LhFollowed = $false
        for ($LhIndex = 0; $LhIndex -lt $LhParts.Count; $LhIndex++) {
            $LhNext = [System.IO.Path]::Combine($LhAt, $LhParts[$LhIndex])
            $LhStep = Get-Item -LiteralPath $LhNext -Force -ErrorAction SilentlyContinue
            if (-not $LhStep) { return $ApothemHome }
            if ($LhKinds -contains [string]$LhStep.LinkType) {
                $LhTarget = [string]@($LhStep.Target)[0]
                if (-not $LhTarget) { return $ApothemHome }
                if ($LhTarget.StartsWith('\??\', [System.StringComparison]::Ordinal)) { $LhTarget = $LhTarget.Substring(4) }
                # A relative target is read from the folder the link is in.
                $LhJoin = [string[]](@($LhAt, $LhTarget) + @($LhParts | Select-Object -Skip ($LhIndex + 1)))
                $LhPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($LhJoin))
                $LhFollowed = $true
                break
            }
            $LhAt = $LhNext
        }
        if (-not $LhFollowed) {
            if (Test-Path -LiteralPath $LhPath -PathType Container) { return $LhPath.TrimEnd('\', '/') }
            return $ApothemHome
        }
    }
    return $ApothemHome
}

# Resolve-FolderLink PATH - the folder PATH leads to, with every symbolic
# link and junction on the way followed (as cd -P does in the sh scripts);
# for a path that does not exist yet, the part that exists is followed and
# the rest kept. Get-LockHome follows links the same way.
function Resolve-FolderLink {
    param([string]$Path)
    $RlKinds = @('SymbolicLink', 'Junction')
    $RlPath = $Path
    for ($RlTurn = 0; $RlTurn -lt 64; $RlTurn++) {
        $RlRoot = [System.IO.Path]::GetPathRoot($RlPath)
        $RlParts = @($RlPath.Substring($RlRoot.Length).Split([char[]]@([char]'\', [char]'/'), [System.StringSplitOptions]::RemoveEmptyEntries))
        $RlAt = $RlRoot
        $RlFollowed = $false
        for ($RlIndex = 0; $RlIndex -lt $RlParts.Count; $RlIndex++) {
            $RlNext = [System.IO.Path]::Combine($RlAt, $RlParts[$RlIndex])
            $RlStep = Get-Item -LiteralPath $RlNext -Force -ErrorAction SilentlyContinue
            if (-not $RlStep) { return $RlPath }
            if ($RlKinds -contains [string]$RlStep.LinkType) {
                $RlTarget = [string]@($RlStep.Target)[0]
                if (-not $RlTarget) { return $RlPath }
                if ($RlTarget.StartsWith('\??\', [System.StringComparison]::Ordinal)) { $RlTarget = $RlTarget.Substring(4) }
                $RlJoin = [string[]](@($RlAt, $RlTarget) + @($RlParts | Select-Object -Skip ($RlIndex + 1)))
                $RlPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($RlJoin))
                $RlFollowed = $true
                break
            }
            $RlAt = $RlNext
        }
        if (-not $RlFollowed) { return $RlPath }
    }
    return $Path
}

# Get-FolderWriter PATH KIND - who other than you can change PATH, as
# Names, and Owner, set when PATH belongs to someone else. On Windows:
# each account or group an allow entry gives write access, named as the
# Security tab names it (Deny entries are not read, so a warning can be
# extra but is never missed), other than you, this run's own sign-in
# session, SYSTEM, Administrators, TrustedInstaller, CREATOR OWNER and
# OWNER RIGHTS (the last two stand for the one who makes or owns the
# item); Inherited, true when each such entry comes from the folder
# above; and Owner, the owner when it is none of those. Elsewhere: 'all
# users' from the mode bits ls prints, else 'the group G' (the group stat
# names; a group named after you is your own) when its own access-list
# entry (group::, where getfacl lists one: ls shows the list's mask in
# the group bits) or else the group bits let it write, then each user and
# group an access list (getfacl, where installed) lets write; and Owner,
# 'the user U' when U owns PATH and is neither you nor root (ls -n gives
# the number). KIND: 'home' (PATH and what it holds), 'parent' (others
# can rename or remove what PATH holds; a sticky folder stops that, but
# not for its owner) or 'new' (a new folder made in PATH, and the files
# made in it; outside Windows, by the umask, given as Umask, and the
# group of PATH when PATH is setgid or the system is macOS or a BSD).
# Windows only: 'link' (others can delete the link PATH, whose own
# entries are read) and 'make' (others can make folders in PATH); for
# these, an owner who is someone else is one of the Names. A failed read
# names no one; outside Windows, a failed read of the owner's number or
# of the access list leaves the rest of the check as it is.
function Get-FolderWriter {
    # Outside Windows, where this calls ls, PowerShell has no ls alias.
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingCmdletAliases', '')]
    param([string]$Path, [string]$Kind)
    $FwNames = @()
    $FwInherited = $true
    $FwMask = ''
    $FwOwner = ''
    try {
        if ((Get-Variable IsWindows -ValueOnly -ErrorAction SilentlyContinue) -ne $false) {
            $FwMe = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
            # SYSTEM, Administrators, TrustedInstaller, CREATOR OWNER and
            # OWNER RIGHTS. A sign-in session's entry (S-1-5-5-x-y) counts
            # as yours only for this run's own session, which whoami names
            # (.NET leaves it out of the groups it lists); another one is
            # named.
            $FwTrusted = '^S-1-(5-18|5-32-544|5-80-956008885-3418522649-1831038044-1853292631-2271478464|3-0|3-4)$'
            $FwSession = ''
            try { $FwSession = ([string](& "$env:SystemRoot\System32\whoami.exe" /logonid 2>$null)).Trim() } catch { $FwSession = '' }
            $FwOurs = { param([string]$Sid) $Sid -eq $FwMe -or $Sid -eq $FwSession -or $Sid -match $FwTrusted }
            # Parent: delete children, change permissions, take ownership,
            # generic all. Home and new: also create files or folders,
            # delete, generic write. Link: delete, change permissions, take
            # ownership, generic all. Make: create folders, generic write
            # or all.
            $FwRights = switch ($Kind) { 'parent' { 0x100C0040 } 'link' { 0x100D0000 } 'make' { 0x50000004 } default { 0x500D0046 } }
            # Read as Get-Acl does, without Get-Acl: Windows PowerShell
            # cannot load it when it inherits PowerShell 7's module path.
            $FwAcl = [System.Security.AccessControl.DirectorySecurity]::new($Path, [System.Security.AccessControl.AccessControlSections]'Access, Owner')
            $FwSids = [System.Collections.Generic.List[string]]::new()
            foreach ($FwRule in $FwAcl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
                $FwSid = [string]$FwRule.IdentityReference.Value
                if ((& $FwOurs $FwSid) -or $FwRule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) { continue }
                if (([int]$FwRule.FileSystemRights -band $FwRights) -eq 0) { continue }
                $FwInheritOnly = ($FwRule.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]::InheritOnly) -ne 0
                # A new folder takes an entry that passes to folders, and
                # one that passes to files unless NoPropagateInherit keeps
                # it on the files of PATH itself.
                $FwToFolders = ($FwRule.InheritanceFlags -band [System.Security.AccessControl.InheritanceFlags]::ContainerInherit) -ne 0
                $FwToFiles = ($FwRule.InheritanceFlags -band [System.Security.AccessControl.InheritanceFlags]::ObjectInherit) -ne 0 -and ($FwRule.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]::NoPropagateInherit) -eq 0
                if (($Kind -notmatch '^(home|new)$' -and $FwInheritOnly) -or ($Kind -eq 'new' -and -not ($FwToFolders -or $FwToFiles))) { continue }
                if (-not $FwSids.Contains($FwSid)) { $FwSids.Add($FwSid) }
                if (-not $FwRule.IsInherited) { $FwInherited = $false }
            }
            $FwBy = $FwAcl.GetOwner([System.Security.Principal.SecurityIdentifier])
            $FwBy = if ($FwBy) { [string]$FwBy.Value } else { '' }
            if ($Kind -ne 'new' -and $FwBy -and -not (& $FwOurs $FwBy)) {
                if ($Kind -match '^(home|parent)$') {
                    $FwOwner = $FwBy
                } elseif (-not $FwSids.Contains($FwBy)) {
                    $FwSids.Add($FwBy)
                    $FwInherited = $false
                }
            }
            # As the Security tab names them: a built-in group, an NT
            # AUTHORITY or an APPLICATION PACKAGE AUTHORITY name without
            # its domain, any other as DOMAIN\name, and one that cannot be
            # looked up by its SID.
            $FwName = {
                param([string]$Sid)
                try {
                    $FwText = [System.Security.Principal.SecurityIdentifier]::new($Sid).Translate([System.Security.Principal.NTAccount]).Value
                } catch {
                    return $Sid
                }
                if ($Sid -match '^S-1-(1-0|5-\d+|5-32-\d+|15-[23]-\d+)$') { $FwText = $FwText.Substring($FwText.LastIndexOf('\') + 1) }
                return $FwText
            }
            $FwNames = @($FwSids | ForEach-Object { & $FwName $_ })
            if ($FwOwner) { $FwOwner = & $FwName $FwOwner }
        } else {
            $FwMe = [string](& id -un)
            $FwField = @('', '', '', '')
            $FwOs = ''
            $FwAces = @()
            if ($Kind -ne 'new' -or (Test-Path -LiteralPath $Path -PathType Container)) {
                $FwLine = @(& ls -ldL $Path)
                if ($LASTEXITCODE -eq 0 -and $FwLine.Count) { $FwField = @(-split [string]$FwLine[0]) + $FwField }
                # ls splits a group name that holds a space; stat does not.
                try {
                    $FwOs = [string](& uname -s)
                    $FwOut = @(if ($FwOs -match 'Darwin|BSD') { & stat -Lf '%Sg' $Path } else { & stat -Lc '%G' $Path })
                    if ($LASTEXITCODE -eq 0 -and $FwOut.Count) { $FwField[3] = [string]$FwOut[0] }
                } catch {
                    $FwOs = ''
                }
            }
            if ($Kind -ne 'new') {
                # The owner by number (ls -n), and the access list where
                # getfacl is installed. A failed read of either leaves the
                # rest of the check as it is, as in install.sh.
                $FwId = @()
                $FwUid = ''
                try {
                    $FwNum = @(& ls -ldnL $Path)
                    if ($LASTEXITCODE -eq 0 -and $FwNum.Count) { $FwId = @(-split [string]$FwNum[0]) }
                    $FwUid = [string](& id -u)
                } catch {
                    $FwId = @()
                }
                if ($FwId.Count -gt 2 -and $FwField[2] -and $FwUid -and $FwId[2] -ne '0' -and $FwId[2] -ne $FwUid) { $FwOwner = "the user $($FwField[2])" }
                $prior = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                try {
                    $FwAces = @(& getfacl -- $Path 2>$null)
                } catch {
                    $FwAces = @()
                } finally {
                    $ErrorActionPreference = $prior
                }
            }
            $FwMode = $FwField[0]
            $FwGroup = $FwField[3]
            if ($Kind -eq 'new') {
                if (-not $FwGroup -or -not ($FwOs -match 'Darwin|BSD' -or $FwMode -cmatch '^.{6}[sS]')) { $FwGroup = [string](& id -gn) }
                $FwMask = [string](& sh -c umask)
                $FwMode = 'd----' + $(if ($FwMask -match '[0145].$') { 'w' } else { '-' }) + '--' + $(if ($FwMask -match '[0145]$') { 'w' } else { '-' }) + '-'
            }
            $FwSticky = $Kind -eq 'parent' -and $FwMode -cmatch '^.{9}[tT]'
            if ($FwSticky) { $FwMode = '' }
            # The group's own access-list entry (group::) decides for the
            # group where the list has one: ls shows the list's mask in the
            # group bits.
            $FwGroupWrites = $FwMode -cmatch '^.{5}w'
            $FwListed = @()
            foreach ($FwAce in $FwAces) {
                if ($FwSticky -or "$FwAce" -cnotmatch '^(user|group):([^:]*):([^:\s]*)') { continue }
                # Each -cmatch below sets $Matches anew: read this one first.
                # getfacl writes a \ in a name as \\, and a space, tab, line
                # break, colon or comma as \ and three octal digits: the name
                # is read back as it is (as install.sh's dq does).
                $FwAceName = [regex]::Replace($Matches[2], '\\(\\|[0-7]{3})', { param($FwEscape) if ($FwEscape.Length -eq 2) { '\' } else { [string][char][Convert]::ToInt32($FwEscape.Value.Substring(1), 8) } })
                $FwWho = "the $($Matches[1]) $FwAceName"
                $FwOwning = $Matches[1] -ceq 'group' -and $FwAceName -ceq ''
                $FwSkip = $FwAceName -ceq '' -or $FwAceName -ceq $FwMe
                $FwPerm = $Matches[3]
                if ("$FwAce" -cmatch '^user:root:') { $FwSkip = $true }
                if ("$FwAce" -cmatch '#\s*effective:\s*(.*)') { $FwPerm = $Matches[1] }
                if ($FwOwning) {
                    $FwGroupWrites = $FwPerm.Contains('w')
                } elseif ($FwPerm.Contains('w') -and -not $FwSkip) {
                    $FwListed += $FwWho
                }
            }
            if ($FwMode -cmatch '^.{8}w') { $FwNames = @('all users') }
            elseif ($FwGroupWrites -and $FwGroup -cne $FwMe) { $FwNames = @("the group $FwGroup") }
            foreach ($FwWho in $FwListed) {
                if ($FwNames -cnotcontains $FwWho) { $FwNames += $FwWho }
            }
        }
    } catch {
        $FwNames = @()
        $FwOwner = ''
    }
    return @{ Names = ($FwNames -join ', '); Inherited = $FwInherited; Umask = $FwMask; Owner = $FwOwner }
}

# Write-HomeAccessWarning - warn, never stop, when users other than you can
# change the code a run starts as you: they can write to APOTHEM_HOME (a
# new one: by what it would inherit, or the umask), or rename what the
# folder holding it holds, or the folder holding APOTHEM_HOME's link, or
# one of those folders belongs to someone else (as install.sh's
# warn_home_access). The messages name the folder a link leads to, as a
# junction's entries cover only the junction itself.
function Write-HomeAccessWarning {
    try {
        $HaWindows = (Get-Variable IsWindows -ValueOnly -ErrorAction SilentlyContinue) -ne $false
        $HaRoot = ", access that folders made at the root of a drive inherit from the drive's default permissions"
        $HaParent = {
            param([string]$Folder, [string]$Child, [bool]$Link)
            if (-not $Folder -or -not (Test-Path -LiteralPath $Folder -PathType Container)) { return }
            $HpBy = Get-FolderWriter $Folder 'parent'
            $HpWho = $HpBy.Names
            # A link others may delete, in a folder they may make folders
            # in, can be swapped for one of theirs as well.
            if (-not $HpWho -and $Link -and $HaWindows -and (Get-FolderWriter $Folder 'make').Names) { $HpWho = (Get-FolderWriter $Child 'link').Names }
            if ($HpBy.Owner -and $HaWindows) {
                Write-Warn "Other users can change the code Apothem runs as you: $($HpBy.Owner) owns $Folder. To fix it, move APOTHEM_HOME into your user folder."
            } elseif ($HpBy.Owner) {
                Write-Warn "Other users can change the code Apothem runs as you: $($HpBy.Owner) owns $Folder. To fix it, move APOTHEM_HOME into a folder you own."
            } elseif ($HpWho -and $HaWindows) {
                Write-Warn "Other users can replace ${Child}: $HpWho can delete or rename what is in $Folder, the folder that holds it. To fix it, remove $HpWho from that folder's Security tab, or move APOTHEM_HOME into your user folder."
            } elseif ($HpWho) {
                Write-Warn "Other users can replace ${Child}: $HpWho can write to $Folder, the folder that holds it. To fix it, run chmod go-w `"$Folder`", or move APOTHEM_HOME."
            }
        }
        $HaItem = Get-Item -LiteralPath $ApothemHome -Force -ErrorAction SilentlyContinue
        if ($HaItem -and @('SymbolicLink', 'Junction') -contains [string]$HaItem.LinkType) {
            & $HaParent (Split-Path -Parent $ApothemHome) $ApothemHome $true
        }
        $HaDir = Resolve-FolderLink $ApothemHome
        $HaUp = Split-Path -Parent $HaDir
        if (Test-Path -LiteralPath $HaDir -PathType Container) {
            $HaWho = Get-FolderWriter $HaDir 'home'
            if ($HaWho.Owner -and $HaWindows) {
                Write-Warn "Other users can change the code Apothem runs as you: $($HaWho.Owner) owns $HaDir. To fix it, move APOTHEM_HOME into your user folder."
            } elseif ($HaWho.Owner) {
                Write-Warn "Other users can change the code Apothem runs as you: $($HaWho.Owner) owns $HaDir. To fix it, move APOTHEM_HOME into a folder you own."
            } elseif ($HaWho.Names -and $HaWindows) {
                $HaWhy = ''
                if ($HaWho.Inherited -and $HaUp -match '^[A-Za-z]:\\$') { $HaWhy = $HaRoot }
                Write-Warn "Other users can change the code Apothem runs as you: $($HaWho.Names) can write to $HaDir$HaWhy. To fix it, turn off inheritance for that folder and remove $($HaWho.Names) (Properties > Security > Advanced), or move APOTHEM_HOME into your user folder."
            } elseif ($HaWho.Names) {
                Write-Warn "Other users can change the code Apothem runs as you: $($HaWho.Names) can write to $HaDir. To fix it, run chmod go-w `"$HaDir`", or move APOTHEM_HOME."
            }
        } else {
            # Windows reads what the nearest folder that exists passes on.
            $HaFrom = $HaUp
            while ($HaWindows -and $HaFrom -and -not (Test-Path -LiteralPath $HaFrom -PathType Container)) { $HaFrom = Split-Path -Parent $HaFrom }
            $HaWho = Get-FolderWriter $HaFrom 'new'
            if ($HaWho.Names -and $HaWindows) {
                $HaWhy = ", from the permissions of $HaFrom"
                if ($HaFrom -match '^[A-Za-z]:\\$') { $HaWhy = $HaRoot }
                Write-Warn "A new $HaDir would let $($HaWho.Names) change the code Apothem runs as you$HaWhy. To fix it, set APOTHEM_HOME to a folder inside your user folder."
            } elseif ($HaWho.Names) {
                Write-Warn "A new $HaDir would let $($HaWho.Names) change the code Apothem runs as you (umask $($HaWho.Umask)). To fix it, run umask 022, then run the installer again."
            }
        }
        & $HaParent $HaUp $HaDir
    } catch {
        return
    }
}

# Lock-ApothemHome - take the install lock: an install, update or uninstall
# holds <APOTHEM_HOME>.lock for its whole run, so two runs never change
# APOTHEM_HOME, or the folders beside it, at the same time (mirrors
# update.sh's take_lock). The lock is a file opened with no sharing, so a
# second open fails while this run holds it; Windows closes it when the run
# ends, a forced kill included, which frees the lock and deletes the file.
# install.sh, update.sh and uninstall.sh use a folder of the same name that
# holds the process ID of the run that made it. That ID cannot be checked
# from here (under Git Bash it is not a Windows process ID), so such a
# folder is reported, with how to remove it, and never taken over. When
# APOTHEM_HOME is a link, the lock sits beside the folder it leads to (see
# Get-LockHome).
$script:HomeLock = $null
$HomeLockPath = "$(Get-LockHome).lock"
function Lock-ApothemHome {
    $LkParent = Split-Path -Parent $HomeLockPath
    # With no folder to hold APOTHEM_HOME there is nothing to work on, and
    # the run stops below without the lock.
    if (-not $LkParent -or -not (Test-Path -LiteralPath $LkParent -PathType Container)) { return }
    $LkItem = Get-Item -LiteralPath $HomeLockPath -Force -ErrorAction SilentlyContinue
    if ($LkItem -and ($LkItem.LinkType -or $LkItem.PSIsContainer)) {
        $LkPid = ''
        if ($LkItem.PSIsContainer -and -not $LkItem.LinkType) {
            try { $LkPid = ([System.IO.File]::ReadAllText((Join-Path $LkItem.FullName 'pid'))).Trim() } catch { $LkPid = '' }
            if ($LkPid -notmatch '^[0-9]+$') {
                # A POSIX run that has just made the lock folder writes
                # its process ID a moment later; look again before
                # calling the lock stale.
                Start-Sleep -Seconds 1
                try { $LkPid = ([System.IO.File]::ReadAllText((Join-Path $LkItem.FullName 'pid'))).Trim() } catch { $LkPid = '' }
            }
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
        # A folder or link made there since the look above (a Git Bash run
        # taking its lock) makes the open fail as a folder does.
        $LkItem = Get-Item -LiteralPath $HomeLockPath -Force -ErrorAction SilentlyContinue
        if ($LkItem -and ($LkItem.LinkType -or $LkItem.PSIsContainer)) {
            Write-Fail "Another Apothem install, update or uninstall is running on $ApothemHome. Wait for it to finish, then re-run. If none is running, remove $HomeLockPath, then re-run."
        }
        Write-Fail "Could not create the lock $HomeLockPath. Check that you can write to $LkParent, then re-run."
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

Write-Bold "Apothem updater"

# One install, update or uninstall at a time on APOTHEM_HOME (see
# Lock-ApothemHome); the finally block at the end lets the lock go.
Lock-ApothemHome
try {
# The git variables described at the top are cleared or set for the run:
# each one set now is kept in $SavedGitEnv, with GIT_NO_REPLACE_OBJECTS,
# GIT_NO_LAZY_FETCH, GIT_ALLOW_PROTOCOL and GIT_ATTR_NOSYSTEM as they
# were, and the finally block at the end puts them all back.
$SavedGitEnv = @{ GIT_NO_REPLACE_OBJECTS = $env:GIT_NO_REPLACE_OBJECTS; GIT_NO_LAZY_FETCH = $env:GIT_NO_LAZY_FETCH; GIT_ALLOW_PROTOCOL = $env:GIT_ALLOW_PROTOCOL; GIT_ATTR_NOSYSTEM = $env:GIT_ATTR_NOSYSTEM }
# git writes paths and names in UTF-8, and PowerShell reads a program's
# output in [Console]::OutputEncoding, the console's code page, where a
# non-ASCII path reads as one that does not exist. It is UTF-8 for the
# run, and the finally block at the end puts it back (a host with no
# console keeps its own).
$SavedOutputEncoding = $null
try { $SavedOutputEncoding = [Console]::OutputEncoding; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { $SavedOutputEncoding = $null }
try {
foreach ($GitVar in @('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR', 'GIT_NAMESPACE', 'GIT_REPLACE_REF_BASE', 'GIT_CEILING_DIRECTORIES', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_EXEC_PATH', 'GIT_TEMPLATE_DIR', 'GIT_CONFIG', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM', 'GIT_ATTR_SOURCE')) {
    if (Test-Path -LiteralPath "Env:$GitVar") {
        $SavedGitEnv[$GitVar] = [string](Get-Item -LiteralPath "Env:$GitVar").Value
        Remove-Item -LiteralPath "Env:$GitVar"
    }
}
$env:GIT_NO_REPLACE_OBJECTS = '1'
$env:GIT_NO_LAZY_FETCH = '1'
$env:GIT_ALLOW_PROTOCOL = 'file:git:http:https:ssh'
$env:GIT_ATTR_NOSYSTEM = '1'

function Test-ApothemSource {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Dir, 'src', 'apothem')))) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Dir 'pyproject.toml')) -or
           (Test-Path -LiteralPath (Join-Path $Dir '.claude-plugin'))
}

# Every Python start from here to the prerequisite check gets the caller's
# PYTHONPATH without its empty and relative entries (Get-SafePythonPath); the
# caller's value is restored afterwards.
$PriorProbePyPath = $env:PYTHONPATH
$env:PYTHONPATH = Get-SafePythonPath '' $PriorProbePyPath
try {
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
    Write-Fail "Missing prerequisites under ${PY}: $($MissingDeps -join ', '). Install them with: '${PY}' -m pip install $($MissingDeps -join ' ') - or set APOTHEM_AUTO_INSTALL_DEPS=1 to install automatically. See $PrereqDoc for help."
}
} finally {
    $env:PYTHONPATH = $PriorProbePyPath
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
} elseif ((Test-Path -LiteralPath (Join-Path $ApothemHome '.git')) -and (Test-ApothemSource $ApothemHome)) {
    $NoHooksDir = Join-Path ([System.IO.Path]::GetTempPath()) ("apothem-nohooks-" + [System.Guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $NoHooksDir | Out-Null
        $GitSafe = @($GitNoProgram + @('-c', "core.hooksPath=$NoHooksDir"))
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

        if ((Test-ReleaseTag $ApothemRef) -and $ApothemAllowUnverified -ne '1') {
            # Release tags carry OpenPGP signatures whatever gpg.format says, so
            # the program git verify-tag runs for one must be present:
            # gpg.openpgp.program, else gpg.program, else gpg.
            $prior = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                $GpgProg = Invoke-GitOutsideRepository { & git config --get gpg.openpgp.program 2>$null }
                if (-not $GpgProg) { $GpgProg = Invoke-GitOutsideRepository { & git config --get gpg.program 2>$null } }
                $GitExecPath = & git --exec-path 2>$null
            } finally {
                $ErrorActionPreference = $prior
            }
            if ($GpgProg) {
                $GpgFound = (Test-Path -LiteralPath $GpgProg -PathType Leaf) -or [bool](Get-Command $GpgProg -ErrorAction SilentlyContinue)
            } else {
                # Git for Windows runs the gpg it ships (usr\bin\gpg.exe under its
                # install root), which is not on PATH.
                $GpgFound = [bool](Get-Command 'gpg' -ErrorAction SilentlyContinue)
                if (-not $GpgFound -and $GitExecPath) {
                    $GitRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $GitExecPath))
                    $GpgFound = [bool]($GitRoot -and (Test-Path -LiteralPath (Join-Path $GitRoot 'usr\bin\gpg.exe')))
                }
            }
            if (-not $GpgFound) {
                Write-Fail "gpg not found - needed to check the $ApothemRef release tag's signature against the maintainer key. Install Git for Windows (it ships gpg) or GnuPG (https://gnupg.org/download/), then re-run."
            }
        }

        Assert-CleanClone $ApothemHome

        # Fetch, check the tag, and only then check it out, so a failed check
        # leaves the clone where it was (mirrors update.sh). git reports a failed
        # fetch or checkout on stderr, which PowerShell before 7.2 turns into a
        # terminating error under 'Stop', so the preference is localized around
        # each call.
        Write-Info "Updating clone at $ApothemHome (ref: $ApothemRef)"
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & git @GitLongPaths @GitSafe -C $ApothemHome fetch --quiet --tags origin
            $FetchCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($FetchCode -ne 0) {
            Write-Fail "Could not fetch from the origin of $ApothemHome. If a local tag differs from origin's, delete it with 'git -C $ApothemHome tag -d <tag>', then re-run."
        }

        Write-Bold "Verifying source signature"
        $TagCommit = ''
        if (Test-ReleaseTag $ApothemRef) {
            # The tag ref is read once: the signature, the signed tag object's
            # own name and the commit all come from that one tag object, and
            # the commit is then checked out by its ID, so a tag ref moved
            # after the check cannot change what is installed (mirrors
            # update.sh).
            $prior = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                $TagObject = "$(& git @GitLongPaths @GitSafe -C $ApothemHome rev-parse --verify --quiet "refs/tags/$ApothemRef" 2>$null)".Trim()
                if ($LASTEXITCODE -ne 0) { $TagObject = '' }
            } finally {
                $ErrorActionPreference = $prior
            }
            $script:VerifyTagOutput = ''
            if ($TagObject -and (Test-TagSignature $ApothemHome $TagObject) -and (Test-TagSignedByMaintainer)) {
                # The signed tag object must name itself APOTHEM_REF: a signed tag
                # for another release, re-pointed here, would roll the update
                # back. Its header runs to the first empty line, and the last
                # `type` and `tag` lines in it must read exactly `type commit` and
                # `tag APOTHEM_REF`, as update.sh's awk check requires.
                $ErrorActionPreference = 'Continue'
                try {
                    $TagLines = @(& git @GitLongPaths @GitSafe -C $ApothemHome cat-file tag $TagObject 2>$null)
                } finally {
                    $ErrorActionPreference = $prior
                }
                $TagType = ''
                $TagName = ''
                foreach ($TagLine in $TagLines) {
                    $TagText = [string]$TagLine
                    if ($TagText -eq '') { break }
                    $TagField = @($TagText.Trim() -split '\s+')[0]
                    if ($TagField -ceq 'type') { $TagType = $TagText }
                    elseif ($TagField -ceq 'tag') { $TagName = $TagText }
                }
                if (-not ($TagType -ceq 'type commit' -and $TagName -ceq "tag $ApothemRef")) {
                    Write-Fail "Tag $ApothemRef carries the maintainer key's signature, but the signed tag object is not the $ApothemRef release tag (it names another tag, or no commit), so it was re-pointed (possible tampering). Aborting before anything is checked out or re-materialized."
                }
                $TagCommit = "$(& git @GitLongPaths @GitSafe -C $ApothemHome rev-parse --verify --quiet "$TagObject^{commit}")".Trim()
                if ($LASTEXITCODE -ne 0 -or -not $TagCommit) { Write-Fail "Could not read the commit the $ApothemRef tag points at" }
                Write-Ok "Tag $ApothemRef carries a valid signature from the maintainer key $MaintainerFingerprint"
            } elseif ($ApothemAllowUnverified -eq '1') {
                if ($TagObject) {
                    $ErrorActionPreference = 'Continue'
                    try {
                        $TagCommit = "$(& git @GitLongPaths @GitSafe -C $ApothemHome rev-parse --verify --quiet "$TagObject^{commit}" 2>$null)".Trim()
                        if ($LASTEXITCODE -ne 0) { $TagCommit = '' }
                    } finally {
                        $ErrorActionPreference = $prior
                    }
                }
                Write-Warn "Tag $ApothemRef is unsigned, its signature did not verify, or the maintainer key did not make it - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
            } elseif (Test-TagSignedByOtherKey) {
                $Signers = Get-TagSigner
                Write-Fail "Tag $ApothemRef is signed by $Signers. A release tag must be signed by the maintainer key $MaintainerFingerprint that SECURITY.md publishes, and by no other key (possible tampering). Aborting before anything is checked out or re-materialized."
            } elseif (Test-VerifyTagMissingKey) {
                Write-Fail "Tag $ApothemRef is signed, but the maintainer public key is not in the local keyring, so the signature cannot be checked. Import the key first: run & `"$env:ProgramFiles\Git\bin\bash.exe`" -c 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import && gpg --fingerprint 70396FED9C634163' (the gpg that ships with Git for Windows, which git verify-tag uses), check that the fingerprint matches the one published in SECURITY.md, then re-run this updater."
            } else {
                Write-Fail "Tag $ApothemRef is unsigned or its signature did not verify (possible tampering). Aborting before anything is checked out or re-materialized."
            }
        } elseif ($ApothemAllowUnverified -eq '1') {
            Write-Warn "Ref $ApothemRef is not a signed release tag - proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
        } else {
            Write-Fail "Ref $ApothemRef is not a signed release tag and cannot be verified. Pin a vMAJOR.MINOR.PATCH tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to proceed without verification."
        }

        # A change to a tracked file stops the update before anything is checked
        # out (mirrors update.sh).
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & git @GitLongPaths @GitSafe -C $ApothemHome diff --quiet --no-textconv --no-ext-diff HEAD
            $DiffCode = $LASTEXITCODE
            & git @GitLongPaths @GitSafe -C $ApothemHome diff --cached --quiet --no-textconv --no-ext-diff
            $CachedCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($DiffCode -ne 0 -or $CachedCode -ne 0) {
            Write-Fail "$ApothemHome has changes to tracked files. Commit or stash them, then re-run."
        }

        # A release tag is checked out, detached, by the commit ID its check
        # recorded ($TagCommit), never by its name again: a tag ref moved
        # since, or a branch that shares the tag's name, cannot change what is
        # checked out, and HEAD must then be that commit. Any other ref follows
        # origin's branch of that name when there is one (a local branch may
        # be stale), and otherwise resolves directly, after --end-of-options so
        # a ref cannot pass for an option. No --force, so local changes stop
        # the update instead of being lost, and afterwards the tracked files
        # must match the ref. Submodules are left alone.
        if ((Test-ReleaseTag $ApothemRef) -and -not $TagCommit) {
            Write-Fail "Could not check out the $ApothemRef tag in $ApothemHome. If it has local changes, commit or stash them, then re-run."
        }
        $prior = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            if (Test-ReleaseTag $ApothemRef) {
                & git @GitLongPaths @GitSafe -C $ApothemHome checkout --quiet --detach $TagCommit
                $CoCode = $LASTEXITCODE
            } else {
                & git @GitLongPaths @GitSafe -C $ApothemHome show-ref --verify --quiet "refs/remotes/origin/$ApothemRef"
                if ($LASTEXITCODE -eq 0) {
                    & git @GitLongPaths @GitSafe -C $ApothemHome checkout --quiet --detach "refs/remotes/origin/$ApothemRef"
                } else {
                    & git @GitLongPaths @GitSafe -C $ApothemHome checkout --quiet --end-of-options $ApothemRef
                }
                $CoCode = $LASTEXITCODE
            }
        } finally {
            $ErrorActionPreference = $prior
        }
        if (Test-ReleaseTag $ApothemRef) {
            if ($CoCode -ne 0) { Write-Fail "Could not check out the $ApothemRef tag in $ApothemHome. If it has local changes, commit or stash them, then re-run." }
            $CoHead = & git @GitLongPaths @GitSafe -C $ApothemHome rev-parse --verify --quiet HEAD
            $CoTag = $TagCommit
            if ("$CoHead" -ne "$CoTag") {
                Write-Fail "The checkout in $ApothemHome is at '$CoHead', not at the $ApothemRef tag's commit '$CoTag'. Aborting before re-materialization."
            }
        } elseif ($CoCode -ne 0) {
            Write-Fail "Could not check out $ApothemRef in $ApothemHome. If it has local changes, commit or stash them, then re-run."
        }
        $ErrorActionPreference = 'Continue'
        try {
            $CoDirty = @(& git @GitLongPaths @GitSafe -C $ApothemHome status --porcelain --untracked-files=no 2>$null)
            $CoStatusCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($CoStatusCode -ne 0 -or $CoDirty.Count -gt 0) {
            Write-Fail "The checkout in $ApothemHome does not match $ApothemRef after the update. Aborting before re-materialization."
        }
        Remove-SourceCache $ApothemHome
        $Source = $ApothemHome
        if (-not (Test-ApothemSource $Source)) { Write-Fail "Updated tree is not an apothem source: $Source" }
        Write-Ok "Source updated at $Source (ref: $ApothemRef)"
    } finally {
        $GitSafe = @()
        if (Test-Path -LiteralPath $NoHooksDir) { Remove-Item -LiteralPath $NoHooksDir -Recurse -Force }
    }
} elseif (Test-ApothemSource $ApothemHome) {
    Write-Fail "$ApothemHome was installed from a release archive, which has no git clone to update. Re-run install.ps1 with cosign and gpg on PATH to update it to the latest verified release."
} else {
    Write-Fail "No source found at $ApothemHome - run install.ps1 first or set APOTHEM_SOURCE"
}
# Warn when users other than you can change the code this run starts
# (APOTHEM_SOURCE's code is not in APOTHEM_HOME).
if (-not $env:APOTHEM_SOURCE) { Write-HomeAccessWarning }
$SrcPath = Join-Path $Source 'src'
# Vendored runtime dependencies resolve ahead of the host's site-packages,
# mirroring the plugin runtime's vendor-first precedence.
$VendorPath = [System.IO.Path]::Combine($SrcPath, 'apothem', '_vendor')
$EnginePyPath = "$VendorPath$([System.IO.Path]::PathSeparator)$SrcPath"

Write-Bold "Re-materializing harness: $Harness"
if (-not (Test-Path $ApothemProfile)) { Write-Fail "Profile not found at $ApothemProfile" }
$PriorPyPath = $env:PYTHONPATH
$PriorSafePath = $env:PYTHONSAFEPATH
$env:PYTHONPATH = Get-SafePythonPath $EnginePyPath $PriorPyPath
$env:PYTHONSAFEPATH = '1'
$EngineCode = 0
try {
    & $PY -c $EngineProgram update --harness $Harness --profile $ApothemProfile
    # Exit code 2 means the engine ended as partial (mirrors install.ps1): it
    # left some files as they are, or it stopped after it had written some,
    # and its messages above say which. The update then finishes
    # and the run ends with code 2 (see the end of this script). Any other
    # non-zero code stops the run here.
    $EngineCode = $LASTEXITCODE
    if ($EngineCode -eq 2) {
        Write-Warn "The engine ended as partial (exit code 2): its messages above say which files it left as they are, or which harness stopped. Fix what they name, then run 'apothem update --harness $Harness' again."
    } elseif ($EngineCode -ne 0) {
        Write-Fail "Harness re-materialization failed for $Harness"
    } else {
        Write-Ok "Harness $Harness updated"
    }
}
finally {
    $env:PYTHONPATH = $PriorPyPath
    $env:PYTHONSAFEPATH = $PriorSafePath
}

Write-Bold "Update complete."
} finally {
    # The caller's git variables, the encoding PowerShell read a program's
    # output in, and the caller's native-command preference, as they were
    # before the run.
    if ($HadNativeErrorPref) { $PSNativeCommandUseErrorActionPreference = $SavedNativeErrorPref } else { Remove-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue }
    foreach ($GitVar in @($SavedGitEnv.Keys)) {
        if ($null -eq $SavedGitEnv[$GitVar]) {
            Remove-Item -LiteralPath "Env:$GitVar" -ErrorAction SilentlyContinue
        } else {
            Set-Item -LiteralPath "Env:$GitVar" -Value $SavedGitEnv[$GitVar]
        }
    }
    if ($SavedOutputEncoding) { try { [Console]::OutputEncoding = $SavedOutputEncoding } catch { $SavedOutputEncoding = $null } }
}

# A partial engine run (exit code 2) ends the run with that code (mirrors
# install.ps1). Run by path (pwsh -File, & .\update.ps1, update.bat), the
# script exits with it. A piped run (irm ... | iex) has no $PSCommandPath,
# and exit there would close the PowerShell session it runs in, so the run
# leaves $LASTEXITCODE at 2 instead and the session open. Either way the
# finally below still lets the install lock go.
if ($EngineCode -eq 2) {
    if ($PSCommandPath) { exit 2 }
    $global:LASTEXITCODE = 2
}
} finally {
    Unlock-ApothemHome
}
