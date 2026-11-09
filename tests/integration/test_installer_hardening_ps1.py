# SPDX-License-Identifier: MIT

"""The PowerShell installer, updater and uninstaller: what an existing clone
may carry, the git environment they run in, the install lock, the folders a
stopped run leaves, the tag's commit, and downloads that are redirected.

The Windows counterpart of the sh tests for the same rules
(``test_installer_*`` for install.sh, update.sh and uninstall.sh), which
print the same messages (tests/scripts/test_installer_parity.py compares
them). Each case plants what a run must refuse or survive: a setting in the
clone's own config or config.worktree, an attribute that assigns a filter, a
git variable inherited from the calling shell, a lock held by another run,
folders a killed run left, a tag ref moved while it is checked, or a
download redirected away from https. Stub gpg programs (sh scripts, which
Git for Windows runs through its own sh) report a signature and, where a
case needs it, record whether the lock is held, wait, or move the tag ref.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests._shared.release_fixture import (
    MAINTAINER_FINGERPRINT,
    OTHER_FINGERPRINT,
    git,
    good_signature_status,
    make_tagged_repo,
    repoint_tag,
)
from tests.integration.test_installer_release_mode_ps1 import (
    _PWSH,
    EXECUTABLE_MODE,
    OLD_TAG,
    REPO_ROOT,
    TAG,
    UNUSED_BASE,
    _clone_at_old_tag,
    _commit_in,
    _env,
    _head,
    _plain,
    _seed_earlier_install,
    _squashed,
    global_gitconfig,
)

INSTALLER_DIR = REPO_ROOT / "scripts" / "installer"
GOOD = good_signature_status(MAINTAINER_FINGERPRINT)
TRUSTED = ", which the update would trust. Remove it from"

pytestmark = [
    pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host"),
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="Git for Windows runs the sh stubs; the sh scripts' own tests cover POSIX",
    ),
]


# Helpers -------------------------------------------------------------------


def _sh(path: Path, body: str) -> Path:
    """Write an sh script (Git for Windows runs it through its own sh)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    path.chmod(EXECUTABLE_MODE)
    return path


def _gpg(folder: Path, body: str, status: str = GOOD) -> Path:
    """Write a stub gpg that drains stdin, runs BODY, then prints STATUS on
    git's status fd, and return a git config file that names it."""
    status_file = folder / "status.txt"
    folder.mkdir(parents=True, exist_ok=True)
    status_file.write_text(status, encoding="utf-8", newline="\n")
    stub = _sh(
        folder / "gpg", f"cat >/dev/null\n{body}cat '{status_file.as_posix()}'\n"
    )
    config = folder / "gitconfig"
    config.write_text(
        f"[gpg]\n\tprogram = {stub.as_posix()}\n", encoding="utf-8", newline="\n"
    )
    return config


