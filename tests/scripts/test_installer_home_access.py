# SPDX-License-Identifier: MIT

"""The sh installers' warning when other users can write to APOTHEM_HOME.

``install.sh`` and ``update.sh`` call ``warn_home_access`` once, before the
engine first runs from APOTHEM_HOME. It warns, and never stops the run, when
the permission bits let users other than you write to APOTHEM_HOME (or, for a
home not made yet, when the umask would), or rename what the folder holding it
holds. A group named after you is your user-private group (umask 002 setups on
Debian, Ubuntu, Fedora and RHEL), so its write bit is no warning. Git Bash,
MSYS2 and Cygwin make the bits up from Windows permissions, so the check is
skipped there; the ps1 scripts read the Windows permissions instead.

These tests run the two functions, as install.sh carries them, under sh with
a ``warn`` that prints its text, and stub ``id`` and ``uname`` on PATH.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
INSTALLER: Path = REPO_ROOT / "scripts" / "installer"
SH_SCRIPT: str = (INSTALLER / "install.sh").read_text(encoding="utf-8")

#: Owner-only folder (rwx------), the shape of a private parent.
PRIVATE_DIR = 0o700
#: The folder a umask of 022 makes (rwxr-xr-x).
DEFAULT_DIR = 0o755
#: A folder anyone can write to (rwxrwxrwx).
OPEN_DIR = 0o777
#: A folder anyone can write to, with the sticky bit (rwxrwxrwt), as /tmp.
STICKY_OPEN_DIR = 0o1777
#: Permission bits of the stub programs (rwxr-xr-x).
EXECUTABLE_MODE = 0o755

TEST_USER = "apothem-test-user"
H_OPENING = "Other users can change the code Apothem runs as you:"
P_OPENING = "Other users can replace "

posix_only = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sh") is None,
    reason="reads POSIX permission bits; install.ps1 checks Windows permissions",
)


def _sh_function(script: str, name: str) -> str:
    """The definition of shell function NAME, from ``NAME() {`` to the
    closing ``}`` at column 0."""
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}$", script, re.MULTILINE | re.DOTALL)
    assert match, f"no {name}() definition found"
    return match.group(0)


def _posix_sh() -> str | None:
    """Git for Windows' sh on Windows (found from git on PATH), else sh."""
    if sys.platform != "win32":
        return shutil.which("sh")
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).resolve().parents[:3]:
        for candidate in (root / "usr" / "bin" / "sh.exe", root / "bin" / "sh.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


_SH = _posix_sh()

PROGRAM = (
    "set -eu\n"
    "warn() { printf 'WARN %s\\n' \"$*\"; }\n"
    + _sh_function(SH_SCRIPT, "warn_writable")
    + "\n"
    + _sh_function(SH_SCRIPT, "warn_home_access")
    + "\nwarn_home_access\nprintf 'DONE\\n'\n"
)


def _stub_bin(
    tmp_path: Path,
    *,
    user: str | None,
    group: str | None,
    uname: str | None,
    stat_group: str | None = None,
) -> Path:
    """A folder of stub programs: ``id -un`` prints USER and ``id -gn``
    prints GROUP (other ``id`` calls run the real one); ``uname`` prints
    UNAME; ``stat`` prints STAT_GROUP. A None leaves that answer to the real
    program."""
    stubs = tmp_path / "stub-bin"
    stubs.mkdir(exist_ok=True)
    real_id = shutil.which("id") or "/usr/bin/id"
    lines = ["#!/bin/sh"]
    if user is not None:
        lines.append(f"[ \"$1\" = -un ] && {{ printf '%s\\n' '{user}'; exit 0; }}")
    if group is not None:
        lines.append(f"[ \"$1\" = -gn ] && {{ printf '%s\\n' '{group}'; exit 0; }}")
    lines.append(f"exec '{real_id}' \"$@\"")
    (stubs / "id").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (stubs / "id").chmod(EXECUTABLE_MODE)
    if uname is not None:
        (stubs / "uname").write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{uname}'\n", encoding="utf-8"
        )
        (stubs / "uname").chmod(EXECUTABLE_MODE)
    if stat_group is not None:
        (stubs / "stat").write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{stat_group}'\n", encoding="utf-8"
        )
        (stubs / "stat").chmod(EXECUTABLE_MODE)
    return stubs


