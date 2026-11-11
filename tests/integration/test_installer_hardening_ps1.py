# SPDX-License-Identifier: MIT

"""The PowerShell installer, updater and uninstaller: what an existing clone
may carry, the git environment they run in, the install lock, the folders a
stopped run leaves, the tag's commit, and downloads that are redirected.

The Windows counterpart of the sh tests for the same rules
(``test_installer_*`` for install.sh, update.sh and uninstall.sh), which
print the same messages (tests/scripts/test_installer_parity.py compares
them). Each case plants what a run must refuse or survive: a key in the
clone's own config or config.worktree that is not on the allow-list, an
attribute that assigns a filter, a submodule, a git variable inherited from
the calling shell, a lock held by another run, folders a killed run left
(for this APOTHEM_HOME or another), a tag ref moved while it is checked, or
a download redirected away from https. Stub gpg programs (sh scripts, which
Git for Windows runs through its own sh) report a signature and, where a
case needs it, record whether the lock is held, wait, move the tag ref, or
record what they were asked to verify.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
    _make_junction,
    _plain,
    _seed_earlier_install,
    _squashed,
    global_gitconfig,
)

INSTALLER_DIR = REPO_ROOT / "scripts" / "installer"
GOOD = good_signature_status(MAINTAINER_FINGERPRINT)
TRUSTED = (
    ", which an update in place does not accept in a clone's own config. Remove it from"
)

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


@pytest.mark.parametrize(
    ("script", "path"),
    [
        ("install.ps1", "in-place"),
        ("update.ps1", "in-place"),
        ("install.ps1", "replace"),
    ],
)
def test_the_update_runs_no_fsmonitor_and_no_ext_transport_from_any_config(
    tmp_path: Path, script: str, path: str
) -> None:
    """Every git command on the clone empties core.fsmonitor and refuses the
    ext transport, so neither runs even when the user's own config (trusted,
    so not refused) asks for them: here a fsmonitor program and an ext::
    rewrite of the origin, each writing a marker. An update in place then
    fails at the fetch. When -Yes replaces the clone with the archive, the
    git status calls that look for local work run with the same settings,
    and the run goes on to the download, which fails here."""
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

    extra = user_config.read_text(encoding="utf-8")
    if path == "replace":
        env = _script_env(
            tmp_path,
            mode="checksum",
            gitconfig_extra=extra,
            extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"},
        )
    else:
        env = _script_env(tmp_path, gitconfig_extra=extra)

    result = _invoke(tmp_path, script, env)

    plain = _out(result)
    assert not fsmonitor_marker.exists(), plain
    assert not ext_marker.exists(), plain
    if path == "replace":
        assert "Replacing the git clone at" in plain, plain
        assert "Could not download" in plain, plain
    else:
        assert "Could not fetch from the origin of" in plain, plain
    assert _head(home) == old_commit, plain


# L2: the settings are checked before git reads the clone ---------------------


@pytest.mark.parametrize("path", ["in-place", "replace"])
def test_a_clones_fsmonitor_never_runs(tmp_path: Path, path: str) -> None:
    """A core.fsmonitor program in the clone's own config runs whenever git
    reads the index. It never runs here, in an update in place or when -Yes
    replaces the clone with the archive (git status checks it for local
    work), and the run names the key. Two defences each stop it: the config
    check refuses the key, and every git command empties core.fsmonitor, so
    this test cannot tell which came first. The static order checks in
    tests/scripts/test_installer_parity.py guard that the config check runs
    before any command that reads the index."""
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
    clear both for the run, so git reads the user's own config and the
    update gets the real tag."""
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


#: APOTHEM_HOME's own folder name in these tests; staging folders carry it.
LEAF = "apothem-home"
OLD_NOTE = (
    " (made by an earlier installer that did not record which home it was for, "
    "so it may belong to any Apothem home in {parent}: check what it holds "
    "before you move or remove it)"
)
#: install.ps1's aside temp folder, left empty by a kill between its
#: creation and its rename; the report leaves it out.
ASIDE_TEMP = "aside." + "0123456789abcdef" * 2


