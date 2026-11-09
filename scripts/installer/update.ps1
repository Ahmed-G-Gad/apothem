# SPDX-License-Identifier: MIT

# Purpose: Re-fetch the bundled Apothem source (self-contained - no package
#          installation) and re-materialize harness config (PowerShell
#          parity to update.sh).
# Usage:   pwsh -NoProfile -File scripts/installer/update.ps1
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
# may not set a filter, it may hold no submodules, no tracked file may be
# marked assume-unchanged or skip-worktree, and its work tree must be
# APOTHEM_HOME itself. Every git command on the clone runs with its hooks,
# its fsmonitor, the pager and automatic maintenance off, with no ext::
# transport, and without going into submodules, and a clone of something
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
# settings, read its configuration from other files, use another git
# program, or swap objects through replace refs, so the run clears them
# once it holds the install lock (see the start of the run, below;
# mirrors update.sh). Run by irm | iex, the script shares the caller's
# session, so the caller's values are put back as the run ends, however
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
# update.sh's cgit).
$GitNoProgram = @('--no-pager', '-c', 'core.fsmonitor=', '-c', 'protocol.ext.allow=never', '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=always', '-c', 'protocol.git.allow=always', '-c', 'protocol.http.allow=always', '-c', 'protocol.https.allow=always', '-c', 'protocol.ssh.allow=always', '-c', 'submodule.recurse=false', '-c', 'fetch.recurseSubmodules=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'diff.ignoreSubmodules=all', '-c', 'core.longpaths=true')
$GitSafe = @()

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
        $Lines = & git @GitSafe -C $Dir verify-tag --raw $Ref 2>&1
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
# update.sh's git_path).
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
# (mirrors update.sh's check_clone_config). Each file is listed alone, so
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
        # Read as git reads it, byte by byte: NUL bytes dropped (as
        # install.sh does), lines ended by LF only, and a comment only where
        # # follows nothing but spaces, tabs or CR. Read as text, a
        # UTF-16 byte-order mark would turn every line into other characters
        # while git still applies them.
        try {
            $CfBytes = [System.IO.File]::ReadAllBytes($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CfFile))
            $CfText = [System.Text.Encoding]::GetEncoding(28591).GetString($CfBytes).Replace([string][char]0, '')
            $CfLines = @($CfText.Split([char]10))
        } catch {
            $CfLines = @()
        }
        foreach ($CfLine in $CfLines) {
            if ($CfLine -cnotmatch '^[ \t\r]*#' -and $CfLine.Contains('filter=')) {
                Write-Fail "$Dir's own git attributes set a filter (filter=), which the update would trust. Remove it from $CfFile, then re-run."
            }
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
# hides a change to it.
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
            & git @GitSafe -C $ApothemHome fetch --quiet --tags origin
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
                $TagObject = "$(& git @GitSafe -C $ApothemHome rev-parse --verify --quiet "refs/tags/$ApothemRef" 2>$null)".Trim()
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
                    $TagLines = @(& git @GitSafe -C $ApothemHome cat-file tag $TagObject 2>$null)
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
                $TagCommit = "$(& git @GitSafe -C $ApothemHome rev-parse --verify --quiet "$TagObject^{commit}")".Trim()
                if ($LASTEXITCODE -ne 0 -or -not $TagCommit) { Write-Fail "Could not read the commit the $ApothemRef tag points at" }
                Write-Ok "Tag $ApothemRef carries a valid signature from the maintainer key $MaintainerFingerprint"
            } elseif ($ApothemAllowUnverified -eq '1') {
                if ($TagObject) {
                    $ErrorActionPreference = 'Continue'
                    try {
                        $TagCommit = "$(& git @GitSafe -C $ApothemHome rev-parse --verify --quiet "$TagObject^{commit}" 2>$null)".Trim()
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
            & git @GitSafe -C $ApothemHome diff --quiet HEAD
            $DiffCode = $LASTEXITCODE
            & git @GitSafe -C $ApothemHome diff --cached --quiet
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
                & git @GitSafe -C $ApothemHome checkout --quiet --detach $TagCommit
                $CoCode = $LASTEXITCODE
            } else {
                & git @GitSafe -C $ApothemHome show-ref --verify --quiet "refs/remotes/origin/$ApothemRef"
                if ($LASTEXITCODE -eq 0) {
                    & git @GitSafe -C $ApothemHome checkout --quiet --detach "refs/remotes/origin/$ApothemRef"
                } else {
                    & git @GitSafe -C $ApothemHome checkout --quiet --end-of-options $ApothemRef
                }
                $CoCode = $LASTEXITCODE
            }
        } finally {
            $ErrorActionPreference = $prior
        }
        if (Test-ReleaseTag $ApothemRef) {
            if ($CoCode -ne 0) { Write-Fail "Could not check out the $ApothemRef tag in $ApothemHome. If it has local changes, commit or stash them, then re-run." }
            $CoHead = & git @GitSafe -C $ApothemHome rev-parse --verify --quiet HEAD
            $CoTag = $TagCommit
            if ("$CoHead" -ne "$CoTag") {
                Write-Fail "The checkout in $ApothemHome is at '$CoHead', not at the $ApothemRef tag's commit '$CoTag'. Aborting before re-materialization."
            }
        } elseif ($CoCode -ne 0) {
            Write-Fail "Could not check out $ApothemRef in $ApothemHome. If it has local changes, commit or stash them, then re-run."
        }
        $ErrorActionPreference = 'Continue'
        try {
            $CoDirty = @(& git @GitSafe -C $ApothemHome status --porcelain --untracked-files=no 2>$null)
            $CoStatusCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prior
        }
        if ($CoStatusCode -ne 0 -or $CoDirty.Count -gt 0) {
            Write-Fail "The checkout in $ApothemHome does not match $ApothemRef after the update. Aborting before re-materialization."
        }
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
try {
    & $PY -c $EngineProgram update --harness $Harness --profile $ApothemProfile
    if ($LASTEXITCODE -ne 0) { Write-Fail "Harness re-materialization failed for $Harness" }
    Write-Ok "Harness $Harness updated"
}
finally {
    $env:PYTHONPATH = $PriorPyPath
    $env:PYTHONSAFEPATH = $PriorSafePath
}

Write-Bold "Update complete."
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