def _warnings(
    tmp_path: Path,
    home: Path,
    *,
    umask: str = "022",
    user: str | None = None,
    group: str | None = None,
    uname: str | None = None,
    stat_group: str | None = None,
    shell: str | None = None,
) -> list[str]:
    """Run warn_home_access for APOTHEM_HOME=HOME and return its warnings."""
    assert _SH is not None
    stubs = _stub_bin(
        tmp_path, user=user, group=group, uname=uname, stat_group=stat_group
    )
    env = dict(os.environ)
    env["PATH"] = f"{stubs}{os.pathsep}{env.get('PATH', os.defpath)}"
    env["APOTHEM_HOME"] = str(home)
    result = subprocess.run(
        [shell or _SH, "-c", f"umask {umask}\n{PROGRAM}"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("DONE\n"), result.stdout + result.stderr
    assert result.stderr == "", result.stderr
    return [
        line[len("WARN ") :]
        for line in result.stdout.splitlines()
        if line.startswith("WARN ")
    ]


def _folder(path: Path, mode: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)
    return path


def _group_name(path: Path) -> str:
    import grp  # POSIX only; the tests that call this skip on Windows.

    return grp.getgrgid(path.stat().st_gid).gr_name


def _shells() -> list[str]:
    """sh, plus dash and bash where the host has them."""
    found = [_SH] if _SH else []
    for name in ("dash", "bash"):
        program = shutil.which(name)
        if program and program not in found:
            found.append(program)
    return found


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_private_home_in_a_private_folder_gives_no_warning(
    tmp_path: Path, shell: str
) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)

    lines = _warnings(tmp_path, home, shell=shell)

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_group_writable_home_names_the_group(tmp_path: Path, shell: str) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, shell=shell)

    assert lines == [
        f"{H_OPENING} the group {_group_name(home)} can write to {real}. "
        f'To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
    ]


@posix_only
def test_a_group_name_with_a_space_is_named_whole(tmp_path: Path) -> None:
    """ls splits a group name such as ``domain users`` (sssd, AD-joined
    hosts) at the space; the name comes whole from stat."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, stat_group="domain users")

    assert lines == [
        f"{H_OPENING} the group domain users can write to {real}. "
        f'To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
    ]


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_world_writable_home_names_all_users(tmp_path: Path, shell: str) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWOTH)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, shell=shell)

    assert lines == [
        f'{H_OPENING} all users can write to {real}. To fix it, run chmod go-w "{real}", '
        "or move APOTHEM_HOME."
    ]


@posix_only
@pytest.mark.parametrize("made", [True, False], ids=["home-made", "home-missing"])
def test_a_user_private_group_with_umask_002_gives_no_warning(
    tmp_path: Path, made: bool
) -> None:
    """With umask 002 the home is group-writable, but the group is the one
    named after you, which holds only you."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = parent / "home"
    if made:
        home.mkdir()
        home.chmod(0o775)
    own_group = _group_name(home if made else parent)

    lines = _warnings(tmp_path, home, umask="002", user=own_group, group=own_group)

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_world_writable_parent_warns_without_the_sticky_bit(
    tmp_path: Path, shell: str
) -> None:
    parent = _folder(tmp_path / "parent", OPEN_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)
    real_parent = os.path.realpath(parent)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, shell=shell)

    assert lines == [
        f"{P_OPENING}{real}: all users can write to {real_parent}, the folder that "
        f'holds it. To fix it, run chmod go-w "{real_parent}", or move APOTHEM_HOME.'
    ]