def _script_env(
    tmp_path: Path,
    *,
    mode: str | None = "signature",
    gpg_status: str | None = None,
    gpg_config: Path | None = None,
    gitconfig_extra: str = "",
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """The release-mode tests' environment, with GPG_CONFIG (a stub gpg of a
    case's own) as the global git config when given."""
    env = _env(tmp_path, gpg_status=gpg_status, gitconfig_extra=gitconfig_extra)
    if gpg_config is not None:
        env["GIT_CONFIG_GLOBAL"] = str(
            global_gitconfig(tmp_path / "home", gpg_config, gitconfig_extra)
        )
    env["APOTHEM_RELEASE_BASE"] = UNUSED_BASE
    if mode is not None:
        env["APOTHEM_VERIFY"] = mode
    env.update(extra_env or {})
    return env


def _script_args(tmp_path: Path, script: str, *flags: str) -> list[str]:
    """The command line that runs SCRIPT by path. install.ps1 runs from a copy
    outside the checkout, which it would otherwise take as its local tree."""
    path = INSTALLER_DIR / script
    if script == "install.ps1":
        staging = tmp_path / "installer-under-test"
        staging.mkdir(exist_ok=True)
        path = staging / script
        shutil.copy2(INSTALLER_DIR / script, path)
    assert _PWSH is not None
    return [
        _PWSH,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(path),
        *flags,
    ]


def _flags(script: str) -> tuple[str, ...]:
    return () if script == "update.ps1" else ("-Yes",)


def _invoke(
    tmp_path: Path, script: str, env: dict[str, str], *flags: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _script_args(tmp_path, script, *_flags(script), *flags),
        cwd=str(tmp_path / "home"),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _out(result: subprocess.CompletedProcess[str]) -> str:
    return _plain(result.stdout + result.stderr)


def _in(message: str, plain: str) -> bool:
    """MESSAGE is in PLAIN, whitespace aside (a long path may wrap)."""
    return _squashed(message) in _squashed(plain)


def _origin(home: Path) -> str:
    return git(["config", "--get", "remote.origin.url"], home).strip()


def _wait_for(path: Path, seconds: float = 90.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.1)
    return path.exists()


# L1: the clone's own settings and attributes ---------------------------------


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_gpg_program_in_the_worktree_config_is_refused(
    tmp_path: Path, script: str
) -> None:
    """git reads a clone's config.worktree once extensions.worktreeConfig is
    set, so a gpg.program there would run in place of the user's gpg (here
    one that writes a marker and reports a good maintainer signature). It is
    refused before anything is fetched, naming the key and the file."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "evil-gpg-ran"
    _gpg(tmp_path / "evil-gpg", f"touch '{marker.as_posix()}'\n")
    git(["config", "extensions.worktreeConfig", "true"], home)
    git(
        [
            "config",
            "--worktree",
            "gpg.program",
            (tmp_path / "evil-gpg" / "gpg").as_posix(),
        ],
        home,
    )

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert not marker.exists(), plain
    assert _head(home) == old_commit, plain
    assert result.returncode != 0, plain
    assert _in(
        f"{home}'s own git config sets gpg.program{TRUSTED} "
        f"{home}/.git/config.worktree, then re-run.",
        plain,
    ), plain
    assert git(["tag", "--list", TAG], home).strip() == "", plain


_SMUDGE_CONFIG = (
    '[filter "evil"]\n\tclean = cat\n\tsmudge = "touch \'{marker}\'; cat"\n'
)


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize("where", ["clone-config", "user-config"])
def test_a_filter_the_clone_assigns_is_refused(
    tmp_path: Path, script: str, where: str
) -> None:
    """A checkout runs the smudge filter of every file .git/info/attributes
    gives one. The filter may be the clone's own (its config sets
    filter.<name>.*) or one the user's own config defines; either way the
    update stops before anything is fetched, and the filter never runs."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "smudge-ran"
    smudge = _SMUDGE_CONFIG.format(marker=marker.as_posix())
    (home / ".git" / "info").mkdir(exist_ok=True)
    attributes = home / ".git" / "info" / "attributes"
    attributes.write_text("# assigned here\n* filter=evil\n", encoding="utf-8")
    user_config = ""
    if where == "clone-config":
        with (home / ".git" / "config").open("a", encoding="utf-8", newline="\n") as f:
            f.write(smudge)
        expected = f"{home}'s own git config sets filter.evil.clean{TRUSTED}"
    else:
        user_config = smudge
        expected = (
            f"{home}'s own git attributes set a filter (filter=), which the update "
            f"would trust. Remove it from {home}/.git/info/attributes, then re-run."
        )

    result = _invoke(
        tmp_path, script, _script_env(tmp_path, gitconfig_extra=user_config)
    )

    plain = _out(result)
    assert not marker.exists(), plain
    assert _head(home) == old_commit, plain
    assert result.returncode != 0, plain
    assert _in(expected, plain), plain


def test_a_filter_line_that_is_a_comment_is_not_refused(tmp_path: Path) -> None:
    """Only an attribute line sets a filter: a comment that mentions filter=
    leaves the update to go on."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    (home / ".git" / "info").mkdir(exist_ok=True)
    (home / ".git" / "info" / "attributes").write_text(
        "  # was: * filter=evil\n*.txt text\n", encoding="utf-8"
    )

    result = _invoke(tmp_path, "update.ps1", _script_env(tmp_path))

    plain = _out(result)
    assert "own git attributes set a filter" not in plain, plain
    assert _head(home) == _head(repo), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_an_ext_url_rewrite_in_the_clone_is_refused(
    tmp_path: Path, script: str
) -> None:
    """A url.<ext::command>.insteadOf rewrite of the clone's origin, with the
    ext transport allowed, would run the command on fetch. The clone's
    settings are refused before the fetch, and the command never runs."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "ext-ran"
    git(["config", "protocol.ext.allow", "always"], home)
    git(
        [
            "config",
            f"url.ext::cmd /c type nul > {marker} & rem .insteadOf",
            _origin(home),
        ],
        home,
    )

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert not marker.exists(), plain
    assert _head(home) == old_commit, plain
    assert result.returncode != 0, plain
    assert _in(f"{home}'s own git config sets protocol.ext.allow{TRUSTED}", plain), (
        plain
    )


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_the_update_runs_no_fsmonitor_and_no_ext_transport_from_any_config(
    tmp_path: Path, script: str
) -> None:
    """Every git command on the clone empties core.fsmonitor and refuses the
    ext transport, so neither runs even when the user's own config (trusted,
    so not refused) asks for them: here a fsmonitor program and an ext::
    rewrite of the origin, each writing a marker. The fetch then fails."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    fsmonitor_marker = tmp_path / "fsmonitor-ran"
    ext_marker = tmp_path / "ext-ran"
    hook = _sh(
        tmp_path / "fsmonitor.sh", f"touch '{fsmonitor_marker.as_posix()}'\nexit 1\n"
    )
    user_config = tmp_path / "user-extra.gitconfig"
    for key, value in (
        ("core.fsmonitor", hook.as_posix()),
        ("protocol.ext.allow", "always"),
        (f"url.ext::cmd /c type nul > {ext_marker} & rem .insteadOf", _origin(home)),
    ):
        git(["config", "--file", str(user_config), key, value], tmp_path)

    result = _invoke(
        tmp_path,
        script,
        _script_env(tmp_path, gitconfig_extra=user_config.read_text(encoding="utf-8")),
    )

    plain = _out(result)
    assert not fsmonitor_marker.exists(), plain
    assert not ext_marker.exists(), plain
    assert "Could not fetch from the origin of" in plain, plain
    assert _head(home) == old_commit, plain


# L2: the settings are checked before git reads the clone ---------------------


@pytest.mark.parametrize("path", ["in-place", "replace"])
def test_a_clones_fsmonitor_never_runs(tmp_path: Path, path: str) -> None:
    """A core.fsmonitor program in the clone's own config runs whenever git
    reads the index. The settings check runs before every such command: in
    an update in place, and when -Yes replaces the clone with the archive
    (git status checks it for local work)."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "fsmonitor-ran"
    hook = _sh(tmp_path / "fsmonitor.sh", f"touch '{marker.as_posix()}'\nexit 1\n")
    git(["config", "core.fsmonitor", hook.as_posix()], home)
    if path == "replace":
        env = _script_env(
            tmp_path, mode="checksum", extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"}
        )
    else:
        env = _script_env(tmp_path)

    result = _invoke(tmp_path, "install.ps1", env)

    plain = _out(result)
    assert not marker.exists(), plain
    assert _head(home) == old_commit, plain
    assert result.returncode != 0, plain
    assert _in(f"{home}'s own git config sets core.fsmonitor{TRUSTED}", plain), plain


# L3: git config variables from the calling shell ------------------------------


def _evil_mirror(tmp_path: Path, repo: Path) -> tuple[Path, str]:
    """A copy of the fixture repository whose TAG names another commit (one
    that adds evil.txt); return (copy, that commit)."""
    evil = tmp_path / "evil-repo"
    git(["clone", "--quiet", str(repo), str(evil)], tmp_path)
    (evil / "evil.txt").write_text("not in the release\n", encoding="utf-8")
    git(["add", "evil.txt"], evil)
    _commit_in(evil, "evil")
    git(["tag", "--delete", TAG], evil)
    repoint_tag(evil, TAG, TAG)
    return evil, _head(evil)


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize("variable", ["GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"])
def test_git_config_files_named_by_the_calling_shell_are_not_read(
    tmp_path: Path, script: str, variable: str
) -> None:
    """A GIT_CONFIG_GLOBAL or GIT_CONFIG_SYSTEM inherited from the calling
    shell would make git read another config file, here one that sends the
    fetch to another repository whose tag names another commit. The scripts
    clear both (and GIT_CONFIG_NOSYSTEM), so git reads the user's own config
    and the update gets the real tag."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    good_commit = _head(repo)
    evil, evil_commit = _evil_mirror(tmp_path, repo)
    redirect = tmp_path / "redirect.gitconfig"
    stub = tmp_path / "home" / ".gitconfig"
    env = _script_env(tmp_path)
    # The redirecting file names the stub gpg too, so the redirected tag
    # would pass its check on a script that read it.
    redirect.write_text(
        stub.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    git(
        [
            "config",
            "--file",
            str(redirect),
            f"url.{evil.as_posix()}.insteadOf",
            _origin(home),
        ],
        tmp_path,
    )
    env[variable] = str(redirect)
    if variable == "GIT_CONFIG_SYSTEM":
        env.pop("GIT_CONFIG_NOSYSTEM", None)

    result = _invoke(tmp_path, script, env)

    plain = _out(result)
    assert _head(home) == good_commit, plain
    assert _head(home) != evil_commit, plain
    assert not (home / "evil.txt").exists(), plain


# L4: folders a stopped run left ------------------------------------------------


def _plant_leftovers(tmp_path: Path) -> dict[str, Path]:
    """Lay out what a run killed part-way through a swap can leave beside
    APOTHEM_HOME (tmp_path/apothem-home)."""
    old = tmp_path / ".apothem-old.aaaaaa"
    (old / "home" / "src" / "apothem").mkdir(parents=True)
    (old / "home" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    extract = tmp_path / ".apothem-extract.bbbbbb"
    tree = extract / f"apothem-{OLD_TAG}"
    (tree / "src" / "apothem").mkdir(parents=True)
    for name in ("backups", "state"):
        (tree / name).mkdir()
        (tree / name / "data.json").write_text("{}\n", encoding="utf-8")
    clone = tmp_path / ".apothem-clone.cccccc"
    clone.mkdir()
    other = tmp_path / ".apothem-extract.dddddd"
    other.mkdir()
    (other / "partial.zip").write_text("x", encoding="utf-8")
    (other / ".hidden").write_text("x", encoding="utf-8")
    return {
        "old": old,
        "extract": extract,
        "tree": tree,
        "clone": clone,
        "other": other,
    }


def _tree_listing(*roots: Path) -> list[str]:
    """Every path under ROOTS (each root included), sorted."""
    return sorted(
        p.as_posix()
        for root in roots
        if root.exists()
        for p in [root, *root.rglob("*")]
    )


@pytest.mark.parametrize("dry_run", [False, True], ids=["real", "dry-run"])
@pytest.mark.parametrize("home_state", ["present", "missing"])
def test_folders_a_stopped_run_left_stop_the_install(
    tmp_path: Path, dry_run: bool, home_state: str
) -> None:
    """Folders a killed run left beside APOTHEM_HOME stop the next install
    before anything is fetched, in a dry run too. The message names each one
    and what it holds, and nothing is moved or removed. When APOTHEM_HOME is
    missing, the folder it may have been moved into is named too."""
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / "apothem-home"
    if home_state == "present":
        _seed_earlier_install(home)
    aside = tmp_path / "apothem-home.before-apothem-20260101000000"
    (aside / "apothem-home").mkdir(parents=True)
    (aside / "apothem-home" / "notes.txt").write_text("mine\n", encoding="utf-8")
    left = _plant_leftovers(tmp_path)
    watched = (home, aside, left["old"], left["extract"], left["clone"], left["other"])
    before = _tree_listing(*watched)

    result = _invoke(
        tmp_path,
        "install.ps1",
        _script_env(tmp_path),
        *(["-DryRun"] if dry_run else []),
    )

    plain = _out(result)
    assert result.returncode != 0, plain
    expected = [
        f"An earlier run was stopped part-way and left these folders beside {home}:",
        f"{left['old']}: the earlier install that was being replaced, in "
        f"{left['old'] / 'home'}",
        f"{left['extract']}: the new source that was being installed, in "
        f"{left['tree']}, with engine data moved into it: backups state",
        f"{left['other']}: files from that run (partial.zip .hidden)",
        f"{left['clone']}: empty",
        f"Nothing was changed. If {home} is missing, move the earlier install back "
        f"to it first. Then move any engine data listed above back into {home}, "
        "remove these folders, and re-run.",
    ]
    for line in expected:
        assert _in(line, plain), (line, plain)
    aside_line = (
        f"{aside}: the earlier contents of {home}, moved aside, in "
        f"{aside / 'apothem-home'}"
    )
    assert _in(aside_line, plain) == (home_state == "missing"), plain
    order = [_squashed(plain).index(_squashed(line)) for line in expected[1:]]
    assert order[0] < order[1] < order[2] < order[3], plain
    assert _tree_listing(*watched) == before, plain
    assert "Cloning" not in plain, plain


def test_a_local_tree_is_not_stopped_by_leftovers(tmp_path: Path) -> None:
    """A local tree (APOTHEM_SOURCE) is run where it is and swaps nothing, so
    folders beside APOTHEM_HOME do not stop it."""
    _plant_leftovers(tmp_path)
    source = tmp_path / "source"
    (source / "src" / "apothem").mkdir(parents=True)
    (source / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (source / "src" / "apothem" / "__init__.py").write_text("", encoding="utf-8")
    (source / "src" / "apothem" / "__main__.py").write_text("", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity: {}\n", encoding="utf-8")
    env = _script_env(
        tmp_path,
        extra_env={
            "APOTHEM_SOURCE": str(source),
            "APOTHEM_PROFILE": str(profile),
            "APOTHEM_SKIP_VERIFY": "1",
            "APOTHEM_BIN_DIR": str(tmp_path / "bin"),
        },
    )

    result = _invoke(tmp_path, "install.ps1", env)

    plain = _out(result)
    assert "An earlier run was stopped part-way" not in plain, plain
    assert "Using explicit source" in plain, plain


# L5: the install lock -----------------------------------------------------------


def _lock(tmp_path: Path) -> Path:
    return tmp_path / "apothem-home.lock"


def _held_message(tmp_path: Path) -> str:
    home = tmp_path / "apothem-home"
    return (
        f"Another Apothem install, update or uninstall is running on {home}. Wait "
        f"for it to finish, then re-run. If none is running, remove {home}.lock, "
        "then re-run."
    )


def _prepare(tmp_path: Path, script: str) -> Path:
    """What SCRIPT works on: a clone at OLD_TAG with TAG at the next commit
    (update.ps1), the fixture repository for a fresh clone (install.ps1), or
    an install to remove (uninstall.ps1). Return APOTHEM_HOME."""
    home = tmp_path / "apothem-home"
    if script == "update.ps1":
        repo, home, _ = _clone_at_old_tag(tmp_path)
        repoint_tag(repo, TAG, TAG)
    elif script == "install.ps1":
        make_tagged_repo(tmp_path, TAG)
    else:
        _seed_earlier_install(home)
    return home


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1", "uninstall.ps1"])
def test_a_second_run_stops_while_another_holds_the_lock(
    tmp_path: Path, script: str
) -> None:
    """A run holds <APOTHEM_HOME>.lock with no sharing, so a second run's open
    fails and it stops at once, changing nothing. Here the test itself holds
    the file, as a running installer would."""
    home = _prepare(tmp_path, script)
    before = _tree_listing(home)
    lock = _lock(tmp_path)
    env = _script_env(tmp_path)

    with lock.open("w", encoding="utf-8"):
        result = _invoke(tmp_path, script, env)

    plain = _out(result)
    assert result.returncode != 0, plain
    assert _in(_held_message(tmp_path), plain), plain
    assert _tree_listing(home) == before, plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1", "uninstall.ps1"])
@pytest.mark.parametrize("pid", ["4242", ""], ids=["names-a-process", "names-none"])
def test_a_lock_folder_from_the_sh_scripts_is_reported_not_taken(
    tmp_path: Path, script: str, pid: str
) -> None:
    """install.sh, update.sh and uninstall.sh lock with a folder of the same
    name that holds their process ID. A run finds it, cannot check that
    process from PowerShell, and stops with how to remove it, leaving it."""
    _prepare(tmp_path, script)
    lock = _lock(tmp_path)
    lock.mkdir()
    if pid:
        (lock / "pid").write_text(pid + "\n", encoding="utf-8")

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert result.returncode != 0, plain
    home = tmp_path / "apothem-home"
    if pid:
        assert _in(_held_message(tmp_path), plain), plain
    else:
        assert _in(
            f"{lock} exists but names no running process; an Apothem run may have "
            "left it when it was stopped. Check that no Apothem install, update or "
            f"uninstall is running, remove {lock}, then re-run.",
            plain,
        ), plain
    assert lock.is_dir(), plain
    assert (lock / "pid").exists() == bool(pid)
    if script == "install.ps1":
        assert not home.exists(), plain


def _lock_probe(tmp_path: Path, record: Path, *, release: Path | None = None) -> str:
    """sh lines that write "held" to RECORD when the lock file exists and
    cannot be opened (another process holds it with no sharing), "free"
    otherwise; with RELEASE, they then wait (up to a minute) for that file."""
    lock = _lock(tmp_path).as_posix()
    body = (
        f"if [ -e '{lock}' ] && ! (: < '{lock}') 2>/dev/null; then s=held; else s=free; fi\n"
        f"printf '%s\\n' \"$s\" > '{record.as_posix()}.tmp'\n"
        f"mv '{record.as_posix()}.tmp' '{record.as_posix()}'\n"
    )
    if release is not None:
        body += (
            "i=0\n"
            f"while [ ! -e '{release.as_posix()}' ] && [ $i -lt 600 ]; do sleep 0.1; i=$((i+1)); done\n"
        )
    return body


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_the_lock_is_held_for_the_run_and_released_after_it(
    tmp_path: Path, script: str, outcome: str
) -> None:
    """While the tag is checked (the stub gpg looks) the lock is held, and
    once the run ends, after a failed check as after a passing one, the lock
    file is gone, so the next run can take it."""
    home = _prepare(tmp_path, script)
    record = tmp_path / "lock-state"
    status = GOOD if outcome == "success" else ""
    config = _gpg(tmp_path / "probe-gpg", _lock_probe(tmp_path, record), status)

    result = _invoke(tmp_path, script, _script_env(tmp_path, gpg_config=config))

    plain = _out(result)
    assert record.read_text(encoding="utf-8").strip() == "held", plain
    assert not _lock(tmp_path).exists(), plain
    if outcome == "success":
        assert _head(home) == _head(tmp_path / "fixture-repo"), plain
    else:
        assert result.returncode != 0, plain
        assert "is unsigned or its signature did not verify" in plain, plain


def test_the_uninstaller_holds_the_lock_and_releases_it(tmp_path: Path) -> None:
    """The uninstaller holds the lock while the engine runs (a stand-in that
    looks) and lets it go when it ends."""
    record = tmp_path / "lock-state"
    source = tmp_path / "source"
    package = source / "src" / "apothem"
    package.mkdir(parents=True)
    (source / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import os\n"
        "try:\n"
        "    with open(os.environ['APOTHEM_TEST_LOCK'], 'rb'):\n"
        "        state = 'free'\n"
        "except FileNotFoundError:\n"
        "    state = 'absent'\n"
        "except PermissionError:\n"
        "    state = 'held'\n"
        "with open(os.environ['APOTHEM_TEST_RECORD'], 'w') as f:\n"
        "    f.write(state)\n",
        encoding="utf-8",
    )
    env = _script_env(
        tmp_path,
        extra_env={
            "APOTHEM_SOURCE": str(source),
            "APOTHEM_TEST_LOCK": str(_lock(tmp_path)),
            "APOTHEM_TEST_RECORD": str(record),
            "APOTHEM_BIN_DIR": str(tmp_path / "bin"),
        },
    )

    result = _invoke(tmp_path, "uninstall.ps1", env)

    plain = _out(result)
    assert result.returncode == 0, plain
    assert record.read_text(encoding="utf-8") == "held", plain
    assert not _lock(tmp_path).exists(), plain


def test_a_killed_run_frees_the_lock(tmp_path: Path) -> None:
    """The system closes the lock file when the run's process dies, here
    killed while it checks the tag, so the lock is free at once and the file
    is gone."""
    _prepare(tmp_path, "install.ps1")
    record = tmp_path / "lock-state"
    release = tmp_path / "release-the-stub"
    done = tmp_path / "stub-done"
    config = _gpg(
        tmp_path / "probe-gpg",
        _lock_probe(tmp_path, record, release=release) + f": > '{done.as_posix()}'\n",
    )
    run = subprocess.Popen(
        _script_args(tmp_path, "install.ps1", "-Yes"),
        cwd=str(tmp_path / "home"),
        env=_script_env(tmp_path, gpg_config=config),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_for(record), "the stub gpg never ran"
        assert record.read_text(encoding="utf-8").strip() == "held"
        run.kill()
        run.wait(timeout=60)
        deadline = time.monotonic() + 10
        while _lock(tmp_path).exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _lock(tmp_path).exists()
    finally:
        release.write_text("", encoding="utf-8")
        _wait_for(done, 30)
        if run.poll() is None:
            run.kill()


def test_a_run_in_the_callers_session_frees_the_lock_when_it_fails(
    tmp_path: Path,
) -> None:
    """Run the way the one-liner runs it (the script text in the caller's
    own PowerShell session), the installer's failure does not end the
    session, so the lock must be let go as the error leaves the script."""
    _prepare(tmp_path, "install.ps1")
    record = tmp_path / "lock-state"
    config = _gpg(tmp_path / "probe-gpg", _lock_probe(tmp_path, record), "")
    env = _script_env(tmp_path, gpg_config=config)
    env["APOTHEM_TEST_SCRIPT"] = str(INSTALLER_DIR / "install.ps1")
    env["APOTHEM_TEST_LOCK"] = str(_lock(tmp_path))
    command = (
        "try { & ([scriptblock]::Create((Get-Content -Raw -LiteralPath "
        "$env:APOTHEM_TEST_SCRIPT))) -Yes } catch { 'SCRIPT-FAILED' }; "
        "if (Test-Path -LiteralPath $env:APOTHEM_TEST_LOCK) { 'LOCK-STILL-THERE' } "
        "else { 'LOCK-GONE' }"
    )
    assert _PWSH is not None

    result = subprocess.run(
        [_PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=str(tmp_path / "home"),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    plain = _out(result)
    assert record.read_text(encoding="utf-8").strip() == "held", plain
    assert "SCRIPT-FAILED" in plain, plain
    assert "LOCK-GONE" in plain, plain


# PowerShell stops the running pipeline on Ctrl+C; Stop() on the instance
# that runs the script does the same, while the stub gpg holds the run in
# the tag check.
_STOP_LIKE_CTRL_C = """
$ps = [powershell]::Create()
$null = $ps.AddScript((Get-Content -Raw -LiteralPath $env:APOTHEM_TEST_SCRIPT)).AddParameter('Yes')
$null = $ps.BeginInvoke()
$deadline = (Get-Date).AddSeconds(90)
while (-not (Test-Path -LiteralPath $env:APOTHEM_TEST_RECORD) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 100
}
$stop = $ps.BeginStop($null, $null)
$freed = $false
$deadline = (Get-Date).AddSeconds(30)
while (-not $freed -and (Get-Date) -lt $deadline) {
    $freed = -not (Test-Path -LiteralPath $env:APOTHEM_TEST_LOCK)
    if (-not $freed) { Start-Sleep -Milliseconds 100 }
}
New-Item -ItemType File -Path $env:APOTHEM_TEST_RELEASE | Out-Null
$ps.EndStop($stop)
"STATE=$($ps.InvocationStateInfo.State)"
"FREED=$freed"
"""


def test_stopping_a_run_like_ctrl_c_frees_the_lock(tmp_path: Path) -> None:
    """Ctrl+C stops the run's pipeline; the run lets the lock go as it stops,
    while the tag check it was in has not even finished."""
    _prepare(tmp_path, "install.ps1")
    record = tmp_path / "lock-state"
    release = tmp_path / "release-the-stub"
    config = _gpg(
        tmp_path / "probe-gpg", _lock_probe(tmp_path, record, release=release)
    )
    env = _script_env(tmp_path, gpg_config=config)
    env.update(
        {
            "APOTHEM_TEST_SCRIPT": str(INSTALLER_DIR / "install.ps1"),
            "APOTHEM_TEST_LOCK": str(_lock(tmp_path)),
            "APOTHEM_TEST_RECORD": str(record),
            "APOTHEM_TEST_RELEASE": str(release),
        }
    )
    assert _PWSH is not None

    result = subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _STOP_LIKE_CTRL_C,
        ],
        cwd=str(tmp_path / "home"),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    plain = _out(result)
    assert record.read_text(encoding="utf-8").strip() == "held", plain
    assert "STATE=Stopped" in plain, plain
    assert "FREED=True" in plain, plain
    assert not _lock(tmp_path).exists(), plain


# L5: the folder an earlier tree is moved into -----------------------------------


def _ps1_function_program(script: str, names: tuple[str, ...], body: str) -> str:
    """PowerShell that parses SCRIPT (not running it), defines its functions
    NAMES, then runs BODY."""
    lookups = "; ".join(
        f"$f = $ast.Find({{ param($n) $n -is [Management.Automation.Language."
        f"FunctionDefinitionAst] -and $n.Name -eq '{name}' }}, $true); "
        f"if (-not $f) {{ throw 'no {name}' }}; . ([scriptblock]::Create($f.Extent.Text))"
        for name in names
    )
    return (
        "Set-StrictMode -Version Latest; $ErrorActionPreference = 'Stop'; "
        "$tokens = $null; $errors = $null; "
        "$ast = [Management.Automation.Language.Parser]::ParseFile("
        f"'{INSTALLER_DIR / script}', [ref]$tokens, [ref]$errors); "
        "if ($errors) { throw ($errors -join ' | ') }; " + lookups + "; " + body
    )


def _pwsh_program(program: str, **env: str) -> subprocess.CompletedProcess[str]:
    assert _PWSH is not None
    return subprocess.run(
        [_PWSH, "-NoProfile", "-NonInteractive", "-Command", program],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_the_aside_folder_is_made_by_the_run_and_never_reused(tmp_path: Path) -> None:
    """New-AsideFolder makes <home>.before-apothem-<time> itself, by renaming
    a folder only this run knows, so a folder of that name made by someone
    else is never reused: the run takes <time>-<pid> instead, and with both
    taken it makes nothing. The time is fixed here."""
    stage = tmp_path / "stage"
    stage.mkdir()
    home = tmp_path / "apothem-home"
    planted = tmp_path / "apothem-home.before-apothem-20260101000000"
    planted.mkdir()
    (planted / "planted.txt").write_text("someone else's\n", encoding="utf-8")
    body = (
        "function Get-Date { '20260101000000' }; "
        "$ApothemHome = $env:T_HOME; "
        "$results = @(); "
        "foreach ($i in 1, 2) { $r = New-AsideFolder $env:T_STAGE; "
        "$results += $(if ($r) { [string]$r } else { 'NONE' }) }; "
        "[pscustomobject]@{ pid = $PID; results = $results } | ConvertTo-Json -Compress"
    )

    result = _pwsh_program(
        _ps1_function_program("install.ps1", ("New-AsideFolder",), body),
        T_HOME=str(home),
        T_STAGE=str(stage),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    claimed = Path(f"{planted}-{data['pid']}")
    assert data["results"] == [str(claimed), "NONE"], data
    assert claimed.is_dir()
    assert not any(claimed.iterdir())
    assert sorted(p.name for p in planted.iterdir()) == ["planted.txt"]
    assert not any(stage.iterdir()), list(stage.iterdir())


# L6: the tag's commit is what gets checked out ------------------------------


def _moving_gpg(tmp_path: Path, record: Path) -> Path:
    """A stub gpg that, the first time it runs (inside git verify-tag, after
    git has read the tag), moves refs/tags/TAG in the repository it runs in
    to an unsigned tag object of the same name for another commit, records
    that commit in RECORD, and reports a good maintainer signature."""
    flag = tmp_path / "moved-once"
    tag_file = tmp_path / "moved.tag"
    body = (
        f"if [ ! -e '{flag.as_posix()}' ]; then\n"
        f"    : > '{flag.as_posix()}'\n"
        "    export GIT_AUTHOR_NAME=Mover GIT_AUTHOR_EMAIL=mover@example.invalid\n"
        "    export GIT_COMMITTER_NAME=Mover GIT_COMMITTER_EMAIL=mover@example.invalid\n"
        "    tree=\"$(git rev-parse 'HEAD^{tree}')\"\n"
        '    moved="$(git commit-tree "$tree" -m moved)"\n'
        f"    printf 'object %s\\ntype commit\\ntag {TAG}\\n"
        "tagger Mover <mover@example.invalid> 1700000000 +0000\\n\\nmoved\\n' "
        f"\"$moved\" > '{tag_file.as_posix()}'\n"
        f"    object=\"$(git hash-object -t tag -w '{tag_file.as_posix()}')\"\n"
        f'    git update-ref refs/tags/{TAG} "$object"\n'
        f"    printf '%s\\n' \"$moved\" > '{record.as_posix()}'\n"
        "fi\n"
    )
    return _gpg(tmp_path / "moving-gpg", body)


@pytest.mark.parametrize(
    ("script", "case"),
    [
        ("install.ps1", "in-place"),
        ("update.ps1", "in-place"),
        ("install.ps1", "fresh-clone"),
    ],
)
def test_a_tag_moved_after_its_check_is_not_what_gets_checked_out(
    tmp_path: Path, script: str, case: str
) -> None:
    """The tag ref is read once and the commit its check found is checked out
    by ID. A ref moved while the check runs (here by the stub gpg) to another
    commit changes nothing: HEAD is the checked commit."""
    if case == "in-place":
        repo, home, _ = _clone_at_old_tag(tmp_path)
        repoint_tag(repo, TAG, TAG)
        good = _head(repo)
    else:
        repo, good = make_tagged_repo(tmp_path, TAG)
        home = tmp_path / "apothem-home"
    record = tmp_path / "moved-to"
    config = _moving_gpg(tmp_path, record)

    result = _invoke(tmp_path, script, _script_env(tmp_path, gpg_config=config))

    plain = _out(result)
    moved = record.read_text(encoding="utf-8").strip()
    assert moved, plain
    assert moved != good, plain
    assert _head(home) == good, plain


# L7a: the key that signed a tag is named ----------------------------------------


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize("keys", [1, 2])
def test_a_tag_signed_by_another_key_names_that_key(
    tmp_path: Path, script: str, keys: int
) -> None:
    """A valid signature from a key other than the maintainer's is refused,
    and the message says which key (or keys) signed it and which one must."""
    _prepare(tmp_path, script)
    third = "0123456789ABCDEF0123456789ABCDEF01234567"
    status = good_signature_status(OTHER_FINGERPRINT)
    signers = f"the key {OTHER_FINGERPRINT}"
    if keys == 2:
        status += good_signature_status(third.lower())
        signers = f"the keys {OTHER_FINGERPRINT}, {third}"
    after = "materialized." if script == "install.ps1" else "re-materialized."

    result = _invoke(tmp_path, script, _script_env(tmp_path, gpg_status=status))

    plain = _out(result)
    assert result.returncode != 0, plain
    assert _in(
        f"Tag {TAG} is signed by {signers}. A release tag must be signed by the "
        f"maintainer key {MAINTAINER_FINGERPRINT} that SECURITY.md publishes, and "
        "by no other key (possible tampering). Aborting before anything is "
        f"checked out or {after}",
        plain,
    ), plain


# L7b: a clone git will not work in --------------------------------------------


@pytest.mark.parametrize(
    ("script", "mode"),
    [("install.ps1", "signature"), ("update.ps1", None), ("install.ps1", "checksum")],
    ids=["install-in-place", "update", "install-replace"],
)
def test_a_clone_another_user_owns_is_refused_with_what_to_do(
    tmp_path: Path, script: str, mode: str | None
) -> None:
    """git refuses a repository another user owns ("dubious ownership");
    GIT_TEST_ASSUME_DIFFERENT_OWNER makes git treat the clone that way. The
    run stops with what to do, not git's own advice to mark it safe."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    extra = {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
    if mode == "checksum":
        extra["APOTHEM_ALLOW_UNVERIFIED"] = "1"

    result = _invoke(
        tmp_path, script, _script_env(tmp_path, mode=mode, extra_env=extra)
    )

    plain = _out(result)
    assert result.returncode != 0, plain
    assert _in(
        f"{home} is owned by someone else, so git refuses to work in it (git "
        f'reports "dubious ownership"). Run this as the user who owns {home}, take '
        "ownership of it, or point APOTHEM_HOME at a folder you own, then re-run.",
        plain,
    ), plain
    assert "safe.directory" not in plain, plain
    assert git(["rev-parse", "HEAD"], home).strip() == old_commit


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_clone_git_cannot_read_is_named(tmp_path: Path, script: str) -> None:
    """A clone whose .git file points nowhere stops the run with git's own
    first line in a message that says what to do."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    (home / ".git").write_text("gitdir: C:/no/such/repository\n", encoding="utf-8")

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert result.returncode != 0, plain
    assert _in(f"git could not read the clone at {home} (", plain), plain
    assert "Repair it or move it aside, then re-run." in plain, plain


# L7c: downloads that are redirected ---------------------------------------------


# Invoke-WebRequest stand-ins: each writes the file and returns a response
# whose final address is $env:T_FINAL, laid out as Windows PowerShell 5.1
# (BaseResponse.ResponseUri) or PowerShell 7 (BaseResponse.RequestMessage
# .RequestUri) gives it.
_IWR_51 = (
    "function Invoke-WebRequest { param([switch]$UseBasicParsing, $Uri, $OutFile, "
    "[switch]$PassThru) Set-Content -LiteralPath $OutFile -Value 'payload'; "
    "[pscustomobject]@{ BaseResponse = [pscustomobject]@{ ResponseUri = "
    "[uri]$env:T_FINAL } } }; "
)
_IWR_7 = (
    "function Invoke-WebRequest { param([switch]$UseBasicParsing, $Uri, $OutFile, "
    "[switch]$PassThru) Set-Content -LiteralPath $OutFile -Value 'payload'; "
    "[pscustomobject]@{ BaseResponse = [pscustomobject]@{ RequestMessage = "
    "[pscustomobject]@{ RequestUri = [uri]$env:T_FINAL } } } }; "
)


@pytest.mark.parametrize("shape", [_IWR_51, _IWR_7], ids=["5.1-shape", "7-shape"])
@pytest.mark.parametrize(
    ("asked", "final", "kept"),
    [
        ("https://example.invalid/a.zip", "http://example.invalid/a.zip", False),
        ("https://example.invalid/a.zip", "https://mirror.example.invalid/a.zip", True),
        ("http://127.0.0.1:9/a.zip", "http://127.0.0.1:9/b.zip", True),
    ],
    ids=["https-to-http", "https-to-https", "http-base"],
)
def test_a_download_redirected_off_https_fails(
    tmp_path: Path, shape: str, asked: str, final: str, kept: bool
) -> None:
    """A download from an https:// address that ended at another scheme
    fails and leaves no file; an http:// base (a local mirror) is used as
    given, as install.sh's curl --proto-redir =https allows."""
    out = tmp_path / "download.bin"
    body = (
        shape
        + "try { Save-Download $env:T_ASKED $env:T_OUT; 'SAVED' } "
        + "catch { 'REFUSED: ' + $_.Exception.Message }"
    )

    result = _pwsh_program(
        _ps1_function_program("install.ps1", ("Save-Download",), body),
        T_ASKED=asked,
        T_FINAL=final,
        T_OUT=str(out),
    )

    text = result.stdout + result.stderr
    assert result.returncode == 0, text
    assert ("SAVED" in text) == kept, text
    assert out.exists() == kept, text
    if not kept:
        assert "is not an https:// address" in text, text


def test_every_download_goes_through_save_download() -> None:
    """install.ps1 calls Invoke-WebRequest in one place, Save-Download, and
    every release file it fetches goes through it."""
    text = (INSTALLER_DIR / "install.ps1").read_text(encoding="ascii")
    assert text.count("Invoke-WebRequest") == 1, text.count("Invoke-WebRequest")
    assert text.count('Save-Download "$ApothemReleaseBase/$ApothemRef/') == 4