def _plant_leftovers(tmp_path: Path) -> dict[str, Path]:
    """Lay out what killed runs can leave beside APOTHEM_HOME
    (tmp_path/apothem-home): this home's staging folders, named for it; one
    an earlier installer made, whose name does not say which home; and, not
    to be reported, another home's staging folders, a file and a junction
    with staging names."""
    old = tmp_path / f".apothem-old.{LEAF}.aaaaaa"
    (old / "home" / "src" / "apothem").mkdir(parents=True)
    (old / "home" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    extract = tmp_path / f".apothem-extract.{LEAF}.bbbbbb"
    tree = extract / f"apothem-{OLD_TAG}"
    (tree / "src" / "apothem").mkdir(parents=True)
    for name in ("backups", "state"):
        (tree / name).mkdir()
        (tree / name / "data.json").write_text("{}\n", encoding="utf-8")
    (extract / ASIDE_TEMP).mkdir()
    clone = tmp_path / f".apothem-clone.{LEAF}.cccccc"
    (clone / ASIDE_TEMP).mkdir(parents=True)
    other = tmp_path / ".apothem-extract.dddddd"
    other.mkdir()
    for name in ("partial.zip", ".hidden", "Zeta", "_under"):
        (other / name).write_text("x", encoding="utf-8")
    foreign = tmp_path / ".apothem-extract.other-home.eeeeee"
    (foreign / f"apothem-{OLD_TAG}" / "backups").mkdir(parents=True)
    longer = tmp_path / f".apothem-clone.{LEAF}.y.ffffff"
    (longer / "apothem").mkdir(parents=True)
    a_file = tmp_path / f".apothem-old.{LEAF}.gggggg"
    a_file.write_text("not a folder\n", encoding="utf-8")
    target = tmp_path / "junction-target"
    (target / "apothem").mkdir(parents=True)
    junction = tmp_path / f".apothem-extract.{LEAF}.hhhhhh"
    _make_junction(junction, target)
    return {
        "old": old,
        "extract": extract,
        "tree": tree,
        "clone": clone,
        "other": other,
        "foreign": foreign,
        "longer": longer,
        "file": a_file,
        "junction": junction,
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
    before anything is fetched, in a dry run too. Each one gets a line of
    its own on the error stream (PowerShell 7 does not join them): this
    home's folders first, then the one an earlier installer made, with a
    note that it may belong to any home, each group in ordinal order, names
    inside sorted the same way. Another home's folders, a file and a
    junction are not named, nor is the aside temp folder. Nothing is moved
    or removed. When APOTHEM_HOME is missing, the folders it may have been
    moved into are named too: the earlier contents in <aside>/<home's name>,
    or in the aside folder itself for the earlier layout."""
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / LEAF
    if home_state == "present":
        _seed_earlier_install(home)
    aside = tmp_path / f"{LEAF}.before-apothem-20260101000000"
    (aside / LEAF).mkdir(parents=True)
    (aside / LEAF / "notes.txt").write_text("mine\n", encoding="utf-8")
    flat = tmp_path / f"{LEAF}.before-apothem-20250101000000-77"
    flat.mkdir()
    (flat / "notes.txt").write_text("mine\n", encoding="utf-8")
    left = _plant_leftovers(tmp_path)
    watched = (home, aside, flat, *left.values())
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
        f"  x An earlier run was stopped part-way and left these folders beside {home}:",
        f"    {left['clone']}: empty",
        f"    {left['extract']}: the new source that was being installed, in "
        f"{left['tree']}, with these entries moved into it from {home}: backups, "
        "state",
        f"    {left['old']}: the earlier install that was being replaced, in "
        f"{left['old'] / 'home'}",
        f"    {left['other']}: files from that run (.hidden, Zeta, _under, "
        "partial.zip)" + OLD_NOTE.format(parent=tmp_path),
    ]
    if home_state == "missing":
        expected += [
            f"    {flat}: the earlier contents of {home}, moved aside, in {flat}",
            f"    {aside}: the earlier contents of {home}, moved aside, in "
            f"{aside / LEAF}",
        ]
    lines = [line.rstrip() for line in result.stderr.splitlines()]
    assert expected[0] in lines, plain
    first = lines.index(expected[0])
    assert lines[first : first + len(expected)] == expected, plain
    assert _in(
        f"Nothing was changed. If {home} is missing, move the earlier install back "
        "to it first. Then move every entry listed above as moved into a new "
        "source back into the home it came from, remove the folders listed "
        "above, and re-run.",
        plain,
    ), plain
    for name in ("foreign", "longer", "file", "junction"):
        assert str(left[name]) not in plain, (name, plain)
    assert ASIDE_TEMP not in plain, plain
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


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1", "uninstall.ps1"])
def test_a_lock_folder_whose_process_id_comes_a_moment_later_reads_as_held(
    tmp_path: Path, script: str
) -> None:
    """A POSIX run writes its process ID a moment after it makes the lock
    folder. A PowerShell run that finds the folder in between looks again
    and reports the lock as held, not as one a stopped run left. The test
    writes the process ID 0.3 seconds after Lock-ApothemHome starts."""
    lock = _lock(tmp_path)
    lock.mkdir()
    ready = tmp_path / "ready"
    body = (
        "function Write-Fail { param([string]$Msg) throw $Msg }; "
        "$DryRun = $false; $ApothemHome = $env:T_HOME; "
        "$HomeLockPath = $env:T_LOCK; "
        "Set-Content -LiteralPath $env:T_READY -Value 'ready'; "
        "try { Lock-ApothemHome; 'TAKEN' } "
        "catch { 'REFUSED: ' + $_.Exception.Message }"
    )
    assert _PWSH is not None
    run = subprocess.Popen(
        [
            _PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _ps1_function_program(script, ("Lock-ApothemHome",), body),
        ],
        env={
            **os.environ,
            "T_HOME": str(tmp_path / "apothem-home"),
            "T_LOCK": str(lock),
            "T_READY": str(ready),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 120
    while not ready.exists():
        assert run.poll() is None, run.communicate()
        assert time.monotonic() < deadline, "Lock-ApothemHome never started"
        time.sleep(0.02)
    time.sleep(0.3)
    (lock / "pid").write_text("4242\n", encoding="utf-8")

    out, err = run.communicate(timeout=120)

    plain = out + err
    assert "REFUSED: " in plain, plain
    assert _in(_held_message(tmp_path), plain), plain
    assert "names no running process" not in plain, plain


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
# the tag check. Ctrl+C also reaches every process in the console, but
# Stop() ends only the one process the run started, so the run gets the
# git.exe that does the work first on PATH (see _working_git_dir).
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


# The git a PowerShell PATH finds first is Git for Windows' cmd\git.exe (or
# bin\git.exe), which only starts the git.exe that does the work and waits
# for it. Stop() would end that starter and leave the working git.exe
# running, holding the run's output open, so the stop could not finish
# before the tag check did. Git Bash's PATH has the working git.exe first.
def _working_git_dir() -> str:
    """The folder `git --exec-path` names, which holds the working git.exe."""
    folder = Path(git(["--exec-path"], REPO_ROOT).strip())
    assert (folder / "git.exe").is_file(), f"no git.exe in {folder}"
    return str(folder)


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
            "PATH": os.pathsep.join([_working_git_dir(), env["PATH"]]),
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


#: Whether the PowerShell these tests run is PowerShell 7 (pwsh) rather than
#: Windows PowerShell 5.1, which _PWSH falls back to when pwsh is missing.
_PWSH_IS_7 = _PWSH is not None and Path(_PWSH).stem.lower() == "pwsh"


# Invoke-WebRequest stand-ins: each writes the file and returns a response
# whose final address is $env:T_FINAL, laid out as Windows PowerShell 5.1
# (BaseResponse.ResponseUri) or PowerShell 7 (BaseResponse.RequestMessage
# .RequestUri) gives it.
_IWR_51 = (
    "function Invoke-WebRequest { [CmdletBinding()] param([switch]$UseBasicParsing, "
    "$Uri, $OutFile, [switch]$PassThru, $MaximumRedirection) "
    "Set-Content -LiteralPath $OutFile -Value 'payload'; "
    "[pscustomobject]@{ BaseResponse = [pscustomobject]@{ ResponseUri = "
    "[uri]$env:T_FINAL } } }; "
)
_IWR_7 = (
    "function Invoke-WebRequest { [CmdletBinding()] param([switch]$UseBasicParsing, "
    "$Uri, $OutFile, [switch]$PassThru, $MaximumRedirection) "
    "Set-Content -LiteralPath $OutFile -Value 'payload'; "
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
    """Under PowerShell 7, which follows redirects itself, a download from an
    https:// address that ended at another scheme fails and leaves no file;
    an http:// base (a local mirror) is used as given, as install.sh's curl
    --proto-redir =https allows. Windows PowerShell 5.1 follows an https://
    download's redirects one hop at a time instead, which these stand-ins
    do not answer; test_windows_powershell_checks_every_redirect
    covers that."""
    if asked.startswith("https://") and not _PWSH_IS_7:
        pytest.skip("the PowerShell found is Windows PowerShell 5.1, not pwsh")
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
    """install.ps1 calls Invoke-WebRequest only inside Save-Download, and
    every release file it fetches goes through it."""
    text = (INSTALLER_DIR / "install.ps1").read_text(encoding="ascii")
    start = text.index("function Save-Download {")
    end = text.index("\n}", start)
    calls = [m.start() for m in re.finditer("Invoke-WebRequest", text)]
    assert calls, "install.ps1 no longer downloads with Invoke-WebRequest"
    assert all(start < at < end for at in calls), calls
    assert text.count('Save-Download "$ApothemReleaseBase/$ApothemRef/') == 4


# D1: the clone's own config may hold only the keys on the allow-list ---------


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    ("settings", "printed"),
    [
        pytest.param(
            (
                ("hook.apothem-test.command", "touch '{marker}'"),
                ("hook.apothem-test.event", "post-checkout"),
                ("hook.apothem-test.event", "reference-transaction"),
            ),
            "hook.apothem-test.command",
            id="config-hook",
        ),
        pytest.param(
            (("gc.recentObjectsHook", "touch '{marker}'"),),
            "gc.recentobjectshook",
            id="gc-hook",
        ),
        pytest.param(
            (("pager.fetch", "touch '{marker}'; cat"),), "pager.fetch", id="pager"
        ),
        pytest.param(
            (("core.pager", "touch '{marker}'; cat"),), "core.pager", id="core-pager"
        ),
        pytest.param(
            (("remote.upstream.url", "{repo}"),),
            "remote.upstream.url",
            id="other-remote",
        ),
        pytest.param((("core.autocrlf", "true"),), "core.autocrlf", id="autocrlf"),
        pytest.param(
            (
                ("core.repositoryformatversion", "1"),
                ("extensions.refStorage", "reftable://{folder}"),
            ),
            "extensions.refstorage",
            id="ref-storage-folder",
        ),
    ],
)
def test_a_clone_config_key_off_the_allow_list_is_refused(
    tmp_path: Path, script: str, settings: tuple[tuple[str, str], ...], printed: str
) -> None:
    """Only the keys git clone and git init write, and a few that name no
    program, file or address, may be in the clone's own config. Any other
    stops the run before anything is fetched, naming the key and the file:
    a config-based hook (git 2.54 and later run it on checkout and on every
    ref update, whatever core.hooksPath says), gc's recentObjectsHook (the
    fetch's own automatic maintenance runs it), a pager, a second remote,
    a line-ending rule, and extensions.refStorage naming a folder."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "key-program-ran"
    for key, value in settings:
        formatted = value.format(
            marker=marker.as_posix(),
            repo=repo.as_posix(),
            folder=(tmp_path / "refs-elsewhere").as_posix(),
        )
        git(["config", "--add", key, formatted], home)

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert _in(
        f"{home}'s own git config sets {printed}{TRUSTED} {home}/.git/config, then "
        "re-run.",
        plain,
    ), plain
    if printed == "extensions.refstorage":
        # git itself cannot read the refs while that value names a folder.
        git(["config", "--unset-all", "extensions.refStorage"], home)
    assert _head(home) == old_commit, plain
    assert git(["tag", "--list", TAG], home).strip() == "", plain


def test_the_keys_a_clone_may_hold_let_the_update_go_on(tmp_path: Path) -> None:
    """A clone that carries keys from the allow-list beyond the ones clone
    wrote (the user's identity, git pull's and git maintenance's settings,
    a branch description, the long-path switch, and extensions.refStorage
    set to files) is updated."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    for key, value in (
        ("user.name", "Someone"),
        ("user.email", "someone@example.invalid"),
        ("pull.rebase", "false"),
        ("pull.ff", "only"),
        ("maintenance.auto", "false"),
        ("maintenance.strategy", "incremental"),
        ("branch.feature/x.description", "mine"),
        ("core.longpaths", "true"),
        ("core.repositoryformatversion", "1"),
        ("extensions.refStorage", "files"),
    ):
        git(["config", key, value], home)

    result = _invoke(tmp_path, "update.ps1", _script_env(tmp_path))

    plain = _out(result)
    assert "own git config sets" not in plain, plain
    assert _head(home) == _head(repo), plain


# D2: submodules and the user's own maintenance settings ------------------------


def _nested_repository(home: Path, marker: Path) -> None:
    """Make HOME/evilsub a git repository whose own config gives its a.txt a
    clean filter that writes MARKER, change a.txt, and record evilsub in
    HOME's index as a gitlink (a submodule entry). a.txt keeps its size and
    gets a later time, so git status inside evilsub must read it through
    the filter to tell whether it changed."""
    sub = home / "evilsub"
    sub.mkdir()
    git(["init", "--quiet", "--initial-branch", "main"], sub)
    (sub / ".gitattributes").write_text("*.txt filter=evil\n", encoding="utf-8")
    (sub / "a.txt").write_text("a\n", encoding="utf-8")
    git(["add", "-A"], sub)
    _commit_in(sub, "nested")
    git(["config", "filter.evil.clean", f"touch '{marker.as_posix()}'; cat"], sub)
    (sub / "a.txt").write_text("b\n", encoding="utf-8")
    later = time.time() + 60
    os.utime(sub / "a.txt", (later, later))
    git(["add", "evilsub"], home)


@pytest.mark.parametrize(
    ("script", "flags"),
    [("install.ps1", ()), ("update.ps1", ()), ("install.ps1", ("-DryRun",))],
    ids=["install", "update", "install-dry-run"],
)
def test_a_clone_that_holds_a_submodule_is_refused(
    tmp_path: Path, script: str, flags: tuple[str, ...]
) -> None:
    """A gitlink in the clone's index is a submodule, a repository whose own
    settings nothing checks (here a clean filter that writes a marker). A
    release tree has none, so the clone is refused before anything is
    fetched, in a dry run too, and git never runs inside the submodule."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "nested-filter-ran"
    _nested_repository(home, marker)

    result = _invoke(tmp_path, script, _script_env(tmp_path), *flags)

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert _in(
        f"{home} holds a submodule at evilsub (its index records a git repository "
        "there). A release tree has none, and the update would run git inside it. "
        "Remove the submodule from the clone, then re-run.",
        plain,
    ), plain
    assert _head(home) == old_commit, plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_clone_that_keeps_submodule_repositories_is_refused(
    tmp_path: Path, script: str
) -> None:
    """A .git/modules folder holds submodule repositories; such a clone is
    refused before anything is fetched."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    (home / ".git" / "modules" / "evilsub").mkdir(parents=True)

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    modules = f"{home}/.git/modules"
    assert result.returncode != 0, plain
    assert _in(
        f"{home} keeps submodule repositories in {modules}. A release tree has no "
        "submodules, and the update would run git inside them. Remove the "
        f"submodules and {modules}, then re-run.",
        plain,
    ), plain
    assert _head(home) == old_commit, plain


def test_replacing_a_clone_never_runs_git_inside_a_nested_repository(
    tmp_path: Path,
) -> None:
    """When -Yes replaces a clone with the archive, git status looks for
    local work, and would run inside a submodule under the nested
    repository's own config. The clone's submodule is refused first, as for
    an update in place, so the nested repository's clean filter never runs
    and the clone is kept."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "nested-filter-ran"
    _nested_repository(home, marker)
    env = _script_env(
        tmp_path, mode="checksum", extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"}
    )

    result = _invoke(tmp_path, "install.ps1", env)

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert "holds a submodule at evilsub (its index records a git repository" in plain
    assert _head(home) == old_commit, plain


def _old_unreachable_objects(home: Path, scratch: Path, count: int = 3) -> None:
    """Write COUNT loose blobs that nothing refers to into HOME's
    .git/objects/17 (the folder gc --auto counts), dated 40 days back."""
    scratch.mkdir(parents=True, exist_ok=True)
    old = time.time() - 40 * 24 * 3600
    found = 0
    n = 0
    while found < count:
        data = f"unreachable {n}\n".encode()
        n += 1
        # git names a sha1 repository's objects by SHA-1; not a security use.
        name = hashlib.sha1(
            b"blob %d\0" % len(data) + data, usedforsecurity=False
        ).hexdigest()
        if not name.startswith("17"):
            continue
        blob = scratch / name
        blob.write_bytes(data)
        assert git(["hash-object", "-w", str(blob)], home).strip() == name
        os.utime(home / ".git" / "objects" / "17" / name[2:], (old, old))
        found += 1


def test_the_fetch_starts_no_automatic_maintenance(tmp_path: Path) -> None:
    """git fetch starts automatic maintenance (gc --auto), which runs
    gc.recentObjectsHook. Here the user's own config, trusted and so not
    refused, sets gc.auto=1 and a hook that writes a marker, and the clone
    holds old unreachable objects. Every git command on the clone runs with
    gc.auto=0 and maintenance.auto=false, so the hook never runs and the
    update completes."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    _old_unreachable_objects(home, tmp_path / "blobs")
    marker = tmp_path / "gc-hook-ran"
    user_config = (
        "[gc]\n\tauto = 1\n\tautoDetach = false\n"
        f"\trecentObjectsHook = \"touch '{marker.as_posix()}'\"\n"
    )

    result = _invoke(
        tmp_path, "update.ps1", _script_env(tmp_path, gitconfig_extra=user_config)
    )

    plain = _out(result)
    assert not marker.exists(), plain
    assert _head(home) == _head(repo), plain


# D3/D4: which folders the leftover report names, and what it says ---------------


def test_another_homes_staging_folders_do_not_stop_the_install(
    tmp_path: Path,
) -> None:
    """Staging folders carry the name of the APOTHEM_HOME they were made
    for. Folders of another home in the same parent (another home's run may
    be using them now; the lock is per home), including one whose name only
    starts with this home's, are not reported, and the install goes on."""
    make_tagged_repo(tmp_path, TAG)
    foreign = tmp_path / ".apothem-extract.other-home.eeeeee"
    (foreign / f"apothem-{OLD_TAG}" / "backups").mkdir(parents=True)
    longer = tmp_path / f".apothem-clone.{LEAF}.y.ffffff"
    (longer / "apothem").mkdir(parents=True)
    before = _tree_listing(foreign, longer)

    result = _invoke(tmp_path, "install.ps1", _script_env(tmp_path))

    plain = _out(result)
    assert "An earlier run was stopped part-way" not in plain, plain
    assert "Cloning" in plain, plain
    assert _tree_listing(foreign, longer) == before, plain


def test_the_entries_a_swap_carried_are_all_named(tmp_path: Path) -> None:
    """The report names every entry a swap moved from APOTHEM_HOME into the
    new tree, user files as well as engine data: those the run listed in
    .apothem-carried-entries before its first move and that are in the
    tree, or, for a folder an earlier installer made, what the tree's
    source manifest does not list."""
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    listed = tmp_path / f".apothem-extract.{LEAF}.Ab12Cd"
    tree = listed / f"apothem-{TAG}"
    (tree / "src").mkdir(parents=True)
    (tree / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    for name in (".venv", "backups", "my-notes"):
        (tree / name).mkdir()
    # state is listed but was not moved yet: it is not named.
    (listed / ".apothem-carried-entries").write_text(
        ".env\n.venv\nbackups\nmy-notes\nstate\n", encoding="utf-8", newline="\n"
    )
    unlisted = tmp_path / ".apothem-extract.Zx81Qp"
    earlier = unlisted / f"apothem-{OLD_TAG}"
    (earlier / "src").mkdir(parents=True)
    (earlier / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (earlier / ".apothem-source-entries").write_text(
        ".apothem-source-entries\npyproject.toml\nsrc\n", encoding="utf-8", newline="\n"
    )
    (earlier / "notes.txt").write_text("mine\n", encoding="utf-8")
    (earlier / "state").mkdir()

    result = _invoke(tmp_path, "install.ps1", _script_env(tmp_path))

    plain = _out(result)
    assert result.returncode != 0, plain
    lines = [line.rstrip() for line in result.stderr.splitlines()]
    assert (
        f"    {listed}: the new source that was being installed, in {tree}, with "
        f"these entries moved into it from {home}: .env, .venv, backups, my-notes"
    ) in lines, plain
    assert (
        f"    {unlisted}: the new source that was being installed, in {earlier}, "
        "with these entries moved into it from the Apothem home it was made for: "
        "notes.txt, state" + OLD_NOTE.format(parent=tmp_path)
    ) in lines, plain


_SWAP_FUNCTIONS = (
    "Write-Fail",
    "Get-SortedName",
    "Test-Entry",
    "Move-Entry",
    "Get-SourceEntry",
    "Undo-SwapIn",
    "Invoke-SwapIn",
)


def test_a_swap_lists_what_it_will_carry_before_it_moves_anything(
    tmp_path: Path,
) -> None:
    """Before its first move, a keep swap writes the names it will carry
    from APOTHEM_HOME into the new tree to .apothem-carried-entries in the
    staging folder (sorted ordinally, one per line), and the folder the
    earlier tree moves to carries the home's name."""
    stage = tmp_path / f".apothem-extract.{LEAF}.Ab12Cd"
    new = stage / "apothem-new"
    (new / "src" / "apothem").mkdir(parents=True)
    (new / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    home = tmp_path / LEAF
    (home / "src").mkdir(parents=True)
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (home / "backups").mkdir()
    (home / ".env").write_text("x\n", encoding="utf-8")
    (home / "my-notes.txt").write_text("mine\n", encoding="utf-8")
    body = (
        "$ApothemHome = $env:T_HOME; "
        "$EngineDataNames = @('backups', 'state', 'plans', 'memory', 'contexts', "
        "'learning', 'providers'); "
        "$SourceManifest = '.apothem-source-entries'; "
        "$CarryList = '.apothem-carried-entries'; "
        "$GitNoProgram = @(); $script:SwapKeepStaging = $false; "
        "${function:Move-EntryReal} = ${function:Move-Entry}; "
        "$script:Seen = $null; $script:Targets = @(); "
        "function Move-Entry { param([string]$From, [string]$To) "
        "if ($null -eq $script:Seen) { $p = Join-Path $env:T_STAGE "
        "'.apothem-carried-entries'; $script:Seen = $(if (Test-Path -LiteralPath $p) "
        "{ [IO.File]::ReadAllText($p) } else { 'MISSING' }) }; "
        "$script:Targets += $To; Move-EntryReal $From $To }; "
        "Invoke-SwapIn $env:T_NEW 'keep'; "
        "[pscustomobject]@{ seen = $script:Seen; targets = $script:Targets } "
        "| ConvertTo-Json -Compress"
    )

    result = _pwsh_program(
        _ps1_function_program("install.ps1", _SWAP_FUNCTIONS, body),
        T_HOME=str(home),
        T_STAGE=str(stage),
        T_NEW=str(new),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["seen"] == ".env\nbackups\nmy-notes.txt\n", data
    olds = [t for t in data["targets"] if re.search(r"[\\/]\.apothem-old\.", t)]
    assert len(olds) == 1, data
    assert re.search(
        rf"[\\/]\.apothem-old\.{re.escape(LEAF)}\.[0-9a-f]{{32}}[\\/]home$", olds[0]
    ), olds
    assert (home / "src" / "apothem").is_dir()
    assert (home / "my-notes.txt").is_file()
    assert not list(tmp_path.glob(".apothem-old.*"))


def test_the_clone_staging_folder_carries_the_homes_name(tmp_path: Path) -> None:
    """A fresh clone is made in .apothem-clone.<home's folder name>.<32 hex
    digits> beside APOTHEM_HOME; the stub gpg looks while the tag is
    checked."""
    make_tagged_repo(tmp_path, TAG)
    record = tmp_path / "staging-names"
    config = _gpg(
        tmp_path / "looking-gpg",
        f"ls -a '{tmp_path.as_posix()}' > '{record.as_posix()}'\n",
    )

    result = _invoke(tmp_path, "install.ps1", _script_env(tmp_path, gpg_config=config))

    plain = _out(result)
    names = record.read_text(encoding="utf-8").split()
    staging = [n for n in names if n.startswith(".apothem-")]
    assert len(staging) == 1, (staging, plain)
    assert re.fullmatch(
        rf"\.apothem-clone\.{re.escape(LEAF)}\.[0-9a-f]{{32}}", staging[0]
    )


# L6: the tag object read once is the one verified ------------------------------


# Runs a script in this session with `git` resolved to a function that runs
# the real git and, right after the first `rev-parse ... refs/tags/<tag>`,
# moves that ref to another tag object.
_MOVE_AFTER_FIRST_READ = r"""
$RealGit = (Get-Command git -CommandType Application | Select-Object -First 1).Source
$global:ApothemTestMoved = $false
function global:git {
    $ErrorActionPreference = 'Continue'
    $GitOut = & $RealGit @args 2>&1
    $GitCode = $LASTEXITCODE
    if (-not $global:ApothemTestMoved -and $args -contains 'rev-parse' -and $args -contains "refs/tags/$env:T_TAG") {
        $global:ApothemTestMoved = $true
        & $RealGit -C $env:T_HOME update-ref "refs/tags/$env:T_TAG" $env:T_MOVED | Out-Null
    }
    $GitOut
    $global:LASTEXITCODE = $GitCode
}
try {
    if ($env:T_YES) { & $env:T_SCRIPT -Yes } else { & $env:T_SCRIPT }
} catch {
    'SCRIPT-FAILED: ' + $_
}
"MOVED=$global:ApothemTestMoved"
"""


def _script_path(tmp_path: Path, script: str) -> Path:
    """SCRIPT's path as _script_args runs it (install.ps1 from a copy)."""
    return Path(_script_args(tmp_path, script)[5])


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_the_tag_object_read_first_is_the_one_verified(
    tmp_path: Path, script: str
) -> None:
    """The tag ref is read once, and verify-tag, cat-file and the commit all
    use that object ID. Here the ref moves right after that first read, to
    a signed-looking tag of the same name for another commit; the stub gpg
    records what it was asked to verify, which must be the tag for the
    commit that is checked out."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    good = _head(repo)
    tree = git(["rev-parse", "HEAD^{tree}"], home).strip()
    moved = git(
        [
            "-c",
            "user.name=Mover",
            "-c",
            "user.email=mover@example.invalid",
            "commit-tree",
            tree,
            "-m",
            "moved",
        ],
        home,
    ).strip()
    tag_file = tmp_path / "moved.tag"
    tag_file.write_text(
        f"object {moved}\ntype commit\ntag {TAG}\n"
        "tagger Mover <mover@example.invalid> 1700000000 +0000\n\nmoved\n"
        "-----BEGIN PGP SIGNATURE-----\n\nc3R1Yg==\n-----END PGP SIGNATURE-----\n",
        encoding="utf-8",
        newline="\n",
    )
    moved_tag = git(["hash-object", "-t", "tag", "-w", str(tag_file)], home).strip()
    payload = tmp_path / "verified-payload"
    status = tmp_path / "recording-gpg" / "status.txt"
    status.parent.mkdir()
    status.write_text(GOOD, encoding="utf-8", newline="\n")
    stub = _sh(
        tmp_path / "recording-gpg" / "gpg",
        f"cat > '{payload.as_posix()}'\ncat '{status.as_posix()}'\n",
    )
    config = tmp_path / "recording-gpg" / "gitconfig"
    config.write_text(f"[gpg]\n\tprogram = {stub.as_posix()}\n", encoding="utf-8")
    env = _script_env(tmp_path, gpg_config=config)
    env.update(
        {
            "T_TAG": TAG,
            "T_HOME": str(home),
            "T_MOVED": moved_tag,
            "T_SCRIPT": str(_script_path(tmp_path, script)),
            "T_YES": "1" if script == "install.ps1" else "",
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
            _MOVE_AFTER_FIRST_READ,
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
    assert "MOVED=True" in plain, plain
    verified = payload.read_text(encoding="utf-8")
    assert f"object {good}\n" in verified, verified
    assert f"tag {TAG}\n" in verified, verified
    assert _head(home) == good, plain


# D9: the caller's git variables come back -----------------------------------------


_CALLER_SESSION = r"""
try {
    & ([scriptblock]::Create((Get-Content -Raw -LiteralPath $env:APOTHEM_TEST_SCRIPT)))
} catch {
    'SCRIPT-FAILED: ' + $_
}
foreach ($Name in 'GIT_CONFIG_GLOBAL', 'GIT_DIR', 'GIT_CONFIG_NOSYSTEM', 'GIT_NO_REPLACE_OBJECTS', 'GIT_NO_LAZY_FETCH', 'GIT_ALLOW_PROTOCOL') {
    "AFTER $Name=[$([Environment]::GetEnvironmentVariable($Name))]"
}
"""


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_run_in_the_callers_session_puts_its_git_variables_back(
    tmp_path: Path, script: str
) -> None:
    """Run the way the one-liner runs it (in the caller's own session), the
    script clears the git variables only for its run: here it stops at the
    tag check, and the caller's GIT_CONFIG_GLOBAL, GIT_DIR and
    GIT_ALLOW_PROTOCOL are back, GIT_NO_REPLACE_OBJECTS and
    GIT_NO_LAZY_FETCH are unset again, and GIT_CONFIG_NOSYSTEM, which only
    narrows what git reads, stayed set throughout. While the tag is checked
    (the stub gpg looks), git may fetch no missing object and uses only the
    run's own five transports."""
    _prepare(tmp_path, script)
    record = tmp_path / "git-variables"
    config = _gpg(
        tmp_path / "probe-gpg",
        f"env | grep '^GIT_' | sort > '{record.as_posix()}'\n",
        "",
    )
    env = _script_env(tmp_path, gpg_config=config)
    dotfiles = tmp_path / "dotfiles.gitconfig"
    dotfiles.write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
    elsewhere = tmp_path / "no-such-repository"
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(dotfiles),
            "GIT_DIR": str(elsewhere),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ALLOW_PROTOCOL": "ext",
            "APOTHEM_TEST_SCRIPT": str(INSTALLER_DIR / script),
        }
    )
    env.pop("GIT_NO_REPLACE_OBJECTS", None)
    env.pop("GIT_NO_LAZY_FETCH", None)
    assert _PWSH is not None

    result = subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _CALLER_SESSION,
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
    assert "SCRIPT-FAILED" in plain, plain
    assert "is unsigned or its signature did not verify" in plain, plain
    during = record.read_text(encoding="utf-8").splitlines()
    assert "GIT_CONFIG_NOSYSTEM=1" in during, during
    assert "GIT_NO_LAZY_FETCH=1" in during, during
    assert "GIT_ALLOW_PROTOCOL=file:git:http:https:ssh" in during, during
    assert not any(line.startswith("GIT_CONFIG_GLOBAL=") for line in during), during
    assert f"AFTER GIT_CONFIG_GLOBAL=[{dotfiles}]" in result.stdout, plain
    assert f"AFTER GIT_DIR=[{elsewhere}]" in result.stdout, plain
    assert "AFTER GIT_CONFIG_NOSYSTEM=[1]" in result.stdout, plain
    assert "AFTER GIT_NO_REPLACE_OBJECTS=[]" in result.stdout, plain
    assert "AFTER GIT_NO_LAZY_FETCH=[]" in result.stdout, plain
    assert "AFTER GIT_ALLOW_PROTOCOL=[ext]" in result.stdout, plain


# D8: Windows PowerShell 5.1 follows each redirect by hand -------------------------


_POWERSHELL_51 = shutil.which("powershell.exe")

# An Invoke-WebRequest stand-in for Windows PowerShell 5.1 with
# -MaximumRedirection 0: it logs each address asked for and answers from
# $env:T_MAP (address -> Location; an empty Location is the file itself).
_IWR_HOPS = (
    "function Invoke-WebRequest { [CmdletBinding()] param([switch]$UseBasicParsing, "
    "$Uri, $OutFile, [switch]$PassThru, $MaximumRedirection) "
    "Add-Content -LiteralPath $env:T_LOG -Value ([string]$Uri); "
    "$to = ($env:T_MAP | ConvertFrom-Json).PSObject.Properties[[string]$Uri]; "
    "if ($to -and $to.Value) { Set-Content -LiteralPath $OutFile -Value 'moved'; "
    "return [pscustomobject]@{ StatusCode = 302; Headers = @{ Location = $to.Value } } }; "
    "Set-Content -LiteralPath $OutFile -Value 'payload'; "
    "[pscustomobject]@{ StatusCode = 200; Headers = @{} } }; "
)


@pytest.mark.skipif(_POWERSHELL_51 is None, reason="no Windows PowerShell 5.1")
@pytest.mark.parametrize(
    ("chain", "asked", "outcome"),
    [
        (
            {
                "https://a.invalid/f": "http://b.invalid/f",
                "http://b.invalid/f": "https://c.invalid/f",
                "https://c.invalid/f": "",
            },
            ["https://a.invalid/f"],
            "was redirected to http://b.invalid/f, which is not an https:// address",
        ),
        (
            {
                "https://a.invalid/f": "/g",
                "https://a.invalid/g": "https://c.invalid/h",
                "https://c.invalid/h": "",
            },
            ["https://a.invalid/f", "https://a.invalid/g", "https://c.invalid/h"],
            "SAVED",
        ),
        (
            {"https://a.invalid/f": "https://a.invalid/f"},
            ["https://a.invalid/f"] * 11,
            "was redirected more than 10 times",
        ),
    ],
    ids=["through-http", "https-only", "loop"],
)
def test_windows_powershell_checks_every_redirect(
    tmp_path: Path, chain: dict[str, str], asked: list[str], outcome: str
) -> None:
    """Windows PowerShell 5.1 would follow https to http and back to https
    and show only the last address. Save-Download follows each redirect
    itself there: a step to an address that is not https:// stops the
    download before that address is asked for, and no file is left; an
    all-https chain (a relative Location included) is saved."""
    out = tmp_path / "download.bin"
    log = tmp_path / "asked.txt"
    body = (
        _IWR_HOPS
        + "try { Save-Download 'https://a.invalid/f' $env:T_OUT; 'SAVED' } "
        + "catch { 'REFUSED: ' + $_.Exception.Message }"
    )
    assert _POWERSHELL_51 is not None

    result = subprocess.run(
        [
            _POWERSHELL_51,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _ps1_function_program("install.ps1", ("Save-Download",), body),
        ],
        env={
            **os.environ,
            "T_OUT": str(out),
            "T_LOG": str(log),
            "T_MAP": json.dumps(chain),
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    text = result.stdout + result.stderr
    assert result.returncode == 0, text
    assert outcome in text, text
    assert log.read_text(encoding="utf-8").split() == asked, text
    assert out.exists() == (outcome == "SAVED"), text


def test_a_failed_download_says_why(tmp_path: Path) -> None:
    """A release file that cannot be downloaded stops the run with the
    reason the download gave, here that nothing listens at the address."""
    make_tagged_repo(tmp_path, TAG)
    env = _script_env(
        tmp_path,
        mode="checksum",
        extra_env={
            "APOTHEM_ALLOW_UNVERIFIED": "1",
            "APOTHEM_RELEASE_BASE": "http://127.0.0.1:9",
        },
    )

    result = _invoke(tmp_path, "install.ps1", env)

    plain = _out(result)
    assert result.returncode != 0, plain
    match = re.search(
        rf"Could not download apothem-{re.escape(TAG)}-windows\.zip from "
        rf"http://127\.0\.0\.1:9/{re.escape(TAG)} \((.+?)\)",
        plain,
    )
    assert match, plain
    assert match.group(1).strip(), plain


# Round 3: what the PowerShell scripts read and say ---------------------------


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    "bom", [b"\xff\xfe", b"\xfe\xff"], ids=["utf16-le-bom", "utf16-be-bom"]
)
def test_a_filter_behind_a_utf16_byte_order_mark_is_refused(
    tmp_path: Path, script: str, bom: bytes
) -> None:
    """git reads .git/info/attributes byte by byte, so a UTF-16 byte-order
    mark in front hides nothing from it: the next line's filter still runs
    on checkout. The scripts read the file the same way and refuse it before
    anything is fetched; the filter never runs."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "smudge-ran"
    (home / ".git" / "info").mkdir(exist_ok=True)
    attributes = home / ".git" / "info" / "attributes"
    attributes.write_bytes(bom + b"\n* filter=evil\n")
    env = _script_env(
        tmp_path, gitconfig_extra=_SMUDGE_CONFIG.format(marker=marker.as_posix())
    )

    result = _invoke(tmp_path, script, env)

    plain = _out(result)
    assert not marker.exists(), plain
    assert _head(home) == old_commit, plain
    assert result.returncode != 0, plain
    assert _in(
        f"{home}'s own git attributes set a filter (filter=), which the update "
        f"would trust. Remove it from {home}/.git/info/attributes, then re-run.",
        plain,
    ), plain


def test_a_comment_line_holding_a_carriage_return_is_not_refused(
    tmp_path: Path,
) -> None:
    """git ends a line of attributes at LF only, so "#c<CR>* filter=x" is one
    comment line, as install.sh reads it too: the update goes on."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    (home / ".git" / "info").mkdir(exist_ok=True)
    (home / ".git" / "info" / "attributes").write_bytes(b"#c\r* filter=evil\n")

    result = _invoke(tmp_path, "update.ps1", _script_env(tmp_path))

    plain = _out(result)
    assert "own git attributes set a filter" not in plain, plain
    assert _head(home) == _head(repo), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1", "uninstall.ps1"])
def test_a_run_through_a_junction_takes_the_lock_of_the_folder_it_leads_to(
    tmp_path: Path, script: str
) -> None:
    """APOTHEM_HOME given as a junction takes the lock beside the folder the
    junction leads to, as the sh scripts do with cd -P, so a Git Bash run on
    that folder (its lock folder here) stops it. The message names the home
    as given and the lock it found."""
    home = _prepare(tmp_path, script)
    home.mkdir(exist_ok=True)
    link = tmp_path / "home-link"
    _make_junction(link, home)
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()
    (lock / "pid").write_text("4242\n", encoding="utf-8")
    env = _script_env(tmp_path, extra_env={"APOTHEM_HOME": str(link)})

    result = _invoke(tmp_path, script, env)

    plain = _out(result)
    assert result.returncode != 0, plain
    assert _in(
        f"Another Apothem install, update or uninstall is running on {link}. "
        f"Wait for it to finish, then re-run. If none is running, remove {lock}, "
        "then re-run.",
        plain,
    ), plain
    assert not (tmp_path / "home-link.lock").exists(), plain
    assert (lock / "pid").is_file(), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1", "uninstall.ps1"])
def test_a_lock_folder_made_while_the_lock_is_opened_is_named_as_held(
    tmp_path: Path, script: str
) -> None:
    """A Git Bash run can make its lock folder between the look for one and
    the open of the lock file. The open then fails as it does on a folder,
    and the run says another run holds the lock, not that it cannot write
    beside APOTHEM_HOME. Here the first look finds nothing (a stand-in
    Get-Item), and the folder is already there for the open."""
    home = tmp_path / "apothem-home"
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()
    body = (
        "$script:LkLooks = 0; "
        "function Get-Item { [CmdletBinding()] param([string]$LiteralPath, "
        "[switch]$Force) $script:LkLooks++; if ($script:LkLooks -eq 1) "
        "{ return $null }; Microsoft.PowerShell.Management\\Get-Item "
        "-LiteralPath $LiteralPath -Force:$Force -ErrorAction SilentlyContinue }; "
        "function Write-Fail { param([string]$Msg) throw $Msg }; "
        "$ApothemHome = $env:T_HOME; $HomeLockPath = $env:T_LOCK; "
        "$DryRun = $false; $script:HomeLock = $null; "
        "try { Lock-ApothemHome; 'LOCKED' } catch { 'REFUSED: ' + $_.Exception.Message }"
    )

    result = _pwsh_program(
        _ps1_function_program(script, ("Lock-ApothemHome",), body),
        T_HOME=str(home),
        T_LOCK=str(lock),
    )

    text = result.stdout + result.stderr
    assert result.returncode == 0, text
    assert _in(
        f"REFUSED: Another Apothem install, update or uninstall is running on "
        f"{home}. Wait for it to finish, then re-run. If none is running, "
        f"remove {lock}, then re-run.",
        text,
    ), text
    assert lock.is_dir(), text


@pytest.mark.skipif(not _PWSH_IS_7, reason="PowerShell 7 refuses this redirect itself")
def test_powershell_7s_own_redirect_refusal_says_what_happened(tmp_path: Path) -> None:
    """PowerShell 7 refuses a redirect from https to http itself, with the
    error InsecureRedirection, whose message ("Operation is not valid due to
    the current state of the object.") says nothing of it. Save-Download
    says what happened and why it stops, and leaves no file. A stand-in Invoke-WebRequest raises that error here."""
    out = tmp_path / "download.bin"
    body = (
        "function Invoke-WebRequest { [CmdletBinding()] param([switch]$UseBasicParsing, "
        "$Uri, $OutFile, [switch]$PassThru, $MaximumRedirection) "
        "Set-Content -LiteralPath $OutFile -Value 'partial'; "
        "$PSCmdlet.ThrowTerminatingError([System.Management.Automation.ErrorRecord]::new("
        "[System.InvalidOperationException]::new(), 'InsecureRedirection', "
        "[System.Management.Automation.ErrorCategory]::InvalidOperation, $null)) }; "
        "try { Save-Download 'https://a.invalid/f' $env:T_OUT; 'SAVED' } "
        "catch { 'REFUSED: ' + $_.Exception.Message }"
    )

    result = _pwsh_program(
        _ps1_function_program("install.ps1", ("Save-Download",), body), T_OUT=str(out)
    )

    text = result.stdout + result.stderr
    assert result.returncode == 0, text
    assert (
        "REFUSED: https://a.invalid/f was redirected to a plain http:// address; "
        "a download from an https:// address follows only https:// redirects"
    ) in text, text
    assert not out.exists(), text


# Folders others can write: APOTHEM_HOME and the folder that holds it ------------


_WARN_FUNCTIONS = ("Resolve-FolderLink", "Get-FolderWriter", "Write-HomeAccessWarning")
_WARN_SHELLS = [
    pytest.param(_PWSH, id="pwsh"),
    pytest.param(
        _POWERSHELL_51,
        id="powershell-5.1",
        marks=pytest.mark.skipif(
            _POWERSHELL_51 is None, reason="no Windows PowerShell 5.1"
        ),
    ),
]
_USERS = "S-1-5-32-545"
_AUTHENTICATED_USERS = "S-1-5-11"
#: Every user signed in at the console or over Remote Desktop; Windows gives
#: it Modify on what is made in C:\Users\Public.
_INTERACTIVE = "S-1-5-4"
_DRIVE_ROOT = (
    ", access that folders made at the root of a drive inherit from the drive's "
    "default permissions"
)


def _icacls(path: Path, *args: str) -> None:
    subprocess.run(
        ["icacls", str(path), *args], check=True, capture_output=True, timeout=60
    )


def _home_warnings(
    shell: str | None,
    home: Path | str,
    prelude: str = "",
    script: str = "install.ps1",
    env: dict[str, str] | None = None,
) -> list[str]:
    """Run SCRIPT's Write-HomeAccessWarning in SHELL with APOTHEM_HOME set to
    HOME (after PRELUDE, with ENV over the test's own environment) and return
    what it warned, one message per item."""
    assert shell is not None
    body = (
        "function Write-Warn { param([string]$Msg) Write-Output ('WARN: ' + $Msg) }; "
        f"$ApothemHome = $env:T_HOME; {prelude} Write-HomeAccessWarning"
    )
    program = _ps1_function_program(script, _WARN_FUNCTIONS, body)
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", program],
        env={**os.environ, **(env or {}), "T_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr.strip(), result.stderr
    return [
        line[len("WARN: ") :]
        for line in result.stdout.splitlines()
        if line.startswith("WARN: ")
    ]


def _home_message(home: Path | str, who: str, why: str = "") -> str:
    return (
        f"Other users can change the code Apothem runs as you: {who} can write to "
        f"{home}{why}. To fix it, turn off inheritance for that folder and remove "
        f"{who} (Properties > Security > Advanced), or move APOTHEM_HOME into your "
        "user folder."
    )


def _my_sid() -> str:
    out = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    return out.strip().split(",")[-1].strip('"')


def _drive_root_like(folder: Path) -> Path:
    """Give FOLDER what a client Windows's C:\\ passes on: Authenticated
    Users may modify what is made inside, and may make folders in it."""
    folder.mkdir(parents=True, exist_ok=True)
    _icacls(folder, "/grant", f"*{_AUTHENTICATED_USERS}:(OI)(CI)(IO)(M)")
    _icacls(folder, "/grant", f"*{_AUTHENTICATED_USERS}:(AD)")
    return folder


@pytest.mark.parametrize("shell", _WARN_SHELLS)
@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize("state", ["made", "missing"])
def test_a_home_in_a_folder_shaped_like_the_user_folder_gives_no_warning(
    tmp_path: Path, shell: str | None, script: str, state: str
) -> None:
    """A folder only SYSTEM, Administrators and you can use, as a user
    folder is, gives no warning, for a home in it or a new one there."""
    profile = tmp_path / "profile"
    profile.mkdir()
    _icacls(
        profile,
        "/inheritance:r",
        "/grant:r",
        "*S-1-5-18:(OI)(CI)F",
        "*S-1-5-32-544:(OI)(CI)F",
        f"*{_my_sid()}:(OI)(CI)F",
    )
    home = profile / ".apothem"
    if state == "made":
        home.mkdir()

    assert _home_warnings(shell, home, script=script) == []


@pytest.mark.parametrize("shell", _WARN_SHELLS)
@pytest.mark.parametrize(
    ("sid", "who"),
    [
        (_USERS, "Users"),
        (_AUTHENTICATED_USERS, "Authenticated Users"),
        (_INTERACTIVE, "INTERACTIVE"),
    ],
)
def test_a_home_others_may_modify_is_named(
    tmp_path: Path, shell: str | None, sid: str, who: str
) -> None:
    """An entry of the home's own that lets Users or Authenticated Users
    modify it is named, with the fix; the folder holding it is fine."""
    home = tmp_path / "holder" / "apothem"
    home.mkdir(parents=True)
    _icacls(home, "/grant", f"*{sid}:(OI)(CI)(M)")

    assert _home_warnings(shell, home) == [_home_message(home, who)]


def _pwsh_7_module_path() -> str:
    """The PSModulePath PowerShell 7 hands to the programs it starts: its own
    module folders first, then Windows PowerShell's."""
    assert _PWSH is not None
    return subprocess.run(
        [_PWSH, "-NoProfile", "-NonInteractive", "-Command", "$env:PSModulePath"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout.strip()


@pytest.mark.skipif(
    _POWERSHELL_51 is None or not _PWSH_IS_7,
    reason="needs Windows PowerShell 5.1 and PowerShell 7",
)
@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_windows_powershell_given_powershell_7s_module_path_still_warns(
    tmp_path: Path, script: str
) -> None:
    """Windows PowerShell started by a program PowerShell 7 started inherits
    PowerShell 7's module folders first and then cannot load Get-Acl; the
    warning reads the folder's entries without it."""
    home = tmp_path / "holder" / "apothem"
    home.mkdir(parents=True)
    _icacls(home, "/grant", f"*{_USERS}:(OI)(CI)(M)")

    warnings = _home_warnings(
        _POWERSHELL_51,
        home,
        script=script,
        env={"PSModulePath": _pwsh_7_module_path()},
    )

    assert warnings == [_home_message(home, "Users")]


@pytest.mark.parametrize("shell", _WARN_SHELLS)
def test_a_new_home_where_interactive_users_may_modify_is_named(
    tmp_path: Path, shell: str | None
) -> None:
    """A folder that passes INTERACTIVE's Modify to what is made in it, as
    C:\\Users\\Public does, is named for a new home there."""
    holder = tmp_path / "public"
    holder.mkdir()
    _icacls(holder, "/grant", f"*{_INTERACTIVE}:(OI)(CI)(IO)(M)")
    new = holder / "apothem"

    assert _home_warnings(shell, new) == [
        f"A new {new} would let INTERACTIVE change the code Apothem runs as you, "
        f"from the permissions of {holder}. To fix it, set APOTHEM_HOME to a folder "
        "inside your user folder."
    ]


def _free_drive_letter() -> str:
    for letter in "ZYXWVUTSRQPONMLKJIHGFED":
        if not Path(f"{letter}:\\").exists():
            return letter
    pytest.skip("no free drive letter for subst")


@pytest.mark.parametrize("shell", _WARN_SHELLS)
def test_a_home_made_at_the_root_of_a_drive_says_where_the_access_comes_from(
    tmp_path: Path, shell: str | None
) -> None:
    """A folder made at the root of a drive inherits, under a client
    Windows's defaults, Authenticated Users' Modify. A home made in a folder
    that passes that on is named; at a drive's root (a subst drive here) the
    message says the access comes from the drive's default permissions, for
    a home there and for a new one. Making folders in the root is not
    replacing the home, so the root itself is not named."""
    holder = _drive_root_like(tmp_path / "drive")
    home = holder / "apothem"
    home.mkdir()
    new = holder / "new"
    assert _home_warnings(shell, home) == [_home_message(home, "Authenticated Users")]
    assert _home_warnings(shell, new) == [
        f"A new {new} would let Authenticated Users change the code Apothem runs as "
        f"you, from the permissions of {holder}. To fix it, set APOTHEM_HOME to a "
        "folder inside your user folder."
    ]

    letter = _free_drive_letter()
    subprocess.run(["subst", f"{letter}:", str(holder)], check=True, timeout=60)
    try:
        at_root = _home_warnings(shell, f"{letter}:\\apothem")
        new_at_root = _home_warnings(shell, f"{letter}:\\new")
    finally:
        subprocess.run(["subst", f"{letter}:", "/d"], check=False, timeout=60)

    assert at_root == [
        _home_message(f"{letter}:\\apothem", "Authenticated Users", _DRIVE_ROOT)
    ]
    assert new_at_root == [
        f"A new {letter}:\\new would let Authenticated Users change the code Apothem "
        f"runs as you{_DRIVE_ROOT}. To fix it, set APOTHEM_HOME to a folder inside "
        "your user folder."
    ]


@pytest.mark.parametrize("shell", _WARN_SHELLS)
def test_a_folder_where_others_may_delete_what_it_holds_is_named(
    tmp_path: Path, shell: str | None
) -> None:
    """Users given delete-children on the folder holding the home can rename
    the home away and put another in its place: that folder is named."""
    holder = tmp_path / "holder"
    home = holder / "apothem"
    home.mkdir(parents=True)
    _icacls(holder, "/grant", f"*{_USERS}:(DC)")

    assert _home_warnings(shell, home) == [
        f"Other users can replace {home}: Users can delete or rename what is in "
        f"{holder}, the folder that holds it. To fix it, remove Users from that "
        "folder's Security tab, or move APOTHEM_HOME into your user folder."
    ]


@pytest.mark.parametrize("shell", _WARN_SHELLS)
def test_an_entry_only_for_what_a_folder_holds_does_not_name_that_folder(
    tmp_path: Path, shell: str | None
) -> None:
    """An inherit-only entry gives Users nothing on the folder holding the
    home, so that folder is not named; the home, which inherits it, is."""
    holder = tmp_path / "holder"
    holder.mkdir()
    _icacls(holder, "/grant", f"*{_USERS}:(OI)(CI)(IO)(F)")
    home = holder / "apothem"
    home.mkdir()

    assert _home_warnings(shell, home) == [_home_message(home, "Users")]


@pytest.mark.parametrize("shell", _WARN_SHELLS)
def test_a_home_given_as_a_junction_names_the_folder_it_leads_to(
    tmp_path: Path, shell: str | None
) -> None:
    """A junction's entries cover only the junction itself; the warning
    reads, and names, the folder the junction leads to."""
    target = tmp_path / "target"
    target.mkdir()
    _icacls(target, "/grant", f"*{_AUTHENTICATED_USERS}:(OI)(CI)(M)")
    link = tmp_path / "home-link"
    _make_junction(link, target)

    assert _home_warnings(shell, link) == [_home_message(target, "Authenticated Users")]


@pytest.mark.parametrize("shell", _WARN_SHELLS)
@pytest.mark.parametrize("holder_shape", ["modify", "drive-root"])
def test_a_junction_others_may_delete_and_make_again_is_named(
    tmp_path: Path, shell: str | None, holder_shape: str
) -> None:
    """A junction inherits its folder's entries, so Modify on the folder (or
    a drive root's defaults) lets others delete the junction and, with
    create-folders on the folder, make one of their own under the same name.
    The folder is named, though the junction leads to a private folder."""
    target = tmp_path / "target"
    target.mkdir()
    holder = tmp_path / "holder"
    if holder_shape == "modify":
        holder.mkdir()
        _icacls(holder, "/grant", f"*{_AUTHENTICATED_USERS}:(OI)(CI)(M)")
    else:
        _drive_root_like(holder)
    link = holder / "apothem"
    _make_junction(link, target)

    assert _home_warnings(shell, link) == [
        f"Other users can replace {link}: Authenticated Users can delete or rename "
        f"what is in {holder}, the folder that holds it. To fix it, remove "
        "Authenticated Users from that folder's Security tab, or move APOTHEM_HOME "
        "into your user folder."
    ]


# PowerShell outside Windows reads the mode bits ls prints and the group stat
# names, as the sh scripts do. Windows PowerShell 5.1 has no $IsWindows of its
# own, so setting it to $false takes that path here, with ls, stat, uname, id
# and sh stood in for. ls splits a group name at a space, as the real one
# prints it; stat gives it whole.
_POSIX_STUBS = (
    "$IsWindows = $false; Remove-Item Alias:ls -Force -ErrorAction SilentlyContinue; "
    "function ls { $global:LASTEXITCODE = 0; "
    "if ($args[-1] -eq $env:T_HOME) { $m = $env:T_HOME_MODE; $g = $env:T_GROUP } "
    "else { $m = $env:T_UP_MODE; $g = $env:T_UP_GROUP }; "
    '"$m 2 alice $g 4096 Nov 10 01:24 $($args[-1])" }; '
    "function stat { $global:LASTEXITCODE = 0; "
    "if ($args[-1] -eq $env:T_HOME) { $env:T_GROUP } else { $env:T_UP_GROUP } }; "
    "function uname { $env:T_OS }; "
    "function id { if ($args[0] -eq '-un') { 'alice' } else { $env:T_PRIMARY } }; "
    "function sh { $env:T_UMASK }; "
)


@pytest.mark.skipif(_POWERSHELL_51 is None, reason="no Windows PowerShell 5.1")
@pytest.mark.parametrize(
    ("home_mode", "up_mode", "group", "up_group", "os_name", "umask", "expected"),
    [
        ("drwxr-xr-x", "drwxr-x---", "alice", "alice", "Linux", "0022", ""),
        (
            "drwxrwxrwx",
            "drwxr-x---",
            "alice",
            "alice",
            "Linux",
            "0022",
            "home:all users",
        ),
        (
            "drwxrwxr-x",
            "drwxr-x---",
            "staff",
            "alice",
            "Linux",
            "0022",
            "home:the group staff",
        ),
        (
            "drwxrwxr-x",
            "drwxr-x---",
            "domain users",
            "alice",
            "Linux",
            "0022",
            "home:the group domain users",
        ),
        ("drwxrwxr-x", "drwxrwxr-x", "alice", "alice", "Linux", "0002", ""),
        ("drwxr-xr-x", "drwxrwxrwx", "alice", "alice", "Linux", "0022", "up:all users"),
        ("drwxr-xr-x", "drwxrwxrwt", "alice", "alice", "Linux", "0022", ""),
        ("missing", "drwxr-x---", "alice", "alice", "Linux", "0002", ""),
        ("missing", "drwxr-x---", "alice", "alice", "Linux", "0000", "new:all users"),
        ("missing", "drwxr-x---", "alice", "staff", "Linux", "0002", ""),
        (
            "missing",
            "drwxr-s---",
            "alice",
            "staff",
            "Linux",
            "0002",
            "new:the group staff",
        ),
        (
            "missing",
            "drwxr-x---",
            "alice",
            "staff",
            "Darwin",
            "0002",
            "new:the group staff",
        ),
    ],
)
def test_outside_windows_the_mode_bits_decide(
    tmp_path: Path,
    home_mode: str,
    up_mode: str,
    group: str,
    up_group: str,
    os_name: str,
    umask: str,
    expected: str,
) -> None:
    """Outside Windows the ps1 scripts follow the sh rule and messages: others'
    w bit, or the group's when the group is not named after you, and a sticky
    folder holding the home is fine; a new home goes by the umask, with the
    group a new folder gets: your primary group, or the folder's own when it
    is setgid or the system is macOS or a BSD."""
    holder = tmp_path / "holder"
    home = holder / "apothem"
    holder.mkdir()
    if home_mode != "missing":
        home.mkdir()
    prelude = (
        f"$env:T_HOME_MODE = '{home_mode}'; $env:T_UP_MODE = '{up_mode}'; "
        f"$env:T_GROUP = '{group}'; $env:T_UP_GROUP = '{up_group}'; "
        f"$env:T_PRIMARY = 'alice'; $env:T_OS = '{os_name}'; "
        f"$env:T_UMASK = '{umask}'; " + _POSIX_STUBS
    )

    warnings = _home_warnings(_POWERSHELL_51, home, prelude)

    kind, _, who = expected.partition(":")
    messages = {
        "": [],
        "home": [
            f"Other users can change the code Apothem runs as you: {who} can write to "
            f'{home}. To fix it, run chmod go-w "{home}", or move APOTHEM_HOME.'
        ],
        "up": [
            f"Other users can replace {home}: {who} can write to {holder}, the folder "
            f'that holds it. To fix it, run chmod go-w "{holder}", or move APOTHEM_HOME.'
        ],
        "new": [
            f"A new {home} would let {who} change the code Apothem runs as you (umask "
            f"{umask}). To fix it, run umask 022, then run the installer again."
        ],
    }
    assert warnings == messages[kind]


def _went_on_after_one_warning(plain: str, warning: str, next_step: str) -> bool:
    """PLAIN holds WARNING once, and NEXT_STEP (the run's next heading) after
    it: the warning did not stop the run. The fixture repository is no full
    source tree, so the run stops later, at the profile."""
    squashed, mark = _squashed(plain), _squashed(warning)
    at = squashed.find(mark)
    return squashed.count(mark) == 1 and squashed.find(_squashed(next_step), at) > at


@pytest.mark.parametrize("dry_run", [False, True], ids=["real", "dry-run"])
def test_an_install_into_a_folder_others_may_modify_warns_once_and_goes_on(
    tmp_path: Path, dry_run: bool
) -> None:
    """A fresh install into a folder that passes Authenticated Users' Modify
    to what is made in it says so once, for the home it made, and goes on; a
    dry run there names the home it would make."""
    make_tagged_repo(tmp_path, TAG)
    holder = _drive_root_like(tmp_path / "drive")
    home = holder / "apothem-home"
    env = _script_env(tmp_path, extra_env={"APOTHEM_HOME": str(home)})

    result = _invoke(tmp_path, "install.ps1", env, *(["-DryRun"] if dry_run else []))

    plain = _out(result)
    if dry_run:
        warning = (
            f"A new {home} would let Authenticated Users change the code Apothem runs "
            f"as you, from the permissions of {holder}."
        )
        assert not home.exists(), plain
    else:
        warning = _home_message(home, "Authenticated Users")
        assert _head(home) == _head(tmp_path / "fixture-repo"), plain
    assert _went_on_after_one_warning(plain, warning, "Profile setup"), plain
    assert plain.count(" ! ") == 1, plain


def test_an_update_of_a_home_others_may_modify_warns_once_and_goes_on(
    tmp_path: Path,
) -> None:
    """An update in place of a home Users may modify says so once and goes on."""
    home = _prepare(tmp_path, "update.ps1")
    _icacls(home, "/grant", f"*{_USERS}:(OI)(CI)(M)")
    env = _script_env(tmp_path)

    result = _invoke(tmp_path, "update.ps1", env)

    plain = _out(result)
    assert _head(home) == _head(tmp_path / "fixture-repo"), plain
    assert _went_on_after_one_warning(
        plain, _home_message(home, "Users"), "Re-materializing harness"
    ), plain
    assert plain.count(" ! ") == 1, plain