@posix_only
def test_a_world_writable_parent_with_the_sticky_bit_gives_no_warning(
    tmp_path: Path,
) -> None:
    parent = _folder(tmp_path / "parent", STICKY_OPEN_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)

    lines = _warnings(tmp_path, home)

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_missing_home_is_judged_by_the_umask(tmp_path: Path, shell: str) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = parent / "home"

    lines = _warnings(tmp_path, home, umask="000", shell=shell)

    assert lines == [
        f"A new {home} would let all users change the code Apothem runs as you "
        "(umask 0000). To fix it, run umask 022, then run the installer again."
    ]
    assert not home.exists()


@posix_only
@pytest.mark.parametrize("why", ["setgid", "macos"])
def test_a_missing_home_takes_the_group_a_new_folder_would_get(
    tmp_path: Path, why: str
) -> None:
    """A new folder takes the group of a setgid folder holding it, and on
    macOS and the BSDs always takes the group of the folder holding it. With
    your own group private, a dry run then names that other group, as the
    real run does once the folder is made."""
    parent = _folder(tmp_path / "parent", DEFAULT_DIR)
    if why == "setgid":
        parent.chmod(DEFAULT_DIR | stat.S_ISGID)
        if not parent.stat().st_mode & stat.S_ISGID:
            pytest.skip("this file system does not keep the setgid bit")
    home = parent / "home"

    lines = _warnings(
        tmp_path,
        home,
        umask="002",
        user=TEST_USER,
        group=TEST_USER,
        uname="Darwin" if why == "macos" else None,
    )

    assert lines == [
        f"A new {home} would let the group {_group_name(parent)} change the code "
        "Apothem runs as you (umask 0002). To fix it, run umask 022, then run the "
        "installer again."
    ]


@posix_only
def test_a_missing_home_with_umask_022_gives_no_warning(tmp_path: Path) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)

    lines = _warnings(tmp_path, parent / "home", user=TEST_USER)

    assert lines == []


@pytest.mark.skipif(_SH is None, reason="no POSIX sh on this host")
def test_git_bash_skips_the_check(tmp_path: Path) -> None:
    """Under Git Bash the mode bits come from Windows permissions, so the sh
    scripts read nothing there."""
    parent = _folder(tmp_path / "parent", OPEN_DIR)
    home = _folder(parent / "home", OPEN_DIR)

    lines = _warnings(
        tmp_path, home, umask="000", user=TEST_USER, uname="MINGW64_NT-10.0-26100"
    )

    assert lines == []


@posix_only
def test_a_linked_home_names_the_target_and_the_link(tmp_path: Path) -> None:
    """The home check reads the folder the link leads to, and the folder that
    holds the link is checked too: whoever can write to it can re-point the
    link."""
    target_parent = _folder(tmp_path / "real-parent", PRIVATE_DIR)
    target = _folder(target_parent / "target", OPEN_DIR)
    link_parent = _folder(tmp_path / "link-parent", OPEN_DIR)
    link = link_parent / "home"
    link.symlink_to(target, target_is_directory=True)
    real_link_parent = str(link_parent)
    real = os.path.realpath(target)

    lines = _warnings(tmp_path, link, user=TEST_USER)

    assert lines == [
        f"{P_OPENING}{link}: all users can write to {real_link_parent}, the folder "
        f'that holds it. To fix it, run chmod go-w "{real_link_parent}", or move '
        "APOTHEM_HOME.",
        f'{H_OPENING} all users can write to {real}. To fix it, run chmod go-w "{real}", '
        "or move APOTHEM_HOME.",
    ]


def test_both_sh_scripts_carry_the_same_functions() -> None:
    update = (INSTALLER / "update.sh").read_text(encoding="utf-8")
    for name in ("warn_home_access", "warn_writable"):
        assert _sh_function(update, name) == _sh_function(SH_SCRIPT, name), name
